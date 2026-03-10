"""Chain interceptors - observabilidad como ciudadano de primera clase.

Los interceptors NO modifican el flujo de la cadena, solo observan (side-effect puro).
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from ..storage import FileStore
from .envelope import ClassificationEnvelope


class ChainInterceptor(ABC):
    """Abstract base para interceptors de la cadena."""

    @abstractmethod
    def on_stage_complete(self, envelope: ClassificationEnvelope, context: dict) -> None:
        """Llamado cuando un stage completa.

        Args:
            envelope: Envelope producido por el classifier
            context: Contexto de la clasificación
        """
        pass


class TelemetryInterceptor(ChainInterceptor):
    """Exporta telemetría a logs (JSONL).

    Puede ser leído por:
    - tail -f /var/halo/logs/telemetry_*.jsonl
    - jq para análisis
    - Otros agentes monitoreando el store
    """

    def __init__(self, store: FileStore):
        self.store = store

    def on_stage_complete(self, envelope: ClassificationEnvelope, context: dict) -> None:
        """Log de telemetría."""
        self.store.append_log(
            "telemetry",
            {
                "ts": datetime.now().isoformat(),
                "stage": envelope.stage_name,
                "stage_type": envelope.stage_type,
                "confidence": envelope.confidence,
                "latency_ms": envelope.latency_ms,
                "tokens": envelope.tokens_used,
                "result_tool": envelope.result.tool_name if envelope.result else None,
                "diagnostics": envelope.diagnostics,
            },
        )


class LearningInterceptor(ChainInterceptor):
    """Alimenta el sistema de aprendizaje.

    Clasificaciones con alta confianza se guardan como candidatos
    para golden dataset.
    """

    def __init__(self, store: FileStore, confidence_threshold: float = 0.95):
        self.store = store
        self.confidence_threshold = confidence_threshold

    def on_stage_complete(self, envelope: ClassificationEnvelope, context: dict) -> None:
        """Guardar clasificaciones exitosas."""
        if envelope.result and envelope.confidence >= self.confidence_threshold:
            # Candidato para golden dataset
            key = f"{envelope.stage_name}_{datetime.now().timestamp()}"
            self.store.write(
                "learning/candidates",
                key,
                {
                    "ts": datetime.now().isoformat(),
                    "input": context.get("user_input", ""),
                    "result": {
                        "tool_name": envelope.result.tool_name,
                        "parameters": envelope.result.parameters,
                        "confidence": envelope.result.confidence,
                    },
                    "stage": envelope.stage_name,
                    "diagnostics": envelope.diagnostics,
                },
            )


class AlertInterceptor(ChainInterceptor):
    """Para Halo Care - detecta situaciones críticas.

    En casos críticos, puede tomar acciones inmediatas
    (notificar supervisor, escalar, etc.)
    """

    CRITICAL_TOOLS = ["fall_detected", "emergency", "no_response"]

    def __init__(self, store: FileStore):
        self.store = store

    def on_stage_complete(self, envelope: ClassificationEnvelope, context: dict) -> None:
        """Detectar situaciones críticas."""
        if envelope.result and envelope.result.tool_name in self.CRITICAL_TOOLS:
            # Log de alerta crítica
            self.store.append_log(
                "alerts",
                {
                    "ts": datetime.now().isoformat(),
                    "level": "critical",
                    "tool": envelope.result.tool_name,
                    "parameters": envelope.result.parameters,
                    "operator": context.get("operator_on_duty"),
                    "operator_fatigue": context.get("operator_fatigue", 0.0),
                },
            )

            # TODO: Notificar supervisor si operador no responde
            # self._notify_supervisor(envelope, context)


class ClassificationLogInterceptor(ChainInterceptor):
    """Log detallado de cada clasificación para análisis posterior."""

    def __init__(self, store: FileStore):
        self.store = store

    def on_stage_complete(self, envelope: ClassificationEnvelope, context: dict) -> None:
        """Log completo de la clasificación."""
        self.store.append_log(
            "classification",
            {
                "ts": datetime.now().isoformat(),
                "user_input": context.get("user_input", ""),
                "stage": envelope.stage_name,
                "stage_type": envelope.stage_type,
                "result": {
                    "tool_name": envelope.result.tool_name if envelope.result else None,
                    "parameters": envelope.result.parameters if envelope.result else {},
                    "confidence": envelope.confidence,
                    "cached": envelope.result.cached if envelope.result else False,
                },
                "confidence_breakdown": envelope.confidence_breakdown,
                "latency_ms": envelope.latency_ms,
                "tokens_used": envelope.tokens_used,
                "diagnostics": envelope.diagnostics,
            },
        )
