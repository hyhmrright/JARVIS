"""File operations tool with user workspace isolation."""

import pathlib

from langchain_core.tools import BaseTool, tool

_MAX_FILE_SIZE = 1_000_000  # 1 MB


def _format_listing(directory: pathlib.Path) -> str:
    """Format a directory listing as aligned text."""
    entries = sorted(directory.iterdir())
    if not entries:
        return "(empty directory)"
    lines = []
    for entry in entries:
        kind = "dir" if entry.is_dir() else "file"
        size = entry.stat().st_size if entry.is_file() else 0
        lines.append(f"  {kind}  {size:>8}  {entry.name}")
    return "\n".join(lines)


def _safe_resolve(workspace: pathlib.Path, path: str) -> pathlib.Path | None:
    """Resolve a user-provided path within the workspace.

    Returns None if the resolved path escapes the workspace.
    """
    resolved = (workspace / path).resolve()
    try:
        resolved.relative_to(workspace.resolve())
    except ValueError:
        return None
    return resolved


def create_file_tools(user_id: str) -> list[BaseTool]:
    """Create file operation tools scoped to a user's workspace."""
    workspace = pathlib.Path(f"/tmp/jarvis/{user_id}")

    @tool
    def file_read(path: str) -> str:
        """Read the content of a file in your workspace.

        Args:
            path: File name or relative path within workspace.
        """
        safe_path = _safe_resolve(workspace, path)
        if safe_path is None:
            return f"Blocked: path '{path}' escapes workspace."
        if not safe_path.exists():
            return f"File not found: {path}"
        if safe_path.stat().st_size > _MAX_FILE_SIZE:
            return f"File too large (>{_MAX_FILE_SIZE} bytes): {path}"
        return safe_path.read_text(encoding="utf-8")

    @tool
    def file_write(path: str, content: str) -> str:
        """Write content to a file in your workspace.

        Args:
            path: File name or relative path within workspace.
            content: Content to write.
        """
        safe_path = _safe_resolve(workspace, path)
        if safe_path is None:
            return f"Blocked: path '{path}' escapes workspace."
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(content, encoding="utf-8")
        return f"File written: {safe_path.relative_to(workspace.resolve())}"

    @tool
    def file_list(directory: str = ".") -> str:
        """List files in your workspace directory.

        Args:
            directory: Subdirectory to list (default: workspace root).
        """
        safe_path = _safe_resolve(workspace, directory)
        if safe_path is None:
            return f"Blocked: path '{directory}' escapes workspace."
        if not safe_path.exists():
            return f"Directory not found: {directory}"
        return _format_listing(safe_path)

    return [file_read, file_write, file_list]
