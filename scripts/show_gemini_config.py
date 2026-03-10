#!/usr/bin/env python3
"""Show current Gemini model configuration.

Usage:
    uv run python scripts/show_gemini_config.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env file
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"Loaded environment from: {env_path}")
    print()

from src.halo.agents.model_config import ModelConfig


def main():
    """Show Gemini model configuration from environment."""
    print("=" * 60)
    print("Gemini Model Configuration")
    print("=" * 60)
    print()

    # Show environment variables
    print("Environment Variables:")
    print("-" * 60)

    env_vars = [
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "GEMINI_MODELS",
        "GEMINI_FALLBACK_MODEL",
        "GEMINI_VALIDATOR_MODEL",
        "GEMINI_TEMPLATE_MODEL",
    ]

    for var in env_vars:
        value = os.getenv(var)
        if value:
            # Hide API key for security
            if var == "GEMINI_API_KEY":
                display_value = f"{value[:10]}..." if len(value) > 10 else "***"
            else:
                display_value = value

            print(f"  {var:30s} = {display_value}")
        else:
            print(f"  {var:30s} = (not set)")

    print()

    # Load and show configuration
    print("Resolved Configuration:")
    print("-" * 60)

    try:
        config = ModelConfig.from_env()
        print(config)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return 1

    print()

    # Show cost estimate
    print("Cost Estimate:")
    print("-" * 60)

    # Rough estimates based on model pricing
    cost_per_model = {
        "gemini-2.0-flash-exp": 0.02,
        "gemini-1.5-flash": 0.01,
        "gemini-1.5-pro": 0.05,
    }

    # Each role is used roughly:
    # - Fallback: 1-5% of commands (low usage)
    # - Validator: 10-30% during bootstrapping (medium usage)
    # - Template: 1-5 times per template (very low usage)

    usage_weight = {
        "fallback": 0.50,  # 50% of Gemini API calls
        "validator": 0.45,  # 45% of API calls
        "template": 0.05,  # 5% of API calls
    }

    total_cost = (
        cost_per_model.get(config.fallback_model, 0.02) * usage_weight["fallback"]
        + cost_per_model.get(config.validator_model, 0.02) * usage_weight["validator"]
        + cost_per_model.get(config.template_model, 0.02) * usage_weight["template"]
    )

    print(f"  Estimated cost per month: ${total_cost:.2f}")
    print(f"  Estimated cost per year:  ${total_cost * 12:.2f}")
    print()
    print("  (Based on typical usage: ~200 commands/month, 20% reach Gemini)")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
