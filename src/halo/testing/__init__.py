"""Scenario Testing Framework.

Framework para testing end-to-end con captura de agencia.
"""

from .scenario_types import (
    Scenario,
    ScenarioTurn,
    ScenarioRun,
    TurnResult,
    RunHistory
)
from .scenario_runner import ScenarioRunner
from .validators import ExpectationValidator

__all__ = [
    # Types
    "Scenario",
    "ScenarioTurn",
    "ScenarioRun",
    "TurnResult",
    "RunHistory",
    # Runner
    "ScenarioRunner",
    # Validators
    "ExpectationValidator",
]
