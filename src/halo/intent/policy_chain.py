"""Policy-driven classifier chain - next generation.

Diferencias con ClassifierChain (legacy):
1. Cada classifier retorna Envelope con métricas
2. Policy decide qué hacer con cada resultado
3. Interceptors para observabilidad (side-effect puro)
4. Contexto se enriquece progresivamente
"""

import logging
import time
from typing import List, Optional

from .base import IntentClassifier, ClassificationResult
from .envelope import ClassificationEnvelope, Decision
from .interceptors import ChainInterceptor
from .policies import ChainPolicy, ThresholdPolicy

logger = logging.getLogger(__name__)


class PolicyDrivenChain:
    """Classifier chain con policy y interceptors.

    Filosofía:
    - Cada nodo produce, la cadena decide
    - Observabilidad como interceptor
    - Contexto se enriquece progresivamente
    """

    def __init__(
        self,
        classifiers: List[IntentClassifier],
        policy: Optional[ChainPolicy] = None,
    ):
        """
        Args:
            classifiers: Lista de classifiers en orden de prioridad
            policy: Policy para decidir qué hacer con resultados (default: ThresholdPolicy)
        """
        self.classifiers = classifiers
        self.policy = policy or ThresholdPolicy()
        self.interceptors: List[ChainInterceptor] = []

    def add_interceptor(self, interceptor: ChainInterceptor) -> None:
        """Agrega un interceptor a la cadena.

        Args:
            interceptor: Interceptor a agregar
        """
        self.interceptors.append(interceptor)

    def classify(
        self,
        user_input: str,
        context: Optional[dict] = None,
    ) -> ClassificationResult:
        """Clasifica usando la cadena con policy e interceptors.

        Args:
            user_input: Input del usuario
            context: Contexto opcional

        Returns:
            ClassificationResult (del envelope final)
        """
        if not self.classifiers:
            logger.warning("No classifiers in chain")
            return None

        running_context = (context or {}).copy()
        running_context["user_input"] = user_input

        envelopes = []

        for classifier in self.classifiers:
            # Classify usando el classifier
            envelope = self._classify_with_envelope(
                classifier,
                user_input,
                running_context,
            )
            envelopes.append(envelope)

            # Enriquecer contexto para siguiente stage
            running_context.update(envelope.enriched_context)

            # Interceptors observan (side-effect puro)
            for interceptor in self.interceptors:
                try:
                    interceptor.on_stage_complete(envelope, running_context)
                except Exception as e:
                    logger.error(f"Interceptor {interceptor.__class__.__name__} failed: {e}")

            # Policy decide
            decision = self.policy.evaluate(envelope, envelopes, running_context)

            logger.debug(
                f"{classifier.name}: {decision.action} "
                f"(confidence={envelope.confidence:.2f}, reason={decision.reason})"
            )

            if decision.action == "accept":
                logger.info(
                    f"Intent classified by {envelope.stage_name} "
                    f"(confidence={envelope.confidence:.2f})"
                )
                return envelope.result

            # "continue" → siguiente classifier

        # Ninguno fue aceptado, resolver final
        final_envelope = self.policy.resolve_final(envelopes, running_context)

        if final_envelope.result:
            logger.info(
                f"Intent resolved by policy from {final_envelope.stage_name} "
                f"(confidence={final_envelope.confidence:.2f})"
            )
        else:
            logger.warning(f"No classifier handled: {user_input}")

        return final_envelope.result

    def _classify_with_envelope(
        self,
        classifier: IntentClassifier,
        user_input: str,
        context: dict,
    ) -> ClassificationEnvelope:
        """Clasifica y wrappea el resultado en un envelope.

        Args:
            classifier: Classifier a ejecutar
            user_input: Input del usuario
            context: Contexto actual

        Returns:
            ClassificationEnvelope con métricas
        """
        start = time.perf_counter()

        # Clasificar usando el método legacy _do_classify
        result = classifier._do_classify(user_input, context)

        latency = (time.perf_counter() - start) * 1000

        # Determinar confidence
        if result:
            confidence = result.confidence
        else:
            confidence = 0.0

        # Crear envelope
        envelope = ClassificationEnvelope(
            result=result,
            stage_name=classifier.name,
            stage_type=classifier.__class__.__name__,
            confidence=confidence,
            confidence_breakdown=self._get_confidence_breakdown(classifier, result),
            latency_ms=latency,
            tokens_used=self._get_tokens_used(classifier),
            diagnostics=self._get_diagnostics(classifier, result, context),
            enriched_context=self._get_enriched_context(classifier, result, context),
        )

        return envelope

    def _get_confidence_breakdown(
        self,
        classifier: IntentClassifier,
        result: Optional[ClassificationResult],
    ) -> dict:
        """Extrae breakdown de confidence si está disponible."""
        # Por ahora simple, luego los classifiers pueden exponer esto
        if result:
            return {"overall": result.confidence}
        return {}

    def _get_tokens_used(self, classifier: IntentClassifier) -> int:
        """Extrae tokens usados si está disponible."""
        # LLMClassifier y GeminiClassifier pueden tener esto
        if hasattr(classifier, "last_tokens_used"):
            return classifier.last_tokens_used
        return 0

    def _get_diagnostics(
        self,
        classifier: IntentClassifier,
        result: Optional[ClassificationResult],
        context: dict,
    ) -> dict:
        """Extrae diagnósticos del classifier."""
        diagnostics = {}

        # EmbeddingClassifier puede tener matched_example
        if "_matched_example" in context:
            diagnostics["matched_example"] = context["_matched_example"]

        # SpaCySlotFiller puede tener slot info
        if hasattr(classifier, "last_slots"):
            diagnostics["slots"] = classifier.last_slots

        return diagnostics

    def _get_enriched_context(
        self,
        classifier: IntentClassifier,
        result: Optional[ClassificationResult],
        context: dict,
    ) -> dict:
        """Extrae contexto enriquecido para siguientes stages."""
        enriched = {}

        # EmbeddingClassifier setea matched_example
        if "_matched_example" in context:
            enriched["matched_example"] = context["_matched_example"]

        # SpaCySlotFiller setea previous_classification
        if "_previous_classification" in context:
            enriched["previous_classification"] = context["_previous_classification"]

        return enriched

    def get_chain_info(self) -> List[dict]:
        """Get information about classifiers in the chain.

        Returns:
            List of classifier info dicts
        """
        return [
            {
                "name": c.name,
                "type": c.__class__.__name__,
                "threshold": c.confidence_threshold(),
            }
            for c in self.classifiers
        ]
