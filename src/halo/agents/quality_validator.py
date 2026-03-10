"""Quality Validator - Role 2 of Gemini Agent.

Validates classifications BEFORE adding them to the golden dataset to ensure
high-quality training data.

Philosophy: 100 perfect examples > 1000 noisy examples
"""

import json
import random
from dataclasses import dataclass
from typing import Optional

from ..intent.base import ClassificationResult


@dataclass
class ValidationResult:
    """Result from Gemini validation."""

    is_correct: bool
    issues: list[str]
    corrected: Optional[ClassificationResult] = None
    should_ask_user: bool = False
    clarification_question: Optional[str] = None


class QualityValidator:
    """Gemini validates classifications before adding to golden dataset.

    Validation strategy (selective, not all examples):
    1. Bootstrapping: first 100 examples (build solid foundation)
    2. Dubious confidence: 0.85 <= confidence < 0.95
    3. Hardware critical: light/climate/blinds with confidence < 0.95
    4. Spot check: 10% of synthetic examples
    """

    def __init__(self, gemini_classifier):
        """Initialize validator.

        Args:
            gemini_classifier: GeminiClassifier instance for validation
        """
        self.gemini = gemini_classifier
        self.validation_count = 0

    def should_validate(
        self,
        classification: ClassificationResult,
        dataset_size: int,
        is_synthetic: bool = False
    ) -> bool:
        """Decide if a classification should be validated.

        Args:
            classification: Classification to evaluate
            dataset_size: Current golden dataset size
            is_synthetic: True if this is a synthetic example

        Returns:
            True if Gemini validation is recommended
        """
        # 1. Bootstrapping: first 100 examples
        if dataset_size < 100:
            return True

        # 2. Dubious confidence zone (0.85-0.95)
        if 0.85 <= classification.confidence < 0.95:
            return True

        # 3. Hardware critical with less than perfect confidence
        if classification.tool_name in ["light_control", "climate_control", "blinds_control"]:
            if classification.confidence < 0.95:
                return True

        # 4. Spot check 10% of synthetic examples
        if is_synthetic and random.random() < 0.10:
            return True

        return False

    def validate(
        self,
        user_input: str,
        classification: ClassificationResult
    ) -> ValidationResult:
        """Validate a classification with Gemini.

        Args:
            user_input: Original user input
            classification: Classification to validate

        Returns:
            ValidationResult with validation outcome
        """
        self.validation_count += 1

        # Call Gemini to validate
        validation_response = self.gemini.validate_classification(
            user_input,
            classification
        )

        return self._parse_validation_result(validation_response, classification)

    def _parse_validation_result(
        self,
        response: dict,
        original: ClassificationResult
    ) -> ValidationResult:
        """Parse Gemini's validation response.

        Args:
            response: JSON response from Gemini
            original: Original classification

        Returns:
            ValidationResult
        """
        is_correct = response.get("is_correct", False)
        issues = response.get("issues", [])
        should_ask_user = response.get("should_ask_user", False)
        clarification = response.get("clarification_question")

        # If incorrect, parse corrected version
        corrected = None
        if not is_correct and "corrected" in response:
            corrected_data = response["corrected"]
            corrected = ClassificationResult(
                tool_name=corrected_data.get("tool", original.tool_name),
                parameters=corrected_data.get("parameters", original.parameters),
                confidence=corrected_data.get("confidence", 0.95),
                classifier_used="gemini_validator",
                cached=False
            )

        return ValidationResult(
            is_correct=is_correct,
            issues=issues,
            corrected=corrected,
            should_ask_user=should_ask_user,
            clarification_question=clarification
        )

    def detect_systematic_errors(
        self,
        recent_validations: list[ValidationResult]
    ) -> list[str]:
        """Detect patterns of repeated errors.

        Args:
            recent_validations: Recent validation results

        Returns:
            List of detected systematic error patterns
        """
        # Count common issues
        issue_counts = {}
        for validation in recent_validations:
            if not validation.is_correct:
                for issue in validation.issues:
                    issue_counts[issue] = issue_counts.get(issue, 0) + 1

        # Find systematic patterns (appearing 3+ times)
        systematic_errors = [
            f"{issue} (occurred {count} times)"
            for issue, count in issue_counts.items()
            if count >= 3
        ]

        return systematic_errors
