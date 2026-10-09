"""Streaming-avatar provider adapters (HeyGen, D-ID).

Both are paid third-party APIs and need her own keys (live.heygen_api_key
/ live.did_api_key in forge.yaml). The adapters do the real REST calls to
create / query / close streaming sessions. The actual media transport is
WebRTC -- the adapter returns the session credentials and docs/LIVE.md
explains how to view/drive them. Nothing here is simulated.
"""

from __future__ import annotations

import base64
from typing import Any


class LiveNotConfiguredError(Exception):
    """Raised when a live provider has no API key configured."""


class BaseLiveAdapter:
    """Common interface for streaming-avatar providers."""

    name = "base"

    def start(self, **kwargs: Any) -> dict[str, Any]:
        """Create a streaming session. Returns session info dict."""
        raise NotImplementedError

    def stop(self, session: dict[str, Any]) -> dict[str, Any]:
        """Close a streaming session."""
        raise NotImplementedError

    def status(self, session: dict[str, Any]) -> dict[str, Any]:
        """Query a streaming session's status."""
        raise NotImplementedError


def _post_json(url: str, payload: dict[str, Any],
               headers: dict[str, str], timeout: int = 30) -> dict[str, Any]:
    import json
    import urllib.request
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(url: str, headers: dict[str, str],
              timeout: int = 30) -> dict[str, Any]:
    import json
    import urllib.request
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _delete(url: str, headers: dict[str, str],
            payload: dict[str, Any] | None = None,
            timeout: int = 30) -> dict[str, Any]:
    import json
    import urllib.request
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json",
                                          **headers},
                                 method="DELETE")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8") or "{}"
        return json.loads(body)


class HeyGenAdapter(BaseLiveAdapter):
    """HeyGen streaming avatar (https://api.heygen.com).

    Needs: live.heygen_api_key + live.heygen_avatar_id in forge.yaml.
    Follows HeyGen's streaming API: POST /v1/streaming.new creates the
    session; the returned SDP/access_token drive a WebRTC client.
    """

    name = "heygen"
    BASE = "https://api.heygen.com"

    def __init__(self, api_key: str = "", avatar_id: str = "",
                 voice_id: str = ""):
        self.api_key = api_key.strip()
        self.avatar_id = avatar_id.strip()
        self.voice_id = voice_id.strip()
        if not self.api_key:
            raise LiveNotConfiguredError(
                "HeyGen needs live.heygen_api_key in forge.yaml "
                "(get one at heygen.com -- paid plan required).")

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key}

    def start(self, **kwargs: Any) -> dict[str, Any]:
        """Create a streaming session via POST /v1/streaming.new."""
        payload: dict[str, Any] = {
            "quality": kwargs.get("quality", "high"),
            "avatar_id": kwargs.get("avatar_id") or self.avatar_id,
            "voice": {"voice_id": kwargs.get("voice_id") or self.voice_id,
                      "rate": 1.0},
            "version": "v2",
            "video_encoding": "H264",
        }
        data = _post_json(f"{self.BASE}/v1/streaming.new", payload,
                          self._headers())
        info = data.get("data") or {}
        return {"provider": "heygen",
                "session_id": info.get("session_id"),
                "url": info.get("url"),
                "access_token": info.get("access_token"),
                "note": "Drive the session with a WebRTC client using the "
                        "returned SDP/access_token (see docs/LIVE.md)."}

    def stop(self, session: dict[str, Any]) -> dict[str, Any]:
        data = _post_json(f"{self.BASE}/v1/streaming.stop",
                          {"session_id": session.get("session_id")},
                          self._headers())
        return {"provider": "heygen", "stopped": True, "response": data}

    def status(self, session: dict[str, Any]) -> dict[str, Any]:
        sid = session.get("session_id")
        data = _get_json(
            f"{self.BASE}/v1/streaming.status?session_id={sid}",
            self._headers())
        return {"provider": "heygen", "session_id": sid,
                "status": data}


class DIDAdapter(BaseLiveAdapter):
    """D-ID streaming avatar (https://api.d-id.com).

    Needs: live.did_api_key in forge.yaml ("key:secret" or just the key;
    uses HTTP Basic auth). Follows D-ID's streams API: POST
    /talks/streams opens a WebRTC stream from a source image.
    """

    name = "did"
    BASE = "https://api.d-id.com"

    def __init__(self, api_key: str = "", source_image_url: str = ""):
        self.api_key = api_key.strip()
        self.source_image_url = source_image_url.strip()
        if not self.api_key:
            raise LiveNotConfiguredError(
                "D-ID needs live.did_api_key in forge.yaml "
                "(get one at d-id.com -- paid plan required).")

    def _headers(self) -> dict[str, str]:
        token = self.api_key
        if ":" not in token:
            token = token + ":"
        basic = base64.b64encode(token.encode()).decode()
        return {"Authorization": f"Basic {basic}"}

    def start(self, **kwargs: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_url": kwargs.get("source_image_url")
            or self.source_image_url,
        }
        if not payload["source_url"]:
            raise LiveNotConfiguredError(
                "D-ID needs a source image URL: set live.did_source_image "
                "in forge.yaml or pass --source-image.")
        data = _post_json(f"{self.BASE}/talks/streams", payload,
                          self._headers())
        return {"provider": "did",
                "id": data.get("id"),
                "session_id": data.get("session_id"),
                "offer_sdp": (data.get("offer") or {}).get("sdp"),
                "ice_servers": data.get("ice_servers"),
                "note": "Complete the WebRTC handshake with the returned "
                        "offer SDP (see docs/LIVE.md)."}

    def stop(self, session: dict[str, Any]) -> dict[str, Any]:
        sid = session.get("id")
        data = _delete(f"{self.BASE}/talks/streams/{sid}", self._headers(),
                       {"session_id": session.get("session_id")})
        return {"provider": "did", "stopped": True, "response": data}

    def status(self, session: dict[str, Any]) -> dict[str, Any]:
        # D-ID has no session-status endpoint; the open stream IS the state.
        return {"provider": "did", "id": session.get("id"),
                "session_id": session.get("session_id"),
                "status": "open (no status endpoint; stream is live until "
                          "stopped)"}


