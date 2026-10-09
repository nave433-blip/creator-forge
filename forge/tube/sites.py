"""Tube-site registry: honest per-site upload capability matrix.

Reality check (verified 2026-10-09): NONE of the major tube sites offer
a public upload API for regular creators. Pornhub only accepts uploads
from verified Model Program / content partners; xHamster only from
verified members/producers; XVideos/XNXX/RedTube/YouPorn are manual
dashboard uploads. Third-party "auto-upload" tools get accounts banned.

So every site here is manual-assist: CreatorForge prepares the video,
title, description, tags, and a step-by-step checklist -- she taps
"upload" on the site herself. The value is in the metadata engine
(forge/tube/metadata.py), not in fake automation.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TubeSite:
    key: str              # pornhub, xvideos, ...
    name: str
    upload_url: str       # where she uploads manually
    upload_mode: str = "manual"   # always manual; documented honestly
    needs_verification: bool = True
    title_limit: int = 100
    max_tags: int = 20
    description_limit: int = 4000
    notes: tuple[str, ...] = ()
    monetization: str = ""


SITES: tuple[TubeSite, ...] = (
    TubeSite(
        key="pornhub", name="Pornhub",
        upload_url="https://www.pornhub.com/model/upload",
        needs_verification=True, title_limit=100, max_tags=20,
        monetization="Model Program: ad-revenue share on views.",
        notes=(
            "Only verified Model Program / content partners can upload.",
            "7+ minute videos tend to perform best.",
            "Accurate titles/tags beat clickbait; mistagged videos get flagged.",
            "Translate titles/descriptions for more reach.",
            "Watermark with your username; end-cards can plug your paid sites.",
        ),
    ),
    TubeSite(
        key="xvideos", name="XVideos",
        upload_url="https://www.xvideos.com/upload",
        needs_verification=True, title_limit=120, max_tags=15,
        monetization="Content partner program pays per thousand views.",
        notes=(
            "One of the highest-traffic tubes; verification required.",
            "Use the site's own categories + your tags.",
        ),
    ),
    TubeSite(
        key="xnxx", name="XNXX",
        upload_url="https://www.xnxx.com/upload",
        needs_verification=True, title_limit=120, max_tags=15,
        monetization="Pays per views via partner program.",
        notes=("Sister site of XVideos; same manual upload flow.",),
    ),
    TubeSite(
        key="xhamster", name="xHamster",
        upload_url="https://xhamster.com/upload",
        needs_verification=True, title_limit=100, max_tags=10,
        monetization="Ad-revenue share; premium video sales; contests.",
        notes=(
            "Uploads limited to verified members/producers.",
            "Fewer tags allowed -- pick the 10 strongest.",
        ),
    ),
    TubeSite(
        key="redtube", name="RedTube",
        upload_url="https://www.redtube.com/upload",
        needs_verification=True, title_limit=100, max_tags=20,
        monetization="Partner revenue share.",
        notes=("Manual dashboard upload; verification required.",),
    ),
    TubeSite(
        key="youporn", name="YouPorn",
        upload_url="https://www.youporn.com/upload",
        needs_verification=True, title_limit=100, max_tags=20,
        monetization="Partner program revenue share.",
        notes=("Manual dashboard upload; verification required.",),
    ),
)


def get_site(key: str) -> TubeSite:
    for s in SITES:
        if s.key == key.strip().lower():
            return s
    raise KeyError(f"Unknown tube site {key!r}. "
                   f"Pick one of: {', '.join(s.key for s in SITES)}")


def list_sites() -> list[TubeSite]:
    return list(SITES)


def capability_rows() -> list[dict]:
    return [{
        "site": s.name, "key": s.key, "upload": s.upload_mode,
        "verification": "required" if s.needs_verification else "no",
        "monetization": s.monetization,
    } for s in SITES]
