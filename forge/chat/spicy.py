"""Spicy chat mode: flirty/dirty-talk reply packs, monetization flows.

CONSENT-GATED: spicy mode requires the identity pack's consent scope to
explicitly include spicy/adult chat. Scope keywords that unlock it:
"spicy", "adult chat", "explicit", "dirty talk", "sexting", "findom".
Without one of those, every spicy function raises SpicyConsentError with
a clear message telling her to sign a statement that covers it.

Design notes (from the creator herself):
- Tiered escalation: playful -> teasing -> explicit. Tier is per
  conversation ("heat") and only moves when SHE bumps it, or when she
  pins it in config. The bot never escalates on its own.
- Templates are user-editable JSON. The explicit tier ships with
  placeholders she must write herself -- CreatorForge ships no explicit
  copy.
- Spicy drafts go through the SAME approval queue as everything else.
  The spicy engine never auto-approves, even on auto-send platforms.
- Monetization flows: paid "rates" (fan sends a pic -> funny rating
  scorecard -> tip upsell), tip-request triggers ("that custom is $X --
  here's my CashApp"), and opt-in findom-lite "shame" lines that SHE
  writes and approves line by line.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forge.identity.pack import (
    InvalidConsentError,
    load_identity_pack,
    validate_identity_pack,
)


class SpicyConsentError(Exception):
    """Raised when spicy mode is used without spicy scope in consent."""


SPICY_SCOPE_KEYWORDS = (
    "spicy", "adult chat", "explicit", "dirty talk", "sexting", "findom",
)

TIERS = ("playful", "teasing", "explicit")

# keyword -> (tier hint, intent). Intent drives monetization flows.
_INTENT_PATTERNS: list[tuple[str, str, str]] = [
    (r"\brate\b", "playful", "rate"),
    (r"\brating\b", "playful", "rate"),
    (r"\bjudge\b", "teasing", "rate"),
    (r"\bcustom\b", "playful", "tip"),
    (r"\bprice\b|\bcost\b|\bhow much\b", "playful", "tip"),
    (r"\btip\b", "playful", "tip"),
    (r"\bshame\b|\bloser\b|\bpaypig\b|\btribute\b|\bworship\b", "teasing",
     "findom"),
]


def consent_allows_spicy(pack: dict[str, Any]) -> bool:
    """True if the pack's consent scope mentions spicy/adult chat."""
    scope = str(pack.get("consent", {}).get("scope", "")).lower()
    return any(k in scope for k in SPICY_SCOPE_KEYWORDS)


def require_spicy_consent(pack_path: str | Path) -> dict[str, Any]:
    """Load + validate a pack and enforce spicy scope.

    Raises SpicyConsentError with an actionable message when the scope
    doesn't cover spicy chat.
    """
    try:
        pack = validate_identity_pack(load_identity_pack(pack_path))
    except InvalidConsentError as e:
        raise SpicyConsentError(f"Invalid consent pack: {e}")
    except (FileNotFoundError, OSError) as e:
        raise SpicyConsentError(
            f"Identity pack not found: {pack_path} ({e}). "
            "Create one with `forge identity create` first.")
    if not consent_allows_spicy(pack):
        raise SpicyConsentError(
            "Spicy mode is locked: this identity pack's consent scope does "
            "not mention spicy/adult chat. To unlock it she must sign a new "
            "consent statement whose scope explicitly includes it (e.g. "
            "\"...including spicy/flirty chat with fans\"), then run "
            "`forge identity create` again. Refusing to proceed."
        )
    return pack


# -- tiered template packs ---------------------------------------------------
# Playful/teasing ship with mild, tasteful defaults she can edit. The
# explicit tier ships EMPTY -- she writes every line herself.

DEFAULT_SPICY_TEMPLATES: dict[str, dict[str, str]] = {
    "playful": {
        "opener": "Mmm, you know just what to say to get my attention 😘",
        "tease": "Careful babe... keep talking like that and you'll make me blush 🙈",
        "goodnight": "Dream about me tonight 😘",
    },
    "teasing": {
        "opener": "Oh? Someone's feeling bold tonight 😈",
        "tease": "You talk a big game... prove it, babe 😏",
        "goodnight": "Try to behave... or don't 😈",
    },
    "explicit": {
        # Placeholders on purpose: she writes her own explicit copy.
        "opener": "[write your own explicit opener]",
        "tease": "[write your own explicit tease]",
        "goodnight": "[write your own explicit goodnight]",
    },
}


