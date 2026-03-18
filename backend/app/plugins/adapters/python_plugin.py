"""Python plugin install adapter — downloads .py or .zip files."""

from __future__ import annotations

import asyncio
import io
import zipfile
from pathlib import Path

import httpx
import structlog
import yaml

from app.tools.web_fetch_tool import is_safe_url

logger = structlog.get_logger(__name__)

_FETCH_TIMEOUT = 30.0
_MAX_SIZE = 50 * 1024 * 1024  # 50 MB


async def download_python_plugin(url: str, dest_dir: Path) -> tuple[Path, str | None]:
    """Download a .py or .zip plugin. Returns (saved_path, manifest_name_or_None).

    For .py: saves to dest_dir/<filename>.py
    For .zip: extracts to dest_dir/<pkg_name>/, reads manifest.yaml name if present.
    Raises ValueError for unsafe/non-http URLs or oversized responses.
    Raises httpx.HTTPStatusError on non-2xx responses.
    """
    if not is_safe_url(url):
        raise ValueError(f"URL is not allowed (internal or non-http): {url!r}")
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=_FETCH_TIMEOUT
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        if len(response.content) > _MAX_SIZE:
            raise ValueError(f"Response too large ({len(response.content)} bytes)")
        dest_dir.mkdir(parents=True, exist_ok=True)

        clean_path = url.split("?")[0].rstrip("/")
        if clean_path.lower().endswith(".py"):
            filename = clean_path.split("/")[-1]
            dest_path = dest_dir / filename
            await asyncio.to_thread(dest_path.write_bytes, response.content)
            logger.info("python_plugin_downloaded", url=url, path=str(dest_path))
            return dest_path, None

        # ZIP — extract off the event loop to avoid blocking; filter members to
        # prevent zip path traversal (e.g. entries with "../" in their name).
        def _extract(data: bytes, pkg_dir: Path) -> None:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                safe_members = [
                    m
                    for m in z.infolist()
                    if not (
                        m.filename.startswith("/")
                        or ".." in m.filename.replace("\\", "/").split("/")
                    )
                ]
                z.extractall(pkg_dir, members=safe_members)

        pkg_name = clean_path.split("/")[-1].removesuffix(".zip")
        pkg_dir = dest_dir / pkg_name
        await asyncio.to_thread(_extract, response.content, pkg_dir)
        manifest_name = _read_manifest_name(pkg_dir)
        logger.info("python_plugin_extracted", url=url, path=str(pkg_dir))
        return pkg_dir, manifest_name


def _read_manifest_name(pkg_dir: Path) -> str | None:
    """Read the name field from manifest.yaml if present."""
    manifest_path = pkg_dir / "manifest.yaml"
    if not manifest_path.exists():
        candidate = next(pkg_dir.glob("*/manifest.yaml"), None)
        if candidate is None:
            return None
        manifest_path = candidate
    try:
        data = yaml.safe_load(manifest_path.read_text())
        if not isinstance(data, dict):
            return None
        return data.get("name")
    except Exception:
        return None
