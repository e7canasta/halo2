"""Model configuration for Gemini Agent.

Supports flexible model configuration via environment variables:

1. Single model for all roles:
   GEMINI_MODEL=gemini-2.0-flash-exp

2. Different models per role (comma-separated):
   GEMINI_MODELS=fallback:gemini-2.0-flash-exp,validator:gemini-1.5-flash,template:gemini-1.5-pro

3. Specific role variables (highest priority):
   GEMINI_FALLBACK_MODEL=gemini-2.0-flash-exp
   GEMINI_VALIDATOR_MODEL=gemini-1.5-flash
   GEMINI_TEMPLATE_MODEL=gemini-1.5-pro
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    project_root = Path(__file__).parent.parent.parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)  # Don't override existing env vars
except ImportError:
    # python-dotenv not installed, use system env vars only
    pass


@dataclass
class ModelConfig:
    """Configuration for Gemini models by role."""

    fallback_model: str = "gemini-2.0-flash-exp"
    validator_model: str = "gemini-2.0-flash-exp"
    template_model: str = "gemini-2.0-flash-exp"

    @classmethod
    def from_env(cls) -> "ModelConfig":
        """Load model configuration from environment variables.

        Priority (highest to lowest):
        1. Specific role variables (GEMINI_FALLBACK_MODEL, etc.)
        2. Role-specific in GEMINI_MODELS (fallback:model,validator:model)
        3. Single model in GEMINI_MODEL
        4. Default (gemini-2.0-flash-exp)

        Returns:
            ModelConfig with models loaded from environment
        """
        # Start with defaults
        config = {
            "fallback": "gemini-2.0-flash-exp",
            "validator": "gemini-2.0-flash-exp",
            "template": "gemini-2.0-flash-exp",
        }

        # STEP 1: Check for single model (lowest priority)
        single_model = os.getenv("GEMINI_MODEL")
        if single_model:
            logger.info(f"Using single Gemini model for all roles: {single_model}")
            config["fallback"] = single_model
            config["validator"] = single_model
            config["template"] = single_model

        # STEP 2: Parse GEMINI_MODELS for role-specific config
        models_str = os.getenv("GEMINI_MODELS")
        if models_str:
            role_models = cls._parse_models_string(models_str)
            if role_models:
                logger.info(f"Using role-specific Gemini models: {role_models}")
                config.update(role_models)

        # STEP 3: Check individual role variables (highest priority)
        fallback_model = os.getenv("GEMINI_FALLBACK_MODEL")
        if fallback_model:
            logger.info(f"Override fallback model: {fallback_model}")
            config["fallback"] = fallback_model

        validator_model = os.getenv("GEMINI_VALIDATOR_MODEL")
        if validator_model:
            logger.info(f"Override validator model: {validator_model}")
            config["validator"] = validator_model

        template_model = os.getenv("GEMINI_TEMPLATE_MODEL")
        if template_model:
            logger.info(f"Override template model: {template_model}")
            config["template"] = template_model

        return cls(
            fallback_model=config["fallback"],
            validator_model=config["validator"],
            template_model=config["template"],
        )

    @staticmethod
    def _parse_models_string(models_str: str) -> dict[str, str]:
        """Parse GEMINI_MODELS string.

        Format: "fallback:gemini-2.0-flash-exp,validator:gemini-1.5-flash,template:gemini-1.5-pro"

        Args:
            models_str: Comma-separated role:model pairs

        Returns:
            dict mapping role to model name
        """
        result = {}

        # Split by comma
        pairs = models_str.split(",")

        for pair in pairs:
            pair = pair.strip()
            if not pair:
                continue

            # Split by colon
            if ":" not in pair:
                logger.warning(f"Invalid model config format (expected 'role:model'): {pair}")
                continue

            role, model = pair.split(":", 1)
            role = role.strip()
            model = model.strip()

            # Validate role
            if role not in ["fallback", "validator", "template"]:
                logger.warning(f"Unknown role '{role}' in GEMINI_MODELS, ignoring")
                continue

            result[role] = model

        return result

    def __str__(self) -> str:
        """String representation."""
        return (
            f"ModelConfig(\n"
            f"  fallback={self.fallback_model},\n"
            f"  validator={self.validator_model},\n"
            f"  template={self.template_model}\n"
            f")"
        )


def get_model_config() -> ModelConfig:
    """Get model configuration from environment.

    This is a convenience function that caches the config.

    Returns:
        ModelConfig loaded from environment
    """
    return ModelConfig.from_env()
