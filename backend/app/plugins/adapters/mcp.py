"""MCP install adapter — parses npx commands."""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def parse_mcp_command(install_url: str) -> tuple[str, list[str]]:
    """Parse an npx command into (command, args).

    Examples:
        "npx @modelcontextprotocol/server-github"
            → ("npx", ["@modelcontextprotocol/server-github"])
        "npx -y pkg --flag" → ("npx", ["-y", "pkg", "--flag"])
    """
    parts = install_url.strip().split()
    if not parts or parts[0] != "npx":
        raise ValueError(f"MCP install_url must start with 'npx', got: {install_url!r}")
    return parts[0], parts[1:]
