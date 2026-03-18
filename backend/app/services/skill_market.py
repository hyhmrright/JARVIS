"""Skill Market service — reads curated registry from disk."""

import json
from pathlib import Path
from typing import Literal

import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

# Path to registry: skill_market.py → [0]=services [1]=app [2]=backend [3]=repo-root
_REGISTRY_PATH = Path(__file__).parents[3] / "registry" / "index.json"


class MarketSkillOut(BaseModel):
    id: str
    name: str
    description: str
    type: Literal["mcp", "skill_md", "python_plugin"]
    install_url: str
    source: str | None = None
    author: str
    tags: list[str]
    scope: list[Literal["system", "personal"]]


# Backward-compat alias — existing code that imports MarketSkill still works
MarketSkill = MarketSkillOut


class SkillMarketManager:
    def __init__(self) -> None:
        self._registry_path = _REGISTRY_PATH

    async def fetch_registry(self) -> list[MarketSkillOut]:
        """Read the curated registry from disk."""
        try:
            if not self._registry_path.exists():
                logger.warning(
                    "market_registry_not_found", path=str(self._registry_path)
                )
                return []
            data = json.loads(self._registry_path.read_text())
            return [MarketSkillOut(**item) for item in data.get("skills", [])]
        except Exception as e:
            logger.error("market_registry_error", error=str(e))
            return []


skill_market_manager = SkillMarketManager()
