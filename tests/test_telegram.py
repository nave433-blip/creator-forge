"""Tests for the Telegram bot adapter (httpx-based, MockTransport -- no network)."""
from __future__ import annotations

import io
import json
import sys

import httpx
import pytest


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _ok_bot():
    from forge.telegram.bot import TelegramBot
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/getMe"):
            return httpx.Response(200, json={"ok": True, "result": {
                "id": 1, "is_bot": True, "first_name": "Test",
                "username": "testbot"}})
        return httpx.Response(200, json={"ok": True, "result": {
            "message_id": 42, "chat": {"id": 7}}})

    return TelegramBot("TOKEN123", client=_mock_client(handler)), calls


def test_status_validates_token():
    bot, _ = _ok_bot()
    me = bot.status()
    assert me["username"] == "testbot"


def test_send_message_posts_to_bot_api():
    bot, calls = _ok_bot()
    msg = bot.send_message("@channel", "hello fans")
    assert msg["message_id"] == 42
    assert any("sendMessage" in c for c in calls)


def test_send_photo_and_video(tmp_path):
    bot, calls = _ok_bot()
    photo = tmp_path / "p.jpg"
    photo.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)
    assert bot.send_photo("@c", photo, "drop!")["message_id"] == 42
    video = tmp_path / "v.mp4"
    video.write_bytes(b"\x00" * 100)
    assert bot.send_video("@c", video)["message_id"] == 42
    assert any("sendPhoto" in c for c in calls)
    assert any("sendVideo" in c for c in calls)


def test_send_photo_missing_file_and_oversize(tmp_path):
    bot, _ = _ok_bot()
    with pytest.raises(FileNotFoundError):
        bot.send_photo("@c", tmp_path / "nope.jpg")
    big = tmp_path / "big.mp4"
    big.write_bytes(b"\x00")
    with open(big, "r+b") as fh:  # sparse: size without the disk cost
        fh.truncate(60 * 1024 * 1024)
    with pytest.raises(ValueError, match="50MB"):
        bot.send_video("@c", big)
    with pytest.raises(ValueError, match="empty"):
        bot.send_message("@c", "   ")


def test_api_error_surfaces_cleanly():
    from forge.telegram.bot import TelegramBot, TelegramAPIError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False,
                                         "description": "Bad Request: bad token"})

    bot = TelegramBot("BAD", client=_mock_client(handler))
    with pytest.raises(TelegramAPIError, match="Bad Request"):
        bot.status()


def test_network_failure_surfaces_cleanly():
    from forge.telegram.bot import TelegramBot, TelegramAPIError

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    bot = TelegramBot("TOKEN", client=_mock_client(handler))
    with pytest.raises(TelegramAPIError, match="failed"):
        bot.status()


def test_broken_proxy_env_gives_helpful_error(monkeypatch):
    """A malformed HTTP(S)_PROXY env var -> clean error naming the cause."""
    from forge.telegram.bot import TelegramBot, TelegramAPIError
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy:1]")
    monkeypatch.setenv("HTTP_PROXY", "http://proxy:1]")
    with pytest.raises(TelegramAPIError, match="PROXY"):
        TelegramBot("TOKEN123")


def test_missing_token_clean_error():
    from forge.telegram.bot import TelegramBot, TelegramNotConfiguredError
    with pytest.raises(TelegramNotConfiguredError, match="@BotFather"):
        TelegramBot("")


def test_resolve_token_prefers_explicit_then_env():
    from forge.telegram.bot import resolve_token
    assert resolve_token(" abc ", env={}) == "abc"
    assert resolve_token(None, env={"TELEGRAM_BOT_TOKEN": "env-tok"}) == "env-tok"
    assert resolve_token(None, env={}) == ""


# -- CLI (no token configured -> clean errors, no tracebacks) --

def _run_cli(*args: str):
    from forge.cli import app as cli_app
    old_argv, old_out, old_err = sys.argv, sys.stdout, sys.stderr
    out, err = io.StringIO(), io.StringIO()
    sys.argv = ["forge", *args]
    sys.stdout, sys.stderr = out, err
    try:
        try:
            cli_app()
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
        else:
            code = 0
    finally:
        sys.argv, sys.stdout, sys.stderr = old_argv, old_out, old_err
    return code, out.getvalue(), err.getvalue()


def test_cli_telegram_no_token_clean_error(tmp_path):
    cfg = tmp_path / "forge.yaml"
    cfg.write_text("telegram: {}\n", encoding="utf-8")
    for args in (["telegram", "status", "--config", str(cfg)],
                 ["telegram", "send", "--text", "hi", "--chat", "@c",
                  "--config", str(cfg)]):
        code, out, err = _run_cli(*args)
        assert code != 0
        assert "Traceback" not in out + err
        assert "BotFather" in err or "token" in err.lower()


def test_cli_telegram_missing_chat_clean_error(tmp_path):
    cfg = tmp_path / "forge.yaml"
    cfg.write_text("telegram: {bot_token: X}\n", encoding="utf-8")
    code, out, err = _run_cli("telegram", "send", "--text", "hi",
                              "--config", str(cfg))
    assert code != 0
    assert "Traceback" not in out + err
    assert "--chat" in err


def test_send_paid_media_photo_and_video(tmp_path):
    bot, calls = _ok_bot()
    photo = tmp_path / "p.jpg"
    photo.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)
    assert bot.send_paid_media("@c", photo, 50, "ppv drop")["message_id"] == 42
    video = tmp_path / "v.mp4"
    video.write_bytes(b"\x00" * 100)
    assert bot.send_paid_media("@c", video, 100)["message_id"] == 42
    assert any("sendPaidMedia" in c for c in calls)


def test_send_paid_media_validation(tmp_path):
    bot, _ = _ok_bot()
    photo = tmp_path / "p.jpg"
    photo.write_bytes(b"\xff\xd8\xff")
    with pytest.raises(FileNotFoundError):
        bot.send_paid_media("@c", tmp_path / "nope.jpg", 50)
    with pytest.raises(ValueError, match="positive"):
        bot.send_paid_media("@c", photo, 0)
    with pytest.raises(ValueError, match="positive"):
        bot.send_paid_media("@c", photo, -5)
