"""Docker sandbox manager for isolated command execution using Docker SDK."""

import asyncio
from typing import Any

import docker
import structlog
from docker.errors import DockerException, NotFound

from app.core.config import settings

logger = structlog.get_logger(__name__)


class SandboxError(Exception):
    """Raised when a sandbox operation fails."""


class SandboxManager:
    """Create, execute in, and destroy Docker sandbox containers using Docker SDK."""

    def __init__(self) -> None:
        self._client: Any = None

    @property
    def client(self) -> Any:
        """Lazy initialization of the Docker client."""
        if self._client is None:
            try:
                self._client = docker.from_env()
            except DockerException as e:
                logger.error("docker_client_init_failed", error=str(e))
                raise SandboxError(f"Failed to connect to Docker daemon: {e}") from e
        return self._client

    async def create_sandbox(self, user_id: str, session_id: str) -> str:
        """Create a Docker container for isolated execution.

        Returns the container ID.
        """

        def _run() -> Any:
            return self.client.containers.run(
                image=settings.sandbox_image,
                command="sleep " + str(settings.sandbox_timeout),
                detach=True,
                nano_cpus=int(settings.sandbox_cpu_limit * 1e9),
                mem_limit=settings.sandbox_memory_limit,
                network_disabled=True,
                labels={
                    "jarvis.user_id": user_id,
                    "jarvis.session_id": session_id,
                },
                remove=False,  # We want to control removal
            )

        try:
            container = await asyncio.to_thread(_run)
            logger.info(
                "sandbox_created",
                container_id=container.id[:12],
                user_id=user_id,
                session_id=session_id,
            )
            return str(container.id)
        except Exception as e:
            logger.error("sandbox_create_failed", error=str(e))
            raise SandboxError(f"Failed to create sandbox: {e}") from e

    async def exec_in_sandbox(
        self,
        container_id: str,
        command: str,
        timeout: int = 30,
    ) -> str:
        """Execute a command inside a sandbox container.

        Returns combined stdout/stderr output.
        """

        def _exec() -> tuple[int, bytes]:
            container = self.client.containers.get(container_id)
            # exec_run returns (exit_code, output)
            result = container.exec_run(
                cmd=["sh", "-c", command],
                workdir="/tmp",
            )
            return result

        try:
            # Note: Docker SDK doesn't have a direct timeout for exec_run easily.
            # asyncio.wait_for will handle the async side.
            exit_code, output = await asyncio.wait_for(
                asyncio.to_thread(_exec),
                timeout=timeout,
            )

            output_str = output.decode(errors="replace").strip()
            if exit_code != 0:
                logger.warning(
                    "sandbox_nonzero_exit",
                    container_id=container_id[:12],
                    exit_code=exit_code,
                )
            return output_str
        except TimeoutError:
            logger.error(
                "sandbox_exec_timeout",
                container_id=container_id[:12],
                timeout=timeout,
            )
            raise SandboxError(f"Command timed out after {timeout} seconds") from None
        except NotFound as e:
            raise SandboxError(f"Container {container_id} not found") from e
        except Exception as e:
            logger.error(
                "sandbox_exec_failed", container_id=container_id[:12], error=str(e)
            )
            raise SandboxError(f"Failed to execute in sandbox: {e}") from e

    async def destroy_sandbox(self, container_id: str) -> None:
        """Force-remove a sandbox container."""

        def _remove() -> None:
            try:
                container = self.client.containers.get(container_id)
                container.remove(force=True)
            except NotFound:
                pass  # Already gone

        try:
            await asyncio.to_thread(_remove)
            logger.info(
                "sandbox_destroyed",
                container_id=container_id[:12],
            )
        except Exception as e:
            logger.warning(
                "sandbox_destroy_failed",
                container_id=container_id[:12],
                error=str(e),
            )
