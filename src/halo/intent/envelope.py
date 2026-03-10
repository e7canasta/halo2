"""Classification envelope - SOAP-inspired result wrapper.

Cada nodo produce métricas, la cadena decide.
"""

from dataclasses import dataclass, field
from typing import Optional

from .base import ClassificationResult


@dataclass
class ClassificationEnvelope:
    """Resultado enriquecido de un classifier - inspirado en SOAP envelope.

    Philosophy: El nodo NO decide si "pasó" o "falló", solo expone su trabajo
    con métricas de confianza. La cadena y la policy deciden qué hacer.
    """

    # Payload - puede ser None si el classifier no produjo resultado
    result: Optional[ClassificationResult]

    # Identidad del stage
    stage_name: str
    stage_type: str  # "exact_match", "embedding", "llm", "gemini", etc.

    # Métricas de confianza (el nodo las expone, la cadena decide)
    confidence: float  # 0.0 - 1.0
    confidence_breakdown: dict = field(default_factory=dict)  # {"semantic": 0.85, "syntactic": 0.72}

    # Métricas de performance (para observabilidad)
    latency_ms: float = 0.0
    tokens_used: int = 0

    # Diagnóstico (opcional, para debugging)
    diagnostics: dict = field(default_factory=dict)  # {"matched_pattern": "...", "distance": 0.12}

    # Contexto enriquecido para siguientes stages
    enriched_context: dict = field(default_factory=dict)  # {"matched_example": ..., "slots": ...}

    def __str__(self) -> str:
        """Human-readable representation."""
        result_str = f"{self.result.tool_name}" if self.result else "None"
        return (
            f"Envelope({self.stage_name}: {result_str}, "
            f"confidence={self.confidence:.2f}, "
            f"latency={self.latency_ms:.1f}ms)"
        )


@dataclass
class Decision:
    """Decision tomada por la policy sobre un envelope."""

    action: str  # "accept", "continue", "aggregate"
    reason: Optional[str] = None  # Explicación de la decisión
    metadata: dict = field(default_factory=dict)  # Metadata adicional
