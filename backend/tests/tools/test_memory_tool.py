"""Tests for local memory file tools."""

from unittest.mock import patch

import pytest

from app.tools.memory_tool import read_memory_file, search_local_memory

# ---------------------------------------------------------------------------
# search_local_memory
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_search_local_memory_no_directory(tmp_path):
    """Returns 'No local memory found.' when memory dir does not exist."""
    nonexistent = tmp_path / "does_not_exist"
    with patch("app.tools.memory_tool.settings") as mock_settings:
        mock_settings.memory_sync_dir = str(nonexistent)
        result = await search_local_memory.ainvoke({"query": "anything"})
    assert "No local memory found" in result


@pytest.mark.anyio
async def test_search_local_memory_no_matches(tmp_path):
    """Returns a 'no matches' message when query is absent from all files."""
    (tmp_path / "note.md").write_text("hello world")
    with patch("app.tools.memory_tool.settings") as mock_settings:
        mock_settings.memory_sync_dir = str(tmp_path)
        result = await search_local_memory.ainvoke({"query": "xyzzy_not_here"})
    assert "No matches found" in result


@pytest.mark.anyio
async def test_search_local_memory_finds_match(tmp_path):
    """Returns a snippet when the query appears in a memory file."""
    (tmp_path / "memory.md").write_text("User prefers dark mode theme settings.")
    with patch("app.tools.memory_tool.settings") as mock_settings:
        mock_settings.memory_sync_dir = str(tmp_path)
        result = await search_local_memory.ainvoke({"query": "dark mode"})
    assert "dark mode" in result


@pytest.mark.anyio
async def test_search_local_memory_returns_string(tmp_path):
    """Result must always be a string (not an exception)."""
    with patch("app.tools.memory_tool.settings") as mock_settings:
        mock_settings.memory_sync_dir = str(tmp_path)
        result = await search_local_memory.ainvoke({"query": "test"})
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# read_memory_file
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_read_memory_file_not_found(tmp_path):
    """Returns access denied message when the file does not exist."""
    with patch("app.tools.memory_tool.settings") as mock_settings:
        mock_settings.memory_sync_dir = str(tmp_path)
        result = await read_memory_file.ainvoke({"filename": "ghost.md"})
    assert "not found" in result.lower() or "denied" in result.lower()


@pytest.mark.anyio
async def test_read_memory_file_path_traversal_blocked(tmp_path):
    """Path traversal attempts must be blocked."""
    with patch("app.tools.memory_tool.settings") as mock_settings:
        mock_settings.memory_sync_dir = str(tmp_path)
        result = await read_memory_file.ainvoke({"filename": "../etc/passwd"})
    assert "not found" in result.lower() or "denied" in result.lower()


@pytest.mark.anyio
async def test_read_memory_file_success(tmp_path):
    """Returns file content when the file exists inside the memory dir."""
    content = "# Memory\nUser likes Python."
    (tmp_path / "notes.md").write_text(content)
    with patch("app.tools.memory_tool.settings") as mock_settings:
        mock_settings.memory_sync_dir = str(tmp_path)
        result = await read_memory_file.ainvoke({"filename": "notes.md"})
    assert "Python" in result
