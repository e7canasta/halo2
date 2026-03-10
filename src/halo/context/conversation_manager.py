"""Conversation Context Manager for multi-turn interactions.

Tracks conversation history and semantic memory to enable contextual understanding:
- "enciende la luz del salon" → stores room="salon"
- "ahora apagala" → infers room="salon" from context

Philosophy: Context is implicit in human conversation.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from copy import deepcopy

from ..intent.base import ClassificationResult
from .semantic_memory import (
    SEMANTIC_HIERARCHY,
    get_param_memory_key,
    get_tools_for_param,
    is_param_required_for_hardware,
    is_hardware_tool,
    is_query_tool,
    detect_anaphora,
    infer_action_from_verb,
)

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""

    user_input: str
    tool_name: str
    parameters: Dict[str, any]
    confidence: float
    timestamp: float = field(default_factory=time.time)


class ConversationContextManager:
    """Manages conversational context with semantic memory.

    Tracks conversation history and infers missing parameters from context.

    Example:
        manager = ConversationContextManager(max_turns=5)

        # First turn
        result1 = ClassificationResult("light_control", {"action": "on", "room": "salon"}, 0.95, "embedding")
        manager.add_turn("enciende la luz del salon", result1)

        # Second turn (missing room)
        result2 = ClassificationResult("light_control", {"action": "off"}, 0.85, "embedding")
        merged = manager.merge_context(result2, "ahora apagala")
        # merged.parameters = {"action": "off", "room": "salon"}  # room inferred!
    """

    def __init__(self, max_turns: int = 5):
        """Initialize conversation context manager.

        Args:
            max_turns: Maximum number of turns to keep in memory
        """
        self.max_turns = max_turns
        self.turns: List[ConversationTurn] = []

        # Semantic memory: last known values for parameters
        self.semantic_memory: Dict[str, any] = {
            "last_room": None,
            "last_device": None,
            "last_action": None,
            "last_temperature": None,
            "last_brightness": None,
            "last_position": None,
            "last_mode": None,
            "last_tool": None,  # Last tool used
        }

    def add_turn(self, user_input: str, result: ClassificationResult):
        """Add a conversation turn and update semantic memory.

        Args:
            user_input: User's message
            result: Classification result for this turn
        """
        # Create turn
        turn = ConversationTurn(
            user_input=user_input,
            tool_name=result.tool_name,
            parameters=result.parameters.copy(),
            confidence=result.confidence,
        )

        # Add to history (FIFO)
        self.turns.append(turn)
        if len(self.turns) > self.max_turns:
            self.turns.pop(0)  # Remove oldest

        # Update semantic memory
        self._update_semantic_memory(result)

        logger.debug(
            f"Added turn: {user_input} → {result.tool_name} "
            f"(memory: room={self.semantic_memory['last_room']})"
        )

    def _update_semantic_memory(self, result: ClassificationResult):
        """Update semantic memory with values from result.

        Args:
            result: Classification result
        """
        # Update last_tool
        self.semantic_memory["last_tool"] = result.tool_name

        # Update parameter memory
        for param_name, param_info in SEMANTIC_HIERARCHY.items():
            if param_name in result.parameters:
                value = result.parameters[param_name]
                if value:  # Only store non-empty values
                    memory_key = param_info["memory_key"]
                    self.semantic_memory[memory_key] = value

    def get_missing_param(
        self,
        param_name: str,
        tool_name: str,
        user_input: Optional[str] = None
    ) -> Optional[any]:
        """Get value for a missing parameter from context.

        Args:
            param_name: Parameter to look up (e.g., "room")
            tool_name: Tool that needs this parameter
            user_input: Optional user input for anaphora resolution

        Returns:
            Parameter value from memory, or None if not available
        """
        # Check if this parameter is tracked
        memory_key = get_param_memory_key(param_name)
        if not memory_key:
            return None

        # Check if this tool uses this parameter
        applicable_tools = get_tools_for_param(param_name)
        if tool_name not in applicable_tools:
            return None

        # Try anaphora resolution first (if user_input provided)
        if user_input:
            anaphora = detect_anaphora(user_input)
            if anaphora:
                # Check if detected anaphora matches this tool
                anaphora_tools = anaphora["tools"]
                if anaphora_tools is None or tool_name in anaphora_tools:
                    # Return value from memory
                    value = self.semantic_memory.get(memory_key)
                    if value:
                        logger.info(
                            f"Anaphora '{anaphora['pronoun']}' resolved: "
                            f"{param_name}={value} for {tool_name}"
                        )
                        return value

        # Fallback: return last known value
        value = self.semantic_memory.get(memory_key)
        if value:
            logger.info(
                f"Context inferred: {param_name}={value} for {tool_name}"
            )
        return value

    def merge_context(
        self,
        classification: ClassificationResult,
        user_input: str
    ) -> ClassificationResult:
        """Merge missing parameters from context into classification.

        This is the CORE method for context enrichment.

        Args:
            classification: Classification result
            user_input: User's message

        Returns:
            New ClassificationResult with enriched parameters
        """
        # Create copy to avoid modifying original
        enriched = deepcopy(classification)

        # Get tool schema to know which parameters are needed
        # For now, we'll use the semantic hierarchy
        # TODO: Could integrate with tool registry schema

        # Check each tracked parameter
        for param_name in SEMANTIC_HIERARCHY.keys():
            applicable_tools = get_tools_for_param(param_name)

            # Skip if this tool doesn't use this parameter
            if classification.tool_name not in applicable_tools:
                continue

            # Skip if parameter already present
            if param_name in enriched.parameters and enriched.parameters[param_name]:
                continue

            # Try to get value from context
            value = self.get_missing_param(
                param_name,
                classification.tool_name,
                user_input
            )

            if value:
                enriched.parameters[param_name] = value
                logger.info(
                    f"Context enriched: {param_name}={value} "
                    f"for {classification.tool_name}"
                )

        return enriched

    def should_ask_for_clarification(
        self,
        classification: ClassificationResult,
        missing_params: List[str]
    ) -> bool:
        """Decide if system should ask user for clarification.

        Decision logic (based on user preference):
        - Hardware tools (light/climate/blinds) → ASK if missing required params
        - Query tools (home_status) → DON'T ASK, use defaults

        Args:
            classification: Classification result
            missing_params: List of missing parameter names

        Returns:
            True if should ask for clarification
        """
        # No missing params → no need to ask
        if not missing_params:
            return False

        # Hardware tools: be conservative
        if is_hardware_tool(classification.tool_name):
            # Check if any missing param is required for hardware
            for param in missing_params:
                if is_param_required_for_hardware(param):
                    logger.info(
                        f"Missing required param '{param}' for hardware tool "
                        f"'{classification.tool_name}' → asking for clarification"
                    )
                    return True

        # Query tools: permissive, use defaults
        return False

    def get_conversation_history(self, n_turns: int = 3) -> List[Dict[str, str]]:
        """Get recent conversation history for LLM context.

        Returns conversation in format suitable for LLM prompts.

        Args:
            n_turns: Number of recent turns to return

        Returns:
            List of dicts with role/content format
            Example: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        """
        history = []

        # Get last n turns
        recent_turns = self.turns[-n_turns:] if self.turns else []

        for turn in recent_turns:
            # User message
            history.append({
                "role": "user",
                "content": turn.user_input
            })

            # Assistant response (simulated based on tool call)
            response = self._format_tool_call_as_response(turn)
            history.append({
                "role": "assistant",
                "content": response
            })

        return history

    def _format_tool_call_as_response(self, turn: ConversationTurn) -> str:
        """Format a tool call as an assistant response for LLM context.

        Args:
            turn: Conversation turn

        Returns:
            Formatted response string
        """
        # Simple format: "{tool}({params})"
        params_str = ", ".join(f"{k}={v}" for k, v in turn.parameters.items())
        return f"{turn.tool_name}({params_str})"

    def reset(self):
        """Reset conversation context (useful for testing)."""
        self.turns.clear()
        for key in self.semantic_memory:
            self.semantic_memory[key] = None

        logger.debug("Conversation context reset")

    def get_summary(self) -> Dict[str, any]:
        """Get summary of current context state.

        Returns:
            Dict with turns count and semantic memory
        """
        return {
            "turns_count": len(self.turns),
            "semantic_memory": {k: v for k, v in self.semantic_memory.items() if v is not None},
            "last_turn": self.turns[-1].user_input if self.turns else None,
        }
