"""Dashboard Telegram routes (TestClient -- no network, no real token)."""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient


def _client(tmp_path, monkeypatch):
    cfg = tmp_path / "forge.yaml"
    cfg.write_text("telegram: {}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    from forge.dashboard import app as dapp
    return TestClient(dapp.create_app(str(cfg)))


def test_status_unconfigured(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    r = client.get("/telegram/status")
    assert r.status_code == 200
    assert r.json() == {"configured": False}


def test_send_requires_chat(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    r = client.post("/telegram/send", json={"text": "hi"})
    assert r.status_code == 400
    assert "chat" in r.json()["detail"].lower()


def test_send_requires_text_or_media(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    r = client.post("/telegram/send", json={"chat": "@c"})
    assert r.status_code == 400


def test_send_message_uses_mock_transport(tmp_path, monkeypatch):
    from forge.dashboard import app as dapp
    from forge.telegram import bot as botmod

    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json={"ok": True,
                                         "result": {"message_id": 7}})

    real_bot = botmod.TelegramBot

    class FakeBot(real_bot):
        def __init__(self, token):
            super().__init__(token,
                             client=httpx.Client(
                                 transport=httpx.MockTransport(handler)))

    monkeypatch.setattr(botmod, "TelegramBot", FakeBot)
    cfg = tmp_path / "forge.yaml"
    cfg.write_text("telegram: {bot_token: X, default_chat_id: '@c'}\n",
                   encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    client = TestClient(dapp.create_app(str(cfg)))
    r = client.post("/telegram/send", json={"text": "hello fans"})
    assert r.status_code == 200
    assert r.json()["message_id"] == 7
    assert any("sendMessage" in p for p in seen)


def test_send_paid_media_endpoint(tmp_path, monkeypatch):
    from forge.dashboard import app as dapp
    from forge.telegram import bot as botmod

    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json={"ok": True,
                                         "result": {"message_id": 9}})

    real_bot = botmod.TelegramBot

    class FakeBot(real_bot):
        def __init__(self, token):
            super().__init__(token,
                             client=httpx.Client(
                                 transport=httpx.MockTransport(handler)))

    monkeypatch.setattr(botmod, "TelegramBot", FakeBot)
    photo = tmp_path / "p.jpg"
    photo.write_bytes(b"\xff\xd8\xff" + b"\x00" * 50)
    cfg = tmp_path / "forge.yaml"
    cfg.write_text("telegram: {bot_token: X, default_chat_id: '@c'}\n",
                   encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    client = TestClient(dapp.create_app(str(cfg)))
    r = client.post("/telegram/send",
                    json={"photo": str(photo), "paid_stars": 25,
                          "caption": "ppv"})
    assert r.status_code == 200
    assert r.json()["message_id"] == 9
    assert r.json()["paid_stars"] == 25
    assert any("sendPaidMedia" in p for p in seen)


def test_send_missing_media_file_clean_400(tmp_path, monkeypatch):
    from forge.dashboard import app as dapp
    from forge.telegram import bot as botmod

    real_bot = botmod.TelegramBot

    class FakeBot(real_bot):
        def __init__(self, token):
            super().__init__(token)

    monkeypatch.setattr(botmod, "TelegramBot", FakeBot)
    cfg = tmp_path / "forge.yaml"
    cfg.write_text("telegram: {bot_token: X, default_chat_id: '@c'}\n",
                   encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    client = TestClient(dapp.create_app(str(cfg)))
    r = client.post("/telegram/send",
                    json={"photo": str(tmp_path / "nope.jpg")})
    assert r.status_code == 400
    assert "Traceback" not in r.text


def _bot_with_handler(tmp_path, monkeypatch, handler, cfg_extra=""):
    from forge.dashboard import app as dapp
    from forge.telegram import bot as botmod
    real_bot = botmod.TelegramBot

    class FakeBot(real_bot):
        def __init__(self, token):
            super().__init__(token, client=httpx.Client(
                transport=httpx.MockTransport(handler)))

    monkeypatch.setattr(botmod, "TelegramBot", FakeBot)
    cfg = tmp_path / "forge.yaml"
    cfg.write_text("telegram: {bot_token: X, default_chat_id: '@c'}\n"
                   + cfg_extra, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return TestClient(dapp.create_app(str(cfg)))


def test_send_paid_stars_garbage_is_400_not_500(tmp_path, monkeypatch):
    client = _bot_with_handler(
        tmp_path, monkeypatch,
        lambda req: httpx.Response(200, json={"ok": True, "result": {}}))
    r = client.post("/telegram/send",
                    json={"text": "hi", "paid_stars": "lots"})
    assert r.status_code == 400
    assert "paid_stars" in r.json()["detail"]


def test_send_paid_stars_negative_is_400(tmp_path, monkeypatch):
    client = _bot_with_handler(
        tmp_path, monkeypatch,
        lambda req: httpx.Response(200, json={"ok": True, "result": {}}))
    r = client.post("/telegram/send",
                    json={"text": "hi", "paid_stars": -5})
    assert r.status_code == 400


def test_send_transient_upstream_is_502(tmp_path, monkeypatch):
    client = _bot_with_handler(
        tmp_path, monkeypatch,
        lambda req: httpx.Response(503, text="Service Unavailable"))
    r = client.post("/telegram/send", json={"text": "hi"})
    assert r.status_code == 502


def test_send_permanent_telegram_error_is_400(tmp_path, monkeypatch):
    client = _bot_with_handler(
        tmp_path, monkeypatch,
        lambda req: httpx.Response(400, json={
            "ok": False, "description": "Bad Request: chat not found"}))
    r = client.post("/telegram/send", json={"text": "hi"})
    assert r.status_code == 400
