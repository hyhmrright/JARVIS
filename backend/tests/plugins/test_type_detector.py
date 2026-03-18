"""Tests for URL type detector and plugin_id/name derivation."""

import pytest

from app.plugins.type_detector import detect_type


@pytest.mark.parametrize(
    "url,expected_type",
    [
        ("https://example.com/weather.md", "skill_md"),
        ("https://raw.githubusercontent.com/user/repo/main/SKILL.md", "skill_md"),
        ("https://example.com/myplugin.py", "python_plugin"),
        ("https://example.com/bundle.zip", "python_plugin"),
        ("https://github.com/user/repo/archive/refs/heads/main.zip", "python_plugin"),
        ("npx @modelcontextprotocol/server-github", "mcp"),
        ("npx some-package", "mcp"),
        ("mcp://some-server", "mcp"),
    ],
)
def test_detect_type_by_pattern(url: str, expected_type: str) -> None:
    result = detect_type(url)
    assert result is not None
    assert result.type == expected_type


def test_unrecognized_url_returns_none() -> None:
    result = detect_type("https://example.com/something")
    assert result is None


def test_plugin_id_skill_md() -> None:
    result = detect_type("https://example.com/path/weather.md")
    assert result is not None
    assert result.plugin_id == "weather"


def test_plugin_id_python_plugin() -> None:
    result = detect_type("https://example.com/my_plugin.py")
    assert result is not None
    assert result.plugin_id == "my-plugin"


def test_plugin_id_mcp_npx_with_scope() -> None:
    result = detect_type("npx @modelcontextprotocol/server-github")
    assert result is not None
    assert result.plugin_id == "mcp-server-github"


def test_plugin_id_mcp_npx_no_scope() -> None:
    result = detect_type("npx some-package")
    assert result is not None
    assert result.plugin_id == "mcp-some-package"


def test_default_name_from_skill_md_url() -> None:
    result = detect_type("https://example.com/weather_query.md")
    assert result is not None
    assert result.default_name == "Weather Query"


def test_default_name_from_mcp_npx() -> None:
    result = detect_type("npx @modelcontextprotocol/server-github")
    assert result is not None
    assert result.default_name == "Server Github"
