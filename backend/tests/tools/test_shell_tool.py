"""Tests for the shell_exec tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.sandbox.manager import SandboxError
from app.tools.shell_tool import shell_exec

# --- Blocked patterns (no sandbox needed) ---


@pytest.mark.asyncio
async def test_shell_exec_blocked_pattern_rm_rf() -> None:
    """Blocked patterns must be rejected before execution."""
    result = await shell_exec.ainvoke({"command": "rm -rf /"})
    assert "blocked" in result.lower()


@pytest.mark.asyncio
async def test_shell_exec_blocked_pattern_mkfs() -> None:
    result = await shell_exec.ainvoke({"command": "mkfs /dev/sda1"})
    assert "blocked" in result.lower()


@pytest.mark.asyncio
async def test_shell_exec_blocked_pattern_dd() -> None:
    result = await shell_exec.ainvoke({"command": "dd if=/dev/zero of=/dev/sda"})
    assert "blocked" in result.lower()


@pytest.mark.asyncio
async def test_shell_exec_blocked_pattern_fork_bomb() -> None:
    result = await shell_exec.ainvoke({"command": ":(){:|:&};:"})
    assert "blocked" in result.lower()


# --- Sandbox disabled → refuses to run ---


@pytest.mark.asyncio
async def test_shell_exec_requires_sandbox() -> None:
    """When sandbox is disabled, shell_exec refuses to run (never executes locally)."""
    with patch("app.tools.shell_tool.settings") as mock_settings:
        mock_settings.sandbox_enabled = False
        result = await shell_exec.ainvoke({"command": "echo hello"})
    # Must refuse — must NOT execute the command
    assert "disabled" in result.lower() or "not available" in result.lower()
    assert "hello" not in result


@pytest.mark.asyncio
async def test_shell_exec_blocked_pattern_uppercase_bypass() -> None:
    """Uppercase variants of blocked patterns must also be blocked."""
    with patch("app.tools.shell_tool.settings") as mock_settings:
        mock_settings.sandbox_enabled = True
        result = await shell_exec.ainvoke({"command": "RM -RF /"})
    assert "blocked" in result.lower()


@pytest.mark.asyncio
async def test_shell_exec_blocked_pattern_mixed_case_bypass() -> None:
    """Mixed-case variants of blocked patterns must also be blocked."""
    with patch("app.tools.shell_tool.settings") as mock_settings:
        mock_settings.sandbox_enabled = True
        result = await shell_exec.ainvoke({"command": "MkFs /dev/sda1"})
    assert "blocked" in result.lower()


# --- Sandbox enabled → routes through SandboxManager ---


@pytest.mark.asyncio
async def test_shell_exec_routes_through_sandbox() -> None:
    """When sandbox_enabled=True, commands go through SandboxManager."""
    mock_manager = AsyncMock()
    mock_manager.create_sandbox = AsyncMock(return_value="fake-cid")
    mock_manager.exec_in_sandbox = AsyncMock(return_value="sandbox output")
    mock_manager.destroy_sandbox = AsyncMock()

    with (
        patch("app.tools.shell_tool.settings") as mock_settings,
        patch("app.tools.shell_tool.SandboxManager", return_value=mock_manager),
    ):
        mock_settings.sandbox_enabled = True
        mock_settings.tool_shell_max_timeout = 120
        result = await shell_exec.ainvoke({"command": "echo hi"})

    assert result == "sandbox output"
    mock_manager.create_sandbox.assert_awaited_once()
    mock_manager.exec_in_sandbox.assert_awaited_once_with(
        "fake-cid", "echo hi", timeout=30
    )
    mock_manager.destroy_sandbox.assert_awaited_once_with("fake-cid")


@pytest.mark.asyncio
async def test_shell_exec_sandbox_error_returns_message() -> None:
    """When sandbox raises SandboxError, the error message is returned."""
    mock_manager = AsyncMock()
    mock_manager.create_sandbox = AsyncMock(
        side_effect=SandboxError("Docker not available")
    )
    mock_manager.destroy_sandbox = AsyncMock()

    with (
        patch("app.tools.shell_tool.settings") as mock_settings,
        patch("app.tools.shell_tool.SandboxManager", return_value=mock_manager),
    ):
        mock_settings.sandbox_enabled = True
        mock_settings.tool_shell_max_timeout = 120
        result = await shell_exec.ainvoke({"command": "echo hi"})

    assert "sandbox error" in result.lower()
    assert "Docker not available" in result


@pytest.mark.asyncio
async def test_shell_exec_sandbox_cleanup_on_exec_failure() -> None:
    """Sandbox container is destroyed even if exec fails."""
    mock_manager = AsyncMock()
    mock_manager.create_sandbox = AsyncMock(return_value="cid-cleanup")
    mock_manager.exec_in_sandbox = AsyncMock(
        side_effect=SandboxError("timed out after 1 seconds")
    )
    mock_manager.destroy_sandbox = AsyncMock()

    with (
        patch("app.tools.shell_tool.settings") as mock_settings,
        patch("app.tools.shell_tool.SandboxManager", return_value=mock_manager),
    ):
        mock_settings.sandbox_enabled = True
        mock_settings.tool_shell_max_timeout = 120
        result = await shell_exec.ainvoke({"command": "sleep 999"})

    assert "sandbox error" in result.lower()
    mock_manager.destroy_sandbox.assert_awaited_once_with("cid-cleanup")


@pytest.mark.asyncio
async def test_shell_exec_sandbox_output_truncation() -> None:
    """Output exceeding _MAX_OUTPUT should be truncated."""
    mock_manager = AsyncMock()
    mock_manager.create_sandbox = AsyncMock(return_value="cid")
    mock_manager.exec_in_sandbox = AsyncMock(return_value="A" * 20000)
    mock_manager.destroy_sandbox = AsyncMock()

    with (
        patch("app.tools.shell_tool.settings") as mock_settings,
        patch("app.tools.shell_tool.SandboxManager", return_value=mock_manager),
    ):
        mock_settings.sandbox_enabled = True
        mock_settings.tool_shell_max_timeout = 120
        result = await shell_exec.ainvoke({"command": "echo large"})

    assert len(result) <= 10100
    assert "truncated" in result.lower()
