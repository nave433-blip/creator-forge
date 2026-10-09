"""Smart mass-DM builder.

Compose once -> personalized per fan -> per-platform send packets.

Honest delivery model: only platforms with a real messaging API can send
from here (Reddit via PRAW where configured). Everywhere else
(OnlyFans, Fansly, Snapchat) the output is a MANUAL-ASSIST packet: a
folder with per-fan message files + a checklist, because those sites have
no messaging API and automating them risks her account. The scheduler
(`forge post schedule`) can remind her when a mass-DM is due -- it never
sends anything itself.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def personalize(template: str, fan: dict[str, Any]) -> str:
    """Fill {handle}, {first}, {spend} placeholders for one fan."""
    first = str(fan.get("handle", "")).split()[0]
    text = template.replace("{handle}", str(fan.get("handle", "")))
    text = text.replace("{first}", first)
    text = text.replace("{spend}", f"{fan.get('total_spend', 0):.0f}")
    return text


def build_mass_dm(*, message_template: str, fans: list[dict[str, Any]],
                  platform: str, out_dir: str | Path,
                  exclude_recently_chatted: bool = True,
                  recent_handles: set[str] | None = None,
                  dry_run: bool = True) -> dict[str, Any]:
    """Build a mass-DM packet.

    Returns a summary; writes per-fan .txt files + manifest.json into a
    timestamped packet dir under out_dir. dry_run=True (default) only
    reports who WOULD get it.
    """
    recent_handles = recent_handles or set()
    targets = []
    skipped = 0
    for fan in fans:
        if (exclude_recently_chatted
                and fan.get("handle") in recent_handles):
            skipped += 1
            continue
        targets.append(fan)

    packet_dir = Path(out_dir) / (
        "massdm-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    manifest = {
        "platform": platform,
        "created": datetime.now().isoformat(timespec="seconds"),
        "template": message_template,
        "targets": len(targets),
        "skipped_recent": skipped,
        "dry_run": dry_run,
        "delivery": ("manual-assist: copy/paste each message in the "
                     "platform's app -- no messaging API exists here.")
        if platform.lower() in ("onlyfans", "fansly", "snapchat", "of")
        else "api where configured; otherwise manual-assist",
        "fans": [f.get("handle") for f in targets],
    }
    if not dry_run:
        packet_dir.mkdir(parents=True, exist_ok=True)
        for fan in targets:
            safe = "".join(c if c.isalnum() or c in "-_"
                           else "_" for c in str(fan.get("handle")))
            (packet_dir / f"{safe}.txt").write_text(
                personalize(message_template, fan), encoding="utf-8")
        (packet_dir / "manifest.json").write_text(
            __import__("json").dumps(manifest, indent=2), encoding="utf-8")
        (packet_dir / "CHECKLIST.md").write_text(
            "# Mass-DM checklist\n\n"
            f"Platform: {platform} (manual-assist -- no messaging API)\n\n"
            "For each fan file below: open the chat in the app, paste the\n"
            "message, personalize further if you like, send, then tick it\n"
            "off. Log any purchases with `forge crm spend`.\n\n"
            + "".join(f"- [ ] {f.get('handle')}\n" for f in targets),
            encoding="utf-8")
    manifest["packet_dir"] = str(packet_dir) if not dry_run else None
    return manifest
