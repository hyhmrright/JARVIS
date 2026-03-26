"""Shell execution tool for the LangGraph agent."""

import structlog
from langchain_core.tools import tool

from app.core.config import settings
from app.sandbox.manager import SandboxError, SandboxManager

logger = structlog.get_logger(__name__)

# Best-effort pre-filter — the Docker sandbox is the primary security boundary.
# These patterns block the most dangerous commands before they reach the sandbox.
_BLOCKED_PATTERNS: set[str] = {
    "rm -rf /",
    "rm -rf /*",
    "rm --no-preserve-root",
    "mkfs",
    "dd if=",
    "dd of=/dev/",
    ":(){:|:&};:",
    "chmod -R 777 /",
    ">(){ ",
    "fork bomb",
    "/dev/sda",
    "/dev/sdb",
    "/dev/nvme",
    "shred /dev/",
    "> /dev/",
}

_MAX_OUTPUT = 10_000


async def _exec_sandbox(command: str, timeout_seconds: int) -> str:
    """Execute a command inside a Docker sandbox container."""
    manager = SandboxManager()
    container_id: str | None = None
    try:
        container_id = await manager.create_sandbox(
            user_id="agent",
            session_id="tool",
        )
        return await manager.exec_in_sandbox(
            container_id,
            command,
            timeout=timeout_seconds,
        )
    except SandboxError as exc:
        logger.error("sandbox_execution_failed", error=str(exc))
        return f"Sandbox error: {exc}"
    finally:
        if container_id is not None:
            await manager.destroy_sandbox(container_id)


@tool
async def shell_exec(command: str, timeout_seconds: int = 30) -> str:
    """Run a shell command and return combined stdout/stderr output.

    Use this to execute shell commands such as `ls`, `cat`, `grep`, `curl`,
    `git`, `find`, `wc`, `head`, `tail`, `jq`, and other standard CLI tools.

    Dangerous commands (e.g. `rm -rf /`, `mkfs`, `dd if=`, fork bombs) are
    blocked. Output is truncated to 10 000 characters. Default timeout is
    30 seconds.

    Args:
        command: The shell command to execute.
        timeout_seconds: Maximum seconds to wait before killing the process.
    """
    cmd_lower = command.lower()
    for pattern in _BLOCKED_PATTERNS:
        if pattern in cmd_lower:
            return f"Blocked: command contains forbidden pattern '{pattern}'"

    if not settings.sandbox_enabled:
        logger.warning("shell_exec_sandbox_disabled_refused", command=command[:100])
        return "Shell execution is not available: sandbox is disabled."

    # Cap at configured maximum so agents cannot request arbitrarily long timeouts.
    effective_timeout = min(timeout_seconds, settings.tool_shell_max_timeout)
    output = await _exec_sandbox(command, effective_timeout)

    if not output.strip():
        return "(no output)"

    if len(output) > _MAX_OUTPUT:
        return output[:_MAX_OUTPUT] + "\n... (truncated)"

    return output
