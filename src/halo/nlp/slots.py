"""Slot definitions for template + slot filling."""

from dataclasses import dataclass
from typing import Optional
import spacy


@dataclass
class SlotInfo:
    """Information about a parameter slot in a sentence.

    Stores grammatical position for template matching.

    Attributes:
        value: Original value of the parameter
        start: Character index start position
        end: Character index end position
        dep: Dependency relation (e.g., "obl", "obj")
        head: Head token text (parent in dependency tree)
        pos: Part-of-speech tag (e.g., "NOUN", "NUM")
    """

    value: str
    start: int
    end: int
    dep: str
    head: str
    pos: str

    def matches_token(self, token: spacy.tokens.Token) -> bool:
        """Check if token matches this slot's grammatical position.

        Args:
            token: spaCy token to compare

        Returns:
            True if token has same grammatical role
        """
        return (
            token.dep_ == self.dep
            and token.head.text.lower() == self.head.lower()
            and token.pos_ == self.pos
        )


class SlotExtractor:
    """Extracts slot information from spaCy Doc."""

    @staticmethod
    def extract_slots(doc: spacy.tokens.Doc, parameters: dict) -> dict[str, SlotInfo]:
        """Extract grammatical positions of parameter values.

        Args:
            doc: spaCy Doc of the sentence
            parameters: Dict of parameter names to values

        Returns:
            Dict mapping parameter names to SlotInfo
        """
        slots = {}

        for param_name, value in parameters.items():
            if value is None:
                continue

            # Find token matching the value
            value_str = str(value).lower()
            for token in doc:
                if token.text.lower() == value_str:
                    slots[param_name] = SlotInfo(
                        value=str(value),
                        start=token.idx,
                        end=token.idx + len(token.text),
                        dep=token.dep_,
                        head=token.head.text,
                        pos=token.pos_,
                    )
                    break

        return slots

    @staticmethod
    def find_slot_value(
        doc: spacy.tokens.Doc, slot_info: SlotInfo
    ) -> Optional[str]:
        """Find value in new input matching slot's grammatical position.

        Args:
            doc: spaCy Doc of new input
            slot_info: Slot information from template

        Returns:
            Token text if found, None otherwise
        """
        for token in doc:
            if slot_info.matches_token(token):
                return token.text

        return None
