"""
Gemini-based intent classifier (the "Yoda" fallback).

Uses Google Gemini API as the final safety net when all other classifiers
fail or have low confidence. Gemini 2.5 Flash is extremely capable and fast.
"""

import json
import logging
import os
from typing import Optional

from google import genai
from google.genai import types

from halo.intent.base import ClassificationResult, IntentClassifier
from halo.tools.registry import get_tools_schema

logger = logging.getLogger(__name__)


class GeminiClassifier(IntentClassifier):
    """
    Classifier using Google Gemini API (el maestro Yoda).

    This is the FINAL fallback in the chain - only used when all other
    classifiers fail or have low confidence.

    Advantages:
    - Extremely accurate (99%+)
    - Fast (1-2s via API)
    - No local RAM usage
    - Advanced reasoning capabilities

    Disadvantages:
    - Requires API key and internet connection
    - Small cost per call (~$0.0001)
    - Not 100% offline
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash-exp",
        validator_model: Optional[str] = None,
        template_model: Optional[str] = None,
    ):
        """
        Initialize Gemini classifier.

        Args:
            api_key: Google Gemini API key (or None to use env GEMINI_API_KEY)
            model: Gemini model for fallback classification (default: gemini-2.0-flash-exp)
            validator_model: Model for quality validation (default: same as model)
            template_model: Model for template improvement (default: same as model)
        """
        super().__init__("gemini")

        # Get API key from env if not provided
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Gemini API key required. Set GEMINI_API_KEY env var or pass api_key."
            )

        # Store models for different roles
        self.model = model  # Fallback classifier (Role 1)
        self.validator_model = validator_model or model  # Quality validator (Role 2)
        self.template_model = template_model or model  # Template master (Role 3)

        # Initialize Gemini client
        try:
            self.client = genai.Client(api_key=self.api_key)
            logger.info(
                f"Gemini classifier initialized:\n"
                f"  - Fallback: {self.model}\n"
                f"  - Validator: {self.validator_model}\n"
                f"  - Template: {self.template_model}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise

    @property
    def confidence_threshold(self) -> float:
        """
        Confidence threshold for Gemini.

        Since Gemini is the final fallback, we use a low threshold.
        If we reach Gemini, we trust its answer regardless of confidence.
        """
        return 0.70

    def _do_classify(
        self, user_input: str, context: dict
    ) -> Optional[ClassificationResult]:
        """
        Classify using Gemini API.

        Args:
            user_input: Natural language command
            context: Conversation context (may include _conversation_history)

        Returns:
            ClassificationResult or None if API fails
        """
        try:
            # Build system instruction with tools
            system_instruction = self._build_system_instruction()

            # Build contents (supports multi-turn conversation)
            conversation_history = context.get("_conversation_history", []) if context else []

            if conversation_history:
                # Multi-turn conversation: include history
                contents = []
                for msg in conversation_history:
                    # Convert role to Gemini format (user/model)
                    role = "model" if msg["role"] == "assistant" else "user"
                    contents.append({"role": role, "parts": [{"text": msg["content"]}]})

                # Add current user input
                contents.append({"role": "user", "parts": [{"text": user_input}]})
            else:
                # Single-turn: just user input
                contents = user_input

            # Generate with Gemini
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.1,  # Low temperature for deterministic function calling
                    response_mime_type="application/json",
                ),
            )

            # Parse JSON response
            response_text = response.text.strip()
            result = json.loads(response_text)

            # Handle array responses (multi-action commands)
            # Some models return arrays for complex commands like "do X and Y"
            if isinstance(result, list):
                if len(result) == 0:
                    logger.warning("Gemini returned empty array")
                    return None
                logger.info(f"Gemini returned {len(result)} actions, using first one")
                result = result[0]  # Take first action

            # Extract tool and parameters
            if "tool" not in result or "parameters" not in result:
                logger.warning(f"Gemini returned invalid format: {response_text}")
                return None

            tool_name = result["tool"]
            parameters = result["parameters"]

            # Gemini confidence (high by default, since it's the final fallback)
            confidence = result.get("confidence", 0.95)

            return ClassificationResult(
                tool_name=tool_name,
                parameters=parameters,
                confidence=confidence,
                classifier_used=self.name,
                cached=False,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            logger.debug(f"Response text: {response_text}")
            return None
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}", exc_info=True)
            return None

    def _build_system_instruction(self) -> str:
        """
        Build system instruction for Gemini with tool definitions.

        Uses Gemini prompting best practices from gemini_prompting.md.
        """
        tools = get_tools_schema()

        # Format tools in a clear structure
        tools_description = self._format_tools_for_gemini(tools)

        system_instruction = f"""You are a smart home assistant specialized in function calling.

