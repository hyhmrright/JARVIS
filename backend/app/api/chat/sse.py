"""SSE encoding helpers for the chat streaming API."""

import json
import uuid

from langchain_core.messages import ToolMessage


def format_sse(payload: dict) -> str:
    """Encode a dict as an SSE data line."""
    return "data: " + json.dumps(payload) + "\n\n"


def sse_events_from_chunk(
    chunk: dict,
    full_content: str,
    human_msg_id: uuid.UUID | None = None,
) -> tuple[list[str], str]:
    """Convert a LangGraph stream chunk into SSE event lines.

    Returns (list_of_sse_lines, updated_full_content).
    """
    events: list[str] = []

    if "approval" in chunk:
        pending = chunk["approval"]["pending_tool_call"]
        if pending is not None:
            events.append(
                format_sse(
                    {
                        "type": "approval_required",
                        "tool": pending["name"],
                        "args": pending.get("args", {}),
                        "human_msg_id": str(human_msg_id) if human_msg_id else None,
                    }
                )
            )
    elif "llm" in chunk:
        ai_msg = chunk["llm"]["messages"][-1]
        if hasattr(ai_msg, "tool_calls") and ai_msg.tool_calls:
            for tc in ai_msg.tool_calls:
                events.append(
                    format_sse(
                        {
                            "type": "tool_start",
                            "tool": tc["name"],
                            "args": tc.get("args", {}),
                        }
                    )
                )

        new_content = ai_msg.content
        delta = new_content[len(full_content) :]
        full_content = new_content
        if delta:
            events.append(
                format_sse({"type": "delta", "delta": delta, "content": full_content})
            )
    elif "tools" in chunk:
        for tm in chunk["tools"]["messages"]:
            events.append(
                format_sse(
                    {
                        "type": "tool_end",
                        "tool": tm.name,
                        "result_preview": tm.content[:200],
                    }
                )
            )
    return events, full_content


def tool_call_signature(tool_calls: list[dict]) -> tuple[str, ...]:
    return tuple(
        str(tc.get("id") or f"{tc.get('name', 'tool')}_{idx}")
        for idx, tc in enumerate(tool_calls)
    )


def serialize_tool_message(tool_msg: ToolMessage) -> str:
    return json.dumps(
        {
            "tool_call_id": getattr(tool_msg, "tool_call_id", None),
            "name": tool_msg.name,
            "content": tool_msg.content,
        }
    )


def extract_token_counts(ai_msg: object | None) -> tuple[int, int]:
    """Return (tokens_in, tokens_out) from an AIMessage's usage_metadata."""
    if ai_msg is None:
        return 0, 0
    meta = getattr(ai_msg, "usage_metadata", None)
    if not meta:
        return 0, 0
    return meta.get("input_tokens", 0) or 0, meta.get("output_tokens", 0) or 0
