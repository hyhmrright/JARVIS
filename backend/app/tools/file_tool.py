import pathlib

from langchain_core.tools import tool


@tool
def read_file(path: str, user_id: str) -> str:
    """Read the content of a user private file."""
    safe_path = pathlib.Path(f"/tmp/jarvis/{user_id}") / pathlib.Path(path).name
    if not safe_path.exists():
        return f"File not found: {path}"
    return safe_path.read_text(encoding="utf-8")


@tool
def write_file(path: str, content: str, user_id: str) -> str:
    """Write content to a user private file."""
    dir_path = pathlib.Path(f"/tmp/jarvis/{user_id}")
    dir_path.mkdir(parents=True, exist_ok=True)
    safe_path = dir_path / pathlib.Path(path).name
    safe_path.write_text(content, encoding="utf-8")
    return f"File written: {path}"
