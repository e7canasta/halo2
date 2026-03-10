"""Template Master - Role 3 of Gemini Agent.

Improves templates and slots with "agency" - not just validating, but actively
improving grammar, suggesting variations, and learning correct Spanish.

Philosophy: Gemini teaches the system to speak proper Spanish
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TemplateImprovement:
    """Result from template improvement."""

    corrected_template: str
    slot_improvements: dict  # {slot_name: {article_rules, synonyms}}
    natural_variations: list[dict]  # [{template, verb}, ...]
    issues: list[str] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []


class TemplateMaster:
    """Gemini improves templates and slots with agency.

    Not just passive validation - Gemini actively:
    1. Corrects Spanish grammar (articles del/de la, prepositions)
    2. Validates slots are properly extracted
    3. Generates natural variations (synonyms, word order)
    4. Suggests domain-specific rules
    """

    def __init__(self, gemini_classifier):
        """Initialize template master.

        Args:
            gemini_classifier: GeminiClassifier instance
        """
        self.gemini = gemini_classifier
        self.improvement_count = 0

    def improve_template(
        self,
        template: str,
        slots: dict,
        real_examples: list[str]
    ) -> TemplateImprovement:
        """Improve a template with Gemini's agency.

        Args:
            template: Template string (e.g., "enciende la luz de {ROOM}")
            slots: Slot definitions (e.g., {"ROOM": {"value": "salon", "domain": "room"}})
            real_examples: Real user inputs that matched this template

        Returns:
            TemplateImprovement with corrections and suggestions
        """
        self.improvement_count += 1

        # Call Gemini to improve template
        improvement_response = self.gemini.improve_template(
            template,
            slots,
            real_examples
        )

        return self._parse_improvement_result(improvement_response)

    def suggest_article_rules(self, domain: str, values: list[str]) -> dict:
        """Suggest article rules for Spanish.

        Args:
            domain: Domain name (e.g., "room", "device")
            values: List of values (e.g., ["garage", "cocina", "sala"])

        Returns:
            dict mapping values to articles (e.g., {"garage": "del", "cocina": "de la"})
        """
        # This could call Gemini or use heuristics
        # For now, implement basic Spanish article rules
        article_rules = {}

        # Common masculine words ending in -o, -e, -r
        masculine_endings = ["o", "e", "r", "n", "l"]

        for value in values:
            # Simple heuristic: if ends in -a, likely feminine
            if value.endswith("a"):
                article_rules[value] = "de la"
            # Check masculine endings
            elif any(value.endswith(ending) for ending in masculine_endings):
                article_rules[value] = "del"
            # Common exceptions
            elif value in ["salon", "living", "garage", "garaje", "bano"]:
                article_rules[value] = "del"
            else:
                # Default to masculine (more common in Spanish)
                article_rules[value] = "del"

        return article_rules

    def _parse_improvement_result(self, response: dict) -> TemplateImprovement:
        """Parse Gemini's improvement response.

        Args:
            response: JSON response from Gemini

        Returns:
            TemplateImprovement
        """
        return TemplateImprovement(
            corrected_template=response.get("corrected_template", ""),
            slot_improvements=response.get("slot_improvements", {}),
            natural_variations=response.get("natural_variations", []),
            issues=response.get("template_issues", [])
        )
