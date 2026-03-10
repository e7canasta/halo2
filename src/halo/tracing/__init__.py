"""Decision Tracing - Captura agencia del sistema.

Módulo para trazar decisiones y entender por qué el sistema
decidió hacer X (no cuánto tardó).
"""

from .decision_tracer import DecisionTracer, DecisionPoint, AgencyTrace

__all__ = [
    "DecisionTracer",
    "DecisionPoint",
    "AgencyTrace",
]
