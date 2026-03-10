#!/usr/bin/env python3
"""
Test Gemini classifier (Yoda).

Tests:
1. Gemini API connection
2. Simple command classification
3. Complex command classification
4. Ambiguous command handling
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load .env file
try:
    from dotenv import load_dotenv
    project_root = Path(__file__).parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded .env from: {env_path}\n")
except ImportError:
    print("⚠️  python-dotenv not installed, using system environment variables\n")

from halo.intent.classifiers.gemini import GeminiClassifier
from halo.agents.model_config import ModelConfig


def test_gemini_connection():
    """Test that we can connect to Gemini API."""
    print("=" * 70)
    print("TEST 1: Gemini API Connection")
    print("=" * 70)

    try:
        # Load model configuration from .env
        model_config = ModelConfig.from_env()
        print(f"\nModel Configuration:")
        print(f"  Fallback:  {model_config.fallback_model}")
        print(f"  Validator: {model_config.validator_model}")
        print(f"  Template:  {model_config.template_model}")

        # Create classifier with configured model
        classifier = GeminiClassifier(
            model=model_config.fallback_model,
            validator_model=model_config.validator_model,
            template_model=model_config.template_model
        )
        print(f"\n✅ Connected to Gemini API")
        print(f"   Using model: {classifier.model}")
        return classifier
    except Exception as e:
        print(f"\n❌ Failed to connect to Gemini: {e}")
        print("\nMake sure you have:")
        print("1. Set GEMINI_API_KEY in .env file")
        print("2. Installed google-genai: uv pip install google-genai")
        print("3. Model name is correct (check with: make show-gemini-config)")
        sys.exit(1)


def test_simple_command(classifier):
    """Test simple command classification."""
    print("\n" + "=" * 70)
    print("TEST 2: Simple Command")
    print("=" * 70)

    user_input = "enciende la luz del salon"
    print(f"\nUser: {user_input}")

    result = classifier._do_classify(user_input, {})

    if result:
        print(f"\n✅ Classification successful")
        print(f"   Tool: {result.tool_name}")
        print(f"   Parameters: {result.parameters}")
        print(f"   Confidence: {result.confidence}")

        # Verify
        assert result.tool_name == "light_control", f"Expected light_control, got {result.tool_name}"
        assert result.parameters.get("action") == "on", "Expected action=on"
        assert "salon" in result.parameters.get("room", "").lower(), "Expected room=salon"
        print("\n✅ PASSED: Simple command classification")
    else:
        print("\n❌ FAILED: No classification result")
        sys.exit(1)


def test_complex_command(classifier):
    """Test complex command classification."""
    print("\n" + "=" * 70)
    print("TEST 3: Complex Command")
    print("=" * 70)

    user_input = "enciende las luces del salon y la cocina pero atenua la del dormitorio"
    print(f"\nUser: {user_input}")

    result = classifier._do_classify(user_input, {})

    if result:
        print(f"\n✅ Classification successful")
        print(f"   Tool: {result.tool_name}")
        print(f"   Parameters: {result.parameters}")
        print(f"   Confidence: {result.confidence}")

        # Gemini should handle this (might choose one action or explain limitation)
        print("\n✅ PASSED: Complex command handled")
    else:
        print("\n❌ FAILED: No classification result")
        sys.exit(1)


def test_ambiguous_command(classifier):
    """Test ambiguous command handling."""
    print("\n" + "=" * 70)
    print("TEST 4: Ambiguous Command")
    print("=" * 70)

    user_input = "dame luz"
    print(f"\nUser: {user_input}")

    result = classifier._do_classify(user_input, {})

    if result:
        print(f"\n✅ Classification successful")
        print(f"   Tool: {result.tool_name}")
        print(f"   Parameters: {result.parameters}")
        print(f"   Confidence: {result.confidence}")

        # Gemini should handle ambiguity gracefully
        # (might ask for clarification or make reasonable assumption)
        print("\n✅ PASSED: Ambiguous command handled")
    else:
        print("\n❌ FAILED: No classification result")
        sys.exit(1)


def test_conversation_command(classifier):
    """Test conversational (non-tool) command."""
    print("\n" + "=" * 70)
    print("TEST 5: Conversational Command")
    print("=" * 70)

    user_input = "gracias"
    print(f"\nUser: {user_input}")

    result = classifier._do_classify(user_input, {})

    if result:
        print(f"\n✅ Classification successful")
        print(f"   Tool: {result.tool_name}")
        print(f"   Parameters: {result.parameters}")
        print(f"   Confidence: {result.confidence}")

        # Should use "conversation" tool
        assert result.tool_name == "conversation", f"Expected conversation, got {result.tool_name}"
        print("\n✅ PASSED: Conversation command")
    else:
        print("\n❌ FAILED: No classification result")
        sys.exit(1)


def main():
    """Run all tests."""
    print("\n🧪 Testing Gemini Classifier (Yoda)")
    print("\nNOTE: This test requires:")
    print("- GEMINI_API_KEY environment variable")
    print("- Internet connection")
    print("- google-genai library installed")

    try:
        classifier = test_gemini_connection()
        test_simple_command(classifier)
        test_complex_command(classifier)
        test_ambiguous_command(classifier)
        test_conversation_command(classifier)

        print("\n" + "=" * 70)
        print("🎉 ALL TESTS PASSED")
        print("=" * 70)
        print("\n✨ Gemini (Yoda) is ready to dominate the edge computing world!")
        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
