"""Metadata engine: titles, descriptions, and auto-tags for tube uploads.

This is the real value of the tube module. Since every major tube site
is manual upload (see sites.py), what actually saves her hours is NOT
fake auto-posting -- it's great metadata, generated per site, ready to
copy-paste:

- titles from templates (SEO-friendly, per-site length limits)
- descriptions with her links (tip menu, socials) baked in
- auto-tags: her catalog tags + scene keywords + a curated tag taxonomy,
  trimmed to each site's tag limit, deduped, ordered by strength

Everything is editable before it ships -- the packet files are plain
text she can tweak.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from forge.tube.sites import TubeSite

# Curated tag taxonomy: standard, non-graphic tube categories.
# (Deliberately SFW-worded -- the sites map these to their own
# categories. She adds her own edge via custom tags.)
TAG_TAXONOMY: dict[str, tuple[str, ...]] = {
    "format": ("amateur", "homemade", "webcam", "pov", "solo", "duo"),
    "look": ("blonde", "brunette", "redhead", "latina", "ebony", "asian",
             "petite", "curvy", "tattooed"),
    "wardrobe": ("lingerie", "bikini", "stockings", "heels", "cosplay",
                 "uniform"),
    "vibe": ("sensual", "tease", "striptease", "massage", "shower",
             "bedroom", "outdoor"),
    "style": ("4k", "hd", "vertical", "asmr", "roleplay", "joi"),
}

TITLE_TEMPLATES = (
    "{vibe} {outfit} {scene}",
    "{scene} - {vibe} {outfit}",
    "{name} | {vibe} {scene}",
    "{outfit} {scene} ({vibe})",
)

_WORD_RE = re.compile(r"[a-z0-9]+")


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def suggest_tags(scene: dict | None = None,
                 catalog_tags: list[str] | None = None,
                 custom_tags: list[str] | None = None,
                 max_tags: int = 20) -> list[str]:
    """Build an ordered, deduped tag list.

    Priority: her custom tags > catalog tags > scene keywords matched
    against the taxonomy. Never invents graphic terms; everything comes
    from her inputs or the curated taxonomy.
    """
    seen: list[str] = []

    def push(tag: str) -> None:
        t = tag.strip().lower().replace(" ", "-")
        if t and t not in seen:
            seen.append(t)

    for t in (custom_tags or []):
        push(t)
    for t in (catalog_tags or []):
        push(t)
    if scene:
        hay = " ".join(str(v) for v in scene.values() if v).lower()
        for _group, tags in TAG_TAXONOMY.items():
            for tag in tags:
                if tag in hay:
                    push(tag)
    return seen[:max_tags]


def build_title(scene: dict | None = None, name: str = "",
                template_idx: int = 0, limit: int = 100) -> str:
    """Render a title from a template; truncated to the site's limit."""
    scene = scene or {}
    template = TITLE_TEMPLATES[template_idx % len(TITLE_TEMPLATES)]
    title = template.format(
        vibe=str(scene.get("vibe", "") or "").strip(),
        outfit=str(scene.get("outfit", "") or "").strip(),
        scene=str(scene.get("setting", scene.get("scene", "")) or "").strip(),
        name=name.strip(),
    )
    title = re.sub(r"\s+", " ", title).strip(" -|")
    if len(title) > limit:
        title = title[:limit].rsplit(" ", 1)[0]
    return title or "New video"


def build_description(scene: dict | None = None, links: dict | None = None,
                      hashtags: list[str] | None = None,
                      extra: str = "", limit: int = 4000) -> str:
    """Description: what the video is + her links + hashtags."""
    scene = scene or {}
    lines: list[str] = []
    vibe = str(scene.get("vibe", "") or "").strip()
    setting = str(scene.get("setting", scene.get("scene", "")) or "").strip()
    if vibe or setting:
        lines.append(" ".join(p for p in (vibe, setting) if p).capitalize() + ".")
    if extra.strip():
        lines.append(extra.strip())
    if links:
        lines.append("")
        lines.append("Find me:")
        for label, url in links.items():
            lines.append(f"{label}: {url}")
    tags = [t for t in (hashtags or []) if t]
    if tags:
        lines.append("")
        lines.append(" ".join("#" + t.replace("-", "") for t in tags[:10]))
    desc = "\n".join(lines).strip()
    return desc[:limit]


@dataclass
class VideoMetadata:
    site_key: str
    title: str
    description: str
    tags: list[str] = field(default_factory=list)
    notes: tuple[str, ...] = ()
    tags_truncated: bool = False  # True if the site's tag limit cut some

    def to_dict(self) -> dict:
        return {"site": self.site_key, "title": self.title,
                "description": self.description, "tags": self.tags,
                "tags_truncated": self.tags_truncated,
                "notes": list(self.notes)}


def generate_metadata(site: TubeSite, scene: dict | None = None,
                      name: str = "", catalog_tags: list[str] | None = None,
                      custom_tags: list[str] | None = None,
                      links: dict | None = None,
                      extra_description: str = "",
                      template_idx: int = 0) -> VideoMetadata:
    """Full metadata packet for one video on one site."""
    all_tags = suggest_tags(scene, catalog_tags, custom_tags,
                            max_tags=10_000)
    tags = all_tags[:site.max_tags]
    return VideoMetadata(
        site_key=site.key,
        title=build_title(scene, name, template_idx, site.title_limit),
        description=build_description(
            scene, links, hashtags=tags,
            extra=extra_description, limit=site.description_limit),
        tags=tags,
        tags_truncated=len(all_tags) > len(tags),
        notes=site.notes,
    )
