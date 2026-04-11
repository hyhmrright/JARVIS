"""SSE encoding helpers for the chat streaming API."""

import json
import uuid
from typing import Any

from app.agent.protocol import (
    AgentEvent,
    TextDeltaEvent,
    ToolResultEvent,
    ToolUseEvent,
)


def format_sse(event: AgentEvent | dict[str, Any]) -> str:
    """Encode an AgentEvent or dict as an SSE data line."""
    if isinstance(event, AgentEvent):
        return "data: " + event.model_dump_json() + "\n\n"
    return "data: " + json.dumps(event) + "\n\n"


def sse_events_from_chunk(
    chunk: dict,
    full_content: str,
    human_msg_id: uuid.UUID | None = None,
) -> tuple[list[AgentEvent], str]:
    """Convert a LangGraph stream chunk into protocol AgentEvent objects.

    Returns (list_of_events, updated_full_content).
    """
    events: list[AgentEvent] = []

    if "approval" in chunk:
        pending = chunk["approval"]["pending_tool_call"]
        if pending is not None:
            # Note: We can add an ApprovalRequiredEvent to protocol.py if needed
            events.append(
                AgentEvent(
                    type="approval_required",
                    tool=pending["name"],
                    args=pending.get("args", {}),
                    human_msg_id=str(human_msg_id) if human_msg_id else None,
                )
            )
    elif "llm" in chunk:
        ai_msg = chunk["llm"]["messages"][-1]
        if hasattr(ai_msg, "tool_calls") and ai_msg.tool_calls:
            for tc in ai_msg.tool_calls:
                events.append(
                    ToolUseEvent(
                        tool_name=tc["name"],
                        tool_input=tc.get("args", {}),
                    )
                )

        new_content = ai_msg.content
        delta = new_content[len(full_content) :]
        if delta:
            full_content = new_content
            events.append(TextDeltaEvent(delta=delta))

    elif "tools" in chunk:
        for tm in chunk["tools"]["messages"]:
            events.append(
                ToolResultEvent(
                    tool_name=tm.name or "tool",
                    output=str(tm.content)[:500],  # Preview
                )
            )
    return events, full_content


def extract_token_counts(ai_msg: object | None) -> tuple[int, int]:
    """Return (tokens_in, tokens_out) from an AIMessage's usage_metadata."""
    if ai_msg is None:
        return 0, 0
    meta = getattr(ai_msg, "usage_metadata", None)
    if not meta:
        return 0, 0
    return meta.get("input_tokens", 0) or 0, meta.get("output_tokens", 0) or 0
