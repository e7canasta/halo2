"""Shared Pydantic models for API."""

from pydantic import BaseModel, Field
from typing import Literal


class Message(BaseModel):
    """Chat message."""

    role: Literal["system", "user", "assistant"]
    content: str


class ToolCall(BaseModel):
    """Tool call representation."""

    tool: str = Field(..., description="Tool name")
    parameters: dict = Field(default_factory=dict, description="Tool parameters")


class CommandResult(BaseModel):
    """Result of a command execution."""

    status: Literal["completed", "pending", "error"]
    message: str = Field(default="", description="Human-readable message")
    device_state: dict = Field(default_factory=dict, description="Updated device state")
    tool_call: ToolCall | None = Field(None, description="Tool call that was executed")


class TokenUsage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class CommandRequest(BaseModel):
    """Request for command endpoint."""

    message: str
    context: dict = Field(default_factory=dict, description="Conversation context")
    session_id: str | None = Field(None, description="Session identifier (optional)")


class CommandResponse(BaseModel):
    """Response from command endpoint."""

    result: CommandResult
    context: dict = Field(default_factory=dict, description="Updated context")
    usage: TokenUsage
    agency_trace: dict | None = Field(None, description="Decision trace (agencia del sistema)")