def _spicy_path() -> Path:
    p = Path(os.environ.get("CHAT_SPICY_TEMPLATES_PATH",
                            "./forge-data/chat-spicy-templates.json"))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_spicy_templates() -> dict[str, dict[str, str]]:
    p = _spicy_path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    out: dict[str, dict[str, str]] = {}
    for tier, tpl in (data.get("tiers") or {}).items():
        if tier in TIERS and isinstance(tpl, dict):
            out[tier] = {k: str(v) for k, v in tpl.items()}
    return out


def save_spicy_templates(tiers: dict[str, dict[str, str]]) -> None:
    _spicy_path().write_text(json.dumps({"tiers": tiers}, indent=2),
                             encoding="utf-8")


def ensure_spicy_defaults() -> int:
    """Seed default tiers; never overwrites her edits. Returns # added."""
    tiers = load_spicy_templates()
    added = 0
    for tier, tpl in DEFAULT_SPICY_TEMPLATES.items():
        if tier not in tiers:
            tiers[tier] = dict(tpl)
            added += 1
    if added:
        save_spicy_templates(tiers)
    return added


def add_spicy_template(tier: str, name: str, text: str) -> None:
    if tier not in TIERS:
        raise ValueError(f"tier must be one of {TIERS}")
    ensure_spicy_defaults()
    tiers = load_spicy_templates()
    tiers.setdefault(tier, {})
    if name in tiers[tier]:
        raise KeyError(f"Template {name!r} already exists in tier {tier!r}.")
    tiers[tier][name] = text
    save_spicy_templates(tiers)


def delete_spicy_template(tier: str, name: str) -> None:
    tiers = load_spicy_templates()
    if name not in tiers.get(tier, {}):
        raise KeyError(f"No template {name!r} in tier {tier!r}.")
    del tiers[tier][name]
    save_spicy_templates(tiers)


def render_spicy_template(tier: str, name: str, sender: str = "",
                          persona_name: str = "") -> str:
    tiers = load_spicy_templates()
    try:
        text = tiers[tier][name]
    except KeyError:
        raise KeyError(f"No spicy template {name!r} in tier {tier!r}.")
    return text.replace("{sender}", sender or "babe").replace(
        "{persona}", persona_name or "me")


# -- monetization flows ------------------------------------------------------

def build_rate_scorecard(sender: str = "", style: dict[str, Any] | None = None
                         ) -> str:
    """Funny rating scorecard for a fan-sent pic.

    Playful, non-explicit, and deterministic -- the "scores" are clearly
    a bit, not a real judgment. Always ends with a tip upsell hook that
    the caller appends payment links to.
    """
    who = sender or "babe"
    lines = [
        f"Okay {who}, official rating time 😌📋",
        "Confidence: 8/10",
        "Lighting: 7/10 (bathroom lighting is doing WORK)",
        "Creativity: 9/10",
        "Overall: 8/10 — certified cutie 💋",
    ]
    return "\n".join(lines)


def rates_upsell(links: dict[str, str], menu: list[dict[str, Any]] | None = None
                 ) -> str:
    """Tip upsell appended after a rates scorecard."""
    pay = next(iter(links.values()), "")
    items = ""
    if menu:
        items = " " + " ".join(
            f"{m.get('label')} {m.get('price', '')}".strip()
            for m in menu[:3] if isinstance(m, dict))
    tail = f" — tip me here: {pay}" if pay else ""
    return f"Want a custom rated next?{items}{tail} 💕"


def tip_request_reply(item_label: str, price: str,
                      links: dict[str, str]) -> str:
    """'that custom is $X -- here's my CashApp' reply."""
    cashapp = links.get("Cash App", "")
    pay = f" Here's my CashApp: {cashapp}" if cashapp else ""
    return (f"That {item_label} is {price} babe 💕.{pay} "
            f"Send it and I'll get you set up 😘")


# -- findom-lite (strictly opt-in, she writes every line) --------------------

def findom_enabled(config: Any) -> bool:
    try:
        return bool(config.get_path("chat.spicy.findom_enabled", False))
    except Exception:
        return False


def findom_templates(config: Any) -> dict[str, str]:
    """Her own findom-lite lines from forge.yaml chat.spicy.findom_lines.

    She writes and approves every line; nothing ships by default.
    """
    try:
        lines = config.get_path("chat.spicy.findom_lines", {}) or {}
    except Exception:
        return {}
    return {str(k): str(v) for k, v in lines.items() if v}


# -- the spicy engine ----------------------------------------------------------

