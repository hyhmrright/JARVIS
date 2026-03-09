from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.shell_tool import shell_exec


@pytest.mark.asyncio
async def test_shell_exec_success():
    """验证 shell_exec 工具在成功执行命令时的行为。"""
    # Mock settings.sandbox_enabled = True
    with patch("app.tools.shell_tool.settings") as mock_settings:
        mock_settings.sandbox_enabled = True

        # Mock SandboxManager
        with patch("app.tools.shell_tool.SandboxManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            mock_manager.create_sandbox = AsyncMock(return_value="container_123")
            mock_manager.exec_in_sandbox = AsyncMock(return_value="hello world")
            mock_manager.destroy_sandbox = AsyncMock()

            output = await shell_exec.ainvoke("echo hello world")

            assert "hello world" in output
            mock_manager.create_sandbox.assert_called_once()
            mock_manager.exec_in_sandbox.assert_called_once_with(
                "container_123", "echo hello world", timeout=30
            )
            mock_manager.destroy_sandbox.assert_called_once_with("container_123")


@pytest.mark.asyncio
async def test_shell_exec_blocked_pattern():
    """验证 shell_exec 能够拦截危险命令模式。"""
    output = await shell_exec.ainvoke("rm -rf /")
    assert "Blocked" in output


@pytest.mark.asyncio
async def test_shell_exec_local_fallback():
    """验证当沙箱禁用时，shell_exec 能够回退到本地执行。"""
    with patch("app.tools.shell_tool.settings") as mock_settings:
        mock_settings.sandbox_enabled = False

        with patch("app.tools.shell_tool._exec_local") as mock_local:
            mock_local.return_value = "local output"

            output = await shell_exec.ainvoke("ls")

            assert "WARNING: Sandboxing disabled" in output
            assert "local output" in output
            mock_local.assert_called_once()
