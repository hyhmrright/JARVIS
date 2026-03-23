"""MCP (Model Context Protocol) client — loads external server tools."""

from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import dataclass, field
from typing import Any

import structlog
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, create_model

logger = structlog.get_logger(__name__)


@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None


class _MCPConnectionPool:
    """Persistent connection pool for MCP stdio servers.

    Keeps one subprocess per server alive across tool invocations to avoid
    repeated startup overhead (~500 ms per call with per-invocation spawning).
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Any] = {}  # name → ClientSession
        self._exit_stacks: dict[str, contextlib.AsyncExitStack] = {}
        self._init_locks: dict[str, asyncio.Lock] = {}

    def _config_key(self, config: MCPServerConfig) -> str:
        env_items = tuple(sorted((config.env or {}).items()))
        return json.dumps(
            {
                "name": config.name,
                "command": config.command,
                "args": config.args,
                "env": env_items,
            },
        )

    def _init_lock(self, key: str) -> asyncio.Lock:
        return self._init_locks.setdefault(key, asyncio.Lock())

    async def get_session(self, config: MCPServerConfig) -> Any:
        """Return an open ClientSession, creating one if needed."""
        key = self._config_key(config)
        if key in self._sessions:
            return self._sessions[key]
        async with self._init_lock(key):
            if key in self._sessions:
                return self._sessions[key]
            session = await self._open(config, key)
            self._sessions[key] = session
            return session

    async def _open(self, config: MCPServerConfig, key: str) -> Any:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        stack = contextlib.AsyncExitStack()
        server_params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env=config.env,
        )
        read, write = await stack.enter_async_context(stdio_client(server_params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._exit_stacks[key] = stack
        logger.info("mcp_session_opened", server=config.name)
        return session

    async def invalidate(self, config: MCPServerConfig) -> None:
        """Remove a stale session; next call will reconnect."""
        key = self._config_key(config)
        async with self._init_lock(key):
            self._sessions.pop(key, None)
            stack = self._exit_stacks.pop(key, None)
            if stack:
                try:
                    await stack.aclose()
                except Exception:
                    pass

    async def close_all(self) -> None:
        """Close all persistent connections; called on app shutdown."""
        keys = list(self._exit_stacks.keys())
        for key in keys:
            stack = self._exit_stacks.pop(key, None)
            if stack:
                try:
                    await stack.aclose()
                except Exception:
                    pass
        self._sessions.clear()
        self._init_locks.clear()
        logger.info("mcp_pool_closed", server_count=len(keys))


mcp_connection_pool = _MCPConnectionPool()


async def create_mcp_tools(configs: list[MCPServerConfig]) -> list[BaseTool]:
    """Connect to MCP servers and return their tools as LangChain tools.

    Connections are opened in parallel. Returns empty list if configs is
    empty or all connections fail.
    """
    if not configs:
        return []

    async def _safe_load(config: MCPServerConfig) -> list[BaseTool]:
        try:
            server_tools = await _load_tools_from_server(config)
            logger.info(
                "mcp_tools_loaded",
                server=config.name,
                tool_count=len(server_tools),
            )
            return server_tools
        except Exception:
            logger.warning(
                "mcp_server_connect_failed", server=config.name, exc_info=True
            )
            return []

    results = await asyncio.gather(*(_safe_load(c) for c in configs))
    return [tool for server_tools in results for tool in server_tools]


async def _load_tools_from_server(config: MCPServerConfig) -> list[BaseTool]:
    session = await mcp_connection_pool.get_session(config)
    result = await session.list_tools()
    return [
        _make_langchain_tool(
            t.name,
            getattr(t, "description", "") or t.name,
            getattr(t, "inputSchema", None) or {},
            config,
        )
        for t in result.tools
    ]


def _build_args_schema(input_schema: dict[str, Any]) -> type[BaseModel]:
    """Build a Pydantic model from a JSON Schema object definition.

    Produces a model with one field per declared property so that LangChain
    forwards the correct keyword arguments to the tool coroutine.  Fields not
    listed in ``required`` are optional (default ``None``).  If the schema has
    no properties at all a single ``kwargs`` catch-all field is used.
    """
    props: dict[str, Any] = input_schema.get("properties", {})
    required: set[str] = set(input_schema.get("required", []))

    field_defs: dict[str, Any] = {}
    for prop_name, _prop_schema in props.items():
        if prop_name in required:
            field_defs[prop_name] = (Any, ...)
        else:
            field_defs[prop_name] = (Any, None)

    if not field_defs:
        # No declared properties — use a single optional dict field so
        # LangChain does not treat the schema as a no-args tool.
        field_defs["kwargs"] = (dict[str, Any], {})

    return create_model("_MCPArgs", **field_defs)


def _make_langchain_tool(
    tool_name: str,
    tool_desc: str,
    input_schema: dict[str, Any],
    config: MCPServerConfig,
) -> BaseTool:
    """Wrap a single MCP tool as a LangChain StructuredTool."""
    args_schema = _build_args_schema(input_schema)

    async def _invoke(**kwargs: Any) -> str:
        try:
            session = await mcp_connection_pool.get_session(config)
            result = await session.call_tool(tool_name, arguments=kwargs)
            parts = [c.text for c in result.content if hasattr(c, "text") and c.text]
            return "\n".join(parts) or "(no output)"
        except Exception as exc:
            # Invalidate so the next call reopens a fresh connection.
            await mcp_connection_pool.invalidate(config)
            return f"MCP tool error ({tool_name}): {exc}"

    return StructuredTool.from_function(
        coroutine=_invoke,
        name=tool_name,
        description=tool_desc,
        args_schema=args_schema,
    )


def parse_mcp_configs(json_str: str) -> list[MCPServerConfig]:
    """Parse MCP_SERVERS_JSON env var into MCPServerConfig list.

    Returns empty list on empty string or parse errors.
    """
    if not json_str.strip():
        return []
    try:
        raw = json.loads(json_str)
        return [MCPServerConfig(**item) for item in raw]
    except (json.JSONDecodeError, TypeError, KeyError):
        logger.warning("mcp_servers_json_parse_error", json_str=json_str[:200])
        return []
