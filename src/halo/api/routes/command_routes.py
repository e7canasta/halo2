"""Command endpoint with Chain of Responsibility intent classification.

Uses tiered classification:
1. ExactMatchClassifier (0ms, cached)
2. EmbeddingClassifier (5-10ms, semantic similarity)
3. KeywordClassifier (<1ms, regex patterns)
4. LLMClassifier (7s, fallback)
"""

from fastapi import APIRouter, HTTPException, Depends
from ...backend import Backend, get_backend
from ...tools.pipeline import get_pipeline
from ...tools.executor import ToolCallError
from ...intent.factory import create_default_chain
from ...intent.classifiers import ExactMatchClassifier, EmbeddingClassifier
from ...nlp.training import DatasetCollector
from ...nlp.provider import get_nlp
from ...nlp.slots import SlotExtractor
from ...nlp.vocabulary import VocabularyManager
from ...nlp.template_expander import TemplateExpander
from ...agents.gemini_agent import GeminiAgent
from ...context.conversation_manager import ConversationContextManager
from ...flows import HaloProcessEngine, ProcessAction
from ...tracing import DecisionTracer
from ..models import CommandRequest, CommandResponse, CommandResult, ToolCall, TokenUsage
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter()

# Global classifier chain (initialized on first request)
_classifier_chain = None

# Global dataset collector for golden dataset
_dataset_collector = DatasetCollector()

# Global vocabulary manager (initialized with embedding classifier)
_vocab_manager = None
_template_expander = None

# Global Gemini agent (initialized if API key is available)
_gemini_agent = None

# Global conversation context manager (tracks multi-turn context)
_conversation_manager = None

# Global process engine (for multi-step flows)
_process_engine = None


def get_chain(backend: Backend):
    """Get or create the classifier chain (singleton pattern)."""
    global _classifier_chain, _vocab_manager, _template_expander, _gemini_agent, _conversation_manager, _process_engine

    if _classifier_chain is None:
        _classifier_chain = create_default_chain(backend, enable_embeddings=True)

        # Initialize vocabulary manager with embedding classifier
        embedding_clf = None
        for clf in _classifier_chain.classifiers:
            if isinstance(clf, EmbeddingClassifier):
                embedding_clf = clf
                break

        if embedding_clf:
            _vocab_manager = VocabularyManager(
                embedding_classifier=embedding_clf, dataset_collector=_dataset_collector
            )
            _template_expander = TemplateExpander(vocabulary_manager=_vocab_manager)
            logger.info("Vocabulary manager initialized with golden dataset collection")
        else:
            logger.warning("EmbeddingClassifier not found, vocabulary expansion disabled")

        # Initialize Gemini agent if API key is available
        if os.getenv("GEMINI_API_KEY"):
            try:
                _gemini_agent = GeminiAgent()
                logger.info("Gemini agent initialized with 3 roles (Fallback, Validator, Template Master)")
            except Exception as e:
                logger.warning(f"Could not initialize Gemini agent: {e}")
                _gemini_agent = None
        else:
            logger.info("GEMINI_API_KEY not set, Gemini quality validation disabled")

        # Initialize conversation context manager
        _conversation_manager = ConversationContextManager(max_turns=5)
        logger.info("Conversation context manager initialized (max 5 turns)")

        # Initialize process engine
        pipeline = get_pipeline(enable_nlg=True, conversation_manager=_conversation_manager)
        _process_engine = HaloProcessEngine(
            conversation_manager=_conversation_manager,
            tool_pipeline=pipeline
        )

        # Register flows
        try:
            from flows.examples.smart_home_flows import register_all_flows
            register_all_flows(_process_engine)
            logger.info("Process engine initialized with smart home flows")
        except ImportError:
            logger.warning("Could not import smart home flows, process engine initialized empty")

    return _classifier_chain


