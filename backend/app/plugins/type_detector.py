"""URL type detection and plugin_id/name derivation for skill installation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import urlparse

PluginType = Literal["mcp", "skill_md", "python_plugin"]


@dataclass
class DetectionResult:
    type: PluginType
    plugin_id: str
    default_name: str


def _stem_from_url(url: str) -> str:
    """Extract the filename stem from a URL path."""
    path = urlparse(url).path.rstrip("/")
    return PurePosixPath(path).stem.lower()


def _slugify(text: str) -> str:
    """Lowercase, replace non-alphanumeric runs with hyphens."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _title_from_slug(slug: str) -> str:
    """Convert a slug to title-cased words."""
    return " ".join(w.capitalize() for w in re.split(r"[-_]+", slug))


def detect_type(url_or_command: str) -> DetectionResult | None:
    """Detect plugin type from a URL or npx command.

    Returns None when the type cannot be determined by pattern alone
    (bare GitHub repo URL or completely unrecognized input).
    """
    s = url_or_command.strip()

    # MCP: npx command
    if s.startswith("npx "):
        package = s[4:].strip()
        bare = re.sub(r"^@[^/]+/", "", package)
        plugin_id = "mcp-" + _slugify(bare)
        return DetectionResult(
            type="mcp",
            plugin_id=plugin_id,
            default_name=_title_from_slug(_slugify(bare)),
        )

    # Must be an http(s) URL from here
    try:
        parsed = urlparse(s)
        if not parsed.scheme.startswith("http"):
            return None
    except Exception:
        return None

    path_lower = parsed.path.lower()

    if path_lower.endswith(".md"):
        stem = _stem_from_url(s)
        return DetectionResult(
            type="skill_md",
            plugin_id=_slugify(stem),
            default_name=_title_from_slug(stem),
        )

    if path_lower.endswith(".py"):
        stem = _stem_from_url(s)
        return DetectionResult(
            type="python_plugin",
            plugin_id=_slugify(stem),
            default_name=_title_from_slug(stem),
        )

    filename_lower = PurePosixPath(parsed.path).name.lower()
    if path_lower.endswith(".zip") or "archive" in filename_lower:
        stem = _stem_from_url(s)
        return DetectionResult(
            type="python_plugin",
            plugin_id=_slugify(stem),
            default_name=_title_from_slug(stem),
        )

    return None
