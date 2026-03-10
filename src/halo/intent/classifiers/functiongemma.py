"""
FunctionGemma-based intent classifier.

Uses fine-tuned FunctionGemma 270M for fast, accurate function calling.
"""

import logging
from typing import Optional

from halo.backend.functiongemma import FunctionGemmaBackend
from halo.intent.base import ClassificationResult, IntentClassifier

logger = logging.getLogger(__name__)


class FunctionGemmaClassifier(IntentClassifier):
    """
    Classifier using FunctionGemma 270M.

    Advantages over Qwen:
    - 3x smaller (270M vs 800M params)
    - 6x less RAM (~500MB vs 3GB)
    - 15-30x faster (200-500ms vs 7s)
    - Specialized for function calling
    """

    def __init__(
        self,
        backend: Optional[FunctionGemmaBackend] = None,
        model_path: str = "google/functiongemma-270m-it",
    ):
        """
        Initialize FunctionGemma classifier.

        Args:
            backend: Pre-initialized FunctionGemmaBackend (or None to create)
            model_path: Path to fine-tuned model (or HF model ID)
        """
        super().__init__("functiongemma")
        self.backend = backend
        self.model_path = model_path

        if self.backend is None:
            logger.info(f"Creating FunctionGemmaBackend with model: {model_path}")
            self.backend = FunctionGemmaBackend(model_name=model_path)
            self.backend.initialize()

    @property
    def confidence_threshold(self) -> float:
        """
        Confidence threshold for FunctionGemma.

        Lower than Qwen (0.90) because FunctionGemma is fine-tuned
        for this specific task.
        """
        return 0.80

    def _do_classify(
        self, user_input: str, context: dict
    ) -> Optional[ClassificationResult]:
        """
        Classify using FunctionGemma.

        Args:
            user_input: Natural language command
            context: Conversation context (unused for now)

        Returns:
            ClassificationResult or None if no valid function call
        """
        try:
            # Generate with FunctionGemma
            output = self.backend.generate(user_input, max_new_tokens=128)

            # Parse function call
            tool_name, params = self.backend.parse_function_call(output)

            if tool_name is None:
                logger.debug(f"No function call found in output: {output[:100]}")
                return None

            # FunctionGemma confidence
            # If it generates a function call, we trust it (high confidence)
            # This could be enhanced with probability scores from logits
            confidence = 0.85

            return ClassificationResult(
                tool_name=tool_name,
                parameters=params,
                confidence=confidence,
                classifier_used=self.name,
                cached=False,
            )

        except Exception as e:
            logger.error(f"FunctionGemma classification failed: {e}", exc_info=True)
            return None
