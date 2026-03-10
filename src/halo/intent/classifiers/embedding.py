"""Embedding-based classifier - Tier 2 (fast, 0 LLM tokens)."""

from typing import Optional, List
import numpy as np
from ..base import IntentClassifier, ClassificationResult
from ..embeddings import get_embedding_model
import logging

logger = logging.getLogger(__name__)


class IntentExample:
    """Cached intent example with embedding and slots.

    Slots store grammatical positions of parameters for template matching.
    """

    def __init__(
        self,
        text: str,
        tool_name: str,
        parameters: dict,
        embedding: np.ndarray = None,
        slots: dict = None,
    ):
        self.text = text
        self.tool_name = tool_name
        self.parameters = parameters
        self.embedding = embedding
        self.slots = slots or {}  # Dict[param_name, SlotInfo]


class EmbeddingClassifier(IntentClassifier):
    """Tier 2: Embedding similarity classifier.

    Uses sentence-transformers for semantic similarity.
    Latency: 5-10ms on CPU
    Tokens: 0 (no LLM call)
    """

    def __init__(self, similarity_threshold: float = 0.85):
        super().__init__("embedding")
        self._similarity_threshold = similarity_threshold
        self._examples: List[IntentExample] = []
        self._embedding_model = None

    def _get_model(self):
        """Lazy load embedding model."""
        if self._embedding_model is None:
            try:
                self._embedding_model = get_embedding_model()
            except ImportError:
                logger.warning("Embedding model not available, classifier disabled")
                return None
        return self._embedding_model

    def _do_classify(self, user_input: str, context: dict) -> Optional[ClassificationResult]:
        """Try semantic similarity matching.

        Args:
            user_input: User's input
            context: Conversation context

        Returns:
            ClassificationResult if similar example found, None otherwise
        """
        model = self._get_model()
        if not model or not self._examples:
            return None

        try:
            # Encode input
            input_embedding = model.encode(user_input)

            # Find most similar example
            best_match = None
            best_similarity = 0.0

            for example in self._examples:
                if example.embedding is None:
                    # Compute embedding on first use
                    example.embedding = model.encode(example.text)

                similarity = model.cosine_similarity(input_embedding, example.embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = example

            # Check if best match exceeds threshold
            if best_match and best_similarity >= self._similarity_threshold:
                # Store matched example in context for SpaCySlotFiller
                context["_matched_example"] = best_match

                return ClassificationResult(
                    tool_name=best_match.tool_name,
                    parameters=best_match.parameters,
                    confidence=float(best_similarity),
                    classifier_used=self.name,
                    cached=True,
                )

        except Exception as e:
            logger.error(f"Embedding classification error: {e}")

        return None

    def confidence_threshold(self) -> float:
        """Similarity threshold for embedding matching."""
        return self._similarity_threshold

    def learn(self, text: str, tool_name: str, parameters: dict, slots: dict = None):
        """Learn a new example with optional slots.

        Args:
            text: User input text
            tool_name: Tool that was called
            parameters: Parameters used
            slots: Optional slot information (param_name -> SlotInfo)
        """
        example = IntentExample(text, tool_name, parameters, slots=slots)
        self._examples.append(example)
        logger.info(f"Learned new example: {text} -> {tool_name} (slots={bool(slots)})")

    def get_examples_count(self) -> int:
        """Get number of learned examples."""
        return len(self._examples)
