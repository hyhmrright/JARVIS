"""SSE encoding helpers for the chat streaming API."""

import json
from typing import Any

from app.agent.protocol import AgentEvent


def format_sse(event: AgentEvent | dict[str, Any]) -> str:
    """Encode an AgentEvent or dict as an SSE data line."""
    if isinstance(event, AgentEvent):
        return "data: " + event.model_dump_json() + "\n\n"
    return "data: " + json.dumps(event) + "\n\n"
