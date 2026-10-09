"""Chat worker: real-time / polling / manual inbox adapters.

Honest model: CreatorForge has no privileged pipe into Snapchat or
OnlyFans DMs. Adapters declare how they receive messages:

- "realtime": the adapter holds a live connection (e.g. a Discord bot
  gateway, a webhook receiver you run). Drafts flow as messages arrive.
- "poll": the adapter checks a source on an interval.
- "manual": a human drops incoming messages into an inbox file (or the
  dashboard) and the worker drafts replies from there.

The worker only DRAFTS. Sending still follows the conversation mode
(auto / approve-first / manual) in the RuleEngine.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from forge.chat.engine import Draft, RuleEngine


class BaseChatAdapter:
    name = "base"
    mode = "manual"  # "realtime" | "poll" | "manual"

    def poll(self) -> list[dict[str, Any]]:
        """Return new incoming messages: {platform, sender, text}."""
        raise NotImplementedError


class ManualInboxAdapter(BaseChatAdapter):
    """Read incoming messages from a JSONL inbox file.

    Each line: {"platform": "...", "sender": "...", "text": "..."}.
    The worker tracks how far it read in a sidecar ``.offset`` file, so
    re-runs don't re-draft. She (or a helper script) appends lines as
    messages come in -- this is the honest "manual" mode for platforms
    with no messaging API.
    """
    name = "manual-inbox"
    mode = "manual"

    def __init__(self, inbox_path: str | Path):
        self.inbox_path = Path(inbox_path)
        self.offset_path = self.inbox_path.with_suffix(
            self.inbox_path.suffix + ".offset")

    def _offset(self) -> int:
        try:
            return int(self.offset_path.read_text(encoding="utf-8").strip())
        except (FileNotFoundError, ValueError):
            return 0

    def poll(self) -> list[dict[str, Any]]:
        if not self.inbox_path.is_file():
            return []
        lines = self.inbox_path.read_text(encoding="utf-8").splitlines()
        start = self._offset()
        messages = []
        for line in lines[start:]:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if all(k in msg for k in ("platform", "sender", "text")):
                messages.append(msg)
        self.offset_path.write_text(str(len(lines)), encoding="utf-8")
        return messages


class PollingWorker:
    """Pull messages from an adapter through the rule engine."""

    def __init__(self, engine: RuleEngine, adapter: BaseChatAdapter):
        self.engine = engine
        self.adapter = adapter

    def run_once(self) -> list[Draft | None]:
        """Process all currently-available messages. Returns drafts
        (None entries = manual-mode messages, logged as seen)."""
        results: list[Draft | None] = []
        for msg in self.adapter.poll():
            results.append(self.engine.handle_message(
                platform=msg["platform"], sender=msg["sender"],
                text=msg["text"]))
        return results

    def run_forever(self, interval_s: int = 30) -> None:
        """Poll forever until interrupted (Ctrl-C)."""
        print(f"[worker] adapter={self.adapter.name} mode={self.adapter.mode} "
              f"interval={interval_s}s -- Ctrl-C to stop")
        try:
            while True:
                drafts = self.run_once()
                pending = sum(1 for d in drafts
                              if d is not None and d.status == "pending")
                if drafts:
                    print(f"[worker] {len(drafts)} message(s), "
                          f"{pending} draft(s) pending approval")
                time.sleep(interval_s)
        except KeyboardInterrupt:
            print("[worker] stopped")


def get_adapter(name: str, **kwargs: Any) -> BaseChatAdapter:
    adapters = {"manual-inbox": ManualInboxAdapter}
    if name not in adapters:
        raise ValueError(f"Unknown chat adapter {name!r}. "
                         f"Available: {sorted(adapters)}")
    return adapters[name](**kwargs)
