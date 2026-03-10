"""Gemini Agent - Orchestrator of 3 autonomous roles.

Unifies the 3 roles of Gemini:
1. Fallback Classifier - final decision maker
2. Quality Validator - validates before golden dataset
3. Template Master - improves templates with agency

Philosophy: "Nada es más costoso que fallarle al usuario"
"""

import logging
from typing import Optional

from ..intent.base import ClassificationResult
from ..intent.classifiers.gemini import GeminiClassifier
from .quality_validator import QualityValidator, ValidationResult
from .template_master import TemplateMaster, TemplateImprovement
from .model_config import ModelConfig

logger = logging.getLogger(__name__)


class GeminiAgent:
    """Orchestrator of Gemini's 3 roles.

    This agent coordinates:
    - Role 1: Fallback classification (when all other classifiers fail)
    - Role 2: Quality validation (before adding to golden dataset)
    - Role 3: Template improvement (grammar, variations, slots)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_config: Optional[ModelConfig] = None
    ):
        """Initialize Gemini agent.

        Args:
            api_key: Gemini API key (or None to use GEMINI_API_KEY env var)
            model_config: Model configuration (or None to load from env vars)
        """
        # Load model configuration from environment if not provided
        if model_config is None:
            model_config = ModelConfig.from_env()

        self.model_config = model_config

        # Initialize Gemini classifier with role-specific models
        self.gemini = GeminiClassifier(
            api_key=api_key,
            model=model_config.fallback_model,
            validator_model=model_config.validator_model,
            template_model=model_config.template_model,
        )

        # Initialize role-specific components
        self.validator = QualityValidator(self.gemini)
        self.template_master = TemplateMaster(self.gemini)

        # Track usage statistics per role
        self.role_stats = {
            "fallback": 0,
            "validator": 0,
            "template_master": 0,
        }

        logger.info(
            f"GeminiAgent initialized with 3 roles\n{model_config}"
        )

    # ===== ROLE 1: Fallback Classifier =====

    def classify_fallback(
        self,
        user_input: str,
        context: dict = None
    ) -> Optional[ClassificationResult]:
        """Classify using Gemini as fallback (Role 1).

        This is called when ALL other classifiers fail.

        Args:
            user_input: User's natural language input
            context: Optional conversation context

        Returns:
            ClassificationResult or None if Gemini fails
        """
        self.role_stats["fallback"] += 1
        logger.info(f"Gemini Role 1 (Fallback): classifying '{user_input}'")

        result = self.gemini._do_classify(user_input, context or {})

        if result:
            logger.info(
                f"Gemini classified as {result.tool_name} "
                f"with confidence {result.confidence:.2f}"
            )

        return result

    # ===== ROLE 2: Quality Validator =====

    def validate_classification(
        self,
        user_input: str,
        classification: ClassificationResult,
        dataset_size: int = 0,
        is_synthetic: bool = False
    ) -> Optional[ValidationResult]:
        """Validate a classification before learning (Role 2).

        This ensures high-quality data in the golden dataset.

        Args:
            user_input: Original user input
            classification: Classification to validate
            dataset_size: Current golden dataset size
            is_synthetic: True if this is a synthetic example

        Returns:
            ValidationResult if validation is needed, None otherwise
        """
        # Check if validation is needed
        if not self.validator.should_validate(classification, dataset_size, is_synthetic):
            return None

        self.role_stats["validator"] += 1
        logger.info(
            f"Gemini Role 2 (Validator): validating '{user_input}' "
            f"(confidence: {classification.confidence:.2f})"
        )

        validation = self.validator.validate(user_input, classification)

        if not validation.is_correct:
            logger.warning(
                f"Gemini found issues: {', '.join(validation.issues)}"
            )

        return validation

    # ===== ROLE 3: Template Master =====

    def improve_template(
        self,
        template: str,
        slots: dict,
        real_examples: list[str]
    ) -> TemplateImprovement:
        """Improve a template with Gemini's agency (Role 3).

        Gemini actively corrects grammar and suggests variations.

        Args:
            template: Template string
            slots: Slot definitions
            real_examples: Real user inputs

        Returns:
            TemplateImprovement with corrections and suggestions
        """
        self.role_stats["template_master"] += 1
        logger.info(f"Gemini Role 3 (Template Master): improving '{template}'")

        improvement = self.template_master.improve_template(
            template,
            slots,
            real_examples
        )

        if improvement.issues:
            logger.info(
                f"Gemini found template issues: {', '.join(improvement.issues)}"
            )
            logger.info(
                f"Corrected to: '{improvement.corrected_template}'"
            )

        return improvement

    # ===== Statistics =====

    def get_stats(self) -> dict:
        """Get usage statistics per role.

        Returns:
            dict with counts and percentages per role
        """
        total = sum(self.role_stats.values())

        if total == 0:
            return {
                role: {"count": 0, "percentage": 0.0}
                for role in self.role_stats
            }

        return {
            role: {
                "count": count,
                "percentage": (count / total * 100) if total > 0 else 0.0
            }
            for role, count in self.role_stats.items()
        }

    def reset_stats(self):
        """Reset usage statistics."""
        self.role_stats = {role: 0 for role in self.role_stats}
        logger.info("GeminiAgent stats reset")
