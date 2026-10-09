"""Content ideas generator -- template-based, honestly labeled.

Combines HER caption templates, HER hashtag sets, and tags from HER
catalog into fresh post ideas. This is a remix engine over her own
material, NOT generative AI and NOT "AI magic": it recombines what she
already made. She picks what she likes and rewrites the rest.
"""

from __future__ import annotations

import random
from typing import Any

DEFAULT_CAPTION_TEMPLATES = [
    "POV: {tag} but make it personal",
    "Rating my {tag} era, 1-10?",
    "You asked for {tag}, I delivered",
    "Behind the scenes: {tag} edition",
    "{tag} hits different at 2am",
    "New drop: {tag}. Tip menu's pinned if you want the full thing",
]

DEFAULT_HASHTAG_SETS = [
    ["#contentcreator", "#exclusivecontent", "#linkinbio"],
    ["#behindthescenes", "#newdrop", "#foryou"],
    ["#customcontent", "#tipmenu", "#dmme"],
]

DEFAULT_ANGLES = [
    "teaser clip (15s)", "photo set (5)", "poll: what next?",
    "throwback", "tip-menu push", "Q&A replies",
]


def _seeded(tags: list[str], salt: str) -> random.Random:
    import hashlib
    h = int(hashlib.sha256(
        (salt + "|".join(sorted(tags))).encode()).hexdigest(), 16)
    return random.Random(h)


def generate_ideas(*, catalog_tags: list[str],
                   caption_templates: list[str] | None = None,
                   hashtag_sets: list[list[str]] | None = None,
                   angles: list[str] | None = None,
                   count: int = 10,
                   seed_salt: str = "forge") -> list[dict[str, Any]]:
    """Generate `count` post ideas from her tags + templates.

    Deterministic for the same inputs (stable previews); pass a
    different seed_salt for a fresh batch.
    """
    templates = caption_templates or DEFAULT_CAPTION_TEMPLATES
    hsets = hashtag_sets or DEFAULT_HASHTAG_SETS
    ang = angles or DEFAULT_ANGLES
    tags = catalog_tags or ["new content"]
    rng = _seeded(tags, seed_salt)
    ideas = []
    for _ in range(count):
        tag = rng.choice(tags)
        ideas.append({
            "caption": rng.choice(templates).format(tag=tag),
            "hashtags": " ".join(rng.choice(hsets)),
            "angle": rng.choice(ang),
            "tag": tag,
            "method": "template remix of her own tags (not generative AI)",
        })
    return ideas


def catalog_tags_for_ideas(items: list[dict[str, Any]],
                           limit: int = 40) -> list[str]:
    """Pull the most common tags from catalog items for idea generation."""
    from collections import Counter
    c: Counter[str] = Counter()
    for it in items:
        for t in it.get("tags", []) or []:
            c[t] += 1
    return [t for t, _ in c.most_common(limit)]
