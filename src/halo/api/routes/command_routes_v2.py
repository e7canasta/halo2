"""Command endpoint v2 with Policy-Driven Chain and Context Levels.

Nueva arquitectura opt-in mediante HALO_DOMAIN env var:
- HALO_DOMAIN=home → Halo Home con ThresholdPolicy
- HALO_DOMAIN=care → Halo Care con CarePolicy

Diferencias con v1 (legacy):
1. Usa PolicyDrivenChain en lugar de ClassifierChain
2. Carga config desde config/{domain}.json
3. Usa Context Levels (5 niveles de contexto)
4. File-based store con observabilidad
5. Soul-aware (carga manifest y personality)
"""

from fastapi import APIRouter, HTTPException, Depends
from ...backend import Backend, get_backend
from ...tools.pipeline import get_pipeline
from ...tools.executor import ToolCallError
from ...intent.factory import create_policy_driven_chain
from ...config import HaloConfig
from ...storage import FileStore
from ...context import ContextLoader, SoulReader, HaloContext, CommandContext
from ..models import CommandRequest, CommandResponse, CommandResult, ToolCall, TokenUsage
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2")

# Global instances (initialized on first request)
_policy_chain = None
_config = None
_store = None
_context_loader = None
_soul = None

# Session tracking (in-memory for now)
_active_sessions = {}


def get_policy_chain_with_context(backend: Backend):
    """Get or create the policy-driven chain with full context loading."""
    global _policy_chain, _config, _store, _context_loader, _soul

    if _policy_chain is None:
        # Load config based on HALO_DOMAIN env var
        domain = os.getenv("HALO_DOMAIN", "home")
        logger.info(f"Initializing Halo for domain: {domain}")

        try:
            _config = HaloConfig.for_domain(domain)
        except Exception as e:
            logger.warning(f"Could not load config for domain '{domain}': {e}")
            _config = HaloConfig.default_config(domain)

        logger.info(f"Config loaded: {_config}")

        # Initialize file store
        _store = FileStore(_config.store_path)

        # Load soul
        try:
            soul_reader = SoulReader(_store)
            _soul = soul_reader.load()
            detected_domain = soul_reader.get_domain()
            logger.info(
                f"Soul loaded: {len(_soul.manifest)} chars, "
                f"detected_domain={detected_domain}, "
                f"relationships={list(_soul.relationships.keys())}"
            )
        except Exception as e:
            logger.error(f"Could not load soul: {e}")
            _soul = None

        # Initialize context loader
        _context_loader = ContextLoader(_store)

        # Create policy-driven chain
        _policy_chain = create_policy_driven_chain(
            backend=backend,
            policy=_config.policy,
            enable_telemetry=_config.observability.get("enable_telemetry", True),
            enable_learning=_config.observability.get("enable_learning", True),
            store_path=_config.store_path,
            enable_embeddings=_config.classifiers.get("enable_embeddings", True),
            enable_spacy=_config.classifiers.get("enable_spacy", True),
            enable_functiongemma=_config.classifiers.get("enable_functiongemma", False),
            enable_gemini=_config.classifiers.get("enable_gemini", False),
        )

        logger.info(
            f"Policy-driven chain initialized: "
            f"policy={_policy_chain.policy.__class__.__name__}, "
            f"classifiers={len(_policy_chain.classifiers)}, "
            f"interceptors={len(_policy_chain.interceptors)}"
        )

    return _policy_chain, _context_loader


