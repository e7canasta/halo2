"""Flow Engine - Sistema de flows jerárquicos para conversaciones complejas.

Arquitectura modular swappeable:
- FlowEngine (ABC) - Contrato
- HaloFlowEngine - Implementación custom lightweight
- RasaFlowAdapter - Future wrapper para Rasa CALM (si lo necesitás)

Ejemplo de uso:
    from halo.flows import HaloFlowEngine, FlowBuilder, SlotType

    # Crear engine
    engine = HaloFlowEngine(conversation_manager=context_mgr)

    # Definir flow
    scene_flow = (FlowBuilder("scene_setup")
        .description("Configurar escena de iluminación")
        .add_slot("scene_name", SlotType.TEXT, required=True)
        .add_slot("rooms", SlotType.LIST, required=True)
        .add_step("collect", "ask_slot", {"slot": "scene_name"})
        .add_step("execute", "tool_call", {"tool": "scene_control"})
        .build())

    # Registrar flow
    engine.register_flow(scene_flow)

    # Usar flow
    context = engine.start_flow("scene_setup")
    action = engine.process_user_input(context.flow_id, user_input, classification)
"""

from .engine import (
    FlowEngine,
    FlowState,
    FlowContext,
    FlowAction,
    SlotValue,
    FlowValidator,
    # Process-oriented types
    ProcessState,
    StepResult,
    ProcessAction,
)

from .flow_definition import (
    FlowDefinition,
    SlotDefinition,
    FlowStep,
    SlotType,
    FlowBuilder,
    # Process-oriented
    StepAction,
)

from .halo_flow_engine import HaloFlowEngine, HaloProcessEngine

__all__ = [
    # Engine
    "FlowEngine",
    "FlowState",
    "FlowContext",
    "FlowAction",
    "SlotValue",
    "FlowValidator",
    # Process-oriented engine
    "ProcessState",
    "StepResult",
    "ProcessAction",
    # Definitions
    "FlowDefinition",
    "SlotDefinition",
    "FlowStep",
    "SlotType",
    "FlowBuilder",
    "StepAction",
    # Implementations
    "HaloFlowEngine",
    "HaloProcessEngine",
]
