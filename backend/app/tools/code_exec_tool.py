import asyncio

from langchain_core.tools import tool


@tool
async def execute_code(code: str) -> str:
    """Execute Python code in a sandbox and return the output."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3",
            "-c",
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        if stderr:
            return f"Error: {stderr.decode()}"
        return stdout.decode() or "(no output)"
    except asyncio.TimeoutError:
        return "Timeout: code execution exceeded 30 seconds"
