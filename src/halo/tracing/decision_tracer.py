"""Decision Tracer - Captura la agencia del sistema (no performance).

Filosofía: Entender POR QUÉ el sistema decidió hacer X, no cuánto tardó.

Inspirado en:
- n8n execution traces (workflow visibility)
- Rasa CALM decision tracking
- Temporal.io workflow history
"""

import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class DecisionPoint:
    """Un punto de decisión del sistema.

    Representa una pregunta que el sistema tuvo que responder
    y cómo llegó a la decisión.

    Attributes:
        agent: Quién decidió (ClassifierChain, FlowEngine, ProcessEngine, etc.)
        question: Qué pregunta estaba respondiendo
        context_used: Contexto usado para tomar la decisión
        options_considered: Lista de opciones evaluadas
        decided: Decisión final tomada
        why: Explicación humana de por qué tomó esta decisión
        alternative_paths: Qué más pudo haber hecho pero no lo hizo
    """

    agent: str
    question: str
    context_used: Dict[str, Any] = field(default_factory=dict)
    options_considered: List[Dict[str, Any]] = field(default_factory=list)
    decided: str = ""
    why: str = ""
    alternative_paths: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa para JSON."""
        return {
            "agent": self.agent,
            "question": self.question,
            "context_used": self.context_used,
            "options_considered": self.options_considered,
            "decided": self.decided,
            "why": self.why,
            "alternative_paths": self.alternative_paths
        }


@dataclass
class AgencyTrace:
    """Trace completo de la agencia del sistema.

    No mide performance - explica decisiones.

    Attributes:
        trace_id: ID único del trace
        user_input: Input original del usuario
        final_result: Resultado final devuelto
        decisions: Chain of decisions tomadas
        narrative: Narrativa humana auto-generada
    """

    trace_id: str
    user_input: str
    final_result: str
    decisions: List[DecisionPoint]
    narrative: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serializa para JSON response."""
        return {
            "trace_id": self.trace_id,
            "user_input": self.user_input,
            "final_result": self.final_result,
            "decision_chain": [d.to_dict() for d in self.decisions],
            "narrative": self.narrative
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgencyTrace":
        """Deserializa desde JSON."""
        decisions = []
        for d_data in data.get("decision_chain", []):
            decision = DecisionPoint(
                agent=d_data["agent"],
                question=d_data["question"],
                context_used=d_data.get("context_used", {}),
                options_considered=d_data.get("options_considered", []),
                decided=d_data.get("decided", ""),
                why=d_data.get("why", ""),
                alternative_paths=d_data.get("alternative_paths", [])
            )
            decisions.append(decision)

        return cls(
            trace_id=data.get("trace_id", ""),
            user_input=data.get("user_input", ""),
            final_result=data.get("final_result", ""),
            decisions=decisions,
            narrative=data.get("narrative", "")
        )


class DecisionTracer:
    """Tracer de decisiones del sistema (no performance).

    Captura la agencia: qué decidió y por qué.

    Uso:
        tracer = DecisionTracer(user_input="configura escena nocturno")

        # Decisión del classifier
        tracer.decision_point(
            agent="ClassifierChain",
            question="¿Qué intent tiene el usuario?",
            context={"history": [], "embeddings": {...}},
            options=[
                {"tool": "scene_control", "confidence": 0.92, "why": "Match semántico"},
                {"tool": "light_control", "confidence": 0.45, "why": "Palabra luz"},
            ],
            decided="scene_control",
            why="Mayor similitud con template scene"
        )

        trace = tracer.finish(final_result="¿En qué habitaciones?")
    """

    def __init__(self, user_input: str):
        """Inicializa tracer.

        Args:
            user_input: Input del usuario a trazar
        """
        self.trace_id = str(uuid.uuid4())
        self.user_input = user_input
        self.decisions: List[DecisionPoint] = []
        self.final_result = ""

    def decision_point(
        self,
        agent: str,
        question: str,
        context: Dict[str, Any],
        options: List[Dict[str, Any]],
        decided: str,
        why: str
    ) -> "DecisionTracer":
        """Registra un punto de decisión.

        Args:
            agent: Nombre del agente que decidió
            question: Pregunta que estaba respondiendo
            context: Contexto usado para decidir
            options: Opciones consideradas
            decided: Decisión tomada
            why: Por qué tomó esta decisión

        Returns:
            self para chaining
        """
        # Extraer alternative paths de las opciones
        alternatives = []
        for opt in options:
            opt_value = opt.get("option") or opt.get("tool") or opt.get("action") or opt.get("decided")
            if opt_value and opt_value != decided:
                alternatives.append(str(opt_value))

        decision = DecisionPoint(
            agent=agent,
            question=question,
            context_used=context,
            options_considered=options,
            decided=decided,
            why=why,
            alternative_paths=alternatives
        )

        self.decisions.append(decision)
        return self

    def finish(self, final_result: str) -> AgencyTrace:
        """Finaliza trace y genera narrativa.

        Args:
            final_result: Resultado final del sistema

        Returns:
            AgencyTrace completo con narrativa
        """
        self.final_result = final_result
        narrative = self._generate_narrative()

        return AgencyTrace(
            trace_id=self.trace_id,
            user_input=self.user_input,
            final_result=final_result,
            decisions=self.decisions,
            narrative=narrative
        )

    def _generate_narrative(self) -> str:
        """Genera narrativa humana de las decisiones.

        Returns:
            String con narrativa legible
        """
        if not self.decisions:
            return f"Sin decisiones registradas para '{self.user_input}'"

        parts = [f"Para '{self.user_input}':"]

        for i, decision in enumerate(self.decisions, 1):
            parts.append(
                f"{i}. {decision.agent} decidió '{decision.decided}' "
                f"porque {decision.why}"
            )

            if decision.alternative_paths:
                parts.append(
                    f"   (consideró: {', '.join(decision.alternative_paths)})"
                )

        parts.append(f"Resultado: {self.final_result}")

        return "\n".join(parts)
