"""Tests for ConversationContextManager.

Tests context tracking, parameter merging, and anaphora resolution.
"""

import pytest
from src.halo.context.conversation_manager import ConversationContextManager
from src.halo.context.semantic_memory import detect_anaphora, infer_action_from_verb
from src.halo.intent.base import ClassificationResult


class TestSemanticMemory:
    """Test semantic memory functions."""

    def test_detect_anaphora_la(self):
        """Should detect 'la' anaphora for feminine objects."""
        result = detect_anaphora("ahora apagala")
        assert result is not None
        assert result["pronoun"] == "la"
        assert "light_control" in result["tools"]
        assert result["gender"] == "feminine"

    def test_detect_anaphora_lo(self):
        """Should detect 'lo' anaphora for masculine objects."""
        result = detect_anaphora("bájalo dos grados")
        assert result is not None
        assert result["pronoun"] == "lo"
        assert "climate_control" in result["tools"]

    def test_detect_anaphora_eso(self):
        """Should detect 'eso' as neutral anaphora."""
        result = detect_anaphora("haz eso de nuevo")
        assert result is not None
        assert result["pronoun"] == "eso"
        assert result["tools"] is None  # Neutral = any tool

    def test_infer_action_enciende(self):
        """Should infer 'on' action from 'enciende'."""
        action = infer_action_from_verb("enciende la luz", "light_control")
        assert action == "on"

    def test_infer_action_apaga(self):
        """Should infer 'off' action from 'apaga'."""
        action = infer_action_from_verb("apaga todo", "light_control")
        assert action == "off"


