"""Scene director: "she didn't want to film it herself, so AI does it."

A scene template describes a shot: setting, outfit, camera angle, action,
and category tags. The creator's identity pack carries a `comfort`
section naming which categories she films herself vs which are AI-only:

```yaml
comfort:
  self_filmed: ["lifestyle", "talking-head"]   # use REAL catalog footage
  ai_only: ["fantasy", "cosplay"]              # generate with AI
```

`resolve_scene()` maps each requested scene to real footage, AI
generation, or refusal, and logs the decision. Anything uncategorized
is REFUSED -- the boundary defaults to "no", never "yes".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from forge.identity.pack import (
    InvalidConsentError,
    load_identity_pack,
    validate_identity_pack,
)


class SceneRefusedError(Exception):
    """Raised when a scene hits a comfort boundary the pack doesn't allow."""


@dataclass
class Scene:
    name: str
    setting: str = ""
    outfit: str = ""
    camera_angle: str = ""
    action: str = ""
    categories: list[str] = field(default_factory=list)
    prompt_extra: str = ""
    notes: str = ""

    def prompt(self, persona_token: str = "creatorpersona") -> str:
        parts = [f"{persona_token} woman"]
        if self.setting:
            parts.append(f"setting: {self.setting}")
        if self.outfit:
            parts.append(f"wearing {self.outfit}")
        if self.camera_angle:
            parts.append(f"camera: {self.camera_angle}")
        if self.action:
            parts.append(self.action)
        if self.prompt_extra:
            parts.append(self.prompt_extra)
        return ", ".join(parts)


@dataclass
class SceneDecision:
    scene: str
    mode: str  # "real" | "ai" | "refused"
    reason: str
    categories: list[str] = field(default_factory=list)
    catalog_items: list[dict[str, Any]] = field(default_factory=list)


def load_scene(path: str | Path) -> Scene:
    with Path(path).open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return Scene(
        name=data.get("name", Path(path).stem),
        setting=data.get("setting", ""),
        outfit=data.get("outfit", ""),
        camera_angle=data.get("camera_angle", ""),
        action=data.get("action", ""),
        categories=list(data.get("categories", [])),
        prompt_extra=data.get("prompt_extra", ""),
        notes=data.get("notes", ""),
    )


def validate_comfort_section(pack: dict[str, Any]) -> dict[str, list[str]]:
    """Return normalized comfort section; empty lists if absent."""
    comfort = pack.get("comfort", {}) or {}
    if not isinstance(comfort, dict):
        raise InvalidConsentError("'comfort' section must be a mapping.")
    out: dict[str, list[str]] = {}
    for key in ("self_filmed", "ai_only"):
        vals = comfort.get(key, []) or []
        if not isinstance(vals, list) or not all(isinstance(v, str) for v in vals):
            raise InvalidConsentError(
                f"'comfort.{key}' must be a list of category names.")
        out[key] = [v.strip().lower() for v in vals if v.strip()]
    return out


def resolve_scene(
    scene: Scene,
    pack: dict[str, Any],
    catalog_items: list[dict[str, Any]] | None = None,
) -> SceneDecision:
    """Decide real footage vs AI vs refusal for a scene.

    Rules:
    - every category in `ai_only` (and none in `self_filmed`) -> "ai"
    - every category in `self_filmed` (and none in `ai_only`) -> "real"
    - mixed, unknown, or empty categories -> "refused" (boundary defaults
      to no; she reviews and recategorizes)
    """
    comfort = validate_comfort_section(pack)
    cats = [c.strip().lower() for c in scene.categories if c.strip()]
    self_set = set(comfort["self_filmed"])
    ai_set = set(comfort["ai_only"])

    if not cats:
        return SceneDecision(scene.name, "refused",
                             "Scene has no categories; refusing until "
                             "categorized.", cats)
    in_self = [c for c in cats if c in self_set]
    in_ai = [c for c in cats if c in ai_set]
    unknown = [c for c in cats if c not in self_set and c not in ai_set]
    if unknown:
        return SceneDecision(
            scene.name, "refused",
            f"Categories not in comfort section: {unknown}. Add them to "
            "comfort.self_filmed or comfort.ai_only in the identity pack, "
            "with her agreement.", cats)
    if in_self and in_ai:
        return SceneDecision(
            scene.name, "refused",
            f"Categories span both boundaries (self: {in_self}, ai: {in_ai}). "
            "Ambiguous -- refusing until she clarifies.", cats)
    if in_ai:
        return SceneDecision(scene.name, "ai",
                             f"AI-only categories: {in_ai}. Generating with "
                             "her trained persona model.", cats)
    items = [i for i in (catalog_items or [])
             if set(i.get("tags", [])) & set(cats)]
    return SceneDecision(
        scene.name, "real",
        f"Self-filmed categories: {in_self}. Using real catalog footage "
        f"({len(items)} matching item(s)).", cats, items)


def resolve_scene_with_pack(
    scene_path: str | Path,
    identity_pack_path: str | Path,
    catalog_items: list[dict[str, Any]] | None = None,
) -> SceneDecision:
    """Load pack (validating consent) + scene, then resolve."""
    pack = validate_identity_pack(load_identity_pack(identity_pack_path))
    return resolve_scene(load_scene(scene_path), pack, catalog_items)


def log_decision(decision: SceneDecision, log_path: str | Path) -> Path:
    """Append a human-readable decision record to a log file."""
    from datetime import datetime
    p = Path(log_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(
            f"[{datetime.now().isoformat(timespec='seconds')}] "
            f"scene={decision.scene} mode={decision.mode} "
            f"categories={decision.categories} reason={decision.reason}\n"
        )
    return p
