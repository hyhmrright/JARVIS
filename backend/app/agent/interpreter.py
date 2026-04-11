"""Logic for interpreting LangGraph stream chunks into standardized events."""

import uuid
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

from app.agent.protocol import (
    AgentEvent,
    TextDeltaEvent,
    ToolEndEvent,
    ToolStartEvent,
)


def events_from_chunk(
    chunk: dict,
    full_content: str,
    human_msg_id: uuid.UUID | None = None,
) -> tuple[list[AgentEvent], str]:
    """Convert a LangGraph stream chunk into protocol AgentEvent objects."""
    if "approval" in chunk:
        return _handle_approval(chunk, human_msg_id), full_content
    if "llm" in chunk:
        return _handle_llm(chunk, full_content)
    if "tools" in chunk:
        return _handle_tools(chunk), full_content
    return [], full_content


def _handle_approval(chunk: dict, human_msg_id: uuid.UUID | None) -> list[AgentEvent]:
    pending = chunk["approval"]["pending_tool_call"]
    if pending is not None:
        return [
            AgentEvent(
                type="approval_required",
                metadata={
                    "tool": pending["name"],
                    "args": pending.get("args", {}),
                    "human_msg_id": str(human_msg_id) if human_msg_id else None,
                },
            )
        ]
    return []


def _handle_llm(chunk: dict, full_content: str) -> tuple[list[AgentEvent], str]:
    events: list[AgentEvent] = []
    ai_msg = chunk["llm"]["messages"][-1]
    if not isinstance(ai_msg, AIMessage):
        return [], full_content

    if hasattr(ai_msg, "tool_calls") and ai_msg.tool_calls:
        for tc in ai_msg.tool_calls:
            events.append(ToolStartEvent(tool=tc["name"], args=tc.get("args", {})))

    new_content = str(ai_msg.content)
    delta = new_content[len(full_content) :]
    if delta:
        full_content = new_content
        events.append(TextDeltaEvent(delta=delta))
    return events, full_content


def _handle_tools(chunk: dict) -> list[AgentEvent]:
    events: list[AgentEvent] = []
    for tm in chunk["tools"]["messages"]:
        if isinstance(tm, ToolMessage):
            events.append(
                ToolEndEvent(
                    tool=tm.name or "tool",
                    result_preview=str(tm.content)[:200],
                )
            )
    return events


def extract_token_counts(ai_msg: Any) -> tuple[int, int]:
    """Return (tokens_in, tokens_out) from an AIMessage's usage_metadata."""
    if ai_msg is None:
        return 0, 0
    meta = getattr(ai_msg, "usage_metadata", None)
    if not meta:
        return 0, 0
    return meta.get("input_tokens", 0) or 0, meta.get("output_tokens", 0) or 0
