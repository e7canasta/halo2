"""Scenario Testing Types - Data structures para testing end-to-end.

Similar a ML datasets: ScenarioRun es como un training example,
RunHistory es el dataset completo.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime

from ..tracing import AgencyTrace, DecisionPoint


@dataclass
class ScenarioTurn:
    """Un turno en el scenario.

    Attributes:
        turn: Número de turno
        user_input: Input del usuario
        expectations: Dict con expectations a validar
    """

    turn: int
    user_input: str
    expectations: Dict[str, Any]


@dataclass
class Scenario:
    """Scenario de conversación completo.

    Attributes:
        name: Nombre del scenario
        description: Descripción
        category: Categoría (flows, context, learning, etc.)
        turns: Lista de turnos
    """

    name: str
    description: str
    category: str
    turns: List[ScenarioTurn]


@dataclass
class TurnResult:
    """Resultado de un turno del scenario.

    Attributes:
        turn_number: Número de turno
        user_input: Input del usuario
        response: Response completa del sistema
        agency_trace: Trace de agencia capturado
        expectations_met: Si cumplió expectations
        expectation_failures: Lista de expectations que fallaron
    """

    turn_number: int
    user_input: str
    response: Dict[str, Any]
    agency_trace: AgencyTrace
    expectations_met: bool
    expectation_failures: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa para JSON."""
        return {
            "turn_number": self.turn_number,
            "user_input": self.user_input,
            "expectations_met": self.expectations_met,
            "expectation_failures": self.expectation_failures,
            "agency_trace": self.agency_trace.to_dict() if self.agency_trace else None
        }


@dataclass
class ScenarioRun:
    """Corrida completa de un scenario.

    Como un training example en ML.

    Attributes:
        run_id: ID único de la corrida
        scenario_name: Nombre del scenario
        timestamp: Cuando se ejecutó
        turns: Resultados de cada turno
        passed: Si pasó todas las validaciones
        all_decisions: Todas las decisiones (flattened de todos los turnos)
    """

    run_id: str
    scenario_name: str
    timestamp: datetime
    turns: List[TurnResult]
    passed: bool
    all_decisions: List[DecisionPoint] = field(default_factory=list)

    def __post_init__(self):
        """Flatten decisions de todos los turnos."""
        if not self.all_decisions:
            self.all_decisions = []
            for turn in self.turns:
                if turn.agency_trace:
                    self.all_decisions.extend(turn.agency_trace.decisions)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa para JSON."""
        return {
            "run_id": self.run_id,
            "scenario_name": self.scenario_name,
            "timestamp": self.timestamp.isoformat(),
            "passed": self.passed,
            "total_turns": len(self.turns),
            "total_decisions": len(self.all_decisions),
            "turns": [t.to_dict() for t in self.turns]
        }


@dataclass
class RunHistory:
    """Dataset de corridas (como training set en ML).

    Esto es lo que Gemini evalúa para encontrar patterns.

    Attributes:
        runs: Lista de ScenarioRun
        total_decisions: Total de decisiones en el dataset
        decisions_by_agent: Count de decisiones por agente
    """

    runs: List[ScenarioRun]
    total_decisions: int = 0
    decisions_by_agent: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        """Calcula agregados."""
        self.total_decisions = sum(len(r.all_decisions) for r in self.runs)

        # Count por agente
        for run in self.runs:
            for decision in run.all_decisions:
                agent = decision.agent
                self.decisions_by_agent[agent] = self.decisions_by_agent.get(agent, 0) + 1

    def get_all_decisions(self) -> List[DecisionPoint]:
        """Flatten todas las decisiones del dataset.

        Returns:
            Lista con todas las decisiones
        """
        all_decisions = []
        for run in self.runs:
            all_decisions.extend(run.all_decisions)
        return all_decisions

    def get_decisions_by_type(self, decision_type: str) -> List[DecisionPoint]:
        """Filtra decisiones por tipo.

        Args:
            decision_type: Tipo de decisión (decided value)

        Returns:
            Lista de decisiones que coinciden
        """
        return [d for d in self.get_all_decisions() if d.decided == decision_type]

    def get_decisions_by_agent(self, agent: str) -> List[DecisionPoint]:
        """Filtra decisiones por agente.

        Args:
            agent: Nombre del agente

        Returns:
            Lista de decisiones de ese agente
        """
        return [d for d in self.get_all_decisions() if d.agent == agent]

    @property
    def pass_rate(self) -> float:
        """Calcula pass rate del dataset.

        Returns:
            Porcentaje de scenarios que pasaron (0-1)
        """
        if not self.runs:
            return 0.0
        return sum(1 for r in self.runs if r.passed) / len(self.runs)

    def to_evaluation_format(self) -> Dict[str, Any]:
        """Formatea para Gemini Evaluator.

        Returns:
            Dict con el formato que espera GeminiEvaluator
        """
        return {
            "total_runs": len(self.runs),
            "total_turns": sum(len(r.turns) for r in self.runs),
            "total_decisions": self.total_decisions,
            "pass_rate": self.pass_rate,
            "decisions_by_agent": self.decisions_by_agent,
            "runs": [r.to_dict() for r in self.runs]
        }
