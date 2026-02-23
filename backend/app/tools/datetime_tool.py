from datetime import UTC, datetime

from langchain_core.tools import tool


@tool
def get_datetime() -> str:
    """Get the current date and time (UTC)."""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
