"""Agent streaming protocol models.

Defines the structure of events emitted by the AgentEngine during
streaming execution, isolating internal engine state from external
transport layers (SSE/WebSockets).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentEvent(BaseModel):
    """Base model for all agent streaming events."""

    type: str
    timestamp: float = Field(default_factory=lambda: __import__("time").time())


class TextDeltaEvent(AgentEvent):
    """Incremental text update from the LLM."""

    type: Literal["delta"] = "delta"
    delta: str


class RoutingEvent(AgentEvent):
    """Indicates which expert or mode the agent has selected."""

    type: Literal["routing"] = "routing"
    agent: str


class ToolUseEvent(AgentEvent):
    """Indicates a tool is being called."""

    type: Literal["tool_use"] = "tool_use"
    tool_name: str
    tool_input: Any | None = None


class ToolResultEvent(AgentEvent):
    """Result of a tool execution."""

    type: Literal["tool_result"] = "tool_result"
    tool_name: str
    output: str


class ErrorEvent(AgentEvent):
    """Indicates a non-terminal or terminal error during streaming."""

    type: Literal["error"] = "error"
    content: str


class HumanMessageSavedEvent(AgentEvent):
    """Confirmation that the user message was persisted to DB."""

    type: Literal["human_msg_saved"] = "human_msg_saved"
    human_msg_id: str


class FinalResultEvent(AgentEvent):
    """The complete final answer (optional, usually sent as deltas)."""

    type: Literal["final_result"] = "final_result"
    content: str
