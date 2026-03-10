"""
Converter between Halo and FunctionGemma formats.

FunctionGemma uses special tokens:
- <start_function_declaration>...<end_function_declaration> for tool definitions
- <start_function_call>...<end_function_call> for tool invocations
- <escape>...<escape> for string values
"""

import json
import re
from pathlib import Path
from typing import Any

from datasets import Dataset

from halo.tools.registry import Tool, get_tools_schema


class HaloToFunctionGemmaConverter:
    """Convert between Halo and FunctionGemma formats."""

    # FunctionGemma uses STRING/INTEGER/NUMBER/BOOLEAN/OBJECT/ARRAY
    TYPE_MAP = {
        "string": "STRING",
        "integer": "INTEGER",
        "number": "NUMBER",
        "boolean": "BOOLEAN",
        "object": "OBJECT",
        "array": "ARRAY",
    }

    DEFAULT_SYSTEM_MSG = "You are a model that can do function calling with the following functions"

    def tool_to_declaration(self, tool: Tool) -> str:
        """
        Convert Halo Tool to FunctionGemma declaration.

        Example output:
        <start_function_declaration>declaration:light_control{
            description:<escape>Control de luces<escape>,
            parameters:{
                properties:{
                    action:{type:<escape>STRING<escape>,enum:[<escape>on<escape>,<escape>off<escape>]},
                    room:{type:<escape>STRING<escape>}
                },
                required:[<escape>action<escape>,<escape>room<escape>],
                type:<escape>OBJECT<escape>
            }
        }<end_function_declaration>
        """
        params = self._convert_parameters(tool.parameters)
        desc = self._escape_string(tool.description)

        return (
            f"<start_function_declaration>declaration:{tool.name}{{"
            f"description:{desc},"
            f"parameters:{params}"
            f"}}<end_function_declaration>"
        )

    def params_to_call(self, tool_name: str, params: dict[str, Any]) -> str:
        """
        Convert tool call to FunctionGemma format.

        Example output:
        <start_function_call>call:light_control{action:<escape>on<escape>,room:<escape>salon<escape>}<end_function_call>
        """
        params_str = ",".join(
            f"{k}:{self._format_value(v)}" for k, v in params.items()
        )
        return f"<start_function_call>call:{tool_name}{{{params_str}}}<end_function_call>"

    def parse_function_call(self, output: str) -> tuple[str | None, dict[str, Any]]:
        """
        Parse FunctionGemma output to extract tool_name and params.

        Input:
            <start_function_call>call:light_control{action:<escape>on<escape>,room:<escape>salon<escape>}<end_function_call>

        Returns:
            ("light_control", {"action": "on", "room": "salon"})
        """
        pattern = r"<start_function_call>call:(\w+)\{(.*?)\}<end_function_call>"
        match = re.search(pattern, output, re.DOTALL)

        if not match:
            return None, {}

        tool_name = match.group(1)
        args_str = match.group(2)

        # Parse arguments: key:<escape>value<escape> or key:number
        params = {}
        arg_pattern = r"(\w+):(?:<escape>(.*?)<escape>|([^,}]+))"
        for arg_match in re.finditer(arg_pattern, args_str):
            key = arg_match.group(1)
            escaped_val = arg_match.group(2)
            unescaped_val = arg_match.group(3)

            if escaped_val is not None:
                params[key] = escaped_val
            elif unescaped_val is not None:
                # Try to parse as number/bool
                val = unescaped_val.strip()
                if val.lower() == "true":
                    params[key] = True
                elif val.lower() == "false":
                    params[key] = False
                else:
                    try:
                        params[key] = int(val)
                    except ValueError:
                        try:
                            params[key] = float(val)
                        except ValueError:
                            params[key] = val

        return tool_name, params

    def golden_to_training(self, golden_path: str | Path) -> Dataset:
        """
        Convert Halo golden dataset to FunctionGemma training format.

        Input (golden_dataset.jsonl):
        {
            "text": "enciende la luz del salon",
            "tool": "light_control",
            "params": {"action": "on", "room": "salon"},
            "synthetic": false
        }

        Output (HuggingFace Dataset):
        {
            "messages": [
                {"role": "developer", "content": "You are a model..."},
                {"role": "user", "content": "enciende la luz del salon"},
                {"role": "assistant", "tool_calls": [{"type": "function", "function": {...}}]}
            ],
            "tools": [...]
        }
        """
        golden_path = Path(golden_path)
        if not golden_path.exists():
            raise FileNotFoundError(f"Golden dataset not found: {golden_path}")

        # Get tools schema once
        tools_schema = get_tools_schema()

        # Convert to FunctionGemma format
        training_data = []
        with open(golden_path, encoding="utf-8") as f:
            for line in f:
                record = json.loads(line.strip())
                training_data.append(
                    self._convert_record_to_training(record, tools_schema)
                )

        return Dataset.from_list(training_data)

    def _convert_record_to_training(
        self, record: dict, tools_schema: list[dict]
    ) -> dict:
        """Convert a single golden dataset record to FunctionGemma training format."""
        return {
            "messages": [
                {"role": "developer", "content": self.DEFAULT_SYSTEM_MSG},
                {"role": "user", "content": record["text"]},
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": record["tool"],
                                "arguments": record["params"],
                            },
                        }
                    ],
                },
            ],
            "tools": tools_schema,
        }

    def _convert_parameters(self, params: dict) -> str:
        """Convert JSON Schema parameters to FunctionGemma format."""
        if not params:
            return "{type:<escape>OBJECT<escape>}"

        result = []

        # Properties
        if "properties" in params:
            props = []
            for key, val in params["properties"].items():
                props.append(f"{key}:{self._convert_property(val)}")
            result.append(f"properties:{{{','.join(props)}}}")

        # Required fields
        if "required" in params:
            required = ",".join(
                f"<escape>{field}<escape>" for field in params["required"]
            )
            result.append(f"required:[{required}]")

        # Type
        param_type = self.TYPE_MAP.get(
            params.get("type", "object").lower(), "OBJECT"
        )
        result.append(f"type:<escape>{param_type}<escape>")

        return "{" + ",".join(result) + "}"

    def _convert_property(self, prop: dict) -> str:
        """Convert a single property to FunctionGemma format."""
        result = []

        # Type
        if "type" in prop:
            prop_type = self.TYPE_MAP.get(prop["type"].lower(), "STRING")
            result.append(f"type:<escape>{prop_type}<escape>")

        # Description
        if "description" in prop:
            desc = self._escape_string(prop["description"])
            result.append(f"description:{desc}")

        # Enum
        if "enum" in prop:
            enum_vals = ",".join(f"<escape>{v}<escape>" for v in prop["enum"])
            result.append(f"enum:[{enum_vals}]")

        # Minimum/Maximum for numbers
        if "minimum" in prop:
            result.append(f"minimum:{prop['minimum']}")
        if "maximum" in prop:
            result.append(f"maximum:{prop['maximum']}")

        return "{" + ",".join(result) + "}"

    def _escape_string(self, value: str) -> str:
        """Wrap string in <escape> tags."""
        return f"<escape>{value}<escape>"

    def _format_value(self, value: Any) -> str:
        """Format a value for FunctionGemma function call."""
        if isinstance(value, str):
            return self._escape_string(value)
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        else:
            # Fallback: convert to string
            return self._escape_string(str(value))
