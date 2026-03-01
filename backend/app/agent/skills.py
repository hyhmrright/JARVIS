from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field
from pathlib import Path

import structlog
import yaml

logger = structlog.get_logger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class SkillFile:
    name: str
    description: str
    triggers: list[str] = field(default_factory=list)
    content: str = ""


def load_skills(skills_dir: str | Path) -> list[SkillFile]:
    """Load all .md skill files from the given directory.

    Returns empty list if directory doesn't exist or has no valid skill files.
    Results are cached per unique skills_dir path to avoid repeated disk I/O.
    """
    return list(_load_skills_cached(str(skills_dir)))


@functools.lru_cache(maxsize=8)
def _load_skills_cached(skills_dir: str) -> tuple[SkillFile, ...]:
    path = Path(skills_dir)
    if not path.is_dir():
        return ()
    skills: list[SkillFile] = []
    for md_file in sorted(path.glob("*.md")):
        skill = _parse_skill_file(md_file)
        if skill is not None:
            skills.append(skill)
    logger.info("skills_loaded", count=len(skills), dir=skills_dir)
    return tuple(skills)


def _parse_skill_file(md_file: Path) -> SkillFile | None:
    try:
        raw = md_file.read_text(encoding="utf-8")
    except OSError:
        logger.warning("skill_file_read_error", file=str(md_file))
        return None

    match = _FRONTMATTER_RE.match(raw)
    if not match:
        return None

    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        logger.warning("skill_frontmatter_parse_error", file=str(md_file))
        return None

    name = meta.get("name") or md_file.stem
    description = meta.get("description", "")
    triggers = meta.get("triggers") or []

    return SkillFile(
        name=str(name),
        description=str(description),
        triggers=[str(t) for t in triggers],
        content=raw[match.end() :],
    )


def format_skills_for_prompt(skills: list[SkillFile]) -> str:
    """Format loaded skills as a block to append to the system prompt."""
    if not skills:
        return ""
    lines = ["", "## Available Skills", ""]
    for skill in skills:
        trigger_str = (
            ", ".join(skill.triggers) if skill.triggers else "any relevant request"
        )
        lines.append(f"### {skill.name}")
        lines.append(f"*{skill.description}* (triggers: {trigger_str})")
        lines.append("")
        if skill.content.strip():
            lines.append(skill.content.strip())
        lines.append("")
    lines.append("Follow the relevant skill instructions precisely when they apply.")
    return "\n".join(lines)
