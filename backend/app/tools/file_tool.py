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

    ``workspace`` must already be resolved (no symlinks, absolute).
    Returns None if the resolved path escapes the workspace, if resolution
    fails (e.g. broken symlink chains), or if the path is a dangling or
    circular symlink (which ``resolve(strict=False)`` silently accepts).
    """
    candidate = workspace / path
    try:
        resolved = candidate.resolve()
        resolved.relative_to(workspace)
    except (ValueError, OSError):
        return None
    # resolve(strict=False) does not raise for circular/dangling symlinks on
    # Python 3.13 — it returns the link path unchanged.  Reject them explicitly.
    if candidate.is_symlink() and not candidate.exists():
        return None
    return resolved


def create_file_tools(user_id: str) -> list[BaseTool]:  # noqa: C901
    """Create file operation tools scoped to a user's workspace.

    Note: workspace lives under /tmp which is not persistent across
    container restarts. Files will be lost on restart.
    """
    workspace = pathlib.Path(f"/tmp/jarvis/{user_id}")
    workspace.mkdir(parents=True, exist_ok=True)
    workspace = workspace.resolve()  # Resolve once; reused for all checks

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
        return f"File written: {safe_path.relative_to(workspace)}"

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

    @tool
    def file_delete(path: str) -> str:
        """Delete a file or empty directory in your workspace.

        Args:
            path: File name or relative path within workspace.
        """
        safe_path = _safe_resolve(workspace, path)
        if safe_path is None:
            return f"Blocked: path '{path}' escapes workspace."
        if not safe_path.exists():
            return f"File or directory not found: {path}"
        try:
            if safe_path.is_file() or safe_path.is_symlink():
                safe_path.unlink()
            else:
                safe_path.rmdir()
            return f"Deleted: {path}"
        except OSError as e:
            return f"Failed to delete {path}: {e}"

    @tool
    def file_search(pattern: str, directory: str = ".") -> str:
        """Search for files matching a glob pattern in your workspace.

        Args:
            pattern: Glob pattern (e.g., '*.py', '**/*.txt').
            directory: Subdirectory to search in (default: workspace root).
        """
        safe_dir = _safe_resolve(workspace, directory)
        if safe_dir is None:
            return f"Blocked: path '{directory}' escapes workspace."
        if not safe_dir.exists():
            return f"Directory not found: {directory}"

        matches = (
            list(safe_dir.rglob(pattern))
            if "**" in pattern
            else list(safe_dir.glob(pattern))
        )
        if not matches:
            return f"No files matched pattern: {pattern}"

        lines = [f"  {m.relative_to(workspace)}" for m in matches[:100]]
        if len(matches) > 100:
            lines.append(f"  ... and {len(matches) - 100} more")
        return "\n".join(lines)

    return [file_read, file_write, file_list, file_delete, file_search]
