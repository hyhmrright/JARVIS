"""Docker sandbox manager for isolated command execution."""

import asyncio

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class SandboxError(Exception):
    """Raised when a sandbox operation fails."""


class SandboxManager:
    """Create, execute in, and destroy Docker sandbox containers."""

    async def create_sandbox(self, user_id: str, session_id: str) -> str:
        """Create a Docker container for isolated execution.

        Returns the container ID.
        """
        cmd = [
            "docker",
            "run",
            "-d",
            f"--cpus={settings.sandbox_cpu_limit}",
            f"--memory={settings.sandbox_memory_limit}",
            "--network=none",
            f"--label=jarvis.user_id={user_id}",
            f"--label=jarvis.session_id={session_id}",
            settings.sandbox_image,
            "sleep",
            str(settings.sandbox_timeout),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode(errors="replace").strip()
            raise SandboxError(f"Failed to create sandbox: {error_msg}")

        container_id = stdout.decode().strip()
        logger.info(
            "sandbox_created",
            container_id=container_id[:12],
            user_id=user_id,
            session_id=session_id,
        )
        return container_id

    async def exec_in_sandbox(
        self,
        container_id: str,
        command: str,
        timeout: int = 30,
    ) -> str:
        """Execute a command inside a sandbox container.

        Returns combined stdout/stderr output.
        """
        cmd = [
            "docker",
            "exec",
            container_id,
            "sh",
            "-c",
            command,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise SandboxError(f"Command timed out after {timeout} seconds") from None

        output = (stdout + stderr).decode(errors="replace").strip()
        if proc.returncode != 0:
            logger.warning(
                "sandbox_nonzero_exit",
                container_id=container_id[:12],
                returncode=proc.returncode,
            )
        return output

    async def destroy_sandbox(self, container_id: str) -> None:
        """Force-remove a sandbox container."""
        cmd = ["docker", "rm", "-f", container_id]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode(errors="replace").strip()
            logger.warning(
                "sandbox_destroy_failed",
                container_id=container_id[:12],
                error=error_msg,
            )
        else:
            logger.info(
                "sandbox_destroyed",
                container_id=container_id[:12],
            )
