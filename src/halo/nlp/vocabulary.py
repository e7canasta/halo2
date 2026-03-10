"""Vocabulary manager for domain-driven template expansion.

Manages discrete domains (rooms, devices, actions) and automatically
generates synthetic examples when new vocabulary is added.

Key concept: TEMPLATES × DOMAIN = KNOWLEDGE BASE
- 1 new room → N examples generated (for all templates using {ROOM})
- No need to say every variation - system learns the pattern
"""

import json
from pathlib import Path
from typing import Optional, Set
import logging
from .slots import SlotInfo

logger = logging.getLogger(__name__)


class VocabularyManager:
    """Manages vocabulary and template-based expansion.

    When a new domain value is added (e.g., "garage" to "room"),
    automatically generates examples for ALL templates using that domain.

    Example:
        vocab.add_to_domain("room", "garage")
        → Generates "enciende la luz del garage", "apaga la luz del garage", etc.
    """

    def __init__(
        self,
        embedding_classifier=None,
        dataset_collector=None,
        domains_path: str = "data/domains.json",
        templates_path: str = "data/templates.json",
    ):
        self.embedding_clf = embedding_classifier
        self.dataset_collector = dataset_collector  # NEW: for golden dataset
        self.domains_path = Path(domains_path)
        self.templates_path = Path(templates_path)

        # Discrete domains with known values
        self.domains = self._load_domains()

        # Learned templates (structure + slots)
        self.templates = self._load_templates()

    def _load_domains(self) -> dict[str, Set[str]]:
        """Load domains from file or use defaults.

        Returns:
            Dict mapping domain names to sets of values
        """
        defaults = {
            "room": {
                "sala",
                "cocina",
                "patio",
                "dormitorio",
                "baño",
                "comedor",
                "living",
                "salon",
            },
            "device": {"luz", "persiana", "cortina", "aire", "termostato"},
            "action": {"on", "off", "open", "close", "dim", "brightness"},
            "mode": {"heat", "cool", "auto", "off"},
        }

        if not self.domains_path.exists():
            logger.info("No domains file found, using defaults")
            return {k: set(v) for k, v in defaults.items()}

        try:
            with open(self.domains_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {k: set(v) for k, v in data.items()}
        except Exception as e:
            logger.error(f"Error loading domains: {e}, using defaults")
            return {k: set(v) for k, v in defaults.items()}

    def _save_domains(self):
        """Persist domains to file."""
        self.domains_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.domains_path, "w", encoding="utf-8") as f:
            # Convert sets to lists for JSON
            data = {k: list(v) for k, v in self.domains.items()}
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_templates(self) -> list[dict]:
        """Load learned templates from file.

        Returns:
            List of template dicts
        """
        if not self.templates_path.exists():
            logger.info("No templates file found, starting fresh")
            return []

        try:
            with open(self.templates_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Reconstruct SlotInfo objects
                for template in data:
                    if "slots" in template:
                        reconstructed_slots = {}
                        for param_name, slot_data in template["slots"].items():
                            reconstructed_slots[param_name] = SlotInfo(**slot_data)
                        template["slots"] = reconstructed_slots
                return data
        except Exception as e:
            logger.error(f"Error loading templates: {e}")
            return []

    def _save_templates(self):
        """Persist templates to file."""
        self.templates_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.templates_path, "w", encoding="utf-8") as f:
            # Convert SlotInfo to dict for JSON
            serializable_templates = []
            for template in self.templates:
                t = template.copy()
                if "slots" in t:
                    t["slots"] = {
                        k: {
                            "value": v.value,
                            "start": v.start,
                            "end": v.end,
                            "dep": v.dep,
                            "head": v.head,
                            "pos": v.pos,
                        }
                        for k, v in t["slots"].items()
                    }
                serializable_templates.append(t)
            json.dump(serializable_templates, f, ensure_ascii=False, indent=2)

    def add_to_domain(self, domain_name: str, new_value: str) -> int:
        """Add new value to domain and expand ALL templates.

        This is the "vocabulary expansion" - adding one word generates
        multiple examples automatically.

        Args:
            domain_name: Domain to add to ("room", "device", "action", etc.)
            new_value: New value to add ("garage", "termostato", etc.)

        Returns:
            Number of synthetic examples generated
        """
        if domain_name not in self.domains:
            logger.warning(f"Unknown domain: {domain_name}")
            return 0

        # Normalize value
        new_value = new_value.lower().strip()

        if new_value in self.domains[domain_name]:
            logger.info(f"Value '{new_value}' already in domain '{domain_name}'")
            return 0

        # Add to vocabulary
        self.domains[domain_name].add(new_value)
        self._save_domains()
        logger.info(f"Added '{new_value}' to domain '{domain_name}'")

        # Expand ALL compatible templates
        generated = 0
        for template in self.templates:
            if domain_name in template["slots"]:
                # This template uses the domain → generate example
                syn_ex = self._generate_from_template(template, domain_name, new_value)

                if syn_ex:
                    # 1. Add to embedding classifier (immediate use)
                    if self.embedding_clf:
                        self.embedding_clf.learn(
                            syn_ex["text"],
                            syn_ex["tool_name"],
                            syn_ex["parameters"],
                            slots=syn_ex["slots"],
                        )

                    # 2. Add to golden dataset (for spaCy training) - NEW
                    if self.dataset_collector:
                        self.dataset_collector.collect(
                            user_input=syn_ex["text"],
                            tool_name=syn_ex["tool_name"],
                            parameters=syn_ex["parameters"],
                            confidence=0.95,  # Synthetic examples have high confidence
                            classifier_used="vocabulary_expansion",
                            execution_status="completed",
                            synthetic=True,  # Mark as synthetic
                            slots_provided=syn_ex["slots"],
                        )

                    generated += 1

        logger.info(
            f"Vocabulary expansion: +'{new_value}' → {generated} examples generated "
            f"(embedding + golden dataset)"
        )
        return generated

    def register_template(
        self, text: str, tool_name: str, parameters: dict, slots: dict
    ) -> bool:
        """Register new template from high-confidence classification.

        Args:
            text: Original text
            tool_name: Tool classified
            parameters: Parameters
            slots: Slots with grammatical positions

        Returns:
            True if template was registered, False if already exists
        """
        if not slots:
            return False  # No slots = not a useful template

        template = {
            "text": text,
            "tool_name": tool_name,
            "parameters": parameters,
            "slots": slots,
        }

        # Check if similar template exists
        if self._template_exists(template):
            logger.debug(f"Template already exists: {text}")
            return False

        self.templates.append(template)
        self._save_templates()
        logger.info(f"Registered template: {text} (slots={list(slots.keys())})")
        return True

    def _template_exists(self, template: dict) -> bool:
        """Check if similar template already exists.

        Args:
            template: Template to check

        Returns:
            True if exists
        """
        for t in self.templates:
            if (
                t["tool_name"] == template["tool_name"]
                and set(t["slots"].keys()) == set(template["slots"].keys())
            ):
                # Same tool and same slot structure
                return True
        return False

    def _generate_from_template(
        self, template: dict, domain_name: str, new_value: str
    ) -> Optional[dict]:
        """Generate synthetic example from template with new value.

        Args:
            template: Template base
            domain_name: Domain of slot to replace
            new_value: New value from domain

        Returns:
            Synthetic example dict or None
        """
        if domain_name not in template["slots"]:
            return None

        slot_info = template["slots"][domain_name]

        # Replace value in text
        synthetic_text = (
            template["text"][: slot_info.start]
            + new_value
            + template["text"][slot_info.end :]
        )

        # Replace in parameters
        synthetic_params = template["parameters"].copy()
        synthetic_params[domain_name] = new_value

        # Adjust slots (new position for modified slot)
        len_diff = len(new_value) - len(slot_info.value)
        synthetic_slots = {}

        for param_name, slot in template["slots"].items():
            if param_name == domain_name:
                # Update modified slot
                synthetic_slots[param_name] = SlotInfo(
                    value=new_value,
                    start=slot.start,
                    end=slot.start + len(new_value),
                    dep=slot.dep,
                    head=slot.head,
                    pos=slot.pos,
                )
            else:
                # Adjust offset for slots after the modified one
                if slot.start > slot_info.start:
                    synthetic_slots[param_name] = SlotInfo(
                        value=slot.value,
                        start=slot.start + len_diff,
                        end=slot.end + len_diff,
                        dep=slot.dep,
                        head=slot.head,
                        pos=slot.pos,
                    )
                else:
                    synthetic_slots[param_name] = slot

        return {
            "text": synthetic_text,
            "tool_name": template["tool_name"],
            "parameters": synthetic_params,
            "slots": synthetic_slots,
            "synthetic": True,
            "source": "vocabulary_expansion",
        }

    def get_domain_values(self, domain_name: str) -> Set[str]:
        """Get all values for a domain.

        Args:
            domain_name: Domain name

        Returns:
            Set of values
        """
        return self.domains.get(domain_name, set())

    def get_stats(self) -> dict:
        """Get vocabulary statistics.

        Returns:
            Dict with stats
        """
        return {
            "domains": {k: len(v) for k, v in self.domains.items()},
            "templates": len(self.templates),
            "templates_by_tool": self._count_templates_by_tool(),
            "potential_coverage": self._calculate_coverage(),
        }

    def _count_templates_by_tool(self) -> dict:
        """Count templates grouped by tool."""
        counts = {}
        for t in self.templates:
            tool = t["tool_name"]
            counts[tool] = counts.get(tool, 0) + 1
        return counts

    def _calculate_coverage(self) -> int:
        """Calculate potential examples (product of templates × domain values).

        Returns:
            Total potential examples
        """
        coverage = 0
        for template in self.templates:
            # Calculate product of all domain sizes used in this template
            product = 1
            for slot_name in template["slots"].keys():
                if slot_name in self.domains:
                    product *= len(self.domains[slot_name])
            coverage += product
        return coverage
