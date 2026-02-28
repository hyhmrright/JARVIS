"""Tests for SandboxManager with mocked subprocess calls."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.sandbox.manager import SandboxError, SandboxManager


def _make_proc(
    returncode: int = 0,
    stdout: bytes = b"",
    stderr: bytes = b"",
) -> MagicMock:
    """Build a mock async process."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    return proc


@pytest.fixture
def manager() -> SandboxManager:
    return SandboxManager()


# ── create_sandbox ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_sandbox_success(manager: SandboxManager) -> None:
    fake_id = "abc123def456"
    proc = _make_proc(stdout=f"{fake_id}\n".encode())

    target = "app.sandbox.manager.asyncio.create_subprocess_exec"
    with patch(target, return_value=proc) as mock_exec:
        cid = await manager.create_sandbox("user-1", "sess-1")

    assert cid == fake_id
    args = mock_exec.call_args
    flat = args[0]
    assert flat[0] == "docker"
    assert flat[1] == "run"
    assert "-d" in flat
    assert "--network=none" in flat
    assert "--label=jarvis.user_id=user-1" in flat
    assert "--label=jarvis.session_id=sess-1" in flat


@pytest.mark.asyncio
async def test_create_sandbox_failure(manager: SandboxManager) -> None:
    proc = _make_proc(returncode=1, stderr=b"image not found")

    with (
        patch("app.sandbox.manager.asyncio.create_subprocess_exec", return_value=proc),
        pytest.raises(SandboxError, match="image not found"),
    ):
        await manager.create_sandbox("u", "s")


# ── exec_in_sandbox ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_exec_in_sandbox_success(manager: SandboxManager) -> None:
    proc = _make_proc(stdout=b"hello world\n")

    target = "app.sandbox.manager.asyncio.create_subprocess_exec"
    with patch(target, return_value=proc) as mock_exec:
        output = await manager.exec_in_sandbox("cid123", "echo hello world")

    assert output == "hello world"
    args = mock_exec.call_args[0]
    assert args[0] == "docker"
    assert args[1] == "exec"
    assert "cid123" in args
    assert "echo hello world" in args


@pytest.mark.asyncio
async def test_exec_in_sandbox_timeout(manager: SandboxManager) -> None:
    proc = MagicMock()
    proc.communicate = AsyncMock(side_effect=TimeoutError)
    proc.kill = MagicMock()
    proc.wait = AsyncMock()

    with (
        patch("app.sandbox.manager.asyncio.create_subprocess_exec", return_value=proc),
        pytest.raises(SandboxError, match="timed out"),
    ):
        await manager.exec_in_sandbox("cid123", "sleep 999", timeout=1)


@pytest.mark.asyncio
async def test_exec_in_sandbox_nonzero_exit(manager: SandboxManager) -> None:
    proc = _make_proc(returncode=1, stdout=b"", stderr=b"error output")

    with patch("app.sandbox.manager.asyncio.create_subprocess_exec", return_value=proc):
        output = await manager.exec_in_sandbox("cid123", "bad_command")

    assert "error output" in output


# ── destroy_sandbox ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_destroy_sandbox_success(manager: SandboxManager) -> None:
    proc = _make_proc(stdout=b"cid123\n")

    target = "app.sandbox.manager.asyncio.create_subprocess_exec"
    with patch(target, return_value=proc) as mock_exec:
        await manager.destroy_sandbox("cid123")

    args = mock_exec.call_args[0]
    assert args == ("docker", "rm", "-f", "cid123")


@pytest.mark.asyncio
async def test_destroy_sandbox_failure_logs_warning(
    manager: SandboxManager,
) -> None:
    proc = _make_proc(returncode=1, stderr=b"no such container")

    with (
        patch("app.sandbox.manager.asyncio.create_subprocess_exec", return_value=proc),
        patch("app.sandbox.manager.logger") as mock_logger,
    ):
        await manager.destroy_sandbox("cid123")

    mock_logger.warning.assert_called_once()
