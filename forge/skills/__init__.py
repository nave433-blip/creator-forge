"""CreatorForge plugin/skill system.

Skills are small, auto-discovered capability plugins. A skill is any
Python module on the skill path that exposes a ``SKILL`` object (an
instance of :class:`Skill`) with:

- ``name``        -- unique id, e.g. "watermark"
- ``version``     -- "1.0.0"
- ``description`` -- one-line plain-English summary
- ``run(args)``   -- do the work; ``args`` is a list of CLI-style tokens
                    like ["--text", "hi", "in.png", "out.png"];
                    returns a human-readable result string.

Discovery: :func:`discover_skills` scans the built-in
``forge/skills/builtin/`` directory plus any extra directories listed
under ``skills.paths`` in forge.yaml. Drop a new ``.py`` file with a
``SKILL`` object in one of those dirs and it shows up in
``forge skills list`` with no other wiring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any, Callable


@dataclass
class Skill:
    """A capability plugin."""

    name: str
    version: str
    description: str
    run: Callable[[list[str]], str]
    usage: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


class SkillError(Exception):
    """Raised when a skill fails or is misused."""


def _load_skill_file(path: Path) -> Skill | None:
    """Import one .py file and return its SKILL object, if valid."""
    if path.name.startswith("_"):
        return None
    try:
        spec = spec_from_file_location(f"forge_skill_{path.stem}", path)
        if spec is None or spec.loader is None:
            return None
        module = module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception:
        return None  # a broken skill file never breaks discovery
    skill = getattr(module, "SKILL", None)
    if not isinstance(skill, Skill):
        return None
    return skill


def skill_dirs(config: Any = None) -> list[Path]:
    """Built-in dir + any extra dirs from config (skills.paths)."""
    dirs = [Path(__file__).resolve().parent / "builtin"]
    extra = []
    if config is not None:
        try:
            extra = config.get_path("skills.paths", []) or []
        except Exception:
            extra = []
    for e in extra:
        p = Path(e).expanduser()
        if p.is_dir():
            dirs.append(p)
    return dirs


def discover_skills(config: Any = None) -> dict[str, Skill]:
    """Find all skills. Later dirs override earlier ones on name clash."""
    found: dict[str, Skill] = {}
    for d in skill_dirs(config):
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.py")):
            skill = _load_skill_file(f)
            if skill is not None:
                found[skill.name] = skill
    return found


def get_skill(name: str, config: Any = None) -> Skill:
    skills = discover_skills(config)
    if name not in skills:
        known = ", ".join(sorted(skills)) or "(none found)"
        raise SkillError(f"No skill named {name!r}. Known skills: {known}")
    return skills[name]


def run_skill(name: str, args: list[str], config: Any = None) -> str:
    """Run a skill by name with CLI-style args. Returns its result text."""
    skill = get_skill(name, config)
    try:
        return skill.run(args)
    except SkillError:
        raise
    except SystemExit as e:
        # argparse usage errors (bad skill args) -- not a crash
        raise SkillError(f"Skill {name!r}: bad arguments (exit {e.code}). "
                         f"See `forge skills run {name} --help`.")
    except Exception as e:
        raise SkillError(f"Skill {name!r} failed: {e}") from e
