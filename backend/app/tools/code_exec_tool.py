import asyncio

from langchain_core.tools import tool


@tool
async def execute_code(code: str) -> str:
    """Execute Python code and return the output.

    NOTE: This runs code in an isolated Python interpreter (-I flag: no site-packages,
    no user site, no PYTHONPATH). It is NOT a full OS-level sandbox — do not use in
    untrusted multi-tenant environments without additional container isolation.
    """
    proc = await asyncio.create_subprocess_exec(
        "python3",
        "-I",  # isolated mode: disables site-packages, user site, PYTHONPATH
        "-c",
        code,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return "Timeout: code execution exceeded 30 seconds"
    if stderr:
        return f"Error: {stderr.decode()}"
    return stdout.decode() or "(no output)"
