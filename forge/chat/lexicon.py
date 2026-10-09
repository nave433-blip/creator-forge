"""Custom word bank: her saved dictionary of terms, phrases, and words.

Sits next to the learned style profile (``forge/chat/style.py``). The
learned profile is *descriptive* (what her old chats said); the lexicon
is *prescriptive* (what SHE wants the bot to say). Custom entries always
win over learned ones when both exist.

Categories:
- ``slang``      -- her words ("papi", "fr", "lowkey")
- ``phrases``    -- signature multi-word lines ("come get this work")
- ``pet_names``  -- what she calls fans ("baby", "daddy", "pookie")
- ``emoji``      -- go-to emoji, in priority order
- ``openers``    -- how she starts messages
- ``closers``    -- how she ends messages
- ``spicy``      -- spicy-only terms (only used when spicy mode is on
  AND the identity pack's consent scope covers spicy chat)

Stored as plain JSON (``chat.lexicon_path``, default
``./forge-data/lexicon.json``) so she can review/edit it by hand.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CATEGORIES = (
    "slang",
    "phrases",
    "pet_names",
    "emoji",
    "openers",
    "closers",
    "spicy",
)

# {placeholder} tokens render() understands.
_PLACEHOLDER_RE = re.compile(
    r"\{(pet_name|phrase|slang|emoji|opener|closer|spicy|sender)\}")

# placeholder name -> lexicon category
_PLACEHOLDER_CATEGORIES = {
    "pet_name": "pet_names",
    "phrase": "phrases",
    "slang": "slang",
    "emoji": "emoji",
    "opener": "openers",
    "closer": "closers",
    "spicy": "spicy",
}


@dataclass
class LexiconEntry:
    term: str
    note: str = ""
    added: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"term": self.term, "note": self.note, "added": self.added}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LexiconEntry":
        return cls(term=str(data.get("term", "")),
                   note=str(data.get("note", "")),
                   added=float(data.get("added", 0) or 0))


class CustomLexicon:
    """Her saved word bank. Plain data object; use save()/load() for disk."""

    def __init__(self, entries: dict[str, list[LexiconEntry]] | None = None):
        self.entries: dict[str, list[LexiconEntry]] = {
            c: [] for c in CATEGORIES
        }
        if entries:
            for cat, items in entries.items():
                if cat in self.entries:
                    self.entries[cat] = list(items)

    # -- CRUD -----------------------------------------------------------
    def add(self, category: str, term: str, note: str = "") -> bool:
        """Add a term. Returns False if it's already there (no dupes)."""
        self._check_category(category)
        term = term.strip()
        if not term:
            raise ValueError("term must not be empty")
        if any(e.term.lower() == term.lower() for e in self.entries[category]):
            return False
        self.entries[category].append(LexiconEntry(term=term, note=note))
        return True

    def remove(self, category: str, term: str) -> bool:
        """Remove a term. Returns False if it wasn't there."""
        self._check_category(category)
        before = len(self.entries[category])
        self.entries[category] = [
            e for e in self.entries[category]
            if e.term.lower() != term.strip().lower()
        ]
        return len(self.entries[category]) < before

    def list(self, category: str | None = None) -> dict[str, list[LexiconEntry]]:
        if category is not None:
            self._check_category(category)
            return {category: list(self.entries[category])}
        return {c: list(v) for c, v in self.entries.items()}

    def search(self, query: str) -> list[tuple[str, LexiconEntry]]:
        q = query.strip().lower()
        hits = []
        for cat, items in self.entries.items():
            for e in items:
                if q in e.term.lower() or q in e.note.lower():
                    hits.append((cat, e))
        return hits

    def first(self, category: str) -> str | None:
        """Top-priority term in a category (insertion order = priority)."""
        self._check_category(category)
        return self.entries[category][0].term if self.entries[category] else None

    @staticmethod
    def _check_category(category: str) -> None:
        if category not in CATEGORIES:
            raise ValueError(
                f"unknown category {category!r}; pick one of {CATEGORIES}")

    # -- rendering ------------------------------------------------------
    def render(self, template: str, sender: str = "",
               allow_spicy: bool = False) -> str:
        """Fill {placeholders} in a template from the word bank.

        Supported: {pet_name} {phrase} {slang} {emoji} {opener} {closer}
        {spicy} {sender}. Unknown/missing placeholders are left as-is so
        nothing silently vanishes. Spicy terms only render with
        allow_spicy=True.
        """
        def pick(placeholder: str) -> str | None:
            if placeholder == "spicy" and not allow_spicy:
                return None
            return self.first(_PLACEHOLDER_CATEGORIES[placeholder])

        def repl(m: re.Match) -> str:
            key = m.group(1)
            if key == "sender":
                return sender
            term = pick(key)
            return term if term is not None else m.group(0)

        return _PLACEHOLDER_RE.sub(repl, template)

    # -- learning bridge ------------------------------------------------
    def adopt_from_profile(self, profile: Any, n: int = 10,
                           category: str = "slang") -> list[str]:
        """Promote top learned words from a StyleProfile into the bank.

        She reviews the bank afterwards -- this just saves her typing.
        Returns the terms actually added (dupes skipped).
        """
        self._check_category(category)
        added = []
        for word, _count in getattr(profile, "lexicon", [])[:n]:
            if self.add(category, word, note="adopted from style profile"):
                added.append(word)
        return added

    # -- persistence ----------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {"categories": list(CATEGORIES),
                "entries": {c: [e.to_dict() for e in v]
                            for c, v in self.entries.items()}}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CustomLexicon":
        entries = {}
        for cat, items in (data.get("entries") or {}).items():
            if cat in CATEGORIES:
                entries[cat] = [LexiconEntry.from_dict(i) for i in items]
        return cls(entries)

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
                     encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: str | Path) -> "CustomLexicon":
        p = Path(path)
        if not p.is_file():
            return cls()
        return cls.from_dict(json.loads(p.read_text(encoding="utf-8")))


def draft_in_style(profile: Any, base_reply: str,
                   lexicon: CustomLexicon | None = None,
                   allow_spicy: bool = False) -> str:
    """Lightly adapt a base reply toward her style.

    Custom word bank wins over the learned profile: her saved closer,
    opener, and emoji are preferred; the learned profile fills gaps.
    Deterministic and conservative -- the human still reviews the draft.
    """
    from forge.chat.style import EMOJI_RE
    reply = base_reply.strip()
    if lexicon is not None:
        opener = lexicon.first("openers")
        if opener and opener.lower() not in reply.lower():
            reply = f"{opener} {reply}"
        closer = lexicon.first("closers")
        if closer and closer.lower() not in reply.lower():
            reply = f"{reply} {closer}"
        emoji = lexicon.first("emoji")
        if emoji and not EMOJI_RE.search(reply):
            reply = f"{reply} {emoji}"
        _ = allow_spicy  # spicy terms only via explicit render(), never auto
        return reply
    # No word bank: fall back to the learned profile only.
    if getattr(profile, "closers", None):
        closer = profile.closers[0][0]
        if closer.lower() not in reply.lower():
            reply = f"{reply} {closer}"
    top_emojis = getattr(profile, "top_emojis", [])
    if (top_emojis and getattr(profile, "emoji_rate", 0) >= 0.3
            and not EMOJI_RE.search(reply)):
        reply = f"{reply} {top_emojis[0][0]}"
    return reply
