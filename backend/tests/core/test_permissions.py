"""Tests for tool permission definitions."""

from app.core.permissions import (
    DEFAULT_ENABLED_TOOLS,
    TOOL_NAMES,
    TOOL_REGISTRY,
)


def test_tool_registry_not_empty() -> None:
    assert len(TOOL_REGISTRY) > 0


def test_tool_registry_contains_expected_tools() -> None:
    expected = {
        "datetime",
        "code_exec",
        "web_fetch",
        "search",
        "rag_search",
        "shell",
        "browser",
        "file",
        "subagent",
        "mcp",
        "cron",
        "canvas",
        "plugin",
    }
    assert TOOL_NAMES == expected


def test_all_tool_names_unique() -> None:
    names = [t.name for t in TOOL_REGISTRY]
    assert len(names) == len(set(names))


def test_default_enabled_tools_match_registry() -> None:
    expected_enabled = {t.name for t in TOOL_REGISTRY if t.default_enabled}
    assert set(DEFAULT_ENABLED_TOOLS) == expected_enabled


def test_shell_and_browser_disabled_by_default() -> None:
    assert "shell" not in DEFAULT_ENABLED_TOOLS
    assert "browser" not in DEFAULT_ENABLED_TOOLS
    assert "subagent" not in DEFAULT_ENABLED_TOOLS


def test_tool_names_set_matches_registry() -> None:
    assert TOOL_NAMES == {t.name for t in TOOL_REGISTRY}
