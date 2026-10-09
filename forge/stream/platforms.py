"""Spicy livestream platform matrix.

Honest per-platform capabilities, verified 2026-10-09 from public
sources (see docs/STREAMING.md). Details change -- verify on each
platform's broadcaster pages before going live.

What "RTMP ingest: yes" means: she can stream to the platform from OBS
(or any RTMP encoder) using the stream key from her broadcaster
dashboard. What "chat API" means: whether CreatorForge can read/react
to live chat programmatically. Most cam sites offer NO chat API --
their official route is Chaturbate-style apps/bots (Chaturbate only)
or nothing. Where there is no API, chat automation is manual-assist.

ToS/verification: nearly all cam platforms require age+identity
verification of the REAL broadcaster before streaming. An AI avatar
standing in for a verified human is against most platforms' rules and
can get the account banned -- docs/STREAMING.md says this plainly per
platform instead of hiding it.
"""

from __future__ import annotations

from typing import Any

# chat_api: "apps" (official apps/bots API), "none" (no API), plus notes.
PLATFORMS: dict[str, dict[str, Any]] = {
    "chaturbate": {
        "label": "Chaturbate",
        "rtmp_ingest": True,
        "rtmp_notes": "Stream key from broadcaster dashboard; OBS RTMP.",
        "chat_api": "apps",
        "chat_notes": "Official Apps & Bots API for tip-triggered apps; "
                      "custom bots need broadcaster approval flow.",
        "verification": "Age 18+, ID verification required to broadcast.",
        "tos_risk": "HIGH for AI-avatar AFK: Chaturbate expects a live "
                    "performer; avatar-only streams risk reports/bans. "
                    "Tip bots via official Apps API are allowed.",
        "payout_notes": "~$0.05/token (viewers pay ~$0.10); ~60% model cut.",
    },
    "stripchat": {
        "label": "Stripchat",
        "rtmp_ingest": True,
        "rtmp_notes": "Stream key from model dashboard; OBS RTMP.",
        "chat_api": "none",
        "chat_notes": "No public chat API. Chat interaction is manual in "
                      "the site UI.",
        "verification": "Age 18+, ID verification required to broadcast.",
        "tos_risk": "HIGH for AI-avatar AFK: expects live performer; "
                    "account-ban risk. Manual chat only.",
        "payout_notes": "Token-based; competitive model cut.",
    },
    "bongacams": {
        "label": "BongaCams",
        "rtmp_ingest": True,
        "rtmp_notes": "RTMP ingest from broadcaster panel; OBS works.",
        "chat_api": "none",
        "chat_notes": "No public chat API.",
        "verification": "Age 18+, ID verification required.",
        "tos_risk": "HIGH for AI-avatar AFK: live-performer expectation; "
                    "ban risk.",
        "payout_notes": "Up to 90% model cut (among the highest).",
    },
    "camsoda": {
        "label": "CamSoda",
        "rtmp_ingest": True,
        "rtmp_notes": "OBS RTMP via broadcaster dashboard.",
        "chat_api": "none",
        "chat_notes": "No public chat API.",
        "verification": "Age 18+, ID verification required.",
        "tos_risk": "HIGH for AI-avatar AFK: live-performer expectation; "
                    "ban risk.",
        "payout_notes": "Token-based with private/VIP shows.",
    },
    "manyvids": {
        "label": "ManyVids",
        "rtmp_ingest": True,
        "rtmp_notes": "MV Live supports RTMP ingest from OBS.",
        "chat_api": "none",
        "chat_notes": "No public chat API.",
        "verification": "Age 18+, ID verification required.",
        "tos_risk": "MEDIUM-HIGH: MV Live expects live hosts; avatar AFK "
                    "is against the spirit of the rules -- ban risk.",
        "payout_notes": "Clip store + live; commission up to 40%.",
    },
    "myfreecams": {
        "label": "MyFreeCams",
        "rtmp_ingest": True,
        "rtmp_notes": "RTMP via broadcaster tools; OBS supported.",
        "chat_api": "none",
        "chat_notes": "No public chat API.",
        "verification": "Age 18+, ID verification; female-identifying "
                        "models only.",
        "tos_risk": "HIGH for AI-avatar AFK: expects live performer; ban "
                    "risk.",
        "payout_notes": "~60% model cut; loyal fanbase.",
    },
    "fansly-live": {
        "label": "Fansly Live",
        "rtmp_ingest": True,
        "rtmp_notes": "Go-live from creator dashboard; RTMP ingest.",
        "chat_api": "none",
        "chat_notes": "No public API for posting/messaging/stream chat.",
        "verification": "Creator verification required.",
        "tos_risk": "MEDIUM: her own verified account streaming her own "
                    "AI persona is a gray area -- read current ToS; "
                    "manual chat recommended.",
        "payout_notes": "Tied to her Fansly account earnings.",
    },
    "of-live": {
        "label": "OnlyFans Live",
        "rtmp_ingest": True,
        "rtmp_notes": "OF Live via the OF app/site; RTMP details in "
                      "creator dashboard.",
        "chat_api": "none",
        "chat_notes": "No public API. All chat is manual in the app.",
        "verification": "Creator verification required.",
        "tos_risk": "MEDIUM: own verified account; avatar-AFK is a gray "
                    "area -- read current ToS.",
        "payout_notes": "Tied to her OF earnings (subs/tips/PPV).",
    },
}


def list_platforms() -> list[dict[str, Any]]:
    """The full matrix as a list of dicts (with the platform key)."""
    return [{"key": k, **v} for k, v in PLATFORMS.items()]


def get_platform(key: str) -> dict[str, Any]:
    """One platform's matrix entry, or a ValueError listing valid keys."""
    k = key.lower().strip()
    if k not in PLATFORMS:
        raise ValueError(
            f"Unknown streaming platform {key!r}. Available: "
            + ", ".join(sorted(PLATFORMS)))
    return {"key": k, **PLATFORMS[k]}
