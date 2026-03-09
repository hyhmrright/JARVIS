import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from app.sandbox.manager import SandboxManager, SandboxError

@pytest.mark.asyncio
async def test_create_sandbox_success():
    with patch("docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_container = MagicMock()
        mock_container.id = "test_id"
        mock_client.containers.run.return_value = mock_container
        
        manager = SandboxManager()
        cid = await manager.create_sandbox("user-1", "sess-1")
        
        assert cid == "test_id"
        mock_client.containers.run.assert_called_once()

@pytest.mark.asyncio
async def test_create_sandbox_failure():
    with patch("docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_client.containers.run.side_effect = Exception("Docker error")
        
        manager = SandboxManager()
        with pytest.raises(SandboxError, match="Failed to create sandbox"):
            await manager.create_sandbox("u", "s")

@pytest.mark.asyncio
async def test_exec_in_sandbox_success():
    with patch("docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_container.exec_run.return_value = (0, b"output")
        
        manager = SandboxManager()
        output = await manager.exec_in_sandbox("cid", "ls")
        
        assert output == "output"
        mock_container.exec_run.assert_called_once()

@pytest.mark.asyncio
async def test_exec_in_sandbox_timeout():
    with patch("docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container
        
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            manager = SandboxManager()
            with pytest.raises(SandboxError, match="timed out"):
                await manager.exec_in_sandbox("cid", "sleep 10", timeout=1)

@pytest.mark.asyncio
async def test_destroy_sandbox_success():
    with patch("docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container
        
        manager = SandboxManager()
        await manager.destroy_sandbox("cid")
        
        mock_container.remove.assert_called_once_with(force=True)
