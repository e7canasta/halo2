"""Chain policies - deciden qué hacer con los envelopes.

La policy es responsable de:
1. Decidir si aceptar el resultado de un classifier
2. Decidir si continuar al siguiente
3. Resolver el resultado final si ninguno fue aceptado
"""

from abc import ABC, abstractmethod
from typing import Optional

from .envelope import ClassificationEnvelope, Decision


class ChainPolicy(ABC):
    """Abstract base para policies de la cadena."""

    @abstractmethod
    def evaluate(
        self,
        current: ClassificationEnvelope,
        history: list[ClassificationEnvelope],
        context: dict,
    ) -> Decision:
        """Evalúa el envelope actual y decide qué hacer.

        Args:
            current: Envelope del classifier actual
            history: Envelopes de classifiers anteriores
            context: Contexto de la clasificación

        Returns:
            Decision con action="accept" o "continue"
        """
        pass

    @abstractmethod
    def resolve_final(
        self,
        envelopes: list[ClassificationEnvelope],
        context: dict,
    ) -> ClassificationEnvelope:
        """Resuelve cuando ningún classifier fue aceptado.

        Args:
            envelopes: Todos los envelopes de la cadena
            context: Contexto de la clasificación

        Returns:
            El envelope final a retornar
        """
        pass


class ThresholdPolicy(ChainPolicy):
    """Policy simple: acepta si confidence >= threshold del dominio.

    Thresholds por tipo de tool (hardware crítico requiere mayor confianza).
    """

    THRESHOLDS = {
        "light_control": 0.95,
        "climate_control": 0.95,
        "blinds_control": 0.95,
        "home_status": 0.80,
        "conversation": 0.70,
    }

    DEFAULT_THRESHOLD = 0.80

    def evaluate(
        self,
        current: ClassificationEnvelope,
        history: list[ClassificationEnvelope],
        context: dict,
    ) -> Decision:
        """Acepta si confidence >= threshold."""
        if current.result is None:
            return Decision(
                action="continue",
                reason="No result produced",
            )

        threshold = self.THRESHOLDS.get(
            current.result.tool_name,
            self.DEFAULT_THRESHOLD,
        )

        # Ajustar por contexto (ej: operador fatigado → más conservador)
        if context.get("operator_fatigue", 0) > 0.7:
            threshold += 0.05
            reason_suffix = " (adjusted for operator fatigue)"
        else:
            reason_suffix = ""

        if current.confidence >= threshold:
            return Decision(
                action="accept",
                reason=f"Confidence {current.confidence:.2f} >= {threshold:.2f}{reason_suffix}",
                metadata={"threshold": threshold},
            )

        return Decision(
            action="continue",
            reason=f"Confidence {current.confidence:.2f} < {threshold:.2f}{reason_suffix}",
            metadata={"threshold": threshold},
        )

    def resolve_final(
        self,
        envelopes: list[ClassificationEnvelope],
        context: dict,
    ) -> ClassificationEnvelope:
        """Retorna el envelope con mayor confidence."""
        # Filtrar envelopes con resultado
        with_results = [e for e in envelopes if e.result is not None]

        if not with_results:
            # Ninguno produjo resultado, retornar el último
            return envelopes[-1]

        # Retornar el de mayor confidence
        return max(with_results, key=lambda e: e.confidence)


class CarePolicy(ThresholdPolicy):
    """Policy para Halo Care - considera fatiga del operador.

    Hereda de ThresholdPolicy pero ajusta basado en:
    - Nivel de alerta (calm, active, critical)
    - Saturación del operador
    """

    CRITICAL_THRESHOLD = 0.98

    def evaluate(
        self,
        current: ClassificationEnvelope,
        history: list[ClassificationEnvelope],
        context: dict,
    ) -> Decision:
        """Evalúa considerando fatiga y nivel de alerta."""

        # En situaciones críticas, requiere mayor confianza
        if context.get("alert_level") == "critical":
            if current.result and current.confidence < self.CRITICAL_THRESHOLD:
                return Decision(
                    action="continue",
                    reason=f"Critical alert requires {self.CRITICAL_THRESHOLD:.2f} confidence",
                    metadata={"alert_level": "critical"},
                )

        # Si operador está saturado, activar modo directivo
        if context.get("operator_saturation", False):
            # Activar modo directivo en el contexto
            context["care_mode"] = "directive"

            # En modo directivo, aceptar con threshold más bajo
            if current.result and current.confidence >= 0.75:
                return Decision(
                    action="accept",
                    reason="Directive mode - operator saturated",
                    metadata={"care_mode": "directive"},
                )

        # Delegar a ThresholdPolicy para comportamiento normal
        return super().evaluate(current, history, context)


class ConsensusPolicy(ChainPolicy):
    """Policy avanzada: requiere consenso de múltiples classifiers.

    Nunca acepta temprano - siempre corre todos los classifiers
    y luego decide por voting o ensemble.
    """

    def __init__(self, min_consensus: int = 2):
        """
        Args:
            min_consensus: Mínimo de classifiers que deben estar de acuerdo
        """
        self.min_consensus = min_consensus

    def evaluate(
        self,
        current: ClassificationEnvelope,
        history: list[ClassificationEnvelope],
        context: dict,
    ) -> Decision:
        """Nunca acepta temprano - siempre continúa."""
        return Decision(
            action="continue",
            reason="Consensus policy requires all classifiers",
        )

    def resolve_final(
        self,
        envelopes: list[ClassificationEnvelope],
        context: dict,
    ) -> ClassificationEnvelope:
        """Decide por voting de los resultados."""
        # Contar votos por tool_name
        votes = {}
        for envelope in envelopes:
            if envelope.result:
                tool = envelope.result.tool_name
                if tool not in votes:
                    votes[tool] = []
                votes[tool].append(envelope)

        # Verificar si hay consenso
        for tool, supporting_envelopes in votes.items():
            if len(supporting_envelopes) >= self.min_consensus:
                # Hay consenso, retornar el envelope con mayor confidence
                return max(supporting_envelopes, key=lambda e: e.confidence)

        # No hay consenso, retornar el de mayor confidence
        with_results = [e for e in envelopes if e.result is not None]
        if with_results:
            return max(with_results, key=lambda e: e.confidence)

        return envelopes[-1]