@dataclass
class SpicyEngine:
    """Drafts spicy replies into the shared approval queue.

    - Consent-gated at construction (needs a pack path with spicy scope).
    - Per-conversation tier ("heat"): 0=playful, 1=teasing, 2=explicit.
      Only SHE changes it (set_tier); the bot never escalates alone.
    - Never auto-approves: drafts always land pending for her review.
    """

    pack: dict[str, Any]
    queue: Any = None  # ApprovalQueue; Any to avoid import cycle
    style: dict[str, Any] | None = None
    config: Any = None
    heat_path: str | Path | None = None
    _heat: dict[tuple[str, str], int] = field(default_factory=dict)

    @classmethod
    def from_pack(cls, pack_path: str | Path, queue: Any = None,
                  style: dict[str, Any] | None = None,
                  config: Any = None,
                  heat_path: str | Path | None = None) -> "SpicyEngine":
        pack = require_spicy_consent(pack_path)
        ensure_spicy_defaults()
        engine = cls(pack=pack, queue=queue, style=style, config=config,
                     heat_path=heat_path)
        engine.load_heat()
        return engine

    def load_heat(self) -> None:
        """Load per-conversation tiers from disk (missing file = defaults)."""
        if not self.heat_path:
            return
        p = Path(self.heat_path)
        if not p.is_file():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        for key, idx in data.items():
            plat, _, snd = key.partition("\x00")
            if isinstance(idx, int) and 0 <= idx < len(TIERS):
                self._heat[(plat, snd)] = idx

    def save_heat(self) -> None:
        """Persist per-conversation tiers to disk."""
        if not self.heat_path:
            return
        p = Path(self.heat_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {f"{plat}\x00{snd}": idx
                for (plat, snd), idx in self._heat.items()}
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def set_tier(self, platform: str, sender: str, tier: str) -> None:
        if tier not in TIERS:
            raise ValueError(f"tier must be one of {TIERS}")
        self._heat[(platform, sender)] = TIERS.index(tier)
        self.save_heat()

    def get_tier(self, platform: str, sender: str) -> str:
        default = "playful"
        try:
            default = str(self.config.get_path("chat.spicy.default_tier",
                                               "playful"))
        except Exception:
            pass
        if default not in TIERS:
            default = "playful"
        return TIERS[self._heat.get((platform, sender), TIERS.index(default))]

    def _detect_intent(self, text: str) -> str:
        """Return the monetization intent ("rate"|"tip"|"findom"|"chat")."""
        for pattern, _tier_hint, intent in _INTENT_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                if intent == "findom" and not (
                        self.config is not None
                        and findom_enabled(self.config)):
                    continue
                return intent
        return "chat"

    def draft(self, *, platform: str, sender: str, text: str,
              links: dict[str, str] | None = None,
              menu: list[dict[str, Any]] | None = None) -> Any:
        """Draft a spicy reply into the approval queue.

        Returns the Draft (always status pending -- never auto-approved).
        """
        from forge.chat.engine import Trigger  # noqa: F401  (docs)
        if self.queue is None:
            from forge.chat.engine import ApprovalQueue
            self.queue = ApprovalQueue()
        intent = self._detect_intent(text)
        tier = self.get_tier(platform, sender)
        persona_name = ""
        try:
            persona_name = str(self.config.get_path("persona.name", ""))
        except Exception:
            pass

        reply: str
        trigger = f"spicy:{tier}"
        if intent == "rate":
            reply = build_rate_scorecard(sender) + "\n" + rates_upsell(
                links or {}, menu)
            trigger = "spicy:rates"
        elif intent == "tip":
            item = (menu[0].get("label", "custom") if menu else "custom")
            price = (menu[0].get("price", "") if menu else "")
            reply = tip_request_reply(item, price, links or {})
            trigger = "spicy:tip-request"
        elif intent == "findom":
            lines = findom_templates(self.config)
            name = next(iter(lines), "")
            reply = (lines[name].replace("{sender}", sender or "babe")
                     if name else
                     "Aww, feeling generous tonight? 😈")
            trigger = "spicy:findom"
        else:
            # plain flirty chat at the conversation's tier
            templates = load_spicy_templates().get(tier, {})
            name = next(iter(templates), "opener")
            reply = render_spicy_template(tier, name, sender=sender,
                                          persona_name=persona_name)
            # light style touch: mirror her emoji habit if we know it
            if self.style:
                reply = _apply_style_touch(reply, self.style)
        draft = self.queue.add(platform=platform, sender=sender,
                               incoming=text, reply=reply, trigger=trigger)
        return draft


def _apply_style_touch(reply: str, style: dict[str, Any]) -> str:
    """Very light touch: if her profile shows heavy emoji use and the
    template has none, append her most-used emoji. Never rewrites her
    words."""
    try:
        top_emoji = (style.get("emoji") or {}).get("top") or []
        avg = float((style.get("sentence") or {}).get("avg_words", 0))
    except Exception:
        return reply
    if top_emoji and not any(ch in reply for ch in ("😘", "💕", "😈", "😏",
                                                   "🙈", "💋", "👀")):
        reply = reply.rstrip() + " " + str(top_emoji[0])
    return reply
