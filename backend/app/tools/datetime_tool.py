from datetime import datetime, timezone

from langchain_core.tools import tool


@tool
def get_datetime() -> str:
    """Get the current date and time (UTC)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
