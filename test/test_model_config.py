"""Tests for Gemini model configuration.

Tests different ways of configuring models:
1. Single model for all roles (GEMINI_MODEL)
2. Role-specific models via GEMINI_MODELS
3. Individual role variables (GEMINI_FALLBACK_MODEL, etc.)
"""

import os
import pytest
from unittest.mock import patch

from src.halo.agents.model_config import ModelConfig


class TestModelConfig:
    """Test ModelConfig parsing from environment variables."""

    def test_default_config(self):
        """Should use default model if no env vars set."""
        with patch.dict(os.environ, {}, clear=True):
            config = ModelConfig.from_env()

            assert config.fallback_model == "gemini-2.0-flash-exp"
            assert config.validator_model == "gemini-2.0-flash-exp"
            assert config.template_model == "gemini-2.0-flash-exp"

    def test_single_model_for_all(self):
        """Should use single model for all roles when GEMINI_MODEL is set."""
        with patch.dict(os.environ, {"GEMINI_MODEL": "gemini-1.5-pro"}, clear=True):
            config = ModelConfig.from_env()

            assert config.fallback_model == "gemini-1.5-pro"
            assert config.validator_model == "gemini-1.5-pro"
            assert config.template_model == "gemini-1.5-pro"

    def test_role_specific_models_via_gemini_models(self):
        """Should parse role-specific models from GEMINI_MODELS."""
        models_str = (
            "fallback:gemini-2.0-flash-exp,"
            "validator:gemini-1.5-flash,"
            "template:gemini-1.5-pro"
        )

        with patch.dict(os.environ, {"GEMINI_MODELS": models_str}, clear=True):
            config = ModelConfig.from_env()

            assert config.fallback_model == "gemini-2.0-flash-exp"
            assert config.validator_model == "gemini-1.5-flash"
            assert config.template_model == "gemini-1.5-pro"

    def test_individual_role_variables(self):
        """Should use individual role variables (highest priority)."""
        with patch.dict(os.environ, {
            "GEMINI_FALLBACK_MODEL": "gemini-2.0-flash-exp",
            "GEMINI_VALIDATOR_MODEL": "gemini-1.5-flash",
            "GEMINI_TEMPLATE_MODEL": "gemini-1.5-pro",
        }, clear=True):
            config = ModelConfig.from_env()

            assert config.fallback_model == "gemini-2.0-flash-exp"
            assert config.validator_model == "gemini-1.5-flash"
            assert config.template_model == "gemini-1.5-pro"

    def test_priority_individual_over_gemini_models(self):
        """Individual variables should override GEMINI_MODELS."""
        with patch.dict(os.environ, {
            "GEMINI_MODELS": "fallback:gemini-1.5-flash,validator:gemini-1.5-flash",
            "GEMINI_FALLBACK_MODEL": "gemini-2.0-flash-exp",  # Should override
        }, clear=True):
            config = ModelConfig.from_env()

            assert config.fallback_model == "gemini-2.0-flash-exp"  # Overridden
            assert config.validator_model == "gemini-1.5-flash"  # From GEMINI_MODELS

    def test_priority_gemini_models_over_gemini_model(self):
        """GEMINI_MODELS should override GEMINI_MODEL."""
        with patch.dict(os.environ, {
            "GEMINI_MODEL": "gemini-1.5-flash",
            "GEMINI_MODELS": "validator:gemini-1.5-pro",  # Should override for validator
        }, clear=True):
            config = ModelConfig.from_env()

            assert config.fallback_model == "gemini-1.5-flash"  # From GEMINI_MODEL
            assert config.validator_model == "gemini-1.5-pro"  # From GEMINI_MODELS
            assert config.template_model == "gemini-1.5-flash"  # From GEMINI_MODEL

    def test_parse_models_string_partial(self):
        """Should handle partial role specifications."""
        models_str = "fallback:gemini-2.0-flash-exp,validator:gemini-1.5-flash"

        with patch.dict(os.environ, {"GEMINI_MODELS": models_str}, clear=True):
            config = ModelConfig.from_env()

            assert config.fallback_model == "gemini-2.0-flash-exp"
            assert config.validator_model == "gemini-1.5-flash"
            assert config.template_model == "gemini-2.0-flash-exp"  # Default

    def test_parse_models_string_with_spaces(self):
        """Should handle spaces in GEMINI_MODELS."""
        models_str = "fallback: gemini-2.0-flash-exp , validator: gemini-1.5-flash"

        with patch.dict(os.environ, {"GEMINI_MODELS": models_str}, clear=True):
            config = ModelConfig.from_env()

            assert config.fallback_model == "gemini-2.0-flash-exp"
            assert config.validator_model == "gemini-1.5-flash"

    def test_parse_models_string_invalid_format(self):
        """Should skip invalid entries in GEMINI_MODELS."""
        models_str = "fallback:gemini-2.0-flash-exp,invalid_format,validator:gemini-1.5-flash"

        with patch.dict(os.environ, {"GEMINI_MODELS": models_str}, clear=True):
            config = ModelConfig.from_env()

            assert config.fallback_model == "gemini-2.0-flash-exp"
            assert config.validator_model == "gemini-1.5-flash"

    def test_parse_models_string_unknown_role(self):
        """Should skip unknown roles in GEMINI_MODELS."""
        models_str = "fallback:gemini-2.0-flash-exp,unknown:gemini-1.5-flash"

        with patch.dict(os.environ, {"GEMINI_MODELS": models_str}, clear=True):
            config = ModelConfig.from_env()

            assert config.fallback_model == "gemini-2.0-flash-exp"
            # Unknown role should be ignored, use default
            assert config.validator_model == "gemini-2.0-flash-exp"

    def test_str_representation(self):
        """Should have readable string representation."""
        config = ModelConfig(
            fallback_model="gemini-2.0-flash-exp",
            validator_model="gemini-1.5-flash",
            template_model="gemini-1.5-pro",
        )

        str_repr = str(config)

        assert "gemini-2.0-flash-exp" in str_repr
        assert "gemini-1.5-flash" in str_repr
        assert "gemini-1.5-pro" in str_repr


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
