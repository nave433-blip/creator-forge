"""Voice persona: clone HER voice for AI voiceovers, consent-gated.

Same rule as face: voice cloning is refused without a validated identity
pack (docs/CONSENT.md) covering voice use. The adapter calls the real
ElevenLabs API with YOUR key; without a key it raises a clear error
instead of faking audio.

Local alternative: XTTS (Coqui) runs on your own GPU -- notes below.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from forge.identity.pack import (
    InvalidConsentError,
    load_identity_pack,
    validate_identity_pack,
)


class VoiceNotConfiguredError(Exception):
    """Raised when voice backend credentials are missing."""


class VoiceConsentError(InvalidConsentError):
    """Raised when voice cloning is attempted without valid consent."""


def _require_voice_consent(identity_pack_path: str) -> dict:
    try:
        pack = validate_identity_pack(load_identity_pack(identity_pack_path))
    except InvalidConsentError as e:
        raise VoiceConsentError(
            f"Voice cloning refused: {e}") from e
    except OSError as e:
        raise VoiceConsentError(
            f"Voice cloning refused: identity pack not found at "
            f"{identity_pack_path!r} ({e})") from e
    scope = str(pack["consent"].get("scope", "")).lower()
    if "voice" not in scope and "likeness" not in scope:
        raise VoiceConsentError(
            "Voice cloning refused: the consent scope does not mention "
            "voice or likeness. Update the signed consent to cover voice "
            "use (docs/CONSENT.md)."
        )
    return pack


class ElevenLabsVoice:
    """Clone + speak via the ElevenLabs API (paid, your key).

    Needs ``ELEVENLABS_API_KEY`` env var or ``persona.elevenlabs_key`` in
    forge.yaml. Every method requires ``identity_pack_path``.
    """

    API = "https://api.elevenlabs.io/v1"

    def __init__(self, api_key: str | None = None,
                 config_key: str | None = None):
        self.api_key = api_key or config_key or os.environ.get("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise VoiceNotConfiguredError(
                "ElevenLabs not configured: set ELEVENLABS_API_KEY or "
                "persona.elevenlabs_key in forge.yaml. "
                "Sign up at https://elevenlabs.io -- cloning is a paid feature."
            )

    def _post(self, path: str, data: bytes,
              content_type: str = "application/json") -> bytes:
        req = urllib.request.Request(
            self.API + path, data=data,
            headers={"xi-api-key": self.api_key, "Content-Type": content_type},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()

    def clone_voice(self, *, name: str, audio_files: list[str | Path],
                    identity_pack_path: str,
                    description: str = "") -> str:
        """Create a cloned voice from HER sample audio. Returns voice_id.

        ``audio_files``: 1+ minutes of clean recordings of her voice.
        """
        pack = _require_voice_consent(identity_pack_path)
        boundary = "----forgevoice"
        body = b""
        fields = {"name": name, "description": description or
                  f"Voice of {pack.get('name')}, cloned with consent"}
        for k, v in fields.items():
            body += (f"--{boundary}\r\nContent-Disposition: form-data; "
                     f'name="{k}"\r\n\r\n{v}\r\n').encode()
        for f in audio_files:
            p = Path(f)
            data = p.read_bytes()
            body += (f"--{boundary}\r\nContent-Disposition: form-data; "
                     f'name="files"; filename="{p.name}"\r\n'
                     f"Content-Type: audio/mpeg\r\n\r\n").encode() + data + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        raw = self._post("/voices/add", body,
                         f"multipart/form-data; boundary={boundary}")
        return json.loads(raw)["voice_id"]

    def speak(self, *, text: str, voice_id: str, out_path: str | Path,
              identity_pack_path: str,
              model_id: str = "eleven_multilingual_v2") -> Path:
        """Synthesize speech. Returns the MP3 path written."""
        _require_voice_consent(identity_pack_path)
        payload = json.dumps({"text": text, "model_id": model_id}).encode()
        audio = self._post(f"/text-to-speech/{voice_id}", payload)
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(audio)
        return out


def xtts_local_notes() -> str:
    """Honest notes on the local (free, GPU) alternative to ElevenLabs."""
    return """XTTS (Coqui) -- local voice cloning alternative
- Repo: https://github.com/coqui-ai/TTS  (model: tts_models/multilingual/multi-dataset/xtts_v2)
- Needs: CUDA GPU (8GB+ VRAM workable), ~10s+ of clean reference audio of HER voice.
- Quality: good, not quite ElevenLabs-tier; fine for voiceovers.
- Consent: same gate -- only clone HER voice with her signed consent.
- Install: pip install TTS, then run their xtts demo script with her sample.
- CreatorForge does not bundle it (heavy deps); these notes are the integration point.
"""
