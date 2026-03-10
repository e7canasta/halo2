"""Context Levels - 5 niveles de contexto para Halo.

Inspirado en Claude Code:
- Nivel 5: El Alma (manifest, personality, relationships)
- Nivel 4: Ambiente (current_state, shift_context)
- Nivel 3: Sesión (interacción actual)
- Nivel 2: Flujo (tarea en curso)
- Nivel 1: Comando (este input)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..storage import FileStore


@dataclass
class CommandContext:
    """Nivel 1: El Comando - este input específico."""

    user_input: str
    timestamp: datetime = field(default_factory=datetime.now)
    parameters: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


@dataclass
class FlowContext:
    """Nivel 2: El Flujo - tarea multi-paso en curso."""

    flow_id: str
    flow_type: str
    status: str  # "active", "completed", "failed"
    steps: list = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    current_step: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class SessionContext:
    """Nivel 3: La Sesión - interacción actual."""

    session_id: str
    user_or_operator: str
    start_time: datetime
    status: str = "active"
    interaction_count: int = 0
    conversation_history: list = field(default_factory=list)
    context_carryover: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


@dataclass
class EnvironmentContext:
    """Nivel 4: Ambiente - qué está pasando ahora.

    Para Home: estado de dispositivos, ocupancy
    Para Care: estado de residentes, fatiga de operador
    """

    timestamp: datetime
    time_of_day: str  # "morning", "afternoon", "night", "deep_night"
    current_state: dict = field(default_factory=dict)

    # Para Care
    operator_on_duty: Optional[str] = None
    operator_fatigue: float = 0.0  # 0.0 - 1.0
    operator_saturation: bool = False
    alert_level: str = "calm"  # "calm", "active", "critical"
    shift_context: Optional[dict] = None

    # Para Home
    home_mode: str = "active"  # "active", "away", "sleep"
    occupancy: dict = field(default_factory=dict)

    # Contexto conversacional
    last_room_mentioned: Optional[str] = None
    last_device_interacted: Optional[str] = None
    last_action: Optional[str] = None


@dataclass
class SoulContext:
    """Nivel 5: El Alma - quién es este Halo.

    El alma es persistente y evoluciona lentamente con el tiempo.
    """

    manifest: str  # Contenido del manifest.md
    personality: dict  # Voz, tono, límites
    relationships: dict[str, dict] = field(default_factory=dict)  # Conocimiento de usuarios/operadores
    learned_preferences: dict = field(default_factory=dict)  # Evoluciona con el tiempo
    trust_score: float = 0.0
    days_active: int = 0


@dataclass
class HaloContext:
    """Contexto completo de Halo - 5 niveles.

    Esta es la view completa del estado de Halo en un momento dado.
    """

    # Nivel 5: El Alma (persistente, evoluciona lentamente)
    soul: SoulContext

    # Nivel 4: Ambiente (estado actual del mundo)
    environment: EnvironmentContext

    # Nivel 3: Sesión (interacción actual)
    session: SessionContext

    # Nivel 2: Flujo (tarea en curso) - opcional
    flow: Optional[FlowContext] = None

    # Nivel 1: Comando (este input) - opcional
    command: Optional[CommandContext] = None

    def to_dict(self) -> dict:
        """Convierte el contexto completo a dict para pasar a classifiers."""
        return {
            # Soul
            "manifest": self.soul.manifest,
            "personality": self.soul.personality,
            "relationships": self.soul.relationships,
            # Environment
            "time_of_day": self.environment.time_of_day,
            "current_state": self.environment.current_state,
            "operator_on_duty": self.environment.operator_on_duty,
            "operator_fatigue": self.environment.operator_fatigue,
            "operator_saturation": self.environment.operator_saturation,
            "alert_level": self.environment.alert_level,
            "home_mode": self.environment.home_mode,
            "last_room_mentioned": self.environment.last_room_mentioned,
            "last_device_interacted": self.environment.last_device_interacted,
            "last_action": self.environment.last_action,
            # Session
            "session_id": self.session.session_id,
            "user_or_operator": self.session.user_or_operator,
            "interaction_count": self.session.interaction_count,
            "conversation_history": self.session.conversation_history,
            # Flow (si existe)
            "flow_id": self.flow.flow_id if self.flow else None,
            "flow_status": self.flow.status if self.flow else None,
            # Command (si existe)
            "user_input": self.command.user_input if self.command else None,
        }


class ContextLoader:
    """Carga contexto desde el FileStore.

    Permite cargar selectivamente niveles de contexto según sea necesario.
    """

    def __init__(self, store: FileStore):
        self.store = store

    def load_soul(self) -> SoulContext:
        """Carga el contexto del alma (manifest + personality + relationships)."""
        manifest = self.store.read_manifest()

        personality = self.store.read("soul", "personality") or {}

        # Cargar relaciones
        relationships = {}
        for rel_id in self.store.list_keys("soul/relationships"):
            rel_data = self.store.read("soul/relationships", rel_id)
            if rel_data:
                relationships[rel_id] = rel_data

        # Preferencias aprendidas (si existen)
        learned = self.store.read("soul", "learned_preferences") or {}

        return SoulContext(
            manifest=manifest,
            personality=personality,
            relationships=relationships,
            learned_preferences=learned.get("preferences", {}),
            trust_score=learned.get("trust_score", 0.0),
            days_active=learned.get("days_active", 0),
        )

    def load_environment(self) -> EnvironmentContext:
        """Carga el contexto ambiental (current_state + shift_context si existe)."""
        state = self.store.read("environment", "current_state") or {}
        shift = self.store.read("environment", "shift_context")

        return EnvironmentContext(
            timestamp=datetime.fromisoformat(state.get("timestamp", datetime.now().isoformat())),
            time_of_day=state.get("time_of_day", "day"),
            current_state=state.get("devices", state.get("floor_state", {})),
            # Care-specific
            operator_on_duty=state.get("shift_context", {}).get("operator_on_duty") if shift is None else shift.get("operator", {}).get("id"),
            operator_fatigue=state.get("shift_context", {}).get("operator_fatigue", 0.0),
            operator_saturation=state.get("shift_context", {}).get("operator_saturation", False),
            alert_level=state.get("alert_level", "calm"),
            shift_context=shift,
            # Home-specific
            home_mode=state.get("home_mode", "active"),
            occupancy=state.get("occupancy", {}),
            # Context carryover
            last_room_mentioned=state.get("context", {}).get("last_room_mentioned"),
            last_device_interacted=state.get("context", {}).get("last_device_interacted"),
            last_action=state.get("context", {}).get("last_action"),
        )

    def load_session(self, session_id: str) -> Optional[SessionContext]:
        """Carga un sesión específica."""
        session_data = self.store.read("sessions", session_id)
        if not session_data:
            return None

        return SessionContext(
            session_id=session_data["session_id"],
            user_or_operator=session_data.get("user") or session_data.get("operator"),
            start_time=datetime.fromisoformat(session_data["start_time"]),
            status=session_data.get("status", "active"),
            interaction_count=session_data.get("interaction_count", 0),
            conversation_history=session_data.get("context", {}).get("conversation_history", []),
            context_carryover=session_data.get("context_carryover", {}),
            metadata=session_data.get("session_metadata", {}),
        )

    def load_active_flow(self) -> Optional[FlowContext]:
        """Carga el primer flujo activo encontrado."""
        active_flows = self.store.list_keys("flows/active")
        if not active_flows:
            return None

        # Tomar el primer flujo activo
        flow_data = self.store.read("flows/active", active_flows[0])
        if not flow_data:
            return None

        return FlowContext(
            flow_id=flow_data["flow_id"],
            flow_type=flow_data.get("flow_type", "unknown"),
            status=flow_data.get("status", "active"),
            steps=flow_data.get("steps", []),
            started_at=datetime.fromisoformat(flow_data.get("started_at", datetime.now().isoformat())),
            current_step=flow_data.get("current_step", 0),
            metadata=flow_data.get("metadata", {}),
        )

    def load_full_context(self, session_id: Optional[str] = None) -> HaloContext:
        """Carga el contexto completo de Halo.

        Args:
            session_id: ID de sesión específica (opcional)

        Returns:
            HaloContext con todos los niveles cargados
        """
        soul = self.load_soul()
        environment = self.load_environment()

        # Session - si no se especifica, crear una nueva
        if session_id:
            session = self.load_session(session_id)
        else:
            session = SessionContext(
                session_id=f"session_{datetime.now().timestamp()}",
                user_or_operator="unknown",
                start_time=datetime.now(),
            )

        # Flow - si existe uno activo
        flow = self.load_active_flow()

        return HaloContext(
            soul=soul,
            environment=environment,
            session=session,
            flow=flow,
        )
