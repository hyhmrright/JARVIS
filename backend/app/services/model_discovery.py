"""LLM model discovery service.

Wraps infrastructure-level model listing so the API layer does not import
directly from ``app.infra``.
"""

from __future__ import annotations

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


async def get_ollama_models() -> list[str]:
    """Return the names of locally available Ollama models."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if resp.status_code != 200:
                return []
            data = resp.json()
            return [m.get("name") for m in data.get("models", []) if m.get("name")]
    except (httpx.RequestError, ValueError):
        return []