@router.post("/command", response_model=CommandResponse)
async def command(
    request: CommandRequest,
    backend: Backend = Depends(get_backend),
    trace_agency: bool = False
) -> CommandResponse:
    """Smart home command endpoint with Chain of Responsibility classification.

    Uses tiered classification strategy:
    1. ExactMatch (0ms) → 2. Embedding (5ms) → 3. Keyword (1ms) → 4. LLM (7s)

    Args:
        request: Command request with message and context
        backend: Backend instance (injected)
        trace_agency: Si True, captura decision trace (agencia del sistema)

    Returns:
        CommandResponse with result, context, and token usage (+ agency_trace si trace_agency=True)
    """
    chain = get_chain(backend)

    # Inicializar decision tracer si requested
    tracer = None
    if trace_agency or request.context.get("_trace_agency"):
        tracer = DecisionTracer(user_input=request.message)
        logger.debug(f"Decision tracing enabled for: {request.message}")

    # Enrich context with conversation history for LLM/Gemini classifiers
    enriched_context = request.context.copy() if request.context else {}

    if _conversation_manager:
        # Add conversation history to context (for LLM/Gemini)
        conversation_history = _conversation_manager.get_conversation_history(n_turns=3)
        if conversation_history:
            enriched_context["_conversation_history"] = conversation_history
            logger.debug(f"Added {len(conversation_history)} messages to conversation history")

    # === PROCESS ENGINE DECISION TREE ===
    # Check if there's an active process
    current_process = _process_engine.get_current_flow() if _process_engine else None

    if current_process:
        # Process active: classify in process context
        classification = chain.classify(request.message, {
            **enriched_context,
            "process_context": current_process.enriched_context if hasattr(current_process, 'enriched_context') else {},
            "current_step": current_process.current_step,
        })

        if not classification:
            raise HTTPException(status_code=500, detail="No classifier handled the request")

        # Process user input within active process
        try:
            action = _process_engine.process_user_input(
                current_process.flow_id,
                request.message,
                classification
            )
            return _process_action_to_response(action)
        except Exception as e:
            logger.error(f"Process engine error: {e}")
            # Fallback: cancel process and handle as simple command
            _process_engine.cancel_flow(current_process.flow_id)
            # Continue to simple command handling below

    # No active process: classify normally
    classification = chain.classify(request.message, enriched_context)

    if not classification:
        raise HTTPException(status_code=500, detail="No classifier handled the request")

    # Trace classification decision
    if tracer:
        tracer.decision_point(
            agent="ClassifierChain",
            question="¿Qué quiere hacer el usuario?",
            context={
                "user_input": request.message,
                "conversation_history": enriched_context.get("_conversation_history", []),
                "classifier_used": classification.classifier_used,
                "cached": classification.cached,
                "confidence": classification.confidence
            },
            options=[{
                "tool": classification.tool_name,
                "confidence": classification.confidence,
                "classifier": classification.classifier_used
            }],
            decided=classification.tool_name,
            why=f"Classifier '{classification.classifier_used}' con confidence {classification.confidence:.2f}"
        )

    # Handle special tool types
    if classification.tool_name == "conversation":
        # LLM responded with conversation instead of tool
        return CommandResponse(
            result=CommandResult(
                status="completed",
                message=classification.parameters.get("response", ""),
            ),
            context=request.context,
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

    if classification.tool_name == "error":
        raise HTTPException(
            status_code=500, detail=classification.parameters.get("error", "Unknown error")
        )

    # Check if should start a process
    if _process_engine:
        flow_name = _process_engine.get_flow_for_tool(classification.tool_name)
        if flow_name:
            # Tool has associated flow, check if should initiate
            missing = _process_engine.get_missing_required_slots(
                flow_name,
                classification.parameters
            )

            # Trace flow decision
            if tracer:
                if missing:
                    tracer.decision_point(
                        agent="FlowEngine",
                        question="¿Ejecutar directo o iniciar proceso multi-turno?",
                        context={
                            "tool": classification.tool_name,
                            "params": classification.parameters,
                            "flow_available": flow_name,
                            "missing_slots": missing
                        },
                        options=[{
                            "action": "start_flow",
                            "flow": flow_name,
                            "why": f"Faltan slots requeridos: {missing}"
                        }],
                        decided="start_flow",
                        why=f"Slots faltantes: {missing}"
                    )

            if missing:
                # Start process to collect missing slots
                try:
                    logger.info(f"Starting process '{flow_name}' for tool '{classification.tool_name}' (missing: {missing})")
                    process = _process_engine.start_flow(
                        flow_name,
                        initial_slots=classification.parameters
                    )

                    # Process first step
                    action = _process_engine.process_user_input(
                        process.flow_id,
                        request.message,
                        classification
                    )
                    return _process_action_to_response(action)
                except Exception as e:
                    logger.error(f"Failed to start process: {e}")
                    # Fallback to simple command execution

    # Execute the tool through the filter pipeline (simple command)
    # Philosophy: QUALITY > SPEED - all filters run for validation and formatting
    pipeline = get_pipeline(enable_nlg=True, conversation_manager=_conversation_manager)

    try:
        # Add user input to context for ConversationContextManager
        enriched_context = request.context.copy()
        enriched_context["_user_input"] = request.message

        # Run through complete pipeline (pre-filters → execute → post-filters)
        pipeline_result = pipeline.execute(
            tool_name=classification.tool_name,
            parameters=classification.parameters,
            context=enriched_context,
        )

        tool_result = pipeline_result["result"]
        context_updates = pipeline_result["context_updates"]
        filter_metadata = pipeline_result["metadata"]

        # Log filter execution details
        logger.info(
            f"Pipeline executed for {classification.tool_name} "
            f"(pre-filters: {list(filter_metadata['pre_filters'].keys())}, "
            f"post-filters: {list(filter_metadata['post_filters'].keys())})"
        )

        result = CommandResult(
            status=tool_result.get("status", "completed"),
            message=tool_result.get("message", ""),
            device_state=tool_result.get("device_state", {}),
            tool_call=ToolCall(tool=classification.tool_name, parameters=classification.parameters),
        )

        # Update context with pipeline updates
        updated_context = request.context.copy()
        updated_context.update(context_updates)

        # Learn from this interaction (for future caching and golden dataset)
        _learn_from_result(
            classification, request.message, execution_status=result.status
        )

        # Update conversation context manager
        if _conversation_manager and result.status == "completed":
            _conversation_manager.add_turn(request.message, classification)
            logger.debug(f"Conversation context updated: {_conversation_manager.get_summary()}")

        # Token usage (0 for non-LLM classifiers)
        tokens_used = 0 if classification.classifier_used != "llm" else 400  # Estimate for LLM

        # Finish agency trace if enabled
        agency_trace_dict = None
        if tracer:
            agency_trace = tracer.finish(final_result=result.message)
            agency_trace_dict = agency_trace.to_dict()
            logger.debug(f"Agency trace completed: {len(agency_trace.decisions)} decisions")

        return CommandResponse(
            result=result,
            context=updated_context,
            usage=TokenUsage(
                prompt_tokens=tokens_used // 2,
                completion_tokens=tokens_used // 2,
                total_tokens=tokens_used,
            ),
            agency_trace=agency_trace_dict
        )

    except ToolCallError as e:
        # Pipeline validation failed
        logger.error(f"Tool pipeline validation failed: {e}")
        return CommandResponse(
            result=CommandResult(status="error", message=str(e)),
            context=request.context,
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )
    except Exception as e:
        # Unexpected error
        logger.exception(f"Unexpected error in pipeline: {e}")
        return CommandResponse(
            result=CommandResult(status="error", message=f"Error inesperado: {str(e)}"),
            context=request.context,
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )


def _learn_from_result(classification, user_input: str, execution_status: str = "completed"):
    """Learn from successful classifications for future caching and golden dataset.

    This implements the "memoria muscular algoritmica" with Gemini quality validation:
    1. Validate with Gemini (if needed) BEFORE learning
    2. Learn original example (if validation passes)
    3. Register as template (if high confidence)
    4. Improve template with Gemini (if new template)
    5. Expand to ALL domain variations automatically

    Args:
        classification: ClassificationResult from the chain
        user_input: Original user input
        execution_status: Execution status (e.g., "completed", "error")
    """
    # STEP 1: Validate with Gemini before learning (if applicable)
    if _gemini_agent and execution_status == "completed":
        dataset_size = _dataset_collector.count()

        validation = _gemini_agent.validate_classification(
            user_input=user_input,
            classification=classification,
            dataset_size=dataset_size,
            is_synthetic=False
        )

        if validation is not None:
            if not validation.is_correct:
                logger.info(
                    f"Gemini validation REJECTED classification for '{user_input}': "
                    f"{', '.join(validation.issues)}"
                )

                if validation.should_ask_user:
                    # Don't learn this - it needs user clarification
                    logger.info(f"Skipping learning - needs user clarification: {validation.clarification_question}")
                    return
                elif validation.corrected:
                    # Use Gemini's corrected version
                    logger.info(f"Using Gemini-corrected classification")
                    classification = validation.corrected
                else:
                    # Gemini rejected but didn't provide correction - skip learning
                    logger.warning("Gemini rejected but no correction provided - skipping learning")
                    return

    # Extract slots for embedding learning (if execution successful)
    slots = None
    if execution_status == "completed" and classification.confidence >= 0.85:
        try:
            nlp = get_nlp()
            doc = nlp(user_input)
            slots = SlotExtractor.extract_slots(doc, classification.parameters)
        except Exception as e:
            logger.warning(f"Could not extract slots: {e}")

    # Learn for exact match cache (if not already cached)
    if not classification.cached and classification.confidence >= 0.9:
        for classifier in _classifier_chain.classifiers:
            if isinstance(classifier, ExactMatchClassifier):
                classifier.learn(user_input, classification.tool_name, classification.parameters)
            elif isinstance(classifier, EmbeddingClassifier) and classification.confidence >= 0.95:
                # Add to embeddings with slots for template matching
                classifier.learn(
                    user_input, classification.tool_name, classification.parameters, slots=slots
                )

    # VOCABULARY EXPANSION: Template + slot filling
    if (
        not classification.cached
        and classification.confidence >= 0.95
        and slots
        and _vocab_manager
        and _template_expander
    ):
        # 1. Register template in vocabulary manager
        template_registered = _vocab_manager.register_template(
            user_input, classification.tool_name, classification.parameters, slots
        )

        if template_registered:
            logger.info(f"Template registered: {user_input}")

            # STEP 2: Improve template with Gemini (if new template and Gemini available)
            if _gemini_agent:
                try:
                    improvement = _gemini_agent.improve_template(
                        template=user_input,
                        slots=slots,
                        real_examples=[user_input]
                    )

                    if improvement.corrected_template != user_input:
                        logger.info(
                            f"Gemini improved template: '{user_input}' → '{improvement.corrected_template}'"
                        )

                        # Register improved template as well
                        _vocab_manager.register_template(
                            improvement.corrected_template,
                            classification.tool_name,
                            classification.parameters,
                            slots
                        )

                        # Learn natural variations suggested by Gemini
                        if improvement.natural_variations:
                            logger.info(f"Gemini suggested {len(improvement.natural_variations)} variations")

                except Exception as e:
                    logger.warning(f"Gemini template improvement failed: {e}")

        # 2. Immediate expansion to all domain variations
        try:
            synthetic_examples = _template_expander.expand_template(
                user_input,
                classification.tool_name,
                classification.parameters,
                slots,
                classification.confidence,
            )

            # Learn all synthetic examples
            embedding_clf = None
            for clf in _classifier_chain.classifiers:
                if isinstance(clf, EmbeddingClassifier):
                    embedding_clf = clf
                    break

            if embedding_clf:
                for syn_ex in synthetic_examples:
                    # Add to embedding classifier
                    embedding_clf.learn(
                        syn_ex["text"],
                        syn_ex["tool_name"],
                        syn_ex["parameters"],
                        slots=syn_ex["slots"],
                    )

                    # Add to golden dataset for spaCy training
                    _dataset_collector.collect(
                        user_input=syn_ex["text"],
                        tool_name=syn_ex["tool_name"],
                        parameters=syn_ex["parameters"],
                        confidence=syn_ex["confidence"],
                        classifier_used="template_expansion",
                        execution_status="completed",
                        synthetic=True,
                        slots_provided=syn_ex["slots"],
                    )

            if synthetic_examples:
                logger.info(
                    f"Template expansion: 1 example → {len(synthetic_examples) + 1} total "
                    f"(+{len(synthetic_examples)} synthetic, added to embedding + golden dataset)"
                )

        except Exception as e:
            logger.error(f"Template expansion failed: {e}")

    # Collect for golden dataset (for fine-tuning)
    try:
        _dataset_collector.collect(
            user_input=user_input,
            tool_name=classification.tool_name,
            parameters=classification.parameters,
            confidence=classification.confidence,
            classifier_used=classification.classifier_used,
            execution_status=execution_status,
        )
    except Exception as e:
        logger.warning(f"Could not collect example for golden dataset: {e}")


def _process_action_to_response(action: ProcessAction) -> CommandResponse:
    """Convert ProcessAction to CommandResponse.

    Args:
        action: ProcessAction from process engine

    Returns:
        CommandResponse
    """
    if action.type == "ask_question":
        # Collecting slot
        return CommandResponse(
            result=CommandResult(
                status="collecting",
                message=action.payload["question"],
            ),
            context={"process_id": action.payload.get("process_id")},
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

    elif action.type == "tool_call":
        # Tool execution (sync)
        return CommandResponse(
            result=CommandResult(
                status="completed",
                message=action.payload.get("message", "Tool ejecutado"),
                tool_call=ToolCall(
                    tool=action.payload.get("tool"),
                    parameters=action.payload.get("parameters", {})
                ),
            ),
            context={"process_id": action.payload.get("process_id")},
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

    elif action.type == "awaiting_handler":
        # Waiting for MQTT handler
        return CommandResponse(
            result=CommandResult(
                status="awaiting",
                message=action.payload["message"],
            ),
            context={
                "process_id": action.payload.get("process_id"),
                "correlation_id": action.payload["correlation_id"],
            },
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

    elif action.type == "complete":
        # Process completed
        return CommandResponse(
            result=CommandResult(
                status="completed",
                message=action.payload.get("message", "Proceso completado"),
            ),
            context={},
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

    elif action.type == "cancel":
        # Process cancelled
        return CommandResponse(
            result=CommandResult(
                status="error",
                message=action.payload.get("reason", "Proceso cancelado"),
            ),
            context={},
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

    else:
        # Unknown action type
        return CommandResponse(
            result=CommandResult(
                status="error",
                message=f"Unknown process action: {action.type}",
            ),
            context={},
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@router.get("/classifier-chain")
async def get_classifier_chain_info(backend: Backend = Depends(get_backend)):
    """Get information about the classifier chain.

    Returns:
        Info about active classifiers and their configuration
    """
    chain = get_chain(backend)
    return {
        "chain": chain.get_chain_info(),
        "cache_stats": {
            "exact_match_count": len(_classifier_chain.classifiers[0].cache._exact_cache)
            if _classifier_chain
            else 0,
            "embedding_examples": _classifier_chain.classifiers[1].get_examples_count()
            if _classifier_chain and len(_classifier_chain.classifiers) > 1
            else 0,
        },
    }


# ============================================================================
# VOCABULARY MANAGEMENT ENDPOINTS
# ============================================================================


@router.post("/vocabulary/add")
async def add_vocabulary_item(
    domain: str,
    value: str,
    backend: Backend = Depends(get_backend),
):
    """Add new item to vocabulary and expand templates automatically.

    This is the "memoria muscular algoritmica" - adding one word generates
    multiple examples for all templates using that domain.

    Example:
        POST /vocabulary/add?domain=room&value=garage

        If system knows 10 templates using {ROOM}:
        - "enciende la luz de {ROOM}"
        - "apaga la luz de {ROOM}"
        - etc.

        → Automatically generates 10 examples:
        - "enciende la luz del garage"
        - "apaga la luz del garage"
        - etc.

    Args:
        domain: Domain to add to ("room", "device", "action", "mode")
        value: New value ("garage", "termostato", etc.)
        backend: Backend dependency

    Returns:
        Status and number of examples generated
    """
    # Ensure chain is initialized
    get_chain(backend)

    if not _vocab_manager:
        raise HTTPException(
            status_code=503, detail="Vocabulary manager not available (embeddings disabled)"
        )

    try:
        generated = _vocab_manager.add_to_domain(domain, value)

        return {
            "status": "success",
            "domain": domain,
            "value": value,
            "examples_generated": generated,
            "total_templates": len(_vocab_manager.templates),
            "message": f"Added '{value}' to {domain}. Generated {generated} examples automatically.",
        }
    except Exception as e:
        logger.error(f"Error adding vocabulary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vocabulary/stats")
async def get_vocabulary_stats(backend: Backend = Depends(get_backend)):
    """Get vocabulary statistics.

    Returns:
        Stats about domains, templates, and coverage
    """
    # Ensure chain is initialized
    get_chain(backend)

    if not _vocab_manager:
        raise HTTPException(
            status_code=503, detail="Vocabulary manager not available (embeddings disabled)"
        )

    try:
        stats = _vocab_manager.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting vocabulary stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vocabulary/domains")
async def get_domains(backend: Backend = Depends(get_backend)):
    """Get all domain values.

    Returns:
        Dict of domains and their values
    """
    # Ensure chain is initialized
    get_chain(backend)

    if not _vocab_manager:
        raise HTTPException(
            status_code=503, detail="Vocabulary manager not available (embeddings disabled)"
        )

    try:
        return {
            domain: list(values) for domain, values in _vocab_manager.domains.items()
        }
    except Exception as e:
        logger.error(f"Error getting domains: {e}")
        raise HTTPException(status_code=500, detail=str(e))
