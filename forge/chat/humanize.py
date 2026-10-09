"""Draft humanizer: typo simulation, tone fixer, translation hook.

Makes bot drafts read like a real person typing fast on a phone --
because perfect grammar is the fastest way to look like a bot.

- typo_simulate(text, intensity): adjacent-key swaps, dropped doubled
  letters, missing apostrophes. intensity 0.0 (off) to 1.0 (heavy).
  Deterministic per text+seed so previews are stable.
- tone_fix(text, style): optional lowercase-everything, light emoji
  sprinkle from her style profile, punctuation normalization.
- translate(text, target, endpoint): OPTIONAL LibreTranslate-compatible
  HTTP endpoint. Basic machine translation, honestly labeled -- not
  professional quality. Raises TranslationNotConfigured when unset.

Everything here is post-processing on a draft she still approves.
"""

from __future__ import annotations

import random
import re
from typing import Any

_APOS = {"dont": "don't", "cant": "can't", "wont": "won't",
         "im": "i'm", "ive": "i've", "id": "i'd", "ill": "i'll",
         "youre": "you're", "thats": "that's", "its": "it's",
         "lets": "let's", "whats": "what's"}


def _seeded(text: str, salt: str) -> random.Random:
    import hashlib
    h = int(hashlib.sha256((salt + text).encode()).hexdigest(), 16)
    return random.Random(h)


def typo_simulate(text: str, intensity: float = 0.15,
                  seed_salt: str = "forge") -> str:
    """Sprinkle realistic phone typos. intensity 0.0-1.0 (0.15 = light)."""
    if intensity <= 0 or not text:
        return text
    rng = _seeded(text, seed_salt)
    chars = list(text)
    out: list[str] = []
    i = 0
    while i < len(chars):
        c = chars[i]
        r = rng.random()
        # adjacent swap ("teh" style)
        if (r < intensity * 0.35 and i + 1 < len(chars)
                and chars[i].isalpha() and chars[i + 1].isalpha()):
            out.append(chars[i + 1])
            out.append(c)
            i += 2
            continue
        # dropped doubled letter ("really" -> "realy")
        if (r < intensity * 0.25 and i + 1 < len(chars)
                and c.isalpha() and chars[i + 1].lower() == c.lower()):
            out.append(c)
            i += 2
            continue
        # dropped char
        if r < intensity * 0.15 and c.isalpha():
            i += 1
            continue
        out.append(c)
        i += 1
    text = "".join(out)
    # missing apostrophes
    def _drop_apos(m: re.Match) -> str:
        return m.group(0).replace("'", "") \
            if rng.random() < intensity else m.group(0)
    text = re.sub(r"\b\w+'\w+\b", _drop_apos, text)
    return text


def tone_fix(text: str, *, lowercase: bool = False,
             emoji: list[str] | None = None,
             emoji_chance: float = 0.0,
             normalize_punctuation: bool = True,
             seed_salt: str = "forge") -> str:
    """Light tone adjustments. All optional, all off by default."""
    if lowercase:
        text = text.lower()
    if normalize_punctuation:
        text = re.sub(r"!{2,}", "!", text)
        text = re.sub(r"\.{3,}", "...", text)
    if emoji and emoji_chance > 0:
        rng = _seeded(text, seed_salt + "emoji")
        if rng.random() < emoji_chance:
            text = text.rstrip() + " " + rng.choice(emoji)
    return text


def humanize(text: str, config: dict[str, Any] | None = None) -> str:
    """One-call humanizer driven by chat.humanize config.

    Config keys: enabled, typo_intensity, lowercase, emoji (list),
    emoji_chance. Returns text unchanged when disabled/missing.
    """
    cfg = config or {}
    if not cfg.get("enabled"):
        return text
    text = typo_simulate(text,
                         intensity=float(cfg.get("typo_intensity", 0.15)))
    text = tone_fix(text, lowercase=bool(cfg.get("lowercase", False)),
                    emoji=cfg.get("emoji") or None,
                    emoji_chance=float(cfg.get("emoji_chance", 0.0)))
    return text


class TranslationNotConfigured(Exception):
    """Raised when translate() is called without an endpoint."""


def translate(text: str, target_lang: str,
              endpoint: str = "") -> str:
    """Translate via a LibreTranslate-compatible endpoint.

    Honest scope: basic machine translation for casual chat. NOT
    professional quality -- she should review anything important.
    """
    if not endpoint:
        raise TranslationNotConfigured(
            "No translation endpoint configured. Set "
            "chat.humanize.translate_endpoint to a LibreTranslate-compatible"
            " URL (you can self-host LibreTranslate free).")
    import json
    import urllib.request
    payload = json.dumps({"q": text, "source": "auto",
                          "target": target_lang}).encode()
    req = urllib.request.Request(endpoint.rstrip("/") + "/translate",
                                 data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    return data.get("translatedText", text)
