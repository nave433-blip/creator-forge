"""Tests for public AI providers (forge/ai/). No network calls."""

import pytest

from forge.ai import tasks as T
from forge.ai.providers import (
    AINotConfiguredError,
    ClaudeProvider,
    GeminiProvider,
    GrokProvider,
    PROVIDERS,
    get_provider,
    provider_status,
    resolve_provider,
)


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_registry_has_all_three():
    assert set(PROVIDERS) == {"grok", "gemini", "claude"}


def test_unknown_provider():
    with pytest.raises(KeyError):
        get_provider("nope")


def test_not_configured_errors_are_helpful():
    for name in ("grok", "gemini", "claude"):
        p = get_provider(name)
        assert p.is_configured() is False
        with pytest.raises(AINotConfiguredError) as e:
            p.complete("hi")
        assert "not configured" in str(e.value).lower()


def test_env_var_picks_up_key(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test")
    assert get_provider("grok").is_configured() is True
    monkeypatch.setenv("GEMINI_API_KEY", "gem-test")
    assert get_provider("gemini").is_configured() is True
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-test")
    assert get_provider("claude").is_configured() is True


def test_provider_status_never_leaks_keys(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "super-secret")
    for row in provider_status():
        assert "super-secret" not in str(row)
    grok = [r for r in provider_status() if r["provider"] == "grok"][0]
    assert grok["configured"] is True


def test_resolve_default_provider():
    assert resolve_provider(None, {}).key == "grok"
    assert resolve_provider(None, {"ai": {"default_provider": "claude"}}).key == "claude"
    assert resolve_provider("gemini", {}).key == "gemini"


def test_grok_request_shape(monkeypatch):
    calls = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["url"] = url
        calls["json"] = json
        assert headers["Authorization"] == "Bearer k"
        return FakeResp({"choices": [{"message": {"content": "  hi  "}}]})

    monkeypatch.setattr("forge.ai.providers.requests.post", fake_post)
    resp = GrokProvider(api_key="k").complete("hello", system="sys")
    assert resp.text == "hi"  # stripped
    assert calls["url"].endswith("/chat/completions")
    assert calls["json"]["messages"][0] == {"role": "system", "content": "sys"}


def test_gemini_request_shape(monkeypatch):
    def fake_post(url, params=None, json=None, timeout=None):
        assert params == {"key": "k"}
        assert "generateContent" in url
        return FakeResp({"candidates": [{"content": {"parts": [
            {"text": "a"}, {"text": "b"}]}}]}) 
    monkeypatch.setattr("forge.ai.providers.requests.post", fake_post)
    resp = GeminiProvider(api_key="k").complete("hello")
    assert resp.text == "ab"


def test_claude_request_shape(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        assert headers["x-api-key"] == "k"
        assert headers["anthropic-version"] == "2023-06-01"
        return FakeResp({"content": [{"type": "text", "text": "yo"},
                                     {"type": "tool_use", "text": ""}]})
    monkeypatch.setattr("forge.ai.providers.requests.post", fake_post)
    resp = ClaudeProvider(api_key="k").complete("hello", system="s")
    assert resp.text == "yo"
    assert resp.provider == "claude"


def test_task_prompts_mention_topic():
    p = GrokProvider(api_key="k")
    seen = {}

    def fake_complete(prompt, system="", max_tokens=500):
        seen["prompt"] = prompt
        from forge.ai.providers import AIResponse
        return AIResponse("grok", "m", "out")
    p.complete = fake_complete
    T.captions(p, "beach day")
    assert "beach day" in seen["prompt"]
    T.titles(p, "beach day")
    assert "beach day" in seen["prompt"]
    T.hashtags(p, "beach day")
    assert "beach day" in seen["prompt"]
    T.content_ideas(p, "beach niche")
    assert "beach niche" in seen["prompt"]
    T.polish(p, "my draft")
    assert "my draft" in seen["prompt"]
    T.reply_assist(p, "hey cutie")
    assert "hey cutie" in seen["prompt"]
    T.promo_text(p, "custom vid", "$50")
    assert "custom vid" in seen["prompt"] and "$50" in seen["prompt"]
