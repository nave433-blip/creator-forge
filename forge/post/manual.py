"""Manual-assist posting: for platforms with NO posting API.

Snapchat has no public posting API. OnlyFans has no public posting or
messaging API. Automating them anyway (bots, scraped sessions) risks
permanent bans and violates their terms.

So this module does what CAN be done honestly: it builds a "posting
packet" directory per platform containing the media file (copied),
a ready-to-paste caption, hashtags, and a step-by-step checklist
(open app -> upload -> paste caption -> post). The human does the final
tap; CreatorForge does the prep.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


def _checklist(platform: str) -> list[str]:
    base = [
        "Open the {p} app on your phone.",
        "Upload the media file from packet/media/.",
        "Copy the caption from packet/caption.txt and paste it.",
        "Add the hashtags from packet/hashtags.txt if the platform uses them.",
        "Double-check the preview, then post.",
        "Mark this packet DONE in the dashboard (or rename the folder).",
    ]
    return [step.format(p=platform) for step in base]


def build_posting_packet(
    *,
    platform: str,
    media_path: str | Path,
    caption: str,
    hashtags: list[str] | None = None,
    out_dir: str | Path,
    title: str = "",
    scheduled_for: str = "",
    extra_notes: str = "",
) -> Path:
    """Create a posting packet directory.

    Layout::

        <out_dir>/<platform>-<timestamp>/
            media/<original filename>
            caption.txt
            hashtags.txt
            checklist.md
            packet.yaml   (metadata)

    Returns the packet directory path.
    """
    import yaml

    media_path = Path(media_path)
    if not media_path.is_file():
        raise ValueError(f"Media file not found: {media_path}")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    packet_dir = Path(out_dir) / f"{platform.lower()}-{stamp}"
    media_dir = packet_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(media_path, media_dir / media_path.name)
    (packet_dir / "caption.txt").write_text(caption.strip() + "\n",
                                            encoding="utf-8")
    (packet_dir / "hashtags.txt").write_text(
        " ".join(hashtags or []) + "\n", encoding="utf-8")
    (packet_dir / "checklist.md").write_text(
        "# Posting checklist: " + platform + "\n\n"
        + "\n".join(f"- [ ] {s}" for s in _checklist(platform)) + "\n",
        encoding="utf-8",
    )
    meta: dict[str, Any] = {
        "platform": platform,
        "title": title,
        "media": media_path.name,
        "scheduled_for": scheduled_for,
        "extra_notes": extra_notes,
        "created": datetime.now().isoformat(timespec="seconds"),
        "status": "ready",
        "disclaimer": (
            f"{platform} has no public posting API; this packet is for "
            "manual posting. Do not use automation tools against it -- "
            "accounts get banned."
        ),
    }
    with (packet_dir / "packet.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(meta, fh, sort_keys=False)
    return packet_dir


def export_content_calendar(
    packets: list[dict[str, Any]],
    out_csv: str | Path,
) -> Path:
    """Export a simple CSV content calendar from packet metadata dicts.

    Each dict should have: platform, title, scheduled_for, media, status.
    Useful for planning OnlyFans/Snapchat queues outside any API.
    """
    import csv

    out = Path(out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh, fieldnames=["scheduled_for", "platform", "title",
                            "media", "status"])
        w.writeheader()
        for p in packets:
            w.writerow({k: p.get(k, "") for k in w.fieldnames})
    return out
