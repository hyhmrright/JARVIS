"""Tests for install adapters."""

import io
import zipfile

import pytest
import respx
import httpx

from app.plugins.adapters.mcp import parse_mcp_command
from app.plugins.adapters.skill_md import download_skill_md, extract_md_title
from app.plugins.adapters.python_plugin import download_python_plugin


# ── MCP adapter ──────────────────────────────────────────────────────────────

def test_parse_mcp_basic() -> None:
    cmd, args = parse_mcp_command("npx @modelcontextprotocol/server-github")
    assert cmd == "npx"
    assert args == ["@modelcontextprotocol/server-github"]


def test_parse_mcp_with_flags() -> None:
    cmd, args = parse_mcp_command("npx -y some-package --flag")
    assert cmd == "npx"
    assert args == ["-y", "some-package", "--flag"]


def test_parse_mcp_invalid_raises() -> None:
    with pytest.raises(ValueError, match="must start with 'npx'"):
        parse_mcp_command("pip install something")


# ── skill_md adapter ──────────────────────────────────────────────────────────

def test_extract_md_title_from_heading() -> None:
    content = "# Weather Query\n\nSome description."
    assert extract_md_title(content) == "Weather Query"


def test_extract_md_title_no_heading() -> None:
    content = "No heading here\nJust text."
    assert extract_md_title(content) is None


@pytest.mark.anyio
@respx.mock
async def test_download_skill_md(tmp_path):
    url = "https://example.com/weather.md"
    md_content = "# Weather\n\n## Description\nGet weather."
    respx.get(url).mock(return_value=httpx.Response(200, text=md_content))

    dest = tmp_path / "weather.md"
    content = await download_skill_md(url, dest)

    assert dest.exists()
    assert dest.read_text() == md_content
    assert content == md_content


@pytest.mark.anyio
@respx.mock
async def test_download_skill_md_network_error(tmp_path):
    url = "https://example.com/missing.md"
    respx.get(url).mock(return_value=httpx.Response(404))

    dest = tmp_path / "missing.md"
    with pytest.raises(httpx.HTTPStatusError):
        await download_skill_md(url, dest)


# ── python_plugin adapter ─────────────────────────────────────────────────────

@pytest.mark.anyio
@respx.mock
async def test_download_python_plugin_py(tmp_path):
    url = "https://example.com/myplugin.py"
    py_content = "def hello(): return 'world'"
    respx.get(url).mock(return_value=httpx.Response(200, content=py_content.encode()))

    saved_path, manifest_name = await download_python_plugin(url, tmp_path)

    assert saved_path.exists()
    assert saved_path.name == "myplugin.py"
    assert manifest_name is None


@pytest.mark.anyio
@respx.mock
async def test_download_python_plugin_zip(tmp_path):
    url = "https://example.com/mypkg.zip"
    # Build a small zip in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("manifest.yaml", "name: My Plugin\nversion: 1.0")
        z.writestr("__init__.py", "")
    buf.seek(0)

    respx.get(url).mock(return_value=httpx.Response(200, content=buf.read()))

    saved_path, manifest_name = await download_python_plugin(url, tmp_path)

    assert saved_path.is_dir()
    assert manifest_name == "My Plugin"
