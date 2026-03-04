"""Tests for file operations tool with user workspace isolation."""

import pathlib
import shutil
from collections.abc import Iterator

import pytest

from app.tools.file_tool import create_file_tools


@pytest.fixture()
def user_workspace(tmp_path: pathlib.Path) -> Iterator[pathlib.Path]:
    """Create a temporary workspace directory at a fixed path for testing.

    Uses /tmp/jarvis/test-ft-<id> to match the real workspace path pattern,
    cleaning up after each test.
    """
    ws = pathlib.Path(f"/tmp/jarvis/test-ft-{id(tmp_path)}")
    ws.mkdir(parents=True, exist_ok=True)
    yield ws
    shutil.rmtree(ws, ignore_errors=True)


def _tools(workspace: pathlib.Path) -> dict:
    """Create file tools and return them as a name-keyed dict."""
    user_id = workspace.name
    tools = create_file_tools(user_id)
    return {t.name: t for t in tools}


class TestCreateFileTools:
    """Tests for the create_file_tools factory."""

    def test_returns_five_tools(self) -> None:
        tools = create_file_tools("test-user")
        assert len(tools) == 5

    def test_tool_names(self) -> None:
        tools = create_file_tools("test-user")
        names = {t.name for t in tools}
        assert names == {"file_read", "file_write", "file_list", "file_delete", "file_search"}


class TestFileWrite:
    """Tests for file_write tool."""

    def test_write_creates_file(self, user_workspace: pathlib.Path) -> None:
        tools = _tools(user_workspace)
        result = tools["file_write"].invoke(
            {"path": "hello.txt", "content": "hello world"}
        )
        assert "File written: hello.txt" in result
        assert (user_workspace / "hello.txt").read_text() == "hello world"


class TestFileRead:
    """Tests for file_read tool."""

    def test_read_existing_file(self, user_workspace: pathlib.Path) -> None:
        (user_workspace / "data.txt").write_text("some data", encoding="utf-8")
        tools = _tools(user_workspace)
        result = tools["file_read"].invoke({"path": "data.txt"})
        assert result == "some data"

    def test_read_missing_file(self, user_workspace: pathlib.Path) -> None:
        tools = _tools(user_workspace)
        result = tools["file_read"].invoke({"path": "nope.txt"})
        assert "File not found" in result

    def test_read_large_file(self, user_workspace: pathlib.Path) -> None:
        (user_workspace / "big.txt").write_text("x" * 2_000_000, encoding="utf-8")
        tools = _tools(user_workspace)
        result = tools["file_read"].invoke({"path": "big.txt"})
        assert "File too large" in result


class TestFileList:
    """Tests for file_list tool."""

    def test_list_files(self, user_workspace: pathlib.Path) -> None:
        (user_workspace / "a.txt").write_text("aaa", encoding="utf-8")
        (user_workspace / "b.txt").write_text("bbb", encoding="utf-8")
        tools = _tools(user_workspace)
        result = tools["file_list"].invoke({"directory": "."})
        assert "a.txt" in result
        assert "b.txt" in result
        assert "file" in result

    def test_list_empty_directory(self, user_workspace: pathlib.Path) -> None:
        tools = _tools(user_workspace)
        result = tools["file_list"].invoke({"directory": "."})
        assert result == "(empty directory)"

    def test_list_nonexistent_directory(self, user_workspace: pathlib.Path) -> None:
        tools = _tools(user_workspace)
        result = tools["file_list"].invoke({"directory": "nonexistent"})
        assert "Directory not found" in result


class TestPathTraversal:
    """Tests for path traversal protection."""

    def test_traversal_blocked_on_read(self, user_workspace: pathlib.Path) -> None:
        tools = _tools(user_workspace)
        result = tools["file_read"].invoke({"path": "../../etc/passwd"})
        assert "blocked" in result.lower()

    def test_traversal_blocked_on_write(self, user_workspace: pathlib.Path) -> None:
        tools = _tools(user_workspace)
        result = tools["file_write"].invoke(
            {"path": "../../etc/evil.txt", "content": "bad"}
        )
        assert "blocked" in result.lower()

    def test_subdirectory_write_allowed(self, user_workspace: pathlib.Path) -> None:
        tools = _tools(user_workspace)
        result = tools["file_write"].invoke(
            {"path": "subdir/file.txt", "content": "nested"}
        )
        assert "File written" in result
        assert (user_workspace / "subdir" / "file.txt").read_text() == "nested"

    def test_subdirectory_read_allowed(self, user_workspace: pathlib.Path) -> None:
        sub = user_workspace / "subdir"
        sub.mkdir()
        (sub / "data.txt").write_text("nested data", encoding="utf-8")
        tools = _tools(user_workspace)
        result = tools["file_read"].invoke({"path": "subdir/data.txt"})
        assert result == "nested data"


class TestFileDelete:
    """Tests for file_delete tool."""

    def test_delete_file(self, user_workspace: pathlib.Path) -> None:
        file_path = user_workspace / "to_delete.txt"
        file_path.write_text("gone", encoding="utf-8")
        tools = _tools(user_workspace)
        result = tools["file_delete"].invoke({"path": "to_delete.txt"})
        assert "Deleted: to_delete.txt" in result
        assert not file_path.exists()

    def test_delete_missing_file(self, user_workspace: pathlib.Path) -> None:
        tools = _tools(user_workspace)
        result = tools["file_delete"].invoke({"path": "nope.txt"})
        assert "not found" in result

    def test_delete_blocked_path(self, user_workspace: pathlib.Path) -> None:
        tools = _tools(user_workspace)
        result = tools["file_delete"].invoke({"path": "../test.txt"})
        assert "Blocked" in result


class TestFileSearch:
    """Tests for file_search tool."""

    def test_search_files(self, user_workspace: pathlib.Path) -> None:
        (user_workspace / "test1.py").write_text("print(1)", encoding="utf-8")
        (user_workspace / "test2.py").write_text("print(2)", encoding="utf-8")
        (user_workspace / "readme.txt").write_text("hello", encoding="utf-8")
        
        tools = _tools(user_workspace)
        result = tools["file_search"].invoke({"pattern": "*.py", "directory": "."})
        assert "test1.py" in result
        assert "test2.py" in result
        assert "readme.txt" not in result

    def test_search_no_matches(self, user_workspace: pathlib.Path) -> None:
        tools = _tools(user_workspace)
        result = tools["file_search"].invoke({"pattern": "*.md", "directory": "."})
        assert "No files matched" in result

    def test_search_blocked_path(self, user_workspace: pathlib.Path) -> None:
        tools = _tools(user_workspace)
        result = tools["file_search"].invoke({"pattern": "*", "directory": ".."})
        assert "Blocked" in result