<role>
You are Gemini, the final decision maker in a tiered classification system.
You only receive requests that other classifiers couldn't handle with confidence.
Your job is to accurately identify the correct tool and extract parameters.
</role>

<available_tools>
{tools_description}
</available_tools>

<instructions>
1. Analyze the user's command carefully
2. Identify which tool best matches the intent
3. Extract all required parameters from the command
4. Return ONLY a JSON object with this exact format:
   {{
     "tool": "tool_name",
     "parameters": {{"param1": "value1", "param2": "value2"}},
     "confidence": 0.95
   }}
</instructions>

<constraints>
- Return ONLY valid JSON, no additional text
- Use Spanish parameter values when appropriate (e.g., "salon", "cocina")
- If the command is not related to smart home control, use tool "conversation" with parameter "response"
- Be precise with parameter extraction
- Confidence should be 0.95 for clear commands, 0.80-0.90 for ambiguous ones
</constraints>

<examples>
User: "enciende la luz del salon"
Output: {{"tool": "light_control", "parameters": {{"action": "on", "room": "salon"}}, "confidence": 0.95}}

User: "como esta la casa"
Output: {{"tool": "home_status", "parameters": {{"scope": "all"}}, "confidence": 0.95}}

User: "gracias"
Output: {{"tool": "conversation", "parameters": {{"response": "De nada! ¿Algo más?"}}, "confidence": 0.90}}
</examples>

Remember: You are the final authority. Be confident in your decisions.
"""

        return system_instruction

    def _format_tools_for_gemini(self, tools: list[dict]) -> str:
        """Format tools in a clear, Gemini-friendly format."""
        formatted = []

        for tool in tools:
            name = tool["name"]
            description = tool["description"]
            params = tool["parameters"]

            # Extract required and optional params
            required = params.get("required", [])
            properties = params.get("properties", {})

            param_desc = []
            for param_name, param_info in properties.items():
                is_required = param_name in required
                param_type = param_info.get("type", "string")
                param_desc_text = param_info.get("description", "")
                enum_vals = param_info.get("enum", [])

                req_mark = "REQUIRED" if is_required else "optional"
                enum_str = f" (options: {', '.join(enum_vals)})" if enum_vals else ""

                param_desc.append(
                    f"  - {param_name} ({param_type}, {req_mark}): {param_desc_text}{enum_str}"
                )

            formatted.append(
                f"Tool: {name}\n"
                f"Description: {description}\n"
                f"Parameters:\n" + "\n".join(param_desc)
            )

        return "\n\n".join(formatted)

    def validate_classification(
        self,
        user_input: str,
        classification: ClassificationResult
    ) -> dict:
        """Validate a classification result (Role 2: Quality Validator).

        This is used BEFORE adding examples to the golden dataset to ensure
        high-quality training data.

        Args:
            user_input: Original user input
            classification: Classification to validate

        Returns:
            dict with validation result in format:
            {
                "is_correct": bool,
                "issues": [list of problems],
                "corrected": {tool, parameters, confidence} or None,
                "should_ask_user": bool,
                "clarification_question": str or None
            }
        """
        try:
            validation_prompt = f"""You are a quality validator for a smart home system.

<context>
User said: "{user_input}"

Proposed classification:
- Tool: {classification.tool_name}
- Parameters: {json.dumps(classification.parameters, indent=2)}
- Confidence: {classification.confidence}
</context>

<task>
Validate if this classification is correct.
</task>

<rules>
1. If information is missing (e.g., "enciende la luz" without room), the classification is INCORRECT
   → Use tool "conversation" to ask for clarification
2. If there is ambiguity, ALWAYS ask for confirmation
3. Better to ask than to execute incorrect action on hardware
4. Verify that extracted parameters are actually present in the user input
5. Check that parameter values match the allowed values for the tool
</rules>

<output_format>
Respond with ONLY valid JSON in this exact format:
{{
  "is_correct": true/false,
  "issues": ["list of problems found"],
  "corrected": {{
    "tool": "correct_tool_name",
    "parameters": {{"param": "value"}},
    "confidence": 0.95
  }},
  "should_ask_user": true/false,
  "clarification_question": "question for user (if should_ask_user is true)"
}}