class TestConversationContextManager:
    """Test ConversationContextManager."""

    def test_initialization(self):
        """Should initialize with empty state."""
        manager = ConversationContextManager(max_turns=5)
        assert len(manager.turns) == 0
        assert manager.semantic_memory["last_room"] is None

    def test_add_turn_updates_memory(self):
        """Should update semantic memory when adding turn."""
        manager = ConversationContextManager()

        result = ClassificationResult(
            tool_name="light_control",
            parameters={"action": "on", "room": "salon"},
            confidence=0.95,
            classifier_used="embedding",
            cached=False
        )

        manager.add_turn("enciende la luz del salon", result)

        assert len(manager.turns) == 1
        assert manager.semantic_memory["last_room"] == "salon"
        assert manager.semantic_memory["last_action"] == "on"
        assert manager.semantic_memory["last_tool"] == "light_control"

    def test_max_turns_limit(self):
        """Should keep only max_turns in memory."""
        manager = ConversationContextManager(max_turns=3)

        # Add 5 turns
        for i in range(5):
            result = ClassificationResult(
                tool_name="light_control",
                parameters={"action": "on", "room": f"room{i}"},
                confidence=0.95,
                classifier_used="embedding",
                cached=False
            )
            manager.add_turn(f"turn {i}", result)

        # Should keep only last 3
        assert len(manager.turns) == 3
        assert manager.turns[0].parameters["room"] == "room2"  # Oldest kept
        assert manager.turns[-1].parameters["room"] == "room4"  # Newest

    def test_merge_context_with_missing_room(self):
        """Should merge room from context when missing."""
        manager = ConversationContextManager()

        # First turn: establish context
        result1 = ClassificationResult(
            tool_name="light_control",
            parameters={"action": "on", "room": "salon"},
            confidence=0.95,
            classifier_used="embedding",
            cached=False
        )
        manager.add_turn("enciende la luz del salon", result1)

        # Second turn: missing room
        result2 = ClassificationResult(
            tool_name="light_control",
            parameters={"action": "off"},
            confidence=0.85,
            classifier_used="keyword",
            cached=False
        )

        # Merge context
        merged = manager.merge_context(result2, "ahora apagala")

        # Should have room from context
        assert merged.parameters["room"] == "salon"
        assert merged.parameters["action"] == "off"

    def test_merge_context_preserves_existing_params(self):
        """Should not override existing parameters."""
        manager = ConversationContextManager()

        # Establish context
        result1 = ClassificationResult(
            tool_name="light_control",
            parameters={"action": "on", "room": "salon"},
            confidence=0.95,
            classifier_used="embedding",
            cached=False
        )
        manager.add_turn("enciende la luz del salon", result1)

        # New turn with explicit different room
        result2 = ClassificationResult(
            tool_name="light_control",
            parameters={"action": "off", "room": "cocina"},  # Explicit
            confidence=0.95,
            classifier_used="embedding",
            cached=False
        )

        merged = manager.merge_context(result2, "apaga la luz de la cocina")

        # Should keep explicit room
        assert merged.parameters["room"] == "cocina"

    def test_room_inheritance_across_tools(self):
        """Should inherit room between different tools."""
        manager = ConversationContextManager()

        # Turn 1: light in salon
        result1 = ClassificationResult(
            tool_name="light_control",
            parameters={"action": "on", "room": "salon"},
            confidence=0.95,
            classifier_used="embedding",
            cached=False
        )
        manager.add_turn("enciende la luz del salon", result1)

        # Turn 2: climate control (missing room)
        result2 = ClassificationResult(
            tool_name="climate_control",
            parameters={"temperature": 22},
            confidence=0.85,
            classifier_used="llm",
            cached=False
        )

        merged = manager.merge_context(result2, "pon el aire a 22")

        # Should inherit room from previous turn
        assert merged.parameters["room"] == "salon"

    def test_should_ask_for_clarification_hardware(self):
        """Hardware tools should ask for clarification when missing required params."""
        manager = ConversationContextManager()

        result = ClassificationResult(
            tool_name="light_control",  # Hardware
            parameters={"action": "on"},  # Missing room
            confidence=0.85,
            classifier_used="keyword",
            cached=False
        )

        # Should ask because room is required for hardware
        should_ask = manager.should_ask_for_clarification(result, ["room"])
        assert should_ask is True

    def test_should_ask_for_clarification_query(self):
        """Query tools should NOT ask for clarification."""
        manager = ConversationContextManager()

        result = ClassificationResult(
            tool_name="home_status",  # Query tool
            parameters={},  # Missing room
            confidence=0.80,
            classifier_used="keyword",
            cached=False
        )

        # Should NOT ask because home_status can default to "all"
        should_ask = manager.should_ask_for_clarification(result, ["room"])
        assert should_ask is False

    def test_get_conversation_history(self):
        """Should return conversation history in LLM format."""
        manager = ConversationContextManager()

        # Add 2 turns
        result1 = ClassificationResult(
            tool_name="light_control",
            parameters={"action": "on", "room": "salon"},
            confidence=0.95,
            classifier_used="embedding",
            cached=False
        )
        manager.add_turn("enciende la luz del salon", result1)

        result2 = ClassificationResult(
            tool_name="light_control",
            parameters={"action": "off", "room": "salon"},
            confidence=0.95,
            classifier_used="embedding",
            cached=False
        )
        manager.add_turn("apagala", result2)

        # Get history
        history = manager.get_conversation_history(n_turns=2)

        assert len(history) == 4  # 2 turns × 2 messages (user + assistant)
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "enciende la luz del salon"
        assert history[1]["role"] == "assistant"
        assert "light_control" in history[1]["content"]

    def test_reset(self):
        """Should reset all context state."""
        manager = ConversationContextManager()

        # Add turn
        result = ClassificationResult(
            tool_name="light_control",
            parameters={"action": "on", "room": "salon"},
            confidence=0.95,
            classifier_used="embedding",
            cached=False
        )
        manager.add_turn("test", result)

        # Reset
        manager.reset()

        assert len(manager.turns) == 0
        assert manager.semantic_memory["last_room"] is None

    def test_get_summary(self):
        """Should return summary of context state."""
        manager = ConversationContextManager()

        result = ClassificationResult(
            tool_name="light_control",
            parameters={"action": "on", "room": "salon"},
            confidence=0.95,
            classifier_used="embedding",
            cached=False
        )
        manager.add_turn("enciende la luz", result)

        summary = manager.get_summary()

        assert summary["turns_count"] == 1
        assert summary["semantic_memory"]["last_room"] == "salon"
        assert summary["last_turn"] == "enciende la luz"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
