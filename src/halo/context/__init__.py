"""Context management for conversations."""

from .manager import ConversationContext
from .levels import (
    CommandContext,
    FlowContext,
    SessionContext,
    EnvironmentContext,
    SoulContext,
    HaloContext,
    ContextLoader,
)
from .soul_reader import SoulReader

__all__ = [
    # Legacy
    "ConversationContext",
    # New multi-level context
    "CommandContext",
    "FlowContext",
    "SessionContext",
    "EnvironmentContext",
    "SoulContext",
    "HaloContext",
    "ContextLoader",
    "SoulReader",
]
