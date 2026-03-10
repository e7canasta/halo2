"""
FunctionGemma backend for Halo.

Uses FunctionGemma 270M (fine-tuned or base) for function calling.
"""

import logging
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from halo.backend.base import Backend
from halo.nlp.functiongemma.converter import HaloToFunctionGemmaConverter
from halo.tools.registry import get_all_tools

logger = logging.getLogger(__name__)


class FunctionGemmaBackend(Backend):
    """Backend using FunctionGemma 270M for function calling."""

    DEFAULT_SYSTEM_MSG = (
        "You are a model that can do function calling with the following functions"
    )

    def __init__(
        self,
        model_name: str = "google/functiongemma-270m-it",
        device: str | None = None,
    ):
        """
        Initialize FunctionGemma backend.

        Args:
            model_name: HuggingFace model ID or local path
            device: Device to run on ("cpu", "cuda", or None for auto)
        """
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.tokenizer = None
        self.converter = HaloToFunctionGemmaConverter()
        self._tools_declaration = None

    def initialize(self):
        """Load and initialize the FunctionGemma model."""
        logger.info(f"Loading FunctionGemma model: {self.model_name}")

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)

        # Load model
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            device_map="auto" if self.device == "auto" else self.device,
            dtype=torch.bfloat16,
            attn_implementation="eager",
        )

        # Pre-compute tool declarations
        self._tools_declaration = self._format_tool_declarations()

        logger.info(f"FunctionGemma loaded on {self.model.device}")

    def generate(
        self, prompt: str, max_new_tokens: int = 128, **kwargs
    ) -> str:
        """
        Generate function call from prompt.

        Args:
            prompt: User input (natural language)
            max_new_tokens: Maximum tokens to generate
            **kwargs: Additional generation parameters

        Returns:
            FunctionGemma output (with <start_function_call> tokens)
        """
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Backend not initialized. Call initialize() first.")

        # Format as FunctionGemma prompt
        full_prompt = self._format_prompt(prompt)

        # Tokenize
        inputs = self.tokenizer(full_prompt, return_tensors="pt").to(
            self.model.device
        )

        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                pad_token_id=self.tokenizer.eos_token_id,
                **kwargs,
            )

        # Decode (skip input prompt)
        generated_tokens = outputs[0][len(inputs["input_ids"][0]) :]
        response = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)

        return response

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if self.tokenizer is None:
            raise RuntimeError("Tokenizer not initialized")
        return len(self.tokenizer.encode(text))

    def parse_function_call(self, output: str) -> tuple[str | None, dict[str, Any]]:
        """
        Parse FunctionGemma output to extract tool_name and params.

        Args:
            output: FunctionGemma output string

        Returns:
            (tool_name, params) or (None, {}) if no function call found
        """
        return self.converter.parse_function_call(output)

    def _format_prompt(self, user_input: str) -> str:
        """
        Format user input as FunctionGemma prompt.

        Format:
        <bos><start_of_turn>developer
        You are a model that can do function calling with the following functions
        <start_function_declaration>...<end_function_declaration>
        ...(more declarations)
        <end_of_turn>
        <start_of_turn>user
        {user_input}<end_of_turn>
        <start_of_turn>model
        """
        messages = [
            {"role": "developer", "content": self.DEFAULT_SYSTEM_MSG},
            {"role": "user", "content": user_input},
        ]

        # Use tokenizer's chat template
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tools=self._get_tools_schema(),
            tokenize=False,
            add_generation_prompt=True,
        )

        return prompt

    def _format_tool_declarations(self) -> str:
        """Format all Halo tools as FunctionGemma declarations."""
        tools = get_all_tools()
        declarations = [self.converter.tool_to_declaration(tool) for tool in tools]
        return "".join(declarations)

    def _get_tools_schema(self) -> list[dict]:
        """Get tools in JSON Schema format for chat template."""
        from halo.tools.registry import get_tools_schema

        return get_tools_schema()