If the classification is correct, set "corrected" to null.
If you need to ask the user, suggest using tool "conversation" in the corrected field.
</output_format>
"""

            # Call Gemini API (use validator model)
            response = self.client.models.generate_content(
                model=self.validator_model,
                contents=validation_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )

            # Parse JSON response
            response_text = response.text.strip()
            result = json.loads(response_text)

            logger.info(f"Gemini validation result: {result.get('is_correct')} for '{user_input}'")
            if not result.get("is_correct"):
                logger.debug(f"Issues found: {result.get('issues')}")

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini validation response: {e}")
            # Return conservative default (assume incorrect)
            return {
                "is_correct": False,
                "issues": [f"Failed to parse validation response: {e}"],
                "corrected": None,
                "should_ask_user": False,
                "clarification_question": None
            }
        except Exception as e:
            logger.error(f"Gemini validation API call failed: {e}", exc_info=True)
            # Return conservative default
            return {
                "is_correct": False,
                "issues": [f"Validation API call failed: {e}"],
                "corrected": None,
                "should_ask_user": False,
                "clarification_question": None
            }

    def improve_template(
        self,
        template: str,
        slots: dict,
        real_examples: list[str]
    ) -> dict:
        """Improve a template with Gemini's agency (Role 3: Template Master).

        Gemini actively:
        1. Corrects Spanish grammar (articles del/de la, prepositions)
        2. Validates slots are properly extracted
        3. Generates natural variations (synonyms, word order)
        4. Suggests domain-specific rules

        Args:
            template: Template string (e.g., "enciende la luz de {ROOM}")
            slots: Slot definitions
            real_examples: Real user inputs that matched this template

        Returns:
            dict with improvement result in format:
            {
                "corrected_template": str,
                "slot_improvements": {slot_name: {article_rules, synonyms}},
                "natural_variations": [{template, verb}, ...],
                "template_issues": [list of problems]
            }
        """
        try:
            improvement_prompt = f"""You are a Spanish NLU expert specializing in template improvement.

<context>
Template: "{template}"
Slots: {json.dumps(slots, indent=2)}
Real user examples: {json.dumps(real_examples, indent=2)}
</context>

<task>
Analyze and improve this template for a smart home system in Spanish.
</task>

<tasks>
1. Correct grammar (contracted articles del/de la, prepositions)
2. Validate that slots are properly extracted
3. Generate natural variations (verb synonyms, different word orders)
4. Suggest article rules for slot values
</tasks>

<examples>
Input template: "enciende la luz de {{ROOM}}"
Issues: Missing contracted article "del" for masculine rooms
Corrected: "enciende la luz del {{ROOM}}"
Variations: "prende la luz del {{ROOM}}", "pon la luz del {{ROOM}}"

Input template: "apaga el aire de {{ROOM}}"
Corrected: "apaga el aire del {{ROOM}}"
Article rules: {{"garage": "del", "cocina": "de la", "sala": "de la"}}
</examples>

<output_format>
Respond with ONLY valid JSON in this exact format:
{{
  "template_issues": ["list of grammar/style problems found"],
  "corrected_template": "grammatically correct template",
  "slot_improvements": {{
    "ROOM": {{
      "article_rules": {{"garage": "del", "cocina": "de la", "sala": "de la"}},
      "synonyms": ["garage", "garaje", "cochera"]
    }}
  }},
  "natural_variations": [
    {{"template": "prende la luz del {{ROOM}}", "verb": "prende"}},
    {{"template": "pon la luz del {{ROOM}}", "verb": "pon"}},
    {{"template": "activa la luz del {{ROOM}}", "verb": "activa"}}
  ]
}}
</output_format>
"""

            # Call Gemini API (use template model)
            response = self.client.models.generate_content(
                model=self.template_model,
                contents=improvement_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,  # Slightly higher for creative variations
                    response_mime_type="application/json",
                ),
            )

            # Parse JSON response
            response_text = response.text.strip()
            result = json.loads(response_text)

            logger.info(f"Gemini improved template: '{template}' → '{result.get('corrected_template')}'")
            if result.get("template_issues"):
                logger.debug(f"Issues found: {result.get('template_issues')}")

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini template improvement response: {e}")
            # Return safe default (no changes)
            return {
                "corrected_template": template,
                "slot_improvements": {},
                "natural_variations": [],
                "template_issues": [f"Failed to parse improvement response: {e}"]
            }
        except Exception as e:
            logger.error(f"Gemini template improvement API call failed: {e}", exc_info=True)
            # Return safe default
            return {
                "corrected_template": template,
                "slot_improvements": {},
                "natural_variations": [],
                "template_issues": [f"Improvement API call failed: {e}"]
            }
