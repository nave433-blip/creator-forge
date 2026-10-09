"""Text persona: learn how SHE writes from HER exported chats.

Input is ONLY chat history she provides herself (exported from her apps,
stored encrypted in the vault). Building a profile requires her valid
identity pack -- same consent gate as face/voice.

What gets learned (from HER messages only):
- slang/lexicon: most common non-stopword tokens
- emoji habits: how often she uses emoji, and which ones
- sentence length: average words per message
- openers/closers: how she starts and ends messages
- response latency: median time to reply (needs timestamps)

`draft_in_style()` applies the profile lightly to a base reply: her most
common closer, her emoji at her rate. It is a draft aid, not a voice
clone -- the human still reviews every draft in the approval queue.
See docs/STYLE.md.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from forge.identity.pack import (
    InvalidConsentError,
    load_identity_pack,
    validate_identity_pack,
)

EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F"
    "\U0001F000-\U0001F2FF\U0001F900-\U0001F9FF]"
)
WORD_RE = re.compile(r"[a-zA-Z0-9']+")

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for",
    "with", "is", "are", "was", "were", "it", "its", "i", "me", "my",
    "you", "your", "he", "she", "they", "them", "we", "us", "this",
    "that", "these", "those", "at", "by", "from", "as", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "can",
    "could", "should", "so", "if", "not", "no", "yes", "just", "like",
    "get", "got", "im", "dont", "cant", "wont", "ill", "id",
}


@dataclass
class StyleProfile:
    sample_count: int = 0
    avg_words_per_message: float = 0.0
    emoji_rate: float = 0.0  # fraction of her messages containing emoji
    top_emojis: list[tuple[str, int]] = field(default_factory=list)
    lexicon: list[tuple[str, int]] = field(default_factory=list)
    openers: list[tuple[str, int]] = field(default_factory=list)
    closers: list[tuple[str, int]] = field(default_factory=list)
    median_reply_latency_s: float | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # tuples -> lists for clean JSON
        for k in ("top_emojis", "lexicon", "openers", "closers"):
            d[k] = [list(t) for t in d[k]]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StyleProfile":
        d = dict(data)
        for k in ("top_emojis", "lexicon", "openers", "closers"):
            d[k] = [tuple(t) for t in d.get(k, [])]
        return cls(**d)


def _require_consent(identity_pack_path: str | None) -> None:
    if not identity_pack_path:
        raise InvalidConsentError(
            "Style profiling refused: no identity pack given. Style is "
            "learned from HER data and needs her consent record.")
    try:
        validate_identity_pack(load_identity_pack(identity_pack_path))
    except InvalidConsentError as e:
        raise InvalidConsentError(
            f"Style profiling refused: {e}") from e
    except OSError as e:
        raise InvalidConsentError(
            f"Style profiling refused: pack not found ({e})") from e


def build_style_profile(
    messages: list[dict[str, Any]],
    identity_pack_path: str | None = None,
) -> StyleProfile:
    """Build a style profile from exported chat messages.

    Each message: {"sender": "her"|"them", "text": str, "ts": float|None}.
    Only "her" messages are analyzed. Consent-gated via identity pack.
    """
    _require_consent(identity_pack_path)
    hers = [m for m in messages
            if m.get("sender") == "her" and str(m.get("text", "")).strip()]
    profile = StyleProfile(sample_count=len(hers))
    if not hers:
        return profile

    word_counts: list[int] = []
    emoji_msgs = 0
    emoji_counter: Counter[str] = Counter()
    lexicon: Counter[str] = Counter()
    openers: Counter[str] = Counter()
    closers: Counter[str] = Counter()

    for m in hers:
        text = str(m["text"]).strip()
        words = WORD_RE.findall(text.lower())
        word_counts.append(len(words))
        emojis = EMOJI_RE.findall(text)
        if emojis:
            emoji_msgs += 1
            emoji_counter.update(emojis)
        for w in words:
            if w not in STOPWORDS and len(w) > 1:
                lexicon[w] += 1
        tokens = text.split()
        if tokens:
            openers[" ".join(tokens[:3])] += 1
            closers[" ".join(tokens[-2:])] += 1

    profile.avg_words_per_message = round(
        statistics.fmean(word_counts), 2) if word_counts else 0.0
    profile.emoji_rate = round(emoji_msgs / len(hers), 3)
    profile.top_emojis = emoji_counter.most_common(10)
    profile.lexicon = lexicon.most_common(30)
    profile.openers = openers.most_common(10)
    profile.closers = closers.most_common(10)

    # Latency: her reply ts minus previous "them" ts, in order.
    latencies: list[float] = []
    last_them_ts: float | None = None
    for m in messages:
        ts = m.get("ts")
        if m.get("sender") == "them" and isinstance(ts, (int, float)):
            last_them_ts = float(ts)
        elif (m.get("sender") == "her" and isinstance(ts, (int, float))
                and last_them_ts is not None):
            delta = float(ts) - last_them_ts
            if 0 <= delta < 86400:
                latencies.append(delta)
            last_them_ts = None
    if latencies:
        profile.median_reply_latency_s = round(statistics.median(latencies), 1)
    return profile


def style_report_md(profile: StyleProfile) -> str:
    """Human-readable style report she can review and edit."""

    def lines(pairs: list[tuple[str, int]]) -> str:
        return "\n".join(f"- {a} ({n}x)" for a, n in pairs) or "- (none)"

    latency = (f"{profile.median_reply_latency_s}s"
               if profile.median_reply_latency_s is not None else "unknown")
    return f"""# Text style profile

Based on {profile.sample_count} of her messages. Review and edit -- this is
what the bot imitates, so fix anything that doesn't sound like her.

- Avg words per message: {profile.avg_words_per_message}
- Messages with emoji: {profile.emoji_rate * 100:.0f}%
- Median reply latency: {latency}

## Top emojis
{lines(profile.top_emojis)}

## Lexicon (her words)
{lines(profile.lexicon)}

## Openers
{lines(profile.openers)}

## Closers
{lines(profile.closers)}
"""


def draft_in_style(profile: StyleProfile, base_reply: str) -> str:
    """Lightly adapt a base reply toward her style.

    Applies her most common closer (if the reply lacks it) and her top
    emoji at roughly her observed rate. Deterministic and conservative --
    the human still reviews the draft.
    """
    reply = base_reply.strip()
    if profile.closers:
        closer = profile.closers[0][0]
        if closer.lower() not in reply.lower():
            reply = f"{reply} {closer}"
    if (profile.top_emojis and profile.emoji_rate >= 0.3
            and not EMOJI_RE.search(reply)):
        reply = f"{reply} {profile.top_emojis[0][0]}"
    return reply
