"""Integration tests for spaCy slot filler.

Tests template + slot filling functionality.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from halo.intent.classifiers.embedding import EmbeddingClassifier, IntentExample
from halo.intent.classifiers.spacy_slot_filler import SpaCySlotFiller
from halo.intent.base import ClassificationResult
from halo.nlp.slots import SlotInfo
import numpy as np


def test_slot_filling_basic():
    """Test basic slot filling with grammatical templates."""
    print("\n=== Test: Basic Slot Filling ===")

    # Create embedding classifier with a template example
    embedding_clf = EmbeddingClassifier()

    # Create template with slots
    template_example = IntentExample(
        text="enciende la luz de la sala",
        tool_name="light_control",
        parameters={"action": "on", "room": "sala"},
        slots={
            "room": SlotInfo(
                value="sala", start=21, end=25, dep="obl", head="luz", pos="NOUN"
            )
        },
    )
    embedding_clf._examples.append(template_example)

    # Create slot filler
    slot_filler = SpaCySlotFiller()

    # Simulate embedding match with different room
    context = {
        "_previous_classification": ClassificationResult(
            tool_name="light_control",
            parameters={"action": "on", "room": "sala"},  # Template value
            confidence=0.92,
            classifier_used="embedding",
            cached=True,
        ),
        "_matched_example": template_example,
    }

    # Test with new input (different room)
    result = slot_filler.classify("enciende la luz del dormitorio", context)

    print(f"Input: 'enciende la luz del dormitorio'")
    print(f"Template params: {context['_previous_classification'].parameters}")
    print(f"Filled params: {result.parameters}")
    print(f"Confidence: {result.confidence:.4f}")

    # Assertions
    assert result is not None, "Slot filler should return result"
    assert result.parameters["room"] == "dormitorio", "Room should be updated to 'dormitorio'"
    assert result.parameters["action"] == "on", "Action should remain 'on'"
    assert result.confidence > 0.92, "Confidence should be boosted"

    print("✓ Test passed: Slot correctly filled with fresh value\n")


def test_slot_filling_no_slots():
    """Test passthrough when no slots available."""
    print("\n=== Test: Passthrough Without Slots ===")

    # Template without slots
    template_example = IntentExample(
        text="enciende la luz",
        tool_name="light_control",
        parameters={"action": "on", "room": "sala"},
        slots={},  # No slots
    )

    slot_filler = SpaCySlotFiller()

    context = {
        "_previous_classification": ClassificationResult(
            tool_name="light_control",
            parameters={"action": "on", "room": "sala"},
            confidence=0.90,
            classifier_used="embedding",
            cached=True,
        ),
        "_matched_example": template_example,
    }

    result = slot_filler.classify("enciende la luz", context)

    print(f"Input: 'enciende la luz'")
    print(f"No slots in template")
    print(f"Result params: {result.parameters}")

    assert result is not None, "Should return result"
    assert result.parameters == context["_previous_classification"].parameters
    print("✓ Test passed: Passthrough without slots\n")


def test_slot_filling_value_match():
    """Test confidence boost when values match."""
    print("\n=== Test: Confidence Boost on Match ===")

    template_example = IntentExample(
        text="enciende la luz de la sala",
        tool_name="light_control",
        parameters={"action": "on", "room": "sala"},
        slots={
            "room": SlotInfo(
                value="sala", start=21, end=25, dep="obl", head="luz", pos="NOUN"
            )
        },
    )

    slot_filler = SpaCySlotFiller()

    context = {
        "_previous_classification": ClassificationResult(
            tool_name="light_control",
            parameters={"action": "on", "room": "sala"},
            confidence=0.90,
            classifier_used="embedding",
            cached=True,
        ),
        "_matched_example": template_example,
    }

    # Same input as template
    result = slot_filler.classify("enciende la luz de la sala", context)

    print(f"Input: 'enciende la luz de la sala'")
    print(f"Template: 'enciende la luz de la sala'")
    print(f"Original confidence: 0.90")
    print(f"Boosted confidence: {result.confidence:.4f}")

    assert result.confidence > 0.90, "Confidence should be boosted on match"
    print("✓ Test passed: Confidence boosted when values match\n")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("spaCy Slot Filler Integration Tests")
    print("=" * 60)

    try:
        test_slot_filling_basic()
        test_slot_filling_no_slots()
        test_slot_filling_value_match()

        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60 + "\n")

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}\n")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