@router.post("/command", response_model=CommandResponse)
async def command_v2(
    request: CommandRequest,
    backend: Backend = Depends(get_backend),
) -> CommandResponse:
    """Command endpoint v2 with policy-driven chain and context levels.

    Usa:
    - PolicyDrivenChain (envelopes, policies, interceptors)
    - Context Levels (5 niveles: soul, environment, session, flow, command)
    - File-based store (observabilidad transparente)
    - Domain-agnostic (home vs care configurado via HALO_DOMAIN env var)

    Args:
        request: Command request with message and context
        backend: Backend instance (injected)

    Returns:
        CommandResponse with result, context, and token usage
    """
    chain, context_loader = get_policy_chain_with_context(backend)

    # Get or create session
    session_id = request.context.get("session_id") if request.context else None
    if not session_id:
        session_id = f"session_{datetime.now().timestamp()}"

    # Load or get session from active sessions
    if session_id in _active_sessions:
        session = _active_sessions[session_id]
        session.interaction_count += 1
    else:
        # Try loading from store
        session = context_loader.load_session(session_id)
        if not session:
            # Create new session
            from ...context.levels import SessionContext
            session = SessionContext(
                session_id=session_id,
                user_or_operator=request.context.get("user", request.context.get("operator", "unknown")) if request.context else "unknown",
                start_time=datetime.now(),
            )
        _active_sessions[session_id] = session

    # Build full context (5 levels)
    try:
        halo_context = HaloContext(
            soul=_soul or context_loader.load_soul(),
            environment=context_loader.load_environment(),
            session=session,
            flow=context_loader.load_active_flow(),
            command=CommandContext(
                user_input=request.message,
                parameters=request.context or {},
            ),
        )
    except Exception as e:
        logger.warning(f"Could not load full context: {e}")
        # Fallback to minimal context
        from ...context.levels import SoulContext, EnvironmentContext, SessionContext, CommandContext
        halo_context = HaloContext(
            soul=_soul or SoulContext(manifest="", personality={}),
            environment=EnvironmentContext(timestamp=datetime.now(), time_of_day="day"),
            session=session,
            command=CommandContext(user_input=request.message),
        )

    # Convert to dict for classifier
    context_dict = halo_context.to_dict()

    # Classify using policy-driven chain
    result = chain.classify(request.message, context_dict)

    if not result:
        raise HTTPException(status_code=500, detail="No classifier handled the request")

    # Handle conversation response
    if result.tool_name == "conversation":
        return CommandResponse(
            result=CommandResult(
                status="completed",
                message=result.parameters.get("response", ""),
            ),
            context={"session_id": session_id},
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

    # Execute tool through pipeline
    pipeline = get_pipeline(enable_nlg=True)

    try:
        pipeline_result = pipeline.execute(
            tool_name=result.tool_name,
            parameters=result.parameters,
            context=context_dict,
        )

        tool_result = pipeline_result["result"]
        context_updates = pipeline_result["context_updates"]

        # Update session
        session.conversation_history.append({
            "timestamp": datetime.now().isoformat(),
            "user_input": request.message,
            "intent": result.tool_name,
            "parameters": result.parameters,
            "result": tool_result.get("status", "completed"),
        })

        # Persist session
        _store.write("sessions", session_id, {
            "session_id": session.session_id,
            "user" if _config.domain == "home" else "operator": session.user_or_operator,
            "start_time": session.start_time.isoformat(),
            "status": session.status,
            "interaction_count": session.interaction_count,
            "context": {
                "conversation_history": session.conversation_history,
            },
        })

        command_result = CommandResult(
            status=tool_result.get("status", "completed"),
            message=tool_result.get("message", ""),
            device_state=tool_result.get("device_state", {}),
            tool_call=ToolCall(tool=result.tool_name, parameters=result.parameters),
        )

        return CommandResponse(
            result=command_result,
            context={
                "session_id": session_id,
                **context_updates,
            },
            usage=TokenUsage(
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
            ),
        )

    except ToolCallError as e:
        logger.error(f"Tool execution error: {e}")
        return CommandResponse(
            result=CommandResult(status="error", message=str(e)),
            context={"session_id": session_id},
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )


@router.get("/health")
async def health_check_v2():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "v2",
        "domain": os.getenv("HALO_DOMAIN", "home"),
        "policy_chain": _policy_chain is not None,
    }


@router.get("/info")
async def get_info(backend: Backend = Depends(get_backend)):
    """Get information about the Halo instance.

    Returns:
        Domain, config, soul manifest preview, and chain info
    """
    chain, context_loader = get_policy_chain_with_context(backend)

    return {
        "domain": _config.domain,
        "name": _config.name,
        "policy": _policy_chain.policy.__class__.__name__,
        "classifiers": [c.name for c in _policy_chain.classifiers],
        "interceptors": [i.__class__.__name__ for i in _policy_chain.interceptors],
        "soul": {
            "manifest_preview": _soul.manifest[:200] + "..." if _soul else "Not loaded",
            "relationships": list(_soul.relationships.keys()) if _soul else [],
            "trust_score": _soul.trust_score if _soul else 0.0,
        },
        "sessions_active": len(_active_sessions),
    }


@router.get("/soul")
async def get_soul(backend: Backend = Depends(get_backend)):
    """Get the full soul manifest.

    Returns:
        Complete manifest.md content
    """
    chain, context_loader = get_policy_chain_with_context(backend)

    if not _soul:
        raise HTTPException(status_code=404, detail="Soul not loaded")

    return {
        "manifest": _soul.manifest,
        "personality": _soul.personality,
        "relationships": _soul.relationships,
        "learned_preferences": _soul.learned_preferences,
        "trust_score": _soul.trust_score,
        "days_active": _soul.days_active,
    }


@router.get("/context")
async def get_context(
    session_id: str = None,
    backend: Backend = Depends(get_backend),
):
    """Get the full context (5 levels) for a session.

    Args:
        session_id: Optional session ID

    Returns:
        Complete HaloContext as dict
    """
    chain, context_loader = get_policy_chain_with_context(backend)

    try:
        halo_context = context_loader.load_full_context(session_id)
        return halo_context.to_dict()
    except Exception as e:
        logger.error(f"Error loading context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/telemetry")
async def get_telemetry_logs(
    date: str = None,
    backend: Backend = Depends(get_backend),
):
    """Get telemetry logs for a specific date.

    Args:
        date: Date in YYYY-MM-DD format (default: today)

    Returns:
        List of telemetry log entries
    """
    chain, context_loader = get_policy_chain_with_context(backend)

    try:
        logs = _store.read_logs("telemetry", date)
        return {
            "date": date or "today",
            "count": len(logs),
            "logs": logs,
        }
    except Exception as e:
        logger.error(f"Error reading telemetry logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
