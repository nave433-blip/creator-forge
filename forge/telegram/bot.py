"""Telegram bot adapter (announcements + media drops).

Honest scope: Telegram's Bot API is a plain HTTPS API -- this adapter
sends messages/photos/videos to a chat or channel from her bot, including
paid media (Stars paywall) via sendPaidMedia. It does NOT promise Telegram
Stars economics (revenue share and payouts live inside Telegram) and it
does not read or automate fan DMs.

Sourcing note: python-telegram-bot (the established OSS library) is
LGPL-3.0. For this narrow send-only surface, a thin adapter on httpx
(already a dependency) avoids the license question entirely and keeps
the dependency tree light. If a full conversational bot is ever wanted,
revisit python-telegram-bot with Evan's explicit call (see
PLACEHOLDERS.md).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

API_BASE = "https://api.telegram.org"


class TelegramNotConfiguredError(Exception):
    """No bot token configured."""


class TelegramAPIError(Exception):
    """The Bot API returned ok=false or an HTTP error."""


def resolve_token(explicit: str | None = None,
                  env: dict[str, str] | None = None) -> str:
    """Bot token from arg, config, or TELEGRAM_BOT_TOKEN. Empty if none."""
    if explicit:
        return explicit.strip()
    env = env if env is not None else os.environ
    return (env.get("TELEGRAM_BOT_TOKEN") or "").strip()


class TelegramBot:
    """Minimal send-only Bot API client."""

    def __init__(self, token: str,
                 client: httpx.Client | None = None,
                 timeout: float = 30.0):
        token = (token or "").strip()
        if not token:
            raise TelegramNotConfiguredError(
                "No Telegram bot token: create a bot with @BotFather and "
                "set telegram.bot_token in forge.yaml or TELEGRAM_BOT_TOKEN.")
        self.token = token
        try:
            self._client = client or httpx.Client(timeout=timeout)
        except httpx.InvalidURL as e:
            # Usually a malformed HTTP(S)_PROXY / ALL_PROXY env var.
            raise TelegramAPIError(
                f"Could not create HTTP client: {e} "
                f"(check your HTTP(S)_PROXY / ALL_PROXY env vars).") from e

    def _call(self, method: str, **params: Any) -> dict[str, Any]:
        # Files are passed as (filename, bytes) tuples; httpx sends them
        # as multipart automatically.
        files = params.pop("_files", None)
        try:
            resp = self._client.post(
                f"{API_BASE}/bot{self.token}/{method}",
                data={k: v for k, v in params.items() if v is not None},
                files=files)
        except httpx.HTTPError as e:
            raise TelegramAPIError(f"Telegram request failed: {e}") from e
        try:
            body = resp.json()
        except ValueError as e:
            raise TelegramAPIError(
                f"Telegram returned non-JSON (HTTP {resp.status_code}).") from e
        if not body.get("ok"):
            raise TelegramAPIError(
                f"Telegram API error: {body.get('description', body)}")
        return body["result"]

    def status(self) -> dict[str, Any]:
        """Validate the token; returns the bot's user info (getMe)."""
        return self._call("getMe")

    def send_message(self, chat_id: str | int, text: str) -> dict[str, Any]:
        if not text.strip():
            raise ValueError("text must not be empty")
        return self._call("sendMessage", chat_id=chat_id, text=text)

    def _send_media(self, method: str, chat_id: str | int,
                    path: str | Path, caption: str = "") -> dict[str, Any]:
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Media file not found: {p}")
        if p.stat().st_size > 50 * 1024 * 1024:
            raise ValueError(
                f"{p.name} is over Telegram's 50MB bot-API upload limit.")
        field = "photo" if method == "sendPhoto" else "video"
        with p.open("rb") as fh:
            files = {field: (p.name, fh.read())}
            return self._call(method, chat_id=chat_id, caption=caption or None,
                              _files=files)

    def send_photo(self, chat_id: str | int, path: str | Path,
                   caption: str = "") -> dict[str, Any]:
        return self._send_media("sendPhoto", chat_id, path, caption)

    def send_video(self, chat_id: str | int, path: str | Path,
                   caption: str = "") -> dict[str, Any]:
        return self._send_media("sendVideo", chat_id, path, caption)

    # Paid media (PPV in Telegram). Honest scope: the Bot API's
    # sendPaidMedia puts the photo/video behind a Stars paywall; the
    # Stars price, revenue share, and payouts all live inside Telegram.
    # This adapter only drives the API -- it cannot change what Telegram
    # pays her.
    _VIDEO_EXTS = frozenset({".mp4", ".mov", ".avi", ".mkv", ".webm"})

    def send_paid_media(self, chat_id: str | int, path: str | Path,
                        stars: int, caption: str = "") -> dict[str, Any]:
        """Send a photo/video behind a Stars paywall (sendPaidMedia)."""
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Media file not found: {p}")
        if p.stat().st_size > 50 * 1024 * 1024:
            raise ValueError(
                f"{p.name} is over Telegram's 50MB bot-API upload limit.")
        if not isinstance(stars, int) or stars <= 0:
            raise ValueError("stars must be a positive integer "
                             "(Telegram Stars price for the paywall).")
        media_type = ("video" if p.suffix.lower() in self._VIDEO_EXTS
                      else "photo")
        import json as _json
        media = _json.dumps([{
            "type": media_type,
            "media": f"attach://{p.name}",
            "caption": caption or None,
        }])
        with p.open("rb") as fh:
            files = {p.name: (p.name, fh.read())}
            return self._call("sendPaidMedia", chat_id=chat_id,
                              star_count=stars, media=media, _files=files)
