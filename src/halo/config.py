"""Configuration loader for Halo.

Loads domain-specific configuration (home vs care) from JSON files.
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class HaloConfig:
    """Configuration for a Halo instance.

    Can be loaded from:
    1. JSON file (config/home.json, config/care.json)
    2. Environment variables
    3. Programmatically
    """

    def __init__(self, config_dict: dict):
        self.raw = config_dict
        self.domain = config_dict.get("domain", "unknown")
        self.name = config_dict.get("name", "Halo")
        self.description = config_dict.get("description", "")
        self.store_path = config_dict.get("store_path", "data/halo")
        self.policy = config_dict.get("policy", "threshold")

        # Model config
        self.model = config_dict.get("model", {})

        # Classifiers
        self.classifiers = config_dict.get("classifiers", {})

        # Observability
        self.observability = config_dict.get("observability", {})

        # Tools
        self.tools = config_dict.get("tools", {})

        # Context
        self.context = config_dict.get("context", {})

        # Care-specific
        self.care_modes = config_dict.get("care_modes", {})

    @classmethod
    def from_file(cls, config_path: str) -> "HaloConfig":
        """Load configuration from JSON file.

        Args:
            config_path: Path to JSON config file

        Returns:
            HaloConfig instance
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(path) as f:
            config_dict = json.load(f)

        logger.info(f"Loaded config from {config_path}: {config_dict.get('name')}")
        return cls(config_dict)

    @classmethod
    def for_domain(cls, domain: str) -> "HaloConfig":
        """Load configuration for a specific domain.

        Args:
            domain: "home", "care", etc.

        Returns:
            HaloConfig instance
        """
        # Try to find config file
        config_path = Path(f"config/{domain}.json")
        if not config_path.exists():
            # Fallback to default config
            logger.warning(f"No config found for domain '{domain}', using defaults")
            return cls.default_config(domain)

        return cls.from_file(str(config_path))

    @classmethod
    def default_config(cls, domain: str = "home") -> "HaloConfig":
        """Create default configuration.

        Args:
            domain: Domain name

        Returns:
            HaloConfig with default values
        """
        return cls(
            {
                "domain": domain,
                "name": f"Halo {domain.capitalize()}",
                "store_path": f"data/halo/{domain}",
                "policy": "care" if domain == "care" else "threshold",
                "model": {"backend": "qwen"},
                "classifiers": {
                    "enable_embeddings": True,
                    "enable_spacy": True,
                },
                "observability": {
                    "enable_telemetry": True,
                    "enable_learning": True,
                },
                "tools": {},
                "context": {
                    "load_soul_on_init": True,
                },
            }
        )

    def get_tool_threshold(self, tool_name: str) -> float:
        """Get confidence threshold for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Confidence threshold (default 0.80)
        """
        tool_config = self.tools.get(tool_name, {})
        return tool_config.get("confidence_threshold", 0.80)

    def is_tool_enabled(self, tool_name: str) -> bool:
        """Check if a tool is enabled.

        Args:
            tool_name: Name of the tool

        Returns:
            True if enabled (default True)
        """
        tool_config = self.tools.get(tool_name, {})
        return tool_config.get("enabled", True)

    def is_tool_critical(self, tool_name: str) -> bool:
        """Check if a tool is critical (requires higher confidence).

        Args:
            tool_name: Name of the tool

        Returns:
            True if critical (default False)
        """
        tool_config = self.tools.get(tool_name, {})
        return tool_config.get("critical", False)

    def __str__(self) -> str:
        return f"HaloConfig({self.name}, domain={self.domain}, policy={self.policy})"
