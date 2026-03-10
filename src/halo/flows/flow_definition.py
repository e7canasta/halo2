"""Flow Definition - DSL declarativo para definir flows.

Permite definir flows de forma declarativa (Python dataclasses o YAML).
Inspirado en Rasa Flows pero más lightweight.

Ejemplo de uso:
    scene_setup_flow = FlowDefinition(
        name="scene_setup",
        description="Configurar escena de iluminación",
        slots=[
            SlotDefinition("scene_name", SlotType.TEXT, required=True),
            SlotDefinition("rooms", SlotType.LIST, required=True),
        ],
        steps=[
            FlowStep("ask_scene_name", action="ask_slot", params={"slot": "scene_name"}),
            FlowStep("ask_rooms", action="ask_slot", params={"slot": "rooms"}),
            FlowStep("execute", action="tool_call", params={"tool": "scene_control"}),
        ]
    )
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum


class SlotType(str, Enum):
    """Tipos de slots soportados."""

    TEXT = "text"           # String libre
    NUMBER = "number"       # Número (int o float)
    BOOLEAN = "boolean"     # True/False
    CHOICE = "choice"       # Lista de opciones válidas
    LIST = "list"          # Lista de valores
    ENTITY = "entity"      # Entidad extraída por NER
    ANY = "any"           # Sin validación de tipo


class StepAction(str, Enum):
    """Tipos de acciones que un step puede ejecutar.

    Incluye tanto acciones task-oriented (simples) como process-oriented (complejas).
    """

    # Task-oriented (básicas)
    ASK_SLOT = "ask_slot"           # Preguntar por un slot
    TOOL_CALL = "tool_call"         # Ejecutar tool síncronamente
    COMPLETE = "complete"           # Completar proceso
    CANCEL = "cancel"               # Cancelar proceso

    # Process-oriented (avanzadas)
    TOOL_CALL_ASYNC = "tool_call_async"  # Ejecutar tool y esperar handler MQTT
    CONDITION = "condition"              # Evaluar condición (branching)
    PARALLEL = "parallel"                # Ejecutar múltiples steps en paralelo
    AWAIT_EVENT = "await_event"          # Esperar evento externo
    ENRICH_CONTEXT = "enrich_context"    # Solo enriquecer contexto
    ASK_USER = "ask_user"                # Preguntar algo al usuario (no slot)


@dataclass
class SlotDefinition:
    """Definición de un slot a recolectar en un flow.

    Similar a Rasa slots pero más simple.
    """

    name: str
    slot_type: SlotType = SlotType.TEXT
    required: bool = True
    description: str = ""

    # Validation
    choices: Optional[List[Any]] = None  # Para SlotType.CHOICE
    min_value: Optional[float] = None    # Para SlotType.NUMBER
    max_value: Optional[float] = None    # Para SlotType.NUMBER
    regex_pattern: Optional[str] = None  # Para SlotType.TEXT
    custom_validator: Optional[Callable] = None

    # Defaults
    default_value: Optional[Any] = None
    initial_value: Optional[Any] = None

    # UI hints
    prompt_template: Optional[str] = None  # "¿Qué {slot_name} querés?"
    error_message: Optional[str] = None    # Mensaje si validación falla

    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """Validar un valor para este slot.

        Returns:
            (is_valid, error_message)
        """
        # Type validation
        if self.slot_type == SlotType.NUMBER:
            try:
                num_value = float(value)
                if self.min_value is not None and num_value < self.min_value:
                    return (False, f"{self.name} debe ser >= {self.min_value}")
                if self.max_value is not None and num_value > self.max_value:
                    return (False, f"{self.name} debe ser <= {self.max_value}")
            except (ValueError, TypeError):
                return (False, f"{self.name} debe ser un número")

        elif self.slot_type == SlotType.CHOICE:
            if self.choices and value not in self.choices:
                return (False, f"{self.name} debe ser uno de: {', '.join(map(str, self.choices))}")

        # Custom validator
        if self.custom_validator:
            try:
                is_valid = self.custom_validator(value)
                if not is_valid:
                    return (False, self.error_message or f"{self.name} no es válido")
            except Exception as e:
                return (False, str(e))

        return (True, None)


@dataclass
class FlowStep:
    """Un paso en el flow.

    Similar a Rasa actions pero más declarativo.
    """

    id: str
    action: str  # "ask_slot", "tool_call", "condition", "complete", "cancel"
    params: Dict[str, Any] = field(default_factory=dict)

    # Conditional transitions
    next_step: Optional[str] = None  # Next step incondicional
    conditions: List[Dict[str, Any]] = field(default_factory=list)  # [{condition, next_step}]

    # Metadata
    description: str = ""
    retryable: bool = True
    timeout_seconds: Optional[int] = None


@dataclass
class FlowDefinition:
    """Definición completa de un flow.

    Esto es el "blueprint" del flow. El FlowEngine usa esto para ejecutar.
    """

    name: str
    description: str = ""

    # Slots a recolectar
    slots: List[SlotDefinition] = field(default_factory=list)

    # Pasos del flow (state machine)
    steps: List[FlowStep] = field(default_factory=list)

    # Entry point
    entry_step: str = "start"

    # Configuración
    allow_interruptions: bool = True  # ¿Permitir digresiones?
    auto_fill_slots: bool = True      # ¿Auto-fill desde context?
    max_retries: int = 3              # Intentos máximos para un slot

    # Process-oriented: Triggers (cuándo iniciar este flow)
    triggered_by: List[str] = field(default_factory=list)  # tools que lo activan
    trigger_when_missing: List[str] = field(default_factory=list)  # slots críticos

    # Process-oriented: Grafo de relaciones
    allowed_digressions: List[str] = field(default_factory=list)  # flows permitidos como digresión

    # Metadata
    tags: List[str] = field(default_factory=list)
    version: str = "1.0"

    def get_step(self, step_id: str) -> Optional[FlowStep]:
        """Obtener un step por ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def get_required_slots(self) -> List[str]:
        """Obtener lista de slots requeridos."""
        return [slot.name for slot in self.slots if slot.required]

    def get_slot_definition(self, slot_name: str) -> Optional[SlotDefinition]:
        """Obtener definición de un slot."""
        for slot in self.slots:
            if slot.name == slot_name:
                return slot
        return None


