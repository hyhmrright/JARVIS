from pathlib import Path

import aiohttp
import structlog
from pydantic import BaseModel

from app.core.config import settings

logger = structlog.get_logger(__name__)


class MarketSkill(BaseModel):
    id: str
    name: str
    description: str
    author: str
    version: str
    md_url: str
    installed: bool = False


class SkillMarketManager:
    def __init__(self) -> None:
        self.skills_dir = Path(settings.skills_dir)
        self.market_dir = self.skills_dir / "market"
        self.market_dir.mkdir(parents=True, exist_ok=True)

    async def fetch_registry(self) -> list[MarketSkill]:
        """Fetch the remote skill registry."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(settings.skill_registry_url) as response:
                    if response.status != 200:
                        logger.error(
                            "market_registry_fetch_failed", status=response.status
                        )
                        return []
                    data = await response.json()
                    skills = []
                    for item in data.get("skills", []):
                        skill = MarketSkill(**item)
                        skill.installed = self.is_installed(skill.id)
                        skills.append(skill)
                    return skills
        except Exception as e:
            logger.error("market_registry_error", error=str(e))
            return []

    def is_installed(self, skill_id: str) -> bool:
        """Check if a skill is installed locally."""
        return (self.market_dir / f"{skill_id}.md").exists()

    async def install_skill(self, skill_id: str, md_url: str) -> bool:
        """Download and install a skill."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(md_url) as response:
                    if response.status != 200:
                        return False
                    content = await response.text()
                    dest = self.market_dir / f"{skill_id}.md"
                    with open(dest, "w") as f:
                        f.write(content)
                    return True
        except Exception as e:
            logger.error("market_install_error", skill_id=skill_id, error=str(e))
            return False

    def uninstall_skill(self, skill_id: str) -> bool:
        """Remove an installed skill."""
        dest = self.market_dir / f"{skill_id}.md"
        if dest.exists():
            dest.unlink()
            return True
        return False

    def list_installed_ids(self) -> list[str]:
        """List IDs of all market-installed skills."""
        return [f.stem for f in self.market_dir.glob("*.md")]


skill_market_manager = SkillMarketManager()
