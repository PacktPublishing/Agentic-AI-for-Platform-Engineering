"""Load agent skills from disk into the system prompt.

Skills are folders under SKILLS_DIR, each containing a SKILL.md with YAML
frontmatter (name, description, when_to_use, constraints) and a body of
procedural knowledge. We expose the metadata of every skill in the system
prompt at startup, so the agent knows what it can specialize on. Progressive
disclosure of full skill bodies happens at runtime via load_skill_body().
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .settings import settings


@dataclass
class SkillMetadata:
    name: str
    description: str
    body_path: Path

    def metadata_block(self) -> str:
        return f"### {self.name}\n{self.description.strip()}"


def _split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, parts[2].lstrip("\n")


def discover_skills() -> list[SkillMetadata]:
    base = settings.skills_dir
    if not base.exists():
        return []
    out = []
    for sk in sorted(base.iterdir()):
        skill_md = sk / "SKILL.md"
        if not skill_md.is_file():
            continue
        meta, _body = _split_frontmatter(skill_md.read_text(encoding="utf-8"))
        out.append(
            SkillMetadata(
                name=meta.get("name", sk.name),
                description=str(meta.get("description", "")),
                body_path=skill_md,
            )
        )
    return out


def load_skill_body(name: str) -> str | None:
    """Read the full SKILL.md (frontmatter + body) for `name`. Used by the
    `consult_skill` tool when the model decides a skill matches the intent."""
    for sk in discover_skills():
        if sk.name == name:
            return sk.body_path.read_text(encoding="utf-8")
    return None


def skills_system_prompt_section() -> str:
    skills = discover_skills()
    if not skills:
        return ""
    blocks = "\n\n".join(s.metadata_block() for s in skills)
    return (
        "# Skills available\n\n"
        "Each skill below is a procedure for a specific situation. When a user's "
        "intent matches one of these descriptions, call `consult_skill(name=...)` "
        "to load the full procedure before acting.\n\n"
        f"{blocks}"
    )
