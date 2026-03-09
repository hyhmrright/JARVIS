import asyncio
import pytest
from unittest.mock import MagicMock, patch
from app.sandbox.manager import SandboxManager, SandboxError

@pytest.mark.asyncio
async def test_sandbox_create_uses_sdk():
    """验证 create_sandbox 是否使用 Docker SDK。"""
    with patch("docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_container = MagicMock()
        mock_container.id = "test_container_id_123456"
        mock_client.containers.run.return_value = mock_container
        
        manager = SandboxManager()
        container_id = await manager.create_sandbox("user1", "session1")
        
        assert container_id == "test_container_id_123456"
        mock_client.containers.run.assert_called_once()

@pytest.mark.asyncio
async def test_sandbox_exec_uses_sdk():
    """验证 exec_in_sandbox 是否使用 Docker SDK。"""
    with patch("docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container
        
        # mock_container.exec_run returns (exit_code, output)
        mock_container.exec_run.return_value = (0, b"hello world\n")
        
        manager = SandboxManager()
        output = await manager.exec_in_sandbox("test_container_id", "echo hello world")
        
        assert output == "hello world"
        mock_container.exec_run.assert_called_once()

@pytest.mark.asyncio
async def test_sandbox_destroy_uses_sdk():
    """验证 destroy_sandbox 是否使用 Docker SDK。"""
    with patch("docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container
        
        manager = SandboxManager()
        await manager.destroy_sandbox("test_container_id")
        
        mock_container.remove.assert_called_once_with(force=True)

@pytest.mark.asyncio
async def test_sandbox_create_fails():
    """验证 create_sandbox 失败时的处理。"""
    with patch("docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_client.containers.run.side_effect = Exception("Docker run failed")
        
        manager = SandboxManager()
        with pytest.raises(SandboxError, match="Failed to create sandbox"):
            await manager.create_sandbox("user1", "session1")

@pytest.mark.asyncio
async def test_sandbox_exec_timeout():
    """验证 exec_in_sandbox 超时处理。"""
    with patch("docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container
        
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            manager = SandboxManager()
            with pytest.raises(SandboxError, match="timed out after"):
                await manager.exec_in_sandbox("id", "cmd", timeout=1)

@pytest.mark.asyncio
async def test_sandbox_exec_not_found():
    """验证 exec_in_sandbox 容器未找到。"""
    from docker.errors import NotFound
    with patch("docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_client.containers.get.side_effect = NotFound("Container not found")
        
        manager = SandboxManager()
        with pytest.raises(SandboxError, match="not found"):
            await manager.exec_in_sandbox("invalid_id", "cmd")

@pytest.mark.asyncio
async def test_sandbox_exec_multiline_output():
    """验证 exec_in_sandbox 能够返回多行输出。"""
    with patch("docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container
        
        multiline_output = b"line1\nline2\nline3\n"
        mock_container.exec_run.return_value = (0, multiline_output)
        
        manager = SandboxManager()
        output = await manager.exec_in_sandbox("id", "ls -l")
        
        assert output == "line1\nline2\nline3"
        mock_container.exec_run.assert_called_once()

@pytest.mark.asyncio
async def test_sandbox_exec_nonzero_exit():
    """验证 exec_in_sandbox 在非零退出码时的记录（不抛出异常，但返回输出）。"""
    with patch("docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container
        
        mock_container.exec_run.return_value = (1, b"error message\n")
        
        manager = SandboxManager()
        output = await manager.exec_in_sandbox("id", "invalid_cmd")
        
        assert output == "error message"
