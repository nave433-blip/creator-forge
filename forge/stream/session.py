"""AFK streaming session manager.

`forge stream go-live --platform X` runs her AI-avatar pipeline for a
streaming session:

  avatar source (loop clip | SadTalker lip-sync render | HeyGen/D-ID
  streaming) -> OBS Virtual Camera -> RTMP ingest on the platform.

Honest boundaries, stated in code and docs:
- CreatorForge does NOT stream to the platform itself. SHE puts the
  RTMP URL + stream key (from her verified broadcaster dashboard) into
  OBS, and OBS does the actual ingest. This manager tracks the session,
  drives the avatar side, and logs everything.
- "AFK mode" = the AI avatar loop plays while she's away. It CANNOT
  react to chat in real time unless the avatar source is a real-time
  streaming provider (HeyGen/D-ID, paid). A looped clip is honest about
  being a loop.
- Chat auto-mod / tip-triggered actions only run where a platform
  allows it (Chaturbate official Apps API). Everywhere else: manual.
- Most cam platforms expect a live verified performer. Streaming an
  AI avatar AFK can get her account banned -- the per-platform risk is
  printed at go-live and she must type YES to continue.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from forge.stream.platforms import get_platform


class StreamNotConfiguredError(Exception):
    """Raised when streaming isn't set up (no key, no OBS, etc.)."""


class StreamSessionManager:
    """One active AFK stream session at a time, persisted as JSON."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.data_dir / "stream-session.json"
        self.log_file = self.data_dir / "stream-sessions.jsonl"

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
    def go_live(self, *, platform: str, config: Any,
                avatar: str = "loop",
                avatar_source: str = "",
                acknowledged_risk: bool = False) -> dict[str, Any]:
        """Start an AFK stream session.

        avatar: "loop" (media file looped in OBS), "sadtalker" (rendered
        lip-sync clip), "heygen" / "did" (real-time streaming provider).
        acknowledged_risk: she must confirm she read the ToS risk note.
        """
        if self.current() is not None:
            raise RuntimeError(
                "A stream session is already active. "
                "`forge stream stop` first.")
        plat = get_platform(platform)
        stream_key = str(
            config.get_path(f"stream.{plat['key']}_key", "") or "").strip()
        rtmp_url = str(
            config.get_path(f"stream.{plat['key']}_rtmp", "") or "").strip()
        if not stream_key or not rtmp_url:
            raise StreamNotConfiguredError(
                f"Streaming to {plat['label']} isn't set up: put your RTMP "
                f"URL in stream.{plat['key']}_rtmp and your stream key in "
                f"stream.{plat['key']}_key in forge.yaml (from your verified "
                f"broadcaster dashboard). See docs/STREAMING.md.")
        if not acknowledged_risk:
            raise StreamNotConfiguredError(
                "ToS RISK -- read this:\n" + plat["tos_risk"] + "\n\n"
                "Re-run with --i-understand-the-risk to confirm you've "
                "read it. CreatorForge can't protect the account.")
        avatar_info: dict[str, Any] = {"mode": avatar}
        if avatar == "loop":
            if not avatar_source:
                raise StreamNotConfiguredError(
                    "Loop mode needs --avatar-source: a video file of her "
                    "AI persona to loop in OBS.")
            avatar_info["source"] = avatar_source
        elif avatar == "sadtalker":
            from forge.live.adapters import get_adapter
            adapter = get_adapter("sadtalker", config)
            avatar_info["render"] = adapter.start(
                source_image=kwargs_image(avatar_source, config),
                audio=kwargs_audio(config),
                out=str(self.data_dir / "afk-avatar.mp4"))
        elif avatar in ("heygen", "did"):
            from forge.live.adapters import get_adapter
            adapter = get_adapter(avatar, config)
            avatar_info["session"] = adapter.start()
        else:
            raise ValueError(
                f"Unknown avatar mode {avatar!r}. Use loop, sadtalker, "
                "heygen, or did.")
        session = {
            "platform": plat["key"],
            "platform_label": plat["label"],
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "avatar": avatar_info,
            "chat_mode": ("apps-api (Chaturbate official)"
                          if plat["chat_api"] == "apps"
                          else "manual -- no chat API on this platform"),
            "checklist": [
                "OBS: add the avatar output as a Media Source (loop it).",
                f"OBS: Settings -> Stream -> Custom: server={rtmp_url} "
                "(key goes in the key field, never shared).",
                "OBS: Start Streaming. Verify you're live in the "
                "platform's broadcaster dashboard.",
                "Keep the dashboard open: chat is manual unless the "
                "platform offers an official apps API.",
            ],
        }
        self._save(session)
        self._log("go_live", {"platform": plat["key"],
                              "avatar": avatar})
        return session

    def stop(self) -> dict[str, Any]:
        session = self.current()
        if session is None:
            return {"stopped": False, "note": "No active stream session."}
        avatar = session.get("avatar", {})
        mode = avatar.get("mode")
        if mode in ("heygen", "did") and avatar.get("session"):
            try:
                from forge.live.adapters import get_adapter
                adapter = get_adapter(mode, _empty_config())
                adapter.stop(avatar["session"])
            except Exception:
                pass  # best effort; session record is what matters
        self._save(None)
        self._log("stop", {"platform": session.get("platform")})
        return {"stopped": True,
                "note": "Session closed. Stop OBS streaming yourself."}

    def status(self) -> dict[str, Any]:
        session = self.current()
        if session is None:
            return {"active": False}
        return {"active": True, **session}


def kwargs_image(avatar_source: str, config: Any) -> str:
    if avatar_source:
        return avatar_source
    return str(config.get_path("stream.avatar_image", "") or "")


def kwargs_audio(config: Any) -> str:
    return str(config.get_path("stream.avatar_audio", "") or "")


class _EmptyConfig:
    def get_path(self, _key: str, default: Any = None) -> Any:
        return default


def _empty_config() -> _EmptyConfig:
    return _EmptyConfig()
