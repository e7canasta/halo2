"""Confidence policy for hardware actions.

Philosophy: QUALITY > SPEED
"Nada es más costoso que fallarle al usuario"

For hardware actions (lights, climate, blinds), we require higher confidence
or ask the user for clarification rather than execute incorrectly.
"""

from dataclasses import dataclass
from typing import Optional

from .base import ClassificationResult


@dataclass
class ExecutionDecision:
    """Decision about whether to execute a classification result."""

    execute: bool = False
    require_validation: bool = False
    ask_user: bool = False
    reason: str = ""


class ConfidencePolicy:
    """Policy for confidence thresholds based on tool type.

    Hardware-critical tools require higher confidence (0.95) to prevent
    incorrect actions (wrong light, wrong temperature, etc.).

    Query tools can be more permissive (0.80) since they don't change state.
    """

    # Thresholds by tool type
    THRESHOLDS = {
        # Hardware crítico: SER CONSERVADOR
        "light_control": 0.95,
        "climate_control": 0.95,
        "blinds_control": 0.95,

        # Consultas: más permisivo
        "home_status": 0.80,
        "conversation": 0.70,
    }

    # Default threshold for unknown tools
    DEFAULT_THRESHOLD = 0.90

    # Validation zone: if confidence is in this range, validate with Gemini
    VALIDATION_BUFFER = 0.10  # e.g., 0.85-0.95 for hardware tools

    def get_threshold(self, tool_name: str) -> float:
        """Get confidence threshold for a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Minimum confidence threshold (0.0-1.0)
        """
        return self.THRESHOLDS.get(tool_name, self.DEFAULT_THRESHOLD)

    def should_execute(self, classification: ClassificationResult) -> ExecutionDecision:
        """Decide whether to execute a classification result.

        Args:
            classification: Classification result to evaluate

        Returns:
            ExecutionDecision with execute/validate/ask flags
        """
        threshold = self.get_threshold(classification.tool_name)
        confidence = classification.confidence

        # High confidence → execute immediately
        if confidence >= threshold:
            return ExecutionDecision(
                execute=True,
                reason=f"Confidence {confidence:.2f} >= threshold {threshold:.2f}"
            )

        # Medium confidence (in validation buffer) → validate with Gemini
        if confidence >= threshold - self.VALIDATION_BUFFER:
            return ExecutionDecision(
                require_validation=True,
                reason=f"Confidence {confidence:.2f} in validation zone [{threshold - self.VALIDATION_BUFFER:.2f}, {threshold:.2f})"
            )

        # Low confidence → ask user for clarification
        return ExecutionDecision(
            ask_user=True,
            reason=f"Confidence {confidence:.2f} < validation threshold {threshold - self.VALIDATION_BUFFER:.2f}"
        )

    def should_validate_with_gemini(
        self,
        classification: ClassificationResult,
        dataset_size: int = 0
    ) -> bool:
        """Decide if a classification should be validated with Gemini before learning.

        Validation is triggered for:
        1. Bootstrapping: first 100 examples (build solid foundation)
        2. Dubious confidence: 0.85 <= confidence < 0.95
        3. Hardware critical tools with confidence < 0.95

        Args:
            classification: Classification result to evaluate
            dataset_size: Current size of golden dataset

        Returns:
            True if Gemini validation is recommended
        """
        # 1. Bootstrapping: first 100 examples
        if dataset_size < 100:
            return True

        threshold = self.get_threshold(classification.tool_name)
        confidence = classification.confidence

        # 2. Dubious confidence in validation zone
        if threshold - self.VALIDATION_BUFFER <= confidence < threshold:
            return True

        # 3. Hardware critical with less than perfect confidence
        if classification.tool_name in ["light_control", "climate_control", "blinds_control"]:
            if confidence < 0.95:
                return True

        return False
