"""Template expander for immediate vocabulary expansion.

When a new template is learned with high confidence, immediately expand it
to all known values in discrete domains.

Example:
    User says: "enciende la luz de la cocina" (first time)
    Template learned: "enciende la luz de {ROOM}"
    Immediate expansion: Generate for ALL known rooms
        - "enciende la luz de la sala"
        - "enciende la luz del patio"
        - "enciende la luz del dormitorio"
        - etc.
"""

import logging
from typing import List
from .slots import SlotInfo

logger = logging.getLogger(__name__)


class TemplateExpander:
    """Expands templates to all domain variations.

    This is the "memory muscular algoritmica" - learn once, apply everywhere.
    """

    # Domains that are discrete and safe to expand
    DISCRETE_DOMAINS = {
        "room",
        "action",
        "device",
        "mode",
    }

    def __init__(self, vocabulary_manager):
        """Initialize with reference to vocabulary manager.

        Args:
            vocabulary_manager: VocabularyManager instance for domain values
        """
        self.vocab_manager = vocabulary_manager

    def expand_template(
        self,
        text: str,
        tool_name: str,
        parameters: dict,
        slots: dict,
        confidence: float,
        min_confidence: float = 0.95,
    ) -> List[dict]:
        """Expand template to all variations of discrete domains.

        Args:
            text: Original text
            tool_name: Tool name
            parameters: Parameters
            slots: Slots with grammatical positions
            confidence: Classification confidence
            min_confidence: Minimum confidence to expand (default 0.95)

        Returns:
            List of synthetic examples
        """
        if confidence < min_confidence:
            logger.debug(f"Confidence {confidence:.2f} < {min_confidence}, skipping expansion")
            return []

        if not slots:
            logger.debug("No slots, skipping expansion")
            return []

        synthetic_examples = []

        # For each discrete slot
        for param_name, slot_info in slots.items():
            if param_name not in self.DISCRETE_DOMAINS:
                logger.debug(f"Skipping continuous domain: {param_name}")
                continue

            original_value = slot_info.value
            domain_values = self.vocab_manager.get_domain_values(param_name)

            if not domain_values:
                logger.warning(f"No values for domain: {param_name}")
                continue

            logger.info(
                f"Expanding {param_name}: {len(domain_values)} values "
                f"(original: {original_value})"
            )

            # Generate variation for EACH value in domain
            for new_value in domain_values:
                if new_value.lower() == original_value.lower():
                    continue  # Skip original (already exists)

                # Replace value in text
                synthetic_text = self._replace_slot(text, slot_info, new_value)

                # Replace in parameters
                synthetic_params = parameters.copy()
                synthetic_params[param_name] = new_value

                # Adjust slots (new position for modified slot)
                synthetic_slots = self._adjust_slots(slots, param_name, slot_info, new_value)

                # Create synthetic example
                synthetic_examples.append(
                    {
                        "text": synthetic_text,
                        "tool_name": tool_name,
                        "parameters": synthetic_params,
                        "slots": synthetic_slots,
                        "confidence": confidence - 0.05,  # Slight penalty
                        "synthetic": True,
                        "source": "template_expansion",
                    }
                )

        logger.info(
            f"Template expansion: '{text}' → {len(synthetic_examples)} synthetic examples"
        )
        return synthetic_examples

    def _replace_slot(self, text: str, slot_info: SlotInfo, new_value: str) -> str:
        """Replace slot value in text.

        Args:
            text: Original text
            slot_info: Slot information
            new_value: New value to insert

        Returns:
            Text with replaced value
        """
        return text[: slot_info.start] + new_value + text[slot_info.end :]

    def _adjust_slots(
        self, slots: dict, modified_param: str, modified_slot: SlotInfo, new_value: str
    ) -> dict:
        """Adjust slot positions after replacement.

        Args:
            slots: Original slots
            modified_param: Name of modified parameter
            modified_slot: Modified slot info
            new_value: New value

        Returns:
            Adjusted slots dict
        """
        len_diff = len(new_value) - len(modified_slot.value)
        adjusted_slots = {}

        for param_name, slot in slots.items():
            if param_name == modified_param:
                # Update modified slot
                adjusted_slots[param_name] = SlotInfo(
                    value=new_value,
                    start=slot.start,
                    end=slot.start + len(new_value),
                    dep=slot.dep,
                    head=slot.head,
                    pos=slot.pos,
                )
            else:
                # Adjust offset for slots after the modified one
                if slot.start > modified_slot.start:
                    adjusted_slots[param_name] = SlotInfo(
                        value=slot.value,
                        start=slot.start + len_diff,
                        end=slot.end + len_diff,
                        dep=slot.dep,
                        head=slot.head,
                        pos=slot.pos,
                    )
                else:
                    adjusted_slots[param_name] = slot

        return adjusted_slots

    def expand_all_combinations(
        self, text: str, tool_name: str, parameters: dict, slots: dict
    ) -> List[dict]:
        """Expand to ALL combinations of discrete domains (Cartesian product).

        WARNING: Can generate large number of examples (product of domain sizes).
        Use with caution.

        Args:
            text: Original text
            tool_name: Tool name
            parameters: Parameters
            slots: Slots

        Returns:
            List of all combinations
        """
        # Get all discrete slots
        discrete_slots = {k: v for k, v in slots.items() if k in self.DISCRETE_DOMAINS}

        if not discrete_slots:
            return []

        # Get domain values for each slot
        domain_values = {}
        for param_name in discrete_slots:
            values = self.vocab_manager.get_domain_values(param_name)
            if values:
                domain_values[param_name] = list(values)

        if not domain_values:
            return []

        # Generate Cartesian product
        import itertools

        keys = list(domain_values.keys())
        values = [domain_values[k] for k in keys]
        combinations = list(itertools.product(*values))

        logger.info(
            f"Cartesian expansion: {len(combinations)} total combinations "
            f"({' × '.join(str(len(v)) for v in values)})"
        )

        synthetic_examples = []
        for combo in combinations:
            # Skip original combination
            is_original = all(
                combo[i].lower() == parameters[keys[i]].lower() for i in range(len(keys))
            )
            if is_original:
                continue

            # Replace all slots
            synthetic_text = text
            synthetic_params = parameters.copy()
            synthetic_slots = slots.copy()

            # Apply replacements in reverse order (to preserve indices)
            sorted_slots = sorted(
                enumerate(keys), key=lambda x: slots[x[1]].start, reverse=True
            )

            for idx, param_name in sorted_slots:
                new_value = combo[idx]
                slot_info = slots[param_name]

                # Replace in text
                synthetic_text = self._replace_slot(synthetic_text, slot_info, new_value)

                # Replace in parameters
                synthetic_params[param_name] = new_value

                # Update slots
                synthetic_slots = self._adjust_slots(
                    synthetic_slots, param_name, slot_info, new_value
                )

            synthetic_examples.append(
                {
                    "text": synthetic_text,
                    "tool_name": tool_name,
                    "parameters": synthetic_params,
                    "slots": synthetic_slots,
                    "synthetic": True,
                    "source": "cartesian_expansion",
                }
            )

        return synthetic_examples
