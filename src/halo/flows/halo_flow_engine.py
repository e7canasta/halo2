"""Halo Flow Engine - Implementación custom lightweight del FlowEngine protocol.

Esta es NUESTRA implementación. En el futuro se puede swap por RasaFlowAdapter
sin cambiar código del resto del sistema.

Características:
- Stack jerárquico (como Rasa CALM)
- Slot filling incremental con validación
- Digression handling (interrupciones + resume)
- Integración con ConversationContextManager
- ~500 LOC vs. Rasa's ~50K LOC
"""

import uuid
import logging
from typing import Optional, List, Dict, Any
from copy import deepcopy

from .engine import (
    FlowEngine,
    FlowState,
    FlowContext,
    FlowAction,
    SlotValue,
    ProcessState,
    StepResult,
    ProcessAction,
)
from .flow_definition import FlowDefinition, SlotDefinition, StepAction

logger = logging.getLogger(__name__)


class HaloFlowEngine(FlowEngine):
    """Implementación lightweight del FlowEngine.

    Diseño:
    - Stack de flows (LIFO)
    - Cada flow es un state machine
    - Slot collection con auto-fill desde ConversationContext
    - Validación antes de transiciones
    """

    def __init__(self, conversation_manager=None):
        """Initialize flow engine.

        Args:
            conversation_manager: Optional ConversationContextManager para auto-fill
        """
        self.conversation_manager = conversation_manager

        # Flow registry (nombre → definición)
        self.flow_definitions: Dict[str, FlowDefinition] = {}

        # Flow instances activos (id → context)
        self.active_flows: Dict[str, FlowContext] = {}

        # Stack de flow IDs (top = current)
        self.flow_stack: List[str] = []

    def register_flow(self, flow_def: FlowDefinition):
        """Registrar un flow definition.

        Args:
            flow_def: FlowDefinition a registrar
        """
        self.flow_definitions[flow_def.name] = flow_def
        logger.info(f"Flow registered: {flow_def.name}")

    def start_flow(
        self,
        flow_name: str,
        initial_slots: Optional[Dict[str, Any]] = None,
        parent_flow_id: Optional[str] = None
    ) -> FlowContext:
        """Start a new flow."""
        # Get flow definition
        flow_def = self.flow_definitions.get(flow_name)
        if not flow_def:
            raise ValueError(f"Flow '{flow_name}' not registered")

        # Create flow context
        flow_id = str(uuid.uuid4())
        flow_context = FlowContext(
            flow_id=flow_id,
            flow_name=flow_name,
            state=FlowState.ACTIVE,
            slots={},
            current_step=flow_def.entry_step,
            metadata={
                "definition": flow_def,
                "retry_count": 0,
            },
            parent_flow_id=parent_flow_id,
        )

        # Auto-fill slots from conversation context if enabled
        if flow_def.auto_fill_slots and self.conversation_manager:
            self._auto_fill_slots(flow_context, flow_def)

        # Add initial slots
        if initial_slots:
            for name, value in initial_slots.items():
                flow_context.slots[name] = SlotValue(
                    name=name,
                    value=value,
                    confidence=1.0,
                    source="initial"
                )

        # Register flow
        self.active_flows[flow_id] = flow_context
        self.flow_stack.append(flow_id)

        logger.info(
            f"Flow started: {flow_name} (id={flow_id}, "
            f"stack_size={len(self.flow_stack)})"
        )

        return flow_context

    def _auto_fill_slots(self, context: FlowContext, flow_def: FlowDefinition):
        """Auto-fill slots from ConversationContextManager.

        Args:
            context: FlowContext
            flow_def: FlowDefinition
        """
        if not self.conversation_manager:
            return

        for slot_def in flow_def.slots:
            # Try to get value from conversation memory
            value = self.conversation_manager.get_missing_param(
                slot_def.name,
                tool_name="flow"  # Generic tool name
            )

            if value:
                context.slots[slot_def.name] = SlotValue(
                    name=slot_def.name,
                    value=value,
                    confidence=0.8,  # Lower confidence for inferred
                    source="conversation_context"
                )
                logger.debug(f"Auto-filled slot '{slot_def.name}' = {value}")

    def process_user_input(
        self,
        flow_id: str,
        user_input: str,
        classification: Any
    ) -> FlowAction:
        """Process user input in active flow."""
        context = self.active_flows.get(flow_id)
        if not context:
            raise ValueError(f"Flow {flow_id} not found")

        flow_def: FlowDefinition = context.metadata["definition"]

        # Check if collecting a specific slot
        if context.state == FlowState.COLLECTING:
            return self._handle_slot_collection(context, flow_def, user_input, classification)

        # Check if all required slots are filled
        missing_slots = self.get_missing_slots(flow_id)

        if missing_slots:
            # Start collecting next missing slot
            return self._start_slot_collection(context, flow_def, missing_slots[0])

        # All slots filled → execute current step
        return self._execute_step(context, flow_def)

    def _handle_slot_collection(
        self,
        context: FlowContext,
        flow_def: FlowDefinition,
        user_input: str,
        classification: Any
    ) -> FlowAction:
        """Handle slot collection state.

        Args:
            context: FlowContext
            flow_def: FlowDefinition
            user_input: User input
            classification: ClassificationResult

        Returns:
            FlowAction
        """
        collecting_slot = context.metadata.get("collecting_slot")
        if not collecting_slot:
            # No slot being collected, move to next
            missing = self.get_missing_slots(context.flow_id)
            if missing:
                return self._start_slot_collection(context, flow_def, missing[0])
            else:
                return self._execute_step(context, flow_def)

        slot_def = flow_def.get_slot_definition(collecting_slot)
        if not slot_def:
            logger.error(f"Slot definition not found: {collecting_slot}")
            context.state = FlowState.FAILED
            return FlowAction("cancel", {"reason": "Invalid slot"})

        # Extract value from classification
        value = self._extract_slot_value(collecting_slot, classification)

        if value is None:
            # No value extracted, retry
            retry_count = context.metadata.get("retry_count", 0)
            if retry_count >= flow_def.max_retries:
                # Max retries reached
                context.state = FlowState.FAILED
                return FlowAction(
                    "cancel",
                    {"reason": f"Max retries reached for slot '{collecting_slot}'"}
                )

            context.metadata["retry_count"] = retry_count + 1
            return FlowAction(
                "ask_question",
                {
                    "question": slot_def.prompt_template or f"¿Qué {collecting_slot}?",
                    "slot": collecting_slot,
                }
            )

        # Validate slot
        is_valid, error_msg = slot_def.validate(value)
        if not is_valid:
            return FlowAction(
                "ask_question",
                {
                    "question": error_msg or f"{collecting_slot} no es válido. Intentá de nuevo.",
                    "slot": collecting_slot,
                }
            )

        # Collect slot
        success = self.collect_slot(context.flow_id, collecting_slot, value, confidence=0.9)

        if success:
            # Move to next missing slot or execute
            context.state = FlowState.ACTIVE
            context.metadata["collecting_slot"] = None
            context.metadata["retry_count"] = 0

            missing = self.get_missing_slots(context.flow_id)
            if missing:
                return self._start_slot_collection(context, flow_def, missing[0])
            else:
                return self._execute_step(context, flow_def)
        else:
            # Collection failed
            return FlowAction(
                "ask_question",
                {"question": f"No pude guardar {collecting_slot}. Intentá de nuevo."}
            )

    def _start_slot_collection(
        self,
        context: FlowContext,
        flow_def: FlowDefinition,
        slot_name: str
    ) -> FlowAction:
        """Start collecting a slot.

        Args:
            context: FlowContext
            flow_def: FlowDefinition
            slot_name: Slot to collect

        Returns:
            FlowAction to ask for the slot
        """
        context.state = FlowState.COLLECTING
        context.metadata["collecting_slot"] = slot_name

        slot_def = flow_def.get_slot_definition(slot_name)
        prompt = slot_def.prompt_template if slot_def else f"¿Qué {slot_name}?"

        return FlowAction(
            "ask_question",
            {"question": prompt, "slot": slot_name}
        )

    def _extract_slot_value(self, slot_name: str, classification: Any) -> Optional[Any]:
        """Extract slot value from classification.

        Args:
            slot_name: Slot name
            classification: ClassificationResult

        Returns:
            Extracted value or None
        """
        if not classification:
            return None

        # Try to extract from parameters
        if hasattr(classification, "parameters"):
            return classification.parameters.get(slot_name)

        return None

    def _execute_step(self, context: FlowContext, flow_def: FlowDefinition) -> FlowAction:
        """Execute current step.

        Args:
            context: FlowContext
            flow_def: FlowDefinition

        Returns:
            FlowAction
        """
        step = flow_def.get_step(context.current_step)
        if not step:
            logger.error(f"Step not found: {context.current_step}")
            context.state = FlowState.FAILED
            return FlowAction("cancel", {"reason": "Invalid step"})

        # Execute based on action type
        if step.action == "tool_call":
            # Build tool call from slots
            tool_name = step.params.get("tool")
            parameters = {name: slot.value for name, slot in context.slots.items()}

            context.state = FlowState.COMPLETED
            return FlowAction(
                "tool_call",
                {"tool": tool_name, "parameters": parameters}
            )

        elif step.action == "complete":
            context.state = FlowState.COMPLETED
            return FlowAction("complete", {"flow_id": context.flow_id})

        elif step.action == "cancel":
            context.state = FlowState.CANCELLED
            return FlowAction("cancel", {"flow_id": context.flow_id})

        else:
            logger.warning(f"Unknown action: {step.action}")
            return FlowAction("complete", {"flow_id": context.flow_id})

    def collect_slot(
        self,
        flow_id: str,
        slot_name: str,
        value: Any,
        confidence: float = 1.0
    ) -> bool:
        """Collect slot value."""
        context = self.active_flows.get(flow_id)
        if not context:
            return False

        context.slots[slot_name] = SlotValue(
            name=slot_name,
            value=value,
            confidence=confidence,
            source="user"
        )

        logger.debug(f"Slot collected: {slot_name} = {value} (confidence={confidence})")
        return True

    def get_current_flow(self) -> Optional[FlowContext]:
        """Get current flow (top of stack)."""
        if not self.flow_stack:
            return None

        flow_id = self.flow_stack[-1]
        return self.active_flows.get(flow_id)

    def get_flow(self, flow_id: str) -> Optional[FlowContext]:
        """Get flow by ID."""
        return self.active_flows.get(flow_id)

    def complete_flow(self, flow_id: str) -> Optional[FlowContext]:
        """Complete flow and POP from stack."""
        context = self.active_flows.get(flow_id)
        if not context:
            return None

        context.state = FlowState.COMPLETED

        # Remove from stack
        if flow_id in self.flow_stack:
            self.flow_stack.remove(flow_id)

        logger.info(f"Flow completed: {context.flow_name} (id={flow_id})")

        # Return parent flow (resumed)
        if context.parent_flow_id:
            parent = self.active_flows.get(context.parent_flow_id)
            if parent:
                parent.state = FlowState.ACTIVE  # Resume parent
                logger.info(f"Resumed parent flow: {parent.flow_name}")
                return parent

        return None

    def cancel_flow(self, flow_id: str) -> bool:
        """Cancel flow."""
        context = self.active_flows.get(flow_id)
        if not context:
            return False

        context.state = FlowState.CANCELLED

        # Remove from stack
        if flow_id in self.flow_stack:
            self.flow_stack.remove(flow_id)

        logger.info(f"Flow cancelled: {context.flow_name} (id={flow_id})")
        return True

    def push_digression(
        self,
        new_flow_name: str,
        initial_slots: Optional[Dict[str, Any]] = None
    ) -> FlowContext:
        """Push digression (pause current, start new)."""
        # Pause current flow
        current = self.get_current_flow()
        if current:
            current.state = FlowState.PAUSED
            logger.info(f"Paused flow: {current.flow_name} for digression")

        # Start new flow as child
        parent_id = current.flow_id if current else None
        new_context = self.start_flow(new_flow_name, initial_slots, parent_id)

        logger.info(
            f"Digression pushed: {new_flow_name} (stack_size={len(self.flow_stack)})"
        )

        return new_context

    def get_stack_size(self) -> int:
        """Get stack size."""
        return len(self.flow_stack)

    def get_missing_slots(self, flow_id: str) -> List[str]:
        """Get missing slots."""
        context = self.active_flows.get(flow_id)
        if not context:
            return []

        flow_def: FlowDefinition = context.metadata["definition"]
        required_slots = flow_def.get_required_slots()

        missing = []
        for slot_name in required_slots:
            if not context.is_slot_filled(slot_name):
                missing.append(slot_name)

        return missing

    def reset(self):
        """Reset engine."""
        self.active_flows.clear()
        self.flow_stack.clear()
        logger.info("Flow engine reset")