# === Builder Pattern para crear flows más fácilmente ===

class FlowBuilder:
    """Builder para crear FlowDefinitions de forma fluida.

    Ejemplo:
        flow = (FlowBuilder("booking")
            .description("Book a restaurant")
            .add_slot("restaurant", SlotType.TEXT, required=True)
            .add_slot("date", SlotType.TEXT, required=True)
            .add_slot("num_people", SlotType.NUMBER, min_value=1, max_value=20)
            .add_step("ask_restaurant", "ask_slot", {"slot": "restaurant"})
            .add_step("ask_date", "ask_slot", {"slot": "date"})
            .add_step("ask_people", "ask_slot", {"slot": "num_people"})
            .add_step("confirm", "tool_call", {"tool": "restaurant_booking"})
            .build())
    """

    def __init__(self, name: str):
        self.name = name
        self._description = ""
        self._slots: List[SlotDefinition] = []
        self._steps: List[FlowStep] = []
        self._entry_step = "start"
        self._allow_interruptions = True
        self._auto_fill_slots = True
        self._max_retries = 3
        self._tags: List[str] = []
        # Process-oriented
        self._triggered_by: List[str] = []
        self._trigger_when_missing: List[str] = []
        self._allowed_digressions: List[str] = []

    def description(self, desc: str) -> "FlowBuilder":
        """Set description."""
        self._description = desc
        return self

    def add_slot(
        self,
        name: str,
        slot_type: SlotType = SlotType.TEXT,
        required: bool = True,
        **kwargs
    ) -> "FlowBuilder":
        """Add a slot."""
        slot = SlotDefinition(name=name, slot_type=slot_type, required=required, **kwargs)
        self._slots.append(slot)
        return self

    def add_step(
        self,
        step_id: str,
        action: str,
        params: Dict[str, Any] = None,
        **kwargs
    ) -> "FlowBuilder":
        """Add a step."""
        step = FlowStep(id=step_id, action=action, params=params or {}, **kwargs)
        self._steps.append(step)
        return self

    def entry(self, step_id: str) -> "FlowBuilder":
        """Set entry step."""
        self._entry_step = step_id
        return self

    def allow_interruptions(self, allow: bool = True) -> "FlowBuilder":
        """Allow/disallow interruptions."""
        self._allow_interruptions = allow
        return self

    def auto_fill(self, auto: bool = True) -> "FlowBuilder":
        """Enable/disable auto-filling slots from context."""
        self._auto_fill_slots = auto
        return self

    def tag(self, *tags: str) -> "FlowBuilder":
        """Add tags."""
        self._tags.extend(tags)
        return self

    # === Process-oriented methods ===

    def triggered_by(self, *tools: str) -> "FlowBuilder":
        """Tools que pueden iniciar este proceso.

        Args:
            tools: Nombres de tools que activan este flow

        Returns:
            self para chaining
        """
        self._triggered_by.extend(tools)
        return self

    def trigger_when_missing(self, *slots: str) -> "FlowBuilder":
        """Iniciar flow si estos slots faltan en clasificación.

        Args:
            slots: Nombres de slots críticos

        Returns:
            self para chaining
        """
        self._trigger_when_missing.extend(slots)
        return self

    def can_digress_to(self, *flows: str) -> "FlowBuilder":
        """Procesos a los que se puede hacer digresión.

        Args:
            flows: Nombres de flows permitidos como digresión

        Returns:
            self para chaining
        """
        self._allowed_digressions.extend(flows)
        return self

    def add_async_step(
        self,
        step_id: str,
        tool: str,
        params: Dict[str, Any],
        on_success: str,
        on_failure: str,
        **kwargs
    ) -> "FlowBuilder":
        """Step que ejecuta tool y espera respuesta de handler MQTT.

        Args:
            step_id: ID del step
            tool: Nombre del tool a ejecutar
            params: Parámetros del tool
            on_success: Step siguiente si success
            on_failure: Step siguiente si failure
            **kwargs: Otros argumentos para FlowStep

        Returns:
            self para chaining
        """
        step = FlowStep(
            id=step_id,
            action=StepAction.TOOL_CALL_ASYNC,
            params={"tool": tool, "params": params},
            conditions=[
                {"condition": "success", "next_step": on_success},
                {"condition": "failure", "next_step": on_failure},
            ],
            **kwargs
        )
        self._steps.append(step)
        return self

    def add_condition(
        self,
        step_id: str,
        condition: str,
        then_step: str,
        else_step: str,
        **kwargs
    ) -> "FlowBuilder":
        """Step condicional basado en contexto enriquecido.

        Args:
            step_id: ID del step
            condition: Expresión de condición a evaluar
            then_step: Step si condición es True
            else_step: Step si condición es False
            **kwargs: Otros argumentos para FlowStep

        Returns:
            self para chaining
        """
        step = FlowStep(
            id=step_id,
            action=StepAction.CONDITION,
            params={"condition": condition},
            conditions=[
                {"condition": "true", "next_step": then_step},
                {"condition": "false", "next_step": else_step},
            ],
            **kwargs
        )
        self._steps.append(step)
        return self

    def build(self) -> FlowDefinition:
        """Build the FlowDefinition."""
        return FlowDefinition(
            name=self.name,
            description=self._description,
            slots=self._slots,
            steps=self._steps,
            entry_step=self._entry_step,
            allow_interruptions=self._allow_interruptions,
            auto_fill_slots=self._auto_fill_slots,
            max_retries=self._max_retries,
            triggered_by=self._triggered_by,
            trigger_when_missing=self._trigger_when_missing,
            allowed_digressions=self._allowed_digressions,
            tags=self._tags,
        )
