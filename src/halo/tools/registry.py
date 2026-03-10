"""Tool registry with JSON Schema definitions."""

from dataclasses import dataclass
from typing import Callable
from .handlers import light_handler, climate_handler, blinds_handler, status_handler


@dataclass
class Tool:
    """Function tool definition."""

    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: Callable
    is_async: bool = True


# Tool definitions following OpenAI function calling format
TOOLS = [
    Tool(
        name="light_control",
        description="Control de luces: encender, apagar, ajustar brillo",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["on", "off", "dim", "brightness"],
                    "description": "Acción a realizar",
                },
                "room": {"type": "string", "description": "Habitación (ej: sala, cocina)"},
                "level": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Nivel de brillo 0-100 (opcional para dim/brightness)",
                },
            },
            "required": ["action", "room"],
        },
        handler=light_handler,
    ),
    Tool(
        name="climate_control",
        description="Control de clima y temperatura",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["set_temp", "mode", "status"],
                    "description": "Acción a realizar",
                },
                "room": {
                    "type": "string",
                    "description": "Habitación (opcional, por defecto toda la casa)",
                },
                "temperature": {
                    "type": "number",
                    "description": "Temperatura objetivo en Celsius",
                },
                "mode": {
                    "type": "string",
                    "enum": ["heat", "cool", "auto", "off"],
                    "description": "Modo de climatización",
                },
            },
            "required": ["action"],
        },
        handler=climate_handler,
    ),
    Tool(
        name="blinds_control",
        description="Control de persianas y cortinas",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["open", "close", "position"],
                    "description": "Acción a realizar",
                },
                "room": {"type": "string", "description": "Habitación"},
                "position": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Posición 0-100 (0=cerrada, 100=abierta)",
                },
            },
            "required": ["action", "room"],
        },
        handler=blinds_handler,
    ),
    Tool(
        name="home_status",
        description="Consulta estado del hogar, habitaciones o dispositivos",
        parameters={
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["all", "room", "device"],
                    "description": "Alcance de la consulta",
                },
                "room": {
                    "type": "string",
                    "description": "Habitación (para scope=room o device)",
                },
                "device": {
                    "type": "string",
                    "description": "Dispositivo específico (para scope=device)",
                },
            },
        },
        handler=status_handler,
    ),
]


def get_all_tools() -> list[Tool]:
    """Get all registered tools.

    Returns:
        List of all Tool instances
    """
    return TOOLS


def get_tool(name: str) -> Tool | None:
    """Get tool by name.

    Args:
        name: Tool name

    Returns:
        Tool instance or None if not found
    """
    for tool in TOOLS:
        if tool.name == name:
            return tool
    return None


def get_tools_schema() -> list[dict]:
    """Get JSON Schema representation of all tools.

    Returns:
        List of tool schemas compatible with OpenAI function calling format
    """
    return [
        {"name": tool.name, "description": tool.description, "parameters": tool.parameters}
        for tool in TOOLS
    ]
