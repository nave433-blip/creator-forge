"""Approval-gated chat engine.

The bot DRAFTS replies; a human approves them. Nothing is sent without
approval unless a platform is explicitly opted into auto-send
(``chat.auto_send`` per platform in forge.yaml) -- and even then the
draft is logged first.

Components:
- :class:`Persona` -- tone/voice config (name, style notes, boundaries).
- :class:`RuleEngine` -- keyword triggers -> canned/drafted replies.
- :class:`ApprovalQueue` -- pending drafts; approve/reject/send.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Persona:
    """Voice config for the bot. Loaded from examples/persona.example.yaml."""
    name: str = "assistant"
    tone: str = "friendly, playful, professional"
    boundaries: list[str] = field(default_factory=list)
    greeting: str = "Hey! Thanks for messaging me 💕"
    fallback: str = "Thanks for reaching out! I'll get back to you soon 💕"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Persona":
        return cls(
            name=data.get("name", "assistant"),
            tone=data.get("tone", cls.tone),
            boundaries=list(data.get("boundaries", [])),
            greeting=data.get("greeting", cls.greeting),
            fallback=data.get("fallback", cls.fallback),
        )


@dataclass
class Trigger:
    """A keyword trigger: if ``pattern`` matches, draft ``reply_template``."""
    name: str
    pattern: str
    reply_template: str
    flags: int = re.IGNORECASE

    def matches(self, text: str) -> bool:
        return re.search(self.pattern, text, self.flags) is not None


@dataclass
class Draft:
    id: int
    platform: str
    sender: str
    incoming: str
    reply: str
    trigger: str
    status: str = "pending"  # pending | approved | rejected | sent
    created_at: float = field(default_factory=time.time)
    decided_at: float | None = None


class ApprovalQueue:
    """In-memory approval queue. The dashboard persists decisions per session."""

    def __init__(self):
        self._drafts: list[Draft] = []
        self._next_id = 1

    def add(self, *, platform: str, sender: str, incoming: str,
            reply: str, trigger: str) -> Draft:
        draft = Draft(id=self._next_id, platform=platform, sender=sender,
                      incoming=incoming, reply=reply, trigger=trigger)
        self._next_id += 1
        self._drafts.append(draft)
        return draft

    def pending(self) -> list[Draft]:
        return [d for d in self._drafts if d.status == "pending"]

    def get(self, draft_id: int) -> Draft:
        for d in self._drafts:
            if d.id == draft_id:
                return d
        raise KeyError(f"No draft with id {draft_id}")

    def approve(self, draft_id: int) -> Draft:
        d = self.get(draft_id)
        if d.status != "pending":
            raise ValueError(f"Draft {draft_id} is already {d.status}")
        d.status = "approved"
        d.decided_at = time.time()
        return d

    def reject(self, draft_id: int) -> Draft:
        d = self.get(draft_id)
        if d.status != "pending":
            raise ValueError(f"Draft {draft_id} is already {d.status}")
        d.status = "rejected"
        d.decided_at = time.time()
        return d

    def mark_sent(self, draft_id: int) -> Draft:
        """Record that an approved draft was actually sent.

        Sending itself is done by the platform-specific sender (manual copy
        or an approved integration); this just flips the bookkeeping. It
        refuses to mark drafts that were never approved.
        """
        d = self.get(draft_id)
        if d.status != "approved":
            raise ValueError(
                f"Refusing to mark draft {draft_id} sent: status is "
                f"{d.status!r}, must be 'approved' first.")
        d.status = "sent"
        d.decided_at = time.time()
        return d

    def all(self) -> list[Draft]:
        return list(self._drafts)

    def save(self, path: str | Path) -> None:
        """Persist the queue to JSON so CLI runs share state."""
        import json
        from dataclasses import asdict
        from pathlib import Path as _P
        p = _P(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([asdict(d) for d in self._drafts], indent=2),
                     encoding="utf-8")

    def load(self, path: str | Path) -> None:
        """Load a persisted queue (missing file = empty)."""
        import json
        from pathlib import Path as _P
        p = _P(path)
        if not p.is_file():
            return
        for d in json.loads(p.read_text(encoding="utf-8")):
            draft = Draft(**d)
            self._drafts.append(draft)
            self._next_id = max(self._next_id, draft.id + 1)


class RuleEngine:
    """Matches incoming messages against triggers and drafts replies."""

    MODES = ("auto", "approve-first", "manual")

    def __init__(self, persona: Persona, triggers: list[Trigger] | None = None,
                 queue: ApprovalQueue | None = None,
                 auto_send_platforms: set[str] | None = None):
        self.persona = persona
        self.triggers = triggers or []
        self.queue = queue or ApprovalQueue()
        # Explicit opt-in only. Empty by default: nothing auto-sends.
        self.auto_send_platforms = set(auto_send_platforms or [])
        # Per-conversation mode: (platform, sender) -> one of MODES.
        # Default "approve-first": draft into the queue, human approves.
        self.conversation_modes: dict[tuple[str, str], str] = {}
        # Messages seen in "manual" mode (bot stays silent, human handles).
        self.seen: list[dict] = []

    def set_conversation_mode(self, platform: str, sender: str,
                              mode: str) -> None:
        """Set per-conversation behavior.

        - "auto": draft + auto-approve (logged). Use sparingly.
        - "approve-first": draft stays pending for a human. Default.
        - "manual": the bot drafts nothing; the message is logged as seen
          for the human to answer directly.
        """
        if mode not in self.MODES:
            raise ValueError(f"mode must be one of {self.MODES}, got {mode!r}")
        self.conversation_modes[(platform, sender)] = mode

    def get_conversation_mode(self, platform: str, sender: str) -> str:
        return self.conversation_modes.get((platform, sender), "approve-first")

    def save_modes(self, path: str | Path) -> None:
        """Persist conversation modes to JSON."""
        import json
        from pathlib import Path as _P
        p = _P(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {f"{plat}\x00{snd}": mode
                for (plat, snd), mode in self.conversation_modes.items()}
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_modes(self, path: str | Path) -> None:
        """Load persisted conversation modes (missing file = defaults)."""
        import json
        from pathlib import Path as _P
        p = _P(path)
        if not p.is_file():
            return
        data = json.loads(p.read_text(encoding="utf-8"))
        for key, mode in data.items():
            plat, _, snd = key.partition("\x00")
            if mode in self.MODES:
                self.conversation_modes[(plat, snd)] = mode

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "RuleEngine":
        persona = Persona.from_dict(config.get("persona", {}))
        triggers = [Trigger(**t) for t in config.get("triggers", [])]
        chat_cfg = config.get("chat", {})
        auto = {p for p, v in chat_cfg.get("auto_send", {}).items() if v}
        if auto:
            import warnings
            warnings.warn(
                "AUTO-SEND is enabled for platforms: " + ", ".join(sorted(auto))
                + ". Drafts on these platforms will be marked approved "
                  "automatically. Disable unless you really mean it."
            )
        return cls(persona, triggers, auto_send_platforms=auto)

    def handle_message(self, *, platform: str, sender: str,
                       text: str) -> Draft | None:
        """Draft a reply for an incoming message.

        Behavior depends on the conversation mode (see
        :meth:`set_conversation_mode`):
        - "manual": returns None; the message is logged in ``seen`` and the
          bot drafts nothing.
        - "approve-first" (default): returns a pending Draft for a human.
        - "auto": returns an auto-approved Draft (still logged).

        NOTHING here delivers the message to the platform.
        """
        mode = self.get_conversation_mode(platform, sender)
        if mode == "manual":
            self.seen.append({"platform": platform, "sender": sender,
                              "text": text, "at": time.time()})
            return None
        lowered = text.lower()
        for boundary in self.persona.boundaries:
            if boundary.lower() in lowered:
                reply = self.persona.fallback
                trigger_name = "boundary-fallback"
                break
        else:
            trigger_name = "fallback"
            reply = self.persona.fallback
            for trig in self.triggers:
                if trig.matches(text):
                    trigger_name = trig.name
                    reply = trig.reply_template.format(
                        sender=sender, text=text,
                        persona=self.persona.name)
                    break
        draft = self.queue.add(platform=platform, sender=sender,
                               incoming=text, reply=reply,
                               trigger=trigger_name)
        if mode == "auto" or platform in self.auto_send_platforms:
            self.queue.approve(draft.id)
        return draft
