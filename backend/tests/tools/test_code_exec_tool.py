"""Tests for the code execution tool."""

import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.code_exec_tool import execute_code


@pytest.mark.anyio
async def test_execute_code_returns_string():
    """execute_code must always return a string."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = b"42\n"
    mock_proc.stderr = b""

    with patch(
        "app.tools.code_exec_tool.asyncio.to_thread",
        new=AsyncMock(return_value=mock_proc),
    ):
        result = await execute_code.ainvoke({"code": "print(6 * 7)"})

    assert isinstance(result, str)
    assert "42" in result


@pytest.mark.anyio
async def test_execute_code_returns_error_on_nonzero_exit():
    """Non-zero return code must produce an error string."""
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stdout = b""
    mock_proc.stderr = b"NameError: name 'x' is not defined\n"

    with patch(
        "app.tools.code_exec_tool.asyncio.to_thread",
        new=AsyncMock(return_value=mock_proc),
    ):
        result = await execute_code.ainvoke({"code": "print(x)"})

    assert "Error" in result
    assert isinstance(result, str)


@pytest.mark.anyio
async def test_execute_code_handles_timeout():
    """TimeoutExpired must be caught and reported as a string."""
    with patch(
        "app.tools.code_exec_tool.asyncio.to_thread",
        new=AsyncMock(side_effect=subprocess.TimeoutExpired(cmd="python3", timeout=15)),
    ):
        result = await execute_code.ainvoke({"code": "while True: pass"})

    assert "Timeout" in result
    assert isinstance(result, str)


@pytest.mark.anyio
async def test_execute_code_handles_oserror():
    """OSError (interpreter not found) must be caught and reported as a string."""
    with patch(
        "app.tools.code_exec_tool.asyncio.to_thread",
        new=AsyncMock(side_effect=OSError("python3 not found")),
    ):
        result = await execute_code.ainvoke({"code": "print('hi')"})

    assert "Error" in result
    assert isinstance(result, str)


@pytest.mark.anyio
async def test_execute_code_no_output():
    """Empty stdout with zero exit code must return a '(no output)' placeholder."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = b""
    mock_proc.stderr = b""

    with patch(
        "app.tools.code_exec_tool.asyncio.to_thread",
        new=AsyncMock(return_value=mock_proc),
    ):
        result = await execute_code.ainvoke({"code": "x = 1"})

    assert "(no output)" in result
