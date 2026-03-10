"""Semantic memory for conversational context.

Defines which parameters should be tracked and inherited across turns,
and how to resolve anaphora (pronouns like "la", "lo", "eso").

Philosophy: "El contexto es implícito en la conversación humana"
"""

from typing import Optional


# Hardware tools that require conservative handling
HARDWARE_TOOLS = ["light_control", "climate_control", "blinds_control"]

# Query tools that can be more permissive
QUERY_TOOLS = ["home_status"]


# Semantic hierarchy: which parameters are tracked for which tools
SEMANTIC_HIERARCHY = {
    # Parameter: (memory_key, tools_that_use_it, is_required)
    "room": {
        "memory_key": "last_room",
        "tools": ["light_control", "climate_control", "blinds_control", "home_status"],
        "required_for_hardware": True,  # Hardware needs room, queries can default to "all"
    },
    "temperature": {
        "memory_key": "last_temperature",
        "tools": ["climate_control"],
        "required_for_hardware": False,  # Can be inferred from action
    },
    "brightness": {
        "memory_key": "last_brightness",
        "tools": ["light_control"],
        "required_for_hardware": False,
    },
    "action": {
        "memory_key": "last_action",
        "tools": ["light_control", "climate_control", "blinds_control"],
        "required_for_hardware": True,
    },
    "position": {
        "memory_key": "last_position",
        "tools": ["blinds_control"],
        "required_for_hardware": False,
    },
    "mode": {
        "memory_key": "last_mode",
        "tools": ["climate_control"],
        "required_for_hardware": False,
    },
}


# Anaphora resolution patterns (Spanish pronouns)
ANAPHORA_PATTERNS = {
    # Pronoun: possible tool types (None = use last_tool)
    "la": {
        "tools": ["light_control"],  # "apágala" → luz
        "gender": "feminine",
    },
    "lo": {
        "tools": ["climate_control", "blinds_control"],  # "bájalo" → temperatura/persiana
        "gender": "masculine",
    },
    "las": {
        "tools": ["light_control"],  # "apágalas" → luces (plural)
        "gender": "feminine",
        "plural": True,
    },
    "los": {
        "tools": ["climate_control", "blinds_control"],
        "gender": "masculine",
        "plural": True,
    },
    "eso": {
        "tools": None,  # "haz eso" → última acción (cualquier tool)
        "gender": "neutral",
    },
    "esa": {
        "tools": None,  # "esa" → última cosa mencionada
        "gender": "feminine",
    },
    "ese": {
        "tools": None,
        "gender": "masculine",
    },
}


# Action inference from verbs when action is implicit
ACTION_VERBS = {
    # Verb patterns: (action, applicable_tools)
    "enciende": ("on", ["light_control"]),
    "prende": ("on", ["light_control"]),
    "apaga": ("off", ["light_control", "climate_control"]),
    "atenua": ("dim", ["light_control"]),
    "sube": ("increase", ["climate_control", "blinds_control"]),
    "baja": ("decrease", ["climate_control", "blinds_control"]),
    "abre": ("open", ["blinds_control"]),
    "cierra": ("close", ["blinds_control"]),
}


def is_hardware_tool(tool_name: str) -> bool:
    """Check if a tool controls hardware."""
    return tool_name in HARDWARE_TOOLS


def is_query_tool(tool_name: str) -> bool:
    """Check if a tool is a query (read-only)."""
    return tool_name in QUERY_TOOLS


def get_param_memory_key(param_name: str) -> Optional[str]:
    """Get the memory key for a parameter.

    Args:
        param_name: Parameter name (e.g., "room", "temperature")

    Returns:
        Memory key (e.g., "last_room") or None if not tracked
    """
    param_info = SEMANTIC_HIERARCHY.get(param_name)
    if param_info:
        return param_info["memory_key"]
    return None


def get_tools_for_param(param_name: str) -> list[str]:
    """Get list of tools that use a parameter.

    Args:
        param_name: Parameter name

    Returns:
        List of tool names, or empty list if not tracked
    """
    param_info = SEMANTIC_HIERARCHY.get(param_name)
    if param_info:
        return param_info["tools"]
    return []


def is_param_required_for_hardware(param_name: str) -> bool:
    """Check if a parameter is required for hardware tools.

    Args:
        param_name: Parameter name

    Returns:
        True if required for hardware execution
    """
    param_info = SEMANTIC_HIERARCHY.get(param_name)
    if param_info:
        return param_info.get("required_for_hardware", False)
    return False


def detect_anaphora(user_input: str) -> Optional[dict]:
    """Detect anaphora (pronouns) in user input.

    Args:
        user_input: User's message

    Returns:
        dict with detected anaphora info or None
        Example: {"pronoun": "la", "tools": ["light_control"], "gender": "feminine"}
    """
    words = user_input.lower().split()

    for word in words:
        # Check for exact pronoun matches
        if word in ANAPHORA_PATTERNS:
            pattern = ANAPHORA_PATTERNS[word]
            return {
                "pronoun": word,
                "tools": pattern["tools"],
                "gender": pattern["gender"],
                "plural": pattern.get("plural", False),
            }

        # Check for suffixed pronouns (e.g., "apágala", "bájalo")
        for pronoun, pattern in ANAPHORA_PATTERNS.items():
            if word.endswith(pronoun):
                return {
                    "pronoun": pronoun,
                    "tools": pattern["tools"],
                    "gender": pattern["gender"],
                    "plural": pattern.get("plural", False),
                    "verb": word[:-len(pronoun)],  # Extract verb
                }

    return None


def infer_action_from_verb(user_input: str, tool_name: str) -> Optional[str]:
    """Infer action from verb in user input.

    Args:
        user_input: User's message
        tool_name: Tool being used

    Returns:
        Action name or None
    """
    words = user_input.lower().split()

    for word in words:
        for verb, (action, applicable_tools) in ACTION_VERBS.items():
            if word.startswith(verb) and tool_name in applicable_tools:
                return action

    return None
