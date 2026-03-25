import asyncio
import subprocess
import textwrap

from langchain_core.tools import tool

from app.core.config import settings

_SANDBOX_PRELUDE = textwrap.dedent("""\
    import builtins as _b

    _ALLOWED = frozenset({
        "math", "json", "re", "datetime", "collections", "itertools",
        "functools", "string", "random", "statistics", "decimal",
        "fractions", "textwrap", "csv", "typing", "dataclasses",
        "abc", "enum", "operator", "copy", "pprint", "numbers",
        "cmath", "heapq", "bisect", "array", "hashlib", "hmac",
        "base64", "binascii", "struct", "codecs", "unicodedata",
    })
    _ORIG_IMPORT = _b.__import__

    def _safe_import(name, *a, _allowed=_ALLOWED, _orig=_ORIG_IMPORT, **kw):
        top = name.split(".")[0]
        if top not in _allowed:
            raise ImportError(f"module '{top}' is not allowed in sandbox")
        return _orig(name, *a, **kw)

    _b.__import__ = _safe_import

    _delattr = delattr
    _hasattr = hasattr
    for _n in ("open", "exec", "eval", "compile", "globals",
               "setattr", "getattr", "delattr",
               "breakpoint", "exit", "quit"):
        if _hasattr(_b, _n):
            _delattr(_b, _n)

    del _b, _ALLOWED, _ORIG_IMPORT, _safe_import, _n, _delattr, _hasattr
""")


def _set_resource_limits() -> None:
    """Called via preexec_fn to enforce resource limits on the child process."""
    import platform
    import resource

    cpu_secs = 10
    mem_bytes = 256 * 1024 * 1024
    fsize_bytes = 1 * 1024 * 1024

    resource.setrlimit(resource.RLIMIT_CPU, (cpu_secs, cpu_secs))
    # RLIMIT_AS is not supported on macOS
    if platform.system() == "Linux":
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_bytes, fsize_bytes))
    resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))


@tool
async def execute_code(code: str) -> str:
    """Execute Python code and return the output.

    Runs code in an isolated Python interpreter with a security sandbox that:
    - Blocks dangerous modules (os, sys, subprocess, socket, etc.)
    - Removes dangerous builtins (open, exec, eval, compile, etc.)
    - Enforces resource limits (CPU, memory, file size, file descriptors)

    This runs inside a Docker container for additional OS-level isolation.

    Note: Python-level sandboxing alone is not a security boundary — advanced
    techniques (e.g. ``__subclasses__()`` traversal) can bypass it. The Docker
    container provides the actual OS-level isolation layer.
    """
    sandboxed_code = _SANDBOX_PRELUDE + code
    try:
        # Cap subprocess timeout at the configured maximum
        effective_timeout = min(15, settings.tool_shell_max_timeout)
        proc = await asyncio.to_thread(
            subprocess.run,
            ["python3", "-I", "-c", sandboxed_code],
            capture_output=True,
            timeout=effective_timeout,
            preexec_fn=_set_resource_limits,
        )
    except subprocess.TimeoutExpired:
        return f"Timeout: code execution exceeded {effective_timeout} seconds"
    except OSError as e:
        return f"Error: failed to start interpreter: {e}"
    if proc.returncode != 0:
        return f"Error: {proc.stderr.decode(errors='replace')}"
    return proc.stdout.decode(errors="replace") or "(no output)"
