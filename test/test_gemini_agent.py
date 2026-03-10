"""Tests for Gemini Agent with 3 roles.

Tests:
1. Role 2: Quality Validator
2. Role 3: Template Master
3. Integration with learning loop
"""

import os
import pytest
from unittest.mock import Mock, patch

from src.halo.agents.gemini_agent import GeminiAgent
from src.halo.agents.quality_validator import ValidationResult
from src.halo.agents.template_master import TemplateImprovement
from src.halo.intent.base import ClassificationResult
from src.halo.intent.confidence_policy import ConfidencePolicy, ExecutionDecision


# Skip all tests if GEMINI_API_KEY is not set
pytestmark = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set"
)


class TestConfidencePolicy:
    """Test confidence policy for hardware actions."""

    def test_high_confidence_hardware_executes(self):
        """Hardware action with high confidence should execute."""
        policy = ConfidencePolicy()

        classification = ClassificationResult(
            tool_name="light_control",
            parameters={"action": "on", "room": "salon"},
            confidence=0.96,
            classifier_used="embedding",
            cached=False
        )

        decision = policy.should_execute(classification)
        assert decision.execute is True
        assert decision.require_validation is False
        assert decision.ask_user is False

    def test_medium_confidence_hardware_requires_validation(self):
        """Hardware action with medium confidence should require validation."""
        policy = ConfidencePolicy()

        classification = ClassificationResult(
            tool_name="light_control",
            parameters={"action": "on", "room": "salon"},
            confidence=0.88,  # In validation zone (0.85-0.95)
            classifier_used="embedding",
            cached=False
        )

        decision = policy.should_execute(classification)
        assert decision.execute is False
        assert decision.require_validation is True
        assert decision.ask_user is False

    def test_low_confidence_hardware_asks_user(self):
        """Hardware action with low confidence should ask user."""
        policy = ConfidencePolicy()

        classification = ClassificationResult(
            tool_name="light_control",
            parameters={"action": "on", "room": "salon"},
            confidence=0.75,  # Below validation zone
            classifier_used="keyword",
            cached=False
        )

        decision = policy.should_execute(classification)
        assert decision.execute is False
        assert decision.require_validation is False
        assert decision.ask_user is True

    def test_query_tool_more_permissive(self):
        """Query tools should be more permissive than hardware."""
        policy = ConfidencePolicy()

        classification = ClassificationResult(
            tool_name="home_status",
            parameters={"scope": "all"},
            confidence=0.82,  # Would fail for hardware, OK for query
            classifier_used="embedding",
            cached=False
        )

        decision = policy.should_execute(classification)
        assert decision.execute is True


class TestQualityValidator:
    """Test Gemini Role 2: Quality Validator."""

    def test_should_validate_bootstrapping(self):
        """Should validate during bootstrapping (first 100 examples)."""
        agent = GeminiAgent()

        classification = ClassificationResult(
            tool_name="light_control",
            parameters={"action": "on", "room": "salon"},
            confidence=0.99,
            classifier_used="exact_match",
            cached=False
        )

        # During bootstrapping
        should_validate = agent.validator.should_validate(
            classification, dataset_size=50
        )
        assert should_validate is True

        # After bootstrapping
        should_validate = agent.validator.should_validate(
            classification, dataset_size=150
        )
        assert should_validate is False

    def test_should_validate_dubious_confidence(self):
        """Should validate dubious confidence (0.85-0.95)."""
        agent = GeminiAgent()

        classification = ClassificationResult(
            tool_name="light_control",
            parameters={"action": "on", "room": "salon"},
            confidence=0.88,  # Dubious
            classifier_used="embedding",
            cached=False
        )

        should_validate = agent.validator.should_validate(
            classification, dataset_size=200
        )
        assert should_validate is True

    def test_should_validate_hardware_critical(self):
        """Should validate hardware critical actions."""
        agent = GeminiAgent()

        classification = ClassificationResult(
            tool_name="climate_control",
            parameters={"action": "set_temperature", "temperature": 22},
            confidence=0.92,  # < 0.95 for hardware
            classifier_used="embedding",
            cached=False
        )

        should_validate = agent.validator.should_validate(
            classification, dataset_size=200
        )
        assert should_validate is True


class TestTemplateMaster:
    """Test Gemini Role 3: Template Master."""

    def test_suggest_article_rules_spanish(self):
        """Should suggest correct Spanish article rules."""
        agent = GeminiAgent()

        article_rules = agent.template_master.suggest_article_rules(
            domain="room",
            values=["garage", "cocina", "sala", "bano"]
        )

        # Masculine: del
        assert article_rules["garage"] == "del"
        assert article_rules["bano"] == "del"

        # Feminine: de la
        assert article_rules["cocina"] == "de la"
        assert article_rules["sala"] == "de la"


class TestGeminiAgent:
    """Test Gemini Agent orchestration."""

    def test_agent_initialization(self):
        """Should initialize with 3 roles."""
        agent = GeminiAgent()

        assert agent.gemini is not None
        assert agent.validator is not None
        assert agent.template_master is not None
        assert agent.role_stats == {"fallback": 0, "validator": 0, "template_master": 0}

    def test_stats_tracking(self):
        """Should track usage statistics per role."""
        agent = GeminiAgent()

        # Simulate role usage
        agent.role_stats["fallback"] = 10
        agent.role_stats["validator"] = 5
        agent.role_stats["template_master"] = 2

        stats = agent.get_stats()

        assert stats["fallback"]["count"] == 10
        assert stats["fallback"]["percentage"] == pytest.approx(58.82, rel=0.1)

        assert stats["validator"]["count"] == 5
        assert stats["validator"]["percentage"] == pytest.approx(29.41, rel=0.1)

        assert stats["template_master"]["count"] == 2
        assert stats["template_master"]["percentage"] == pytest.approx(11.76, rel=0.1)

    def test_reset_stats(self):
        """Should reset statistics."""
        agent = GeminiAgent()

        agent.role_stats["fallback"] = 10
        agent.reset_stats()

        assert agent.role_stats["fallback"] == 0


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
