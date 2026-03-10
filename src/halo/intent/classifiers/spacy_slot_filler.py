"""spaCy-based slot filler - Tier 2.5 (template + slot filling).

Extracts fresh parameter values from new input using grammatical templates
learned from successful classifications.

This classifier acts as a "consensus mechanism":
- Template matching from embedding similarity
- Fresh value extraction using dependency parsing
- Validates or discards based on structural match
"""

from typing import Optional
from ..base import IntentClassifier, ClassificationResult
from ...nlp.provider import get_nlp
from ...nlp.slots import SlotExtractor
import logging

logger = logging.getLogger(__name__)


class SpaCySlotFiller(IntentClassifier):
    """Tier 2.5: Template + slot filling classifier.

    Uses spaCy dependency parsing to extract fresh parameter values
    from new input based on grammatical templates from cached examples.

    Latency: 5-10ms on CPU
    Tokens: 0 (no LLM call)
    """

    def __init__(self, confidence_boost: float = 0.05):
        super().__init__("spacy_slot_filler")
        self._confidence_boost = confidence_boost
        self._nlp = None

    def _get_nlp(self):
        """Lazy load spaCy model."""
        if self._nlp is None:
            try:
                self._nlp = get_nlp()
            except Exception as e:
                logger.warning(f"spaCy model not available: {e}, classifier disabled")
                return None
        return self._nlp

    def _do_classify(
        self, user_input: str, context: dict
    ) -> Optional[ClassificationResult]:
        """Extract fresh values using template + dependency parsing.

        Args:
            user_input: User's input
            context: Conversation context (contains _matched_example from EmbeddingClassifier)

        Returns:
            ClassificationResult with fresh params, or None
        """
        # Get previous classification result
        previous = context.get("_previous_classification")
        if not previous:
            return None  # Nothing to fill slots for

        # Get matched example with slots
        matched_example = context.get("_matched_example")
        if not matched_example or not matched_example.slots:
            logger.debug("No matched example or slots, passthrough")
            return previous  # No slots to fill, pass through

        # Get spaCy model
        nlp = self._get_nlp()
        if not nlp:
            return previous  # spaCy not available

        try:
            # Parse new input
            doc = nlp(user_input)

            # Extract fresh values for each slot
            fresh_params = previous.parameters.copy()
            slots_filled = 0

            for param_name, slot_info in matched_example.slots.items():
                fresh_value = SlotExtractor.find_slot_value(doc, slot_info)
                if fresh_value:
                    # Normalize value
                    fresh_value = self._normalize_value(fresh_value, param_name)
                    if fresh_value != fresh_params.get(param_name):
                        logger.debug(
                            f"Slot {param_name}: {fresh_params.get(param_name)} → {fresh_value}"
                        )
                        fresh_params[param_name] = fresh_value
                        slots_filled += 1

            # If params changed, return corrected result
            if fresh_params != previous.parameters:
                logger.info(
                    f"Filled {slots_filled} slots from template: {matched_example.text}"
                )
                return ClassificationResult(
                    tool_name=previous.tool_name,
                    parameters=fresh_params,  # FRESH VALUES
                    confidence=previous.confidence + self._confidence_boost,
                    classifier_used=self.name,
                    cached=False,  # Values are fresh, not cached
                )

            # No changes, confirm with small boost
            logger.debug("Slots confirmed, boosting confidence")
            return ClassificationResult(
                tool_name=previous.tool_name,
                parameters=previous.parameters,
                confidence=previous.confidence + (self._confidence_boost / 2),
                classifier_used=self.name,
                cached=previous.cached,
            )

        except Exception as e:
            logger.error(f"Slot filling error: {e}")
            return previous  # Fallback to previous result

    def _normalize_value(self, value: str, param_name: str) -> str | int | float:
        """Normalize extracted value based on parameter type.

        Args:
            value: Extracted token text
            param_name: Parameter name (to infer type)

        Returns:
            Normalized value
        """
        # Numeric parameters
        if param_name in ["temperature", "level", "position"]:
            try:
                # Try convert to number
                if "." in value:
                    return float(value)
                return int(value)
            except ValueError:
                pass

        # String parameters (lowercase for normalization)
        return value.lower()

    def confidence_threshold(self) -> float:
        """No threshold - always processes if previous result exists."""
        return 0.0
