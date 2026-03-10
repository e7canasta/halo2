"""Flow Engine Protocol - Contrato para implementaciones swappeable.

Este es el CONTRATO que cualquier implementación debe cumplir.
Permite cambiar entre HaloFlowEngine (custom) y RasaFlowAdapter (futuro) sin cambiar código.

Filosofía: Interface segregation + Dependency inversion
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class FlowState(str, Enum):
    """Estados posibles de un flow."""

    ACTIVE = "active"           # Flow activo, esperando input
    COLLECTING = "collecting"   # Recolectando slots
    VALIDATING = "validating"   # Validando input del usuario
    PAUSED = "paused"          # Pausado por digression
    COMPLETED = "completed"     # Flow completado exitosamente
    CANCELLED = "cancelled"     # Flow cancelado por usuario
    FAILED = "failed"          # Flow falló por error


@dataclass
class SlotValue:
    """Valor de un slot recolectado."""

    name: str
    value: Any
    confidence: float = 1.0
    source: str = "user"  # user, inferred, default


@dataclass
class FlowContext:
    """Contexto de un flow en ejecución.

    Similar a Rasa Tracker, pero más liviano.
    """

    flow_id: str
    flow_name: str
    state: FlowState
    slots: Dict[str, SlotValue]
    current_step: str
    metadata: Dict[str, Any]
    parent_flow_id: Optional[str] = None  # Para stack jerárquico

    def get_slot(self, name: str) -> Optional[Any]:
        """Get slot value."""
        slot = self.slots.get(name)
        return slot.value if slot else None

    def is_slot_filled(self, name: str) -> bool:
        """Check if slot is filled."""
        return name in self.slots and self.slots[name].value is not None


@dataclass
class FlowAction:
    """Acción a ejecutar como resultado de un flow.

    Esto es lo que el flow devuelve para que se ejecute.
    """

    type: str  # "tool_call", "ask_question", "complete", "cancel"
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = None


@dataclass
class StepResult:
    """Resultado de ejecutar un step del proceso.

    Usado para process-oriented execution con feedback parcial.
    """

    step_id: str
    action: str  # tipo de acción ejecutada
    success: bool
    result: Dict[str, Any]
    timestamp: datetime
    handler_response: Optional[Dict[str, Any]] = None  # Respuesta del handler MQTT


@dataclass
class ProcessState(FlowContext):
    """Estado extendido para process-oriented flows.

    Extiende FlowContext con capacidades de:
    - Ejecución parcial con feedback
    - Contexto enriquecido que crece con cada step
    - Tracking de handlers MQTT asíncronos
    """

    # NEW: Historia de ejecución (cada step ejecutado)
    execution_history: List[StepResult] = field(default_factory=list)

    # NEW: Contexto enriquecido que crece con cada step
    # Contiene resultados de handlers, estado temporal, etc.
    enriched_context: Dict[str, Any] = field(default_factory=dict)

    # NEW: Step esperando respuesta de handler
    awaiting_handler: Optional[str] = None  # step_id que espera handler response

    def add_step_result(self, result: StepResult):
        """Agrega resultado de step y enriquece contexto.

        Args:
            result: Resultado del step ejecutado
        """
        self.execution_history.append(result)

        # Merge handler response al contexto enriquecido
        if result.handler_response:
            self.enriched_context.update(result.handler_response)

    def get_last_result(self) -> Optional[StepResult]:
        """Obtiene el último resultado de ejecución."""
        return self.execution_history[-1] if self.execution_history else None

    def is_waiting_handler(self) -> bool:
        """Check si está esperando respuesta de handler."""
        return self.awaiting_handler is not None


# Alias para compatibilidad: ProcessAction = FlowAction
ProcessAction = FlowAction


class FlowEngine(ABC):
    """Abstract Base Class para Flow Engines.

    Contrato que DEBE cumplir cualquier implementación:
    - HaloFlowEngine (nuestra custom)
    - RasaFlowAdapter (futuro wrapper de Rasa CALM)
    - Cualquier otra implementación

    Diseño inspirado en:
    - Rasa CALM (stack + flows)
    - XState (state machines)
    - AWS Step Functions (orchestration)
    """

    @abstractmethod
    def start_flow(
        self,
        flow_name: str,
        initial_slots: Optional[Dict[str, Any]] = None,
        parent_flow_id: Optional[str] = None
    ) -> FlowContext:
        """Iniciar un nuevo flow.

        Args:
            flow_name: Nombre del flow a iniciar
            initial_slots: Slots iniciales (pre-filled)
            parent_flow_id: ID del flow padre si es una digression

        Returns:
            FlowContext del nuevo flow
        """
        pass

    @abstractmethod
    def process_user_input(
        self,
        flow_id: str,
        user_input: str,
        classification: Any  # ClassificationResult
    ) -> FlowAction:
        """Procesar input del usuario en un flow activo.

        Args:
            flow_id: ID del flow activo
            user_input: Input del usuario
            classification: Resultado de clasificación de intent

        Returns:
            FlowAction a ejecutar
        """
        pass

    @abstractmethod
    def collect_slot(
        self,
        flow_id: str,
        slot_name: str,
        value: Any,
        confidence: float = 1.0
    ) -> bool:
        """Recolectar valor de un slot.

        Args:
            flow_id: ID del flow
            slot_name: Nombre del slot
            value: Valor del slot
            confidence: Confianza en el valor (0-1)

        Returns:
            True si el slot fue aceptado, False si fue rechazado
        """
        pass

    @abstractmethod
    def get_current_flow(self) -> Optional[FlowContext]:
        """Obtener el flow actual (top of stack).

        Returns:
            FlowContext del flow activo, o None si no hay flows
        """
        pass

    @abstractmethod
    def get_flow(self, flow_id: str) -> Optional[FlowContext]:
        """Obtener un flow específico por ID.

        Args:
            flow_id: ID del flow

        Returns:
            FlowContext o None
        """
        pass

    @abstractmethod
    def complete_flow(self, flow_id: str) -> Optional[FlowContext]:
        """Completar un flow y hacer POP del stack.

        Args:
            flow_id: ID del flow a completar

        Returns:
            FlowContext del flow padre (resumed), o None si era el último
        """
        pass

    @abstractmethod
    def cancel_flow(self, flow_id: str) -> bool:
        """Cancelar un flow.

        Args:
            flow_id: ID del flow a cancelar

        Returns:
            True si fue cancelado
        """
        pass

    @abstractmethod
    def push_digression(
        self,
        new_flow_name: str,
        initial_slots: Optional[Dict[str, Any]] = None
    ) -> FlowContext:
        """Pausar flow actual y hacer PUSH de una digression.

        Similar a Rasa CALM digression handling.

        Args:
            new_flow_name: Flow de la digression
            initial_slots: Slots iniciales

        Returns:
            FlowContext del nuevo flow (ahora en top of stack)
        """
        pass

    @abstractmethod
    def get_stack_size(self) -> int:
        """Obtener tamaño del stack de flows.

        Returns:
            Número de flows activos en el stack
        """
        pass

    @abstractmethod
    def get_missing_slots(self, flow_id: str) -> List[str]:
        """Obtener lista de slots faltantes en un flow.

        Args:
            flow_id: ID del flow

        Returns:
            Lista de nombres de slots que faltan
        """
        pass

    @abstractmethod
    def reset(self):
        """Reset completo del engine (útil para testing)."""
        pass


class FlowValidator(ABC):
    """Validador de slots y transiciones.

    Permite custom validation logic swappeable.
    """

    @abstractmethod
    def validate_slot(
        self,
        slot_name: str,
        value: Any,
        context: FlowContext
    ) -> tuple[bool, Optional[str]]:
        """Validar un slot value.

        Args:
            slot_name: Nombre del slot
            value: Valor a validar
            context: Contexto del flow

        Returns:
            (is_valid, error_message)
        """
        pass

    @abstractmethod
    def can_transition(
        self,
        from_step: str,
        to_step: str,
        context: FlowContext
    ) -> bool:
        """Validar si se puede hacer una transición.

        Args:
            from_step: Step actual
            to_step: Step destino
            context: Contexto del flow

        Returns:
            True si la transición es válida
        """
        pass
