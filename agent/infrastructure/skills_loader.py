"""Load Anthropic-style Skills (SKILL.md) from local directories.

Supports multiple directories compatible with Anthropic Skills format:
- Project: .claude/skills/ or skills/
- User: ~/.claude/skills/
- Custom: SKILLS_DIR env (single path or comma-separated)

Each skill is a directory with SKILL.md containing YAML frontmatter and Markdown body.
"""

from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


def _parse_frontmatter(content: str) -> tuple[Optional[dict], str]:
    """Extract YAML frontmatter and return (metadata, body)."""
    if not content.strip().startswith("---"):
        return None, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, content

    frontmatter_str = parts[1].strip()
    body = parts[2].strip()

    if not frontmatter_str:
        return None, body

    if yaml:
        try:
            meta = yaml.safe_load(frontmatter_str)
            return meta if isinstance(meta, dict) else None, body
        except Exception:
            return None, body

    # Fallback: simple key: value parsing
    meta = {}
    for line in frontmatter_str.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip().lower()] = v.strip().strip('"\'')
    return meta if meta else None, body


def _load_skill(skill_dir: Path) -> Optional[tuple[str, str, str]]:
    """
    Load a single skill. Returns (name, description, body) or None if invalid.
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None

    content = skill_md.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(content)

    name = skill_dir.name
    description = ""

    if meta:
        name = meta.get("name", name)
        description = meta.get("description", "")

    if not body and not description:
        return None

    return (name, description, body)


def get_skills_directories(
    project_root: Optional[Path] = None,
    skills_dir_env: Optional[str] = None,
    include_user: bool = True,
    include_project: bool = True,
) -> list[Path]:
    """
    Return list of skill directories to search, in priority order.

    Order: custom (SKILLS_DIR) -> project (.claude/skills, skills) -> user (~/.claude/skills)
    """
    dirs: list[Path] = []
    root = Path(project_root).resolve() if project_root else Path.cwd()

    # 1. Custom from env (comma-separated or single path)
    if skills_dir_env:
        for p in skills_dir_env.split(","):
            path = Path(p.strip()).expanduser().resolve()
            if path.exists() and path not in dirs:
                dirs.append(path)

    # 2. Project directories
    if include_project:
        for subdir in [".claude/skills", "skills"]:
            path = (root / subdir).resolve()
            if path.exists() and path not in dirs:
                dirs.append(path)

    # 3. User directory
    if include_user:
        user_skills = Path.home() / ".claude" / "skills"
        if user_skills.exists() and user_skills not in dirs:
            dirs.append(user_skills)

    return dirs


def load_skills(
    skills_dir: Optional[Path] = None,
    skills_dirs: Optional[list[Path]] = None,
    project_root: Optional[Path] = None,
    include_metadata: bool = True,
) -> str:
    """
    Load all SKILL.md files from skill directories and concatenate into instructions.

    Args:
        skills_dir: Single directory (legacy, overrides skills_dirs if set).
        skills_dirs: Explicit list of directories to search.
        project_root: Project root for .claude/skills and skills/ resolution.
        include_metadata: Include name and description in output for skill discovery.

    Returns:
        Concatenated skill instructions for the agent system prompt.
    """
    import os

    if skills_dir is not None:
        search_dirs = [Path(skills_dir).expanduser().resolve()]
    elif skills_dirs:
        search_dirs = [Path(d).expanduser().resolve() for d in skills_dirs]
    else:
        search_dirs = get_skills_directories(
            project_root=project_root,
            skills_dir_env=os.environ.get("SKILLS_DIR"),
            include_user=os.environ.get("SKILLS_INCLUDE_USER", "true").lower()
            in ("1", "true", "yes"),
            include_project=os.environ.get("SKILLS_INCLUDE_PROJECT", "true").lower()
            in ("1", "true", "yes"),
        )

    seen_names: set[str] = set()
    instructions_parts: list[str] = []

    for skills_path in search_dirs:
        if not skills_path.exists():
            continue
        for skill_path in sorted(skills_path.iterdir()):
            if not skill_path.is_dir():
                continue
            result = _load_skill(skill_path)
            if result is None:
                continue
            name, description, body = result
            if name in seen_names:
                continue
            seen_names.add(name)

            if include_metadata and description:
                header = f"## Skill: {name}\n\n**When to use:** {description}\n\n"
            else:
                header = f"## Skill: {name}\n\n"
            instructions_parts.append(header + (body or ""))

    if not instructions_parts:
        return ""
    return "\n\n---\n\n".join(instructions_parts)


def list_skills_metadata(
    skills_dir: Optional[Path] = None,
    skills_dirs: Optional[list[Path]] = None,
    project_root: Optional[Path] = None,
) -> list[dict[str, str]]:
    """Return skill name + description for routing/classification."""
    import os

    if skills_dir is not None:
        search_dirs = [Path(skills_dir).expanduser().resolve()]
    elif skills_dirs:
        search_dirs = [Path(d).expanduser().resolve() for d in skills_dirs]
    else:
        search_dirs = get_skills_directories(
            project_root=project_root,
            skills_dir_env=os.environ.get("SKILLS_DIR"),
        )

    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for skills_path in search_dirs:
        if not skills_path.exists():
            continue
        for skill_path in sorted(skills_path.iterdir()):
            if not skill_path.is_dir():
                continue
            loaded = _load_skill(skill_path)
            if loaded is None:
                continue
            name, description, _body = loaded
            if name in seen:
                continue
            seen.add(name)
            result.append({"name": name, "description": description})
    return result


def load_skill_by_name(
    skill_name: str,
    skills_dir: Optional[Path] = None,
    project_root: Optional[Path] = None,
) -> str:
    """Load a single skill's instructions by name."""
    import os

    search_dirs: list[Path] = []
    if skills_dir is not None:
        search_dirs = [Path(skills_dir).expanduser().resolve()]
    else:
        search_dirs = get_skills_directories(
            project_root=project_root,
            skills_dir_env=os.environ.get("SKILLS_DIR"),
        )

    for skills_path in search_dirs:
        if not skills_path.exists():
            continue
        for skill_path in sorted(skills_path.iterdir()):
            if not skill_path.is_dir():
                continue
            loaded = _load_skill(skill_path)
            if loaded is None:
                continue
            name, description, body = loaded
            if name != skill_name:
                continue
            header = f"## Skill: {name}\n\n**When to use:** {description}\n\n" if description else f"## Skill: {name}\n\n"
            return header + (body or "")
    return ""
