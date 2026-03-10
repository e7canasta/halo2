"""LLM-based classifier - Tier 4 (fallback, slowest but most flexible)."""

from typing import Optional
from ..base import IntentClassifier, ClassificationResult
from ...backend import Backend
from ...tools.executor import parse_tool_call
import logging

logger = logging.getLogger(__name__)


class LLMClassifier(IntentClassifier):
    """Tier 4: LLM fallback classifier.

    Uses the LLM to interpret intent when other classifiers fail.
    Latency: ~7s on edge CPU
    Tokens: ~200-400
    """

    def __init__(self, backend: Backend, system_prompt: str):
        super().__init__("llm")
        self.backend = backend
        self.system_prompt = system_prompt

    def _do_classify(self, user_input: str, context: dict) -> Optional[ClassificationResult]:
        """Use LLM to classify intent.

        This is the fallback - always returns a result (never returns None).

        Args:
            user_input: User's input
            context: Conversation context (may include _conversation_history)

        Returns:
            ClassificationResult (always, this is the fallback)
        """
        import json

        # Extract conversation history if available
        conversation_history = context.get("_conversation_history", []) if context else []

        # Build messages array
        messages = []

        # System prompt
        if conversation_history:
            # Include conversation history in system prompt
            history_text = "\n".join(
                f"{msg['role']}: {msg['content']}" for msg in conversation_history
            )
            system_content = f"{self.system_prompt}\n\nRecent conversation:\n{history_text}"
        else:
            # Fallback to legacy context serialization
            context_summary = json.dumps(context) if context else "{}"
            system_content = f"{self.system_prompt}\n\nContext: {context_summary}"

        messages.append({"role": "system", "content": system_content})

        # User message
        messages.append({"role": "user", "content": user_input})

        # Format with chat template if available
        if hasattr(self.backend, "format_messages"):
            prompt = self.backend.format_messages(messages)
        else:
            prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])

        try:
            # Generate with LLM
            raw_response = self.backend.generate(prompt, max_new_tokens=200)

            # Try to parse tool call
            tool_call = parse_tool_call(raw_response)

            if tool_call:
                tool_name, parameters = tool_call
                return ClassificationResult(
                    tool_name=tool_name,
                    parameters=parameters,
                    confidence=0.7,  # LLM has moderate confidence
                    classifier_used=self.name,
                    cached=False,
                )

            # No tool call - treat as conversation
            # Return a special "conversation" tool
            return ClassificationResult(
                tool_name="conversation",
                parameters={"response": raw_response},
                confidence=0.5,
                classifier_used=self.name,
                cached=False,
            )

        except Exception as e:
            logger.error(f"LLM classification error: {e}")
            # Return error result
            return ClassificationResult(
                tool_name="error",
                parameters={"error": str(e)},
                confidence=0.0,
                classifier_used=self.name,
                cached=False,
            )

    def confidence_threshold(self) -> float:
        """LLM threshold (moderate confidence)."""
        return 0.5