class HaloProcessEngine(HaloFlowEngine):
    """Process-oriented engine con soporte para ejecución parcial y feedback.

    Extiende HaloFlowEngine con capacidades de:
    - Ejecución parcial con feedback progresivo
    - Handler MQTT asíncrono con correlation
    - Contexto enriquecido que crece con cada step
    - Validación de intents en contexto temporal
    - Evaluación de condiciones (branching)
    """

    def __init__(self, conversation_manager=None, tool_pipeline=None):
        """Initialize process engine.

        Args:
            conversation_manager: Optional ConversationContextManager
            tool_pipeline: Optional ToolExecutionPipeline para ejecutar tools
        """
        super().__init__(conversation_manager)
        self.tool_pipeline = tool_pipeline

        # Correlation tracking para handlers MQTT asíncronos
        self.pending_handlers: Dict[str, str] = {}  # correlation_id → process_id

        # Tool mapping: tool_name → flow_name
        self.tool_to_flow: Dict[str, str] = {}

    def register_flow(self, flow_def: FlowDefinition):
        """Register flow and build tool mapping."""
        super().register_flow(flow_def)

        # Index triggers for quick lookup
        for tool in flow_def.triggered_by:
            self.tool_to_flow[tool] = flow_def.name

    def get_flow_for_tool(self, tool_name: str) -> Optional[str]:
        """Get flow name that is triggered by this tool.

        Args:
            tool_name: Tool name

        Returns:
            Flow name or None
        """
        return self.tool_to_flow.get(tool_name)

    def get_missing_required_slots(
        self,
        flow_name: str,
        current_params: Dict[str, Any]
    ) -> List[str]:
        """Check which required slots are missing from parameters.

        Args:
            flow_name: Flow name
            current_params: Current parameters from classification

        Returns:
            List of missing slot names
        """
        flow_def = self.flow_definitions.get(flow_name)
        if not flow_def:
            return []

        missing = []
        for slot in flow_def.slots:
            if slot.required and slot.name not in current_params:
                missing.append(slot.name)

        return missing

    def start_flow(
        self,
        flow_name: str,
        initial_slots: Optional[Dict[str, Any]] = None,
        parent_flow_id: Optional[str] = None
    ) -> ProcessState:
        """Start flow with ProcessState instead of FlowContext.

        Returns ProcessState with process-oriented capabilities.
        """
        # Call parent to create FlowContext
        flow_context = super().start_flow(flow_name, initial_slots, parent_flow_id)

        # Convert to ProcessState
        process_state = ProcessState(
            flow_id=flow_context.flow_id,
            flow_name=flow_context.flow_name,
            state=flow_context.state,
            slots=flow_context.slots,
            current_step=flow_context.current_step,
            metadata=flow_context.metadata,
            parent_flow_id=flow_context.parent_flow_id,
            execution_history=[],
            enriched_context={},
            awaiting_handler=None,
        )

        # Replace in active_flows
        self.active_flows[flow_context.flow_id] = process_state

        return process_state

    def execute_step(self, process_id: str) -> ProcessAction:
        """Ejecuta el step actual del proceso con soporte process-oriented.

        Args:
            process_id: ID del proceso

        Returns:
            ProcessAction a ejecutar
        """
        state: ProcessState = self.active_flows.get(process_id)
        if not state:
            raise ValueError(f"Process {process_id} not found")

        flow_def: FlowDefinition = state.metadata["definition"]
        step = flow_def.get_step(state.current_step)

        if not step:
            logger.error(f"Step not found: {state.current_step}")
            state.state = FlowState.FAILED
            return ProcessAction("cancel", {"reason": "Invalid step"})

        # Execute based on StepAction type
        if step.action in ["tool_call", StepAction.TOOL_CALL]:
            return self._execute_tool_call(state, step, flow_def)

        elif step.action in ["tool_call_async", StepAction.TOOL_CALL_ASYNC]:
            return self._execute_tool_call_async(state, step, flow_def)

        elif step.action in ["condition", StepAction.CONDITION]:
            return self._evaluate_condition_step(state, step, flow_def)

        elif step.action in ["ask_user", StepAction.ASK_USER]:
            return ProcessAction("ask_question", {
                "question": step.params.get("question"),
                "process_id": process_id,
            })

        elif step.action in ["complete", StepAction.COMPLETE]:
            state.state = FlowState.COMPLETED
            return ProcessAction("complete", {
                "flow_id": process_id,
                "message": step.params.get("message", "Proceso completado"),
                "history": [self._step_result_to_dict(r) for r in state.execution_history],
            })

        elif step.action in ["cancel", StepAction.CANCEL]:
            state.state = FlowState.CANCELLED
            return ProcessAction("cancel", {"flow_id": process_id})

        else:
            logger.warning(f"Unknown step action: {step.action}")
            return ProcessAction("complete", {"flow_id": process_id})

    def _execute_tool_call(
        self,
        state: ProcessState,
        step,
        flow_def: FlowDefinition
    ) -> ProcessAction:
        """Execute tool synchronously."""
        from datetime import datetime

        tool_name = step.params.get("tool")
        parameters = self._build_tool_params(state, step.params.get("params", {}))

        # Execute tool if pipeline available
        if self.tool_pipeline:
            try:
                result = self.tool_pipeline.execute(
                    tool_name=tool_name,
                    parameters=parameters,
                    context={}
                )

                # Record step result
                state.add_step_result(StepResult(
                    step_id=step.id,
                    action="tool_call",
                    success=result.get("status") == "completed",
                    result=result,
                    timestamp=datetime.now(),
                    handler_response=result.get("result")
                ))

                # Advance to next step or complete
                next_step = step.next_step
                if next_step:
                    state.current_step = next_step
                    return self.execute_step(state.flow_id)
                else:
                    state.state = FlowState.COMPLETED
                    return ProcessAction("complete", {
                        "message": result.get("result", {}).get("message", "Tool ejecutado"),
                        "flow_id": state.flow_id
                    })

            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                state.add_step_result(StepResult(
                    step_id=step.id,
                    action="tool_call",
                    success=False,
                    result={"error": str(e)},
                    timestamp=datetime.now()
                ))
                return ProcessAction("cancel", {"reason": str(e)})
        else:
            # No pipeline, just return action
            return ProcessAction("tool_call", {
                "tool": tool_name,
                "parameters": parameters,
                "process_id": state.flow_id,
            })

    def _execute_tool_call_async(
        self,
        state: ProcessState,
        step,
        flow_def: FlowDefinition
    ) -> ProcessAction:
        """Execute tool asynchronously and wait for handler."""
        tool_name = step.params.get("tool")
        parameters = self._build_tool_params(state, step.params.get("params", {}))

        # Generate correlation ID
        correlation_id = str(uuid.uuid4())

        # Mark as waiting
        state.awaiting_handler = step.id
        self.pending_handlers[correlation_id] = state.flow_id

        logger.info(f"Waiting for handler response: {correlation_id}")

        return ProcessAction("awaiting_handler", {
            "correlation_id": correlation_id,
            "tool": tool_name,
            "parameters": parameters,
            "message": f"Ejecutando {tool_name}...",
            "process_id": state.flow_id,
        })

    def _evaluate_condition_step(
        self,
        state: ProcessState,
        step,
        flow_def: FlowDefinition
    ) -> ProcessAction:
        """Evaluate condition and branch."""
        from datetime import datetime

        condition_expr = step.params.get("condition")

        # Simple condition evaluation (can be extended)
        result = self._evaluate_condition(condition_expr, state.enriched_context)

        # Record result
        state.add_step_result(StepResult(
            step_id=step.id,
            action="condition",
            success=True,
            result={"condition_result": result},
            timestamp=datetime.now()
        ))

        # Find next step based on result
        next_step = None
        for cond in step.conditions:
            if (result and cond.get("condition") == "true") or \
               (not result and cond.get("condition") == "false"):
                next_step = cond.get("next_step")
                break

        if next_step:
            state.current_step = next_step
            return self.execute_step(state.flow_id)
        else:
            logger.warning(f"No next step found for condition result: {result}")
            return ProcessAction("complete", {"flow_id": state.flow_id})

    def _evaluate_condition(
        self,
        condition: str,
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate a condition expression against context.

        Args:
            condition: Condition expression
            context: Enriched context

        Returns:
            True/False
        """
        # Simple implementation - can be extended with safe eval
        # For now, check simple keys
        if condition in context:
            return bool(context[condition])

        # Check for simple expressions like "temperature > 20"
        # TODO: Implement safe expression evaluator

        return False

    def _build_tool_params(
        self,
        state: ProcessState,
        params_template: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build tool parameters from template using slots.

        Supports templates like {"room": "{rooms[0]}", "brightness": "{brightness}"}

        Args:
            state: ProcessState
            params_template: Parameter template

        Returns:
            Resolved parameters
        """
        params = {}
        for key, value in params_template.items():
            if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
                # Template variable
                var_name = value[1:-1]  # Remove {}

                # Support array access like "rooms[0]"
                if "[" in var_name:
                    base_name = var_name.split("[")[0]
                    index_str = var_name.split("[")[1].split("]")[0]
                    index = int(index_str)

                    slot_value = state.get_slot(base_name)
                    if isinstance(slot_value, list) and len(slot_value) > index:
                        params[key] = slot_value[index]
                else:
                    # Simple slot reference
                    params[key] = state.get_slot(var_name)
            else:
                params[key] = value

        return params

    def handle_handler_response(
        self,
        correlation_id: str,
        response: Dict[str, Any]
    ) -> Optional[ProcessAction]:
        """Handle response from MQTT handler and continue process.

        Args:
            correlation_id: Correlation ID from original request
            response: Handler response

        Returns:
            ProcessAction to continue, or None if no pending handler
        """
        from datetime import datetime

        if correlation_id not in self.pending_handlers:
            logger.warning(f"No pending handler for correlation_id: {correlation_id}")
            return None

        process_id = self.pending_handlers.pop(correlation_id)
        state: ProcessState = self.active_flows.get(process_id)

        if not state:
            logger.error(f"Process not found: {process_id}")
            return None

        # Record handler response
        state.add_step_result(StepResult(
            step_id=state.awaiting_handler,
            action="tool_call_async",
            success=response.get("status") == "completed",
            result=response,
            timestamp=datetime.now(),
            handler_response=response
        ))

        state.awaiting_handler = None

        flow_def: FlowDefinition = state.metadata["definition"]
        step = flow_def.get_step(state.current_step)

        # Determine next step based on success/failure
        next_step = None
        if response.get("status") == "completed":
            # Find success condition
            for cond in step.conditions:
                if cond.get("condition") == "success":
                    next_step = cond.get("next_step")
                    break
        else:
            # Find failure condition
            for cond in step.conditions:
                if cond.get("condition") == "failure":
                    next_step = cond.get("next_step")
                    break

        if next_step:
            state.current_step = next_step
            return self.execute_step(state.flow_id)
        else:
            # No next step, complete
            state.state = FlowState.COMPLETED
            return ProcessAction("complete", {
                "message": "Handler response received",
                "flow_id": process_id
            })

    def validate_intent_in_context(
        self,
        intent: str,
        params: Dict[str, Any]
    ) -> bool:
        """Validate if intent makes sense in current process context.

        Args:
            intent: Intent/tool name
            params: Parameters

        Returns:
            True if valid in current context
        """
        current = self.get_current_flow()
        if not current:
            return True  # No process active, everything valid

        # TODO: Implement context-aware validation
        # For now, allow all
        return True

    def _step_result_to_dict(self, result: StepResult) -> Dict[str, Any]:
        """Convert StepResult to dict for JSON serialization."""
        return {
            "step_id": result.step_id,
            "action": result.action,
            "success": result.success,
            "timestamp": result.timestamp.isoformat(),
        }
