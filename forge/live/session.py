"""Live session manager: start/stop/status for avatar sessions.

One active session at a time, persisted to JSON in the data dir so the
CLI, dashboard, and mobile app share state. Every start/stop is logged
(call log in live-calls.jsonl) for her records.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class LiveSessionManager:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.data_dir / "live-session.json"
        self.log_file = self.data_dir / "live-calls.jsonl"

    # -- state -----------------------------------------------------------
    def current(self) -> dict[str, Any] | None:
        if not self.session_file.is_file():
            return None
        try:
            return json.loads(self.session_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def _save(self, session: dict[str, Any] | None) -> None:
        if session is None:
            self.session_file.unlink(missing_ok=True)
        else:
            self.session_file.write_text(json.dumps(session, indent=2),
                                         encoding="utf-8")

    def _log(self, event: str, detail: dict[str, Any]) -> None:
        entry = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "event": event, **detail}
        with self.log_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")

    # -- actions ----------------------------------------------------------
    def start(self, provider: str, config: Any,
              api_key: str = "", **kwargs: Any) -> dict[str, Any]:
        """Start a live avatar session via a real provider adapter."""
        from forge.live.adapters import get_adapter

        if self.current() is not None:
            raise RuntimeError(
                "A live session is already active. Stop it first "
                "(`forge live stop`).")
        adapter = get_adapter(provider, config, api_key=api_key)
        info = adapter.start(**kwargs)
        session = {"provider": adapter.name,
                   "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "info": info}
        self._save(session)
        self._log("start", {"provider": adapter.name,
                            "session_id": info.get("session_id")
                            or info.get("id")})
        return session

    def stop(self, config: Any) -> dict[str, Any]:
        """Stop the active session via its provider adapter."""
        from forge.live.adapters import get_adapter

        session = self.current()
        if session is None:
            return {"stopped": False, "note": "No active live session."}
        adapter = get_adapter(session["provider"], config)
        try:
            result = adapter.stop(session["info"])
        except Exception as e:
            result = {"provider": session["provider"], "stopped": False,
                      "error": str(e)}
        self._save(None)
        self._log("stop", {"provider": session["provider"],
                           "result": str(result.get("stopped"))})
        return result

    def status(self) -> dict[str, Any]:
        session = self.current()
        if session is None:
            return {"active": False}
        return {"active": True, **session}


def local_guide_text() -> str:
    """The honest no-budget path: talking-head model + OBS virtual camera.

    Printed by `forge live start --provider local-guide` and mirrored in
    docs/LIVE.md.
    """
    return """LOCAL LIVE-AVATAR PATH (no paid API needed):

1. Generate or pick a talking-head clip of her AI persona
   (`forge video generate` with her trained persona, or a HeyGen/D-ID
   one-off render).
2. Install OBS Studio (free) + enable the Virtual Camera.
3. Add the clip as a Media Source, loop it. Use OBS's built-in
   background removal (or a real green screen + Chroma Key) as your
   "green screen" background.
4. In your VoIP/video-call app (or streaming software), choose
   "OBS Virtual Camera" as the camera.

Voice: pipe her cloned ElevenLabs voice (forge persona voice-speak)
through a virtual audio cable, or just talk yourself and let the
avatar lip-sync loosely.

Honest limits: this is a looped clip, not a real-time responsive
avatar. Latency-free, but it can't react to chat. For reactive
avatars you need HeyGen/D-ID streaming (paid, needs keys).
See docs/LIVE.md for the full guide.
"""
