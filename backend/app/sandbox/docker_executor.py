import time
from typing import Any

import docker
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class DockerSandbox:
    """Secure Docker-based execution environment (inspired by OpenClaw)."""

    def __init__(self, image: str = "python:3.11-slim"):
        self.client = docker.from_env()
        self.image = image

    async def run_code(self, code: str, timeout: int = 30) -> dict[str, Any]:
        """Execute Python code in a strictly isolated container."""
        container = None
        start_time = time.time()

        try:
            # Create a restricted container
            container = self.client.containers.run(
                image=self.image,
                command=["python", "-c", code],
                detach=True,
                network_disabled=True,
                mem_limit=settings.sandbox_memory_limit,
                nano_cpus=int(settings.sandbox_cpu_limit * 1e9),
                remove=False,  # Keep for getting logs/exit code
            )

            # Wait for completion or timeout
            status = "running"
            while status == "running" and (time.time() - start_time) < timeout:
                container.reload()
                status = container.status
                time.sleep(0.5)

            if status == "running":
                container.kill()
                return {"stdout": "", "stderr": "Execution timed out", "exit_code": 124}

            logs = container.logs(stdout=True, stderr=True).decode("utf-8")
            result = container.wait()

            return {
                "stdout": logs,
                "stderr": "",  # Docker merges by default or needs separate capture
                "exit_code": result.get("StatusCode", 0),
            }

        except Exception as e:
            logger.exception("sandbox_execution_failed")
            return {"stdout": "", "stderr": str(e), "exit_code": 1}

        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

    def run_command(self, command: list[str]) -> dict[str, Any]:
        """Run a CLI command in the sandbox."""
        raise NotImplementedError("run_command is not yet implemented")
