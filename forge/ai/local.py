"""Honest local draft builder — rule/template-based, NOT AI.

``forge ai ... --local`` works with zero API keys. Drafts are assembled from
her word bank (:class:`CustomLexicon`), canned templates, and simple string
substitution — no model, no network, no fake "AI". Every output path labels
the result with :data:`LOCAL_TAG` so template drafts are never mistaken for
AI-generated text.

This is the working replacement for the "AI provider keys" placeholder
(see PLACEHOLDERS.md): she gets usable drafts on day one; adding a real
key later upgrades the same commands to real AI output.
"""

from __future__ import annotations

import re
from typing import Any

LOCAL_TAG = "local template draft (not AI-generated)"

_PLACEHOLDER_RE = re.compile(
    r"\{(?:pet_name|phrase|slang|emoji|opener|closer|spicy|sender)\}")


def _fill(template: str, lex: Any | None) -> str:
    """Render word-bank placeholders; strip leftovers when no bank (or the
    bank has no words in that category) so output never shows raw {tokens}.
    Only known word-bank tokens are stripped -- braces in her own topic
    text are left alone."""
    text = template
    if lex is not None:
        try:
            text = lex.render(template)
        except Exception:
            pass
    text = _PLACEHOLDER_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip(" -")


def _topic_title(topic: str) -> str:
    return " ".join(w.capitalize() for w in topic.split())


_CAPTION_TEMPLATES = [
    "{opener} new {topic} just dropped {emoji}",
    "pov: your favorite {topic} girl {emoji} {closer}",
    "{topic} but make it {slang} {emoji}",
    "which {topic} is your favorite? {emoji} {closer}",
    "{phrase} - new {topic} era {emoji}",
    "{opener} {topic} on the timeline today {emoji} {closer}",
]

_TITLE_TEMPLATES = [
    "I Tried {Topic} So You Don't Have To",
    "{Topic} - Behind The Scenes",
    "Rating Your {Topic} Requests",
    "My {Topic} Routine, Unfiltered",
    "You Asked For {Topic}...",
    "{Topic} Q&A - Answering Everything",
]

_IDEA_TEMPLATES = [
    "Day-in-the-life vlog in your {niche} niche",
    "Q&A: fans ask about {niche}",
    "Trying fan-requested {niche} ideas on camera",
    "Behind the scenes of a {niche} shoot",
    "{niche} myths vs reality",
    "Rating {niche} trends this week",
    "Get ready with me: {niche} edition",
    "Storytime: how I got into {niche}",
    "{niche} dos and don'ts for beginners",
    "Fan-favorite {niche} moments compilation",
    "{niche} wishlist - what should I film next?",
    "Reacting to your {niche} DMs",
]

_SCENE_TEMPLATES = [
    "{vibe} bedroom, soft lamp light, slow push-in, satin robe",
    "{vibe} rooftop at golden hour, wind in hair, wide shot",
    "{vibe} neon-lit room, mirror shot, teasing smile",
    "{vibe} cozy kitchen morning, oversized sweater, handheld feel",
    "{vibe} luxury hotel balcony, city lights, cinematic slow-mo",
    "{vibe} vintage car at dusk, leather jacket, confident walk-up",
]

_HASHTAG_BASE = [
    "creator", "contentcreator", "explore", "fyp", "viral", "trending",
    "behindthescenes", "newpost", "dailypost", "supportcreators",
    "model", "photoshoot", "contentday",
]

_REPLY_TEMPLATES = [
    "{opener} {pet_name}, thanks for messaging me {emoji} {closer}",
    "hey {pet_name} {emoji} what can I do for you today? {closer}",
    "{opener} you caught me at a good time {pet_name} {emoji}",
]


def _cycle(templates: list[str], n: int, **kw: Any) -> list[str]:
    """Fill {topic}/{Topic}/{niche}/{vibe} via plain replace, leaving the
    word-bank {placeholders} intact for _fill(). (str.format would raise
    KeyError on those.)"""
    out = []
    for i in range(max(1, n)):
        t = templates[i % len(templates)]
        for k, v in kw.items():
            t = t.replace("{" + k + "}", str(v))
        out.append(t)
    return out


def local_captions(topic: str, n: int = 3, tone: str = "playful",
                   lex: Any | None = None) -> list[str]:
    _ = tone  # tone shapes AI output; templates stay neutral-safe
    return [_fill(t, lex) for t in _cycle(_CAPTION_TEMPLATES, n, topic=topic)]


def local_titles(topic: str, n: int = 5,
                 lex: Any | None = None) -> list[str]:
    _ = lex
    return _cycle(_TITLE_TEMPLATES, n, Topic=_topic_title(topic))


def local_hashtags(topic: str, n: int = 10) -> list[str]:
    topic_tag = re.sub(r"[^a-z0-9]", "", topic.lower())
    tags = ([f"#{topic_tag}"] if topic_tag else []) + \
        [f"#{t}" for t in _HASHTAG_BASE]
    seen: list[str] = []
    for t in tags:
        if t not in seen:
            seen.append(t)
    while len(seen) < max(1, n):
        seen.append(f"#{topic_tag}{len(seen)}" if topic_tag else "#post")
    return seen[:max(1, n)]


def local_content_ideas(niche: str, n: int = 10,
                        lex: Any | None = None) -> list[str]:
    _ = lex
    return _cycle(_IDEA_TEMPLATES, n, niche=niche)


def local_scene_ideas(vibe: str, n: int = 5,
                      lex: Any | None = None) -> list[str]:
    _ = lex
    return _cycle(_SCENE_TEMPLATES, n, vibe=vibe)


def local_promo(item: str, price: str, pay_hint: str = "",
                lex: Any | None = None) -> str:
    text = f"{item} is just {price}"
    if lex is not None:
        text = _fill("{opener} " + text + " {emoji} {closer}", lex)
    if pay_hint:
        text = f"{text} - {pay_hint}"
    return text


def local_polish(text: str) -> str:
    """Mechanical cleanup only: trim, collapse whitespace, capitalize the
    first letter, ensure terminal punctuation. Adds no new content."""
    t = re.sub(r"\s+", " ", text.strip())
    if not t:
        return t
    t = t[0].upper() + t[1:]
    if t[-1] not in ".!?":
        t += "."
    return t


def local_reply_options(incoming: str, lex: Any | None = None,
                        n: int = 2) -> list[str]:
    """Safe generic reply options. Never spicy, never promises anything."""
    _ = incoming  # template-based: does not parse the message
    return [_fill(t, lex) for t in _REPLY_TEMPLATES[:max(1, n)]]
