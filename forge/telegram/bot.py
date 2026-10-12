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

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

API_BASE = "https://api.telegram.org"

#: Bot API file-upload ceiling for bot uploads.
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class TelegramNotConfiguredError(Exception):
    """No bot token configured."""


class TelegramAPIError(Exception):
    """The Bot API returned ok=false or an HTTP error.

    ``transient`` is True when the failure looks temporary (network
    timeout, 5xx, rate limit) and the caller may retry or report a 502;
    False for permanent problems (bad token, unknown chat, bad request).
    """

    def __init__(self, message: str, transient: bool = False):
        super().__init__(message)
        self.transient = transient


def resolve_token(explicit: str | None = None,
                  env: dict[str, str] | None = None) -> str:
    """Bot token from arg, config, or TELEGRAM_BOT_TOKEN. Empty if none."""
    if explicit:
        return explicit.strip()
    env = env if env is not None else os.environ
    return (env.get("TELEGRAM_BOT_TOKEN") or "").strip()


def _retry_after_seconds(resp: httpx.Response) -> float:
    """Honor Telegram's 429 retry_after hint (seconds); 0 if absent."""
    try:
        params = resp.json().get("parameters") or {}
        return max(0.0, float(params.get("retry_after", 0)))
    except (ValueError, TypeError, AttributeError):
        return 0.0


class TelegramBot:
    """Minimal send-only Bot API client.

    Transient failures (timeouts, network errors, HTTP 5xx, 429 rate
    limits) are retried with exponential backoff (honoring Telegram's
    retry_after hint); anything else raises immediately.
    """

    def __init__(self, token: str,
                 client: httpx.Client | None = None,
                 timeout: float = 30.0,
                 max_retries: int = 2):
        token = (token or "").strip()
        if not token:
            raise TelegramNotConfiguredError(
                "No Telegram bot token: create a bot with @BotFather and "
                "set telegram.bot_token in forge.yaml or TELEGRAM_BOT_TOKEN.")
        self.token = token
        self.max_retries = max(0, int(max_retries))
        try:
            self._client = client or httpx.Client(timeout=timeout)
        except httpx.InvalidURL as e:
            # Usually a malformed HTTP(S)_PROXY / ALL_PROXY env var.
            raise TelegramAPIError(
                f"Could not create HTTP client: {e} "
                f"(check your HTTP(S)_PROXY / ALL_PROXY env vars).") from e

    def _sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def _call(self, method: str, _files: dict | None = None,
              **params: Any) -> dict[str, Any]:
        # Files are passed as (filename, bytes) tuples; httpx sends them
        # as multipart automatically. Bytes (not open handles) are used so
        # a retried attempt resends identical content.
        data = {k: v for k, v in params.items() if v is not None}
        url = f"{API_BASE}/bot{self.token}/{method}"
        last_error: TelegramAPIError | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._client.post(url, data=data, files=_files)
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = TelegramAPIError(
                    f"Telegram request failed (attempt "
                    f"{attempt + 1}/{self.max_retries + 1}): {e}",
                    transient=True)
                if attempt < self.max_retries:
                    self._sleep(2.0 ** attempt)
                    continue
                raise last_error from e
            if resp.status_code == 429:
                wait = _retry_after_seconds(resp) or 2.0 ** attempt
                last_error = TelegramAPIError(
                    f"Telegram rate-limited (429); retry suggested after "
                    f"{wait:.0f}s.", transient=True)
                if attempt < self.max_retries:
                    self._sleep(wait)
                    continue
                raise last_error
            if resp.status_code >= 500:
                last_error = TelegramAPIError(
                    f"Telegram server error (HTTP {resp.status_code}).",
                    transient=True)
                if attempt < self.max_retries:
                    self._sleep(2.0 ** attempt)
                    continue
                raise last_error
            break
        try:
            body = resp.json()
        except ValueError as e:
            raise TelegramAPIError(
                f"Telegram returned non-JSON (HTTP {resp.status_code}).",
                transient=True) from e
        if not body.get("ok"):
            # Client-side API errors (400/401/403/404...) are permanent.
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

    @staticmethod
    def _check_media(path: str | Path) -> Path:
        """Validate a media file for upload; returns the resolved Path."""
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Media file not found: {p}")
        if p.stat().st_size > MAX_UPLOAD_BYTES:
            raise ValueError(
                f"{p.name} is over Telegram's 50MB bot-API upload limit.")
        return p

    def _send_media(self, method: str, chat_id: str | int,
                    path: str | Path, caption: str = "") -> dict[str, Any]:
        p = self._check_media(path)
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
        p = self._check_media(path)
        if isinstance(stars, bool) or not isinstance(stars, int) \
                or stars <= 0:
            raise ValueError("stars must be a positive integer "
                             "(Telegram Stars price for the paywall).")
        media_type = ("video" if p.suffix.lower() in self._VIDEO_EXTS
                      else "photo")
        media = json.dumps([{
            "type": media_type,
            "media": f"attach://{p.name}",
            "caption": caption or None,
        }])
        with p.open("rb") as fh:
            files = {p.name: (p.name, fh.read())}
            return self._call("sendPaidMedia", chat_id=chat_id,
                              star_count=stars, media=media, _files=files)