def get_adapter(provider: str, config: Any,
                api_key: str = "") -> BaseLiveAdapter:
    """Build the adapter for a provider, reading keys from config."""
    provider = provider.lower().strip()
    if provider == "heygen":
        key = api_key or str(config.get_path("live.heygen_api_key", "") or "")
        return HeyGenAdapter(
            api_key=key,
            avatar_id=str(config.get_path("live.heygen_avatar_id", "") or ""),
            voice_id=str(config.get_path("live.heygen_voice_id", "") or ""))
    if provider in ("did", "d-id"):
        key = api_key or str(config.get_path("live.did_api_key", "") or "")
        return DIDAdapter(
            api_key=key,
            source_image_url=str(
                config.get_path("live.did_source_image", "") or ""))
    if provider == "sadtalker":
        return SadTalkerAdapter(
            sadtalker_dir=str(
                config.get_path("live.sadtalker_dir", "") or ""),
            checkpoint=str(
                config.get_path("live.sadtalker_checkpoint", "") or ""))
    raise ValueError(f"Unknown live provider {provider!r}. "
                     "Use heygen, did, sadtalker, or local-guide.")


class SadTalkerAdapter(BaseLiveAdapter):
    """Local talking-head lip-sync (SadTalker) -> OBS Virtual Camera.

    Honest scope: this is NOT a hosted streaming API. It renders a
    lip-synced clip from a source image + audio file using a LOCAL
    SadTalker install (needs an NVIDIA GPU + its checkpoints), which she
    then plays through OBS Virtual Camera for calls/streams.

    Needs: live.sadtalker_dir pointing at a working SadTalker checkout
    (see docs/LIVE.md). `start` runs the render and returns the output
    path + OBS checklist. Nothing is faked: if SadTalker isn't there,
    you get setup steps, not a silent failure.
    """

    name = "sadtalker"

    def __init__(self, sadtalker_dir: str = "", checkpoint: str = ""):
        import shutil
        self.dir = sadtalker_dir.strip()
        self.checkpoint = checkpoint.strip()
        if not self.dir:
            raise LiveNotConfiguredError(
                "SadTalker needs live.sadtalker_dir in forge.yaml -- the "
                "path to a working SadTalker install. Setup steps:\n"
                "  1. git clone https://github.com/OpenTalker/SadTalker\n"
                "  2. Follow its README (conda env, checkpoints download;\n"
                "     needs an NVIDIA GPU, ~8GB+ VRAM)\n"
                "  3. Set live.sadtalker_dir to that folder.\n"
                "Full guide: docs/LIVE.md.")
        if not shutil.which("python"):
            raise LiveNotConfiguredError("No python on PATH for SadTalker.")

    def start(self, **kwargs: Any) -> dict[str, Any]:
        """Render image+audio -> lip-synced mp4. Returns output + OBS steps."""
        import subprocess
        source_image = kwargs.get("source_image", "")
        audio = kwargs.get("audio", "")
        out = kwargs.get("out", "sadtalker-output.mp4")
        if not source_image or not audio:
            raise LiveNotConfiguredError(
                "SadTalker needs source_image= (her persona portrait) and "
                "audio= (voiceover mp3, e.g. from `forge persona "
                "voice-speak`).")
        cmd = ["python", "inference.py",
               "--driven_audio", str(audio),
               "--source_image", str(source_image),
               "--result_dir", str(out),
               "--still", "--preprocess", "full",
               "--enhancer", "gfpgan"]
        if self.checkpoint:
            cmd += ["--checkpoint", self.checkpoint]
        try:
            proc = subprocess.run(cmd, cwd=self.dir, capture_output=True,
                                  text=True, timeout=1800)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                "SadTalker render timed out after 30 minutes.") from e
        if proc.returncode != 0:
            raise RuntimeError(
                "SadTalker render failed:\n" + proc.stderr[-2000:])
        return {
            "provider": "sadtalker",
            "output": str(out),
            "note": "Play this clip in OBS as a Media Source (loop it) "
                    "and enable OBS Virtual Camera. Your video-call app "
                    "or streaming software then uses 'OBS Virtual Camera' "
                    "as its camera. See docs/LIVE.md.",
        }

    def stop(self, session: dict[str, Any]) -> dict[str, Any]:
        # Local render: nothing to close server-side.
        return {"provider": "sadtalker", "stopped": True,
                "note": "Local render finished; stop the OBS source "
                        "yourself."}

    def status(self, session: dict[str, Any]) -> dict[str, Any]:
        return {"provider": "sadtalker",
                "status": "local render (no persistent session)"}
