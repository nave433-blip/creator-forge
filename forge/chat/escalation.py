"""Escalation flags: spot messages that need HER eyes, not the bot's.

This is a simple keyword lexicon -- NOT machine learning, NOT sentiment
AI, and it never claims to understand tone. It just flags messages
containing words/phrases that usually mean "a human should handle this":
anger, threats, chargebacks, legal talk, self-harm, or platform-rule
trouble. Flagged drafts get ``escalated=True`` and show up highlighted
in the queue.

She can extend the lists in forge.yaml under ``chat.escalation``.
"""

from __future__ import annotations

import re
from typing import Any

# category -> words/phrases (matched case-insensitively, substring)
DEFAULT_LEXICON: dict[str, list[str]] = {
    "angry": [
        "angry", "furious", "pissed", "hate you", "stupid", "idiot",
        "dumb", "shut up", "fuck you",
    ],
    "refund": [
        "refund", "chargeback", "dispute", "scam", "ripoff", "ripped off",
        "give my money back",
    ],
    "legal": [
        "lawyer", "sue", "court", "police", "report you", "illegal",
    ],
    "self-harm": [
        "kill myself", "suicide", "end it all", "hurt myself",
        "don't want to live",
    ],
    "platform-risk": [
        "ban", "banned", "suspended", "tos", "terms of service",
    ],
}


def _compile(lexicon: dict[str, list[str]]) -> dict[str, re.Pattern]:
    return {
        cat: re.compile("|".join(re.escape(w) for w in words), re.IGNORECASE)
        for cat, words in lexicon.items() if words
    }


def merge_lexicon(config: Any = None) -> dict[str, list[str]]:
    """DEFAULT_LEXICON plus any extra words from config chat.escalation."""
    lex = {cat: list(words) for cat, words in DEFAULT_LEXICON.items()}
    extra: dict[str, list[str]] = {}
    if config is not None:
        try:
            extra = config.get_path("chat.escalation", {}) or {}
        except Exception:
            extra = {}
    for cat, words in extra.items():
        lex.setdefault(cat, []).extend(words)
    return lex


def flag_message(text: str, config: Any = None) -> list[str]:
    """Return the escalation categories matched in ``text`` (may be empty).

    Pure function: no ML, no API calls, no claims beyond keyword hits.
    """
    if not text:
        return []
    patterns = _compile(merge_lexicon(config))
    return [cat for cat, rx in patterns.items() if rx.search(text)]


def analyze(text: str, config: Any = None) -> dict[str, Any]:
    """Full analysis dict for a message: categories + boolean."""
    cats = flag_message(text, config)
    return {"escalated": bool(cats), "categories": cats}
