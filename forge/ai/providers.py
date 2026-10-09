"""Public AI providers: Grok (xAI), Gemini (Google), Claude (Anthropic).

One interface, three backends. Each needs HER OWN API key (paid
services) -- configured in forge.yaml under `ai:` or via environment
variables. No key = a clear setup error, never a fake answer.

Env vars (checked first, so keys never have to live in a file):
    XAI_API_KEY, GEMINI_API_KEY (or GOOGLE_API_KEY), ANTHROPIC_API_KEY

forge.yaml:
    ai:
      default_provider: grok        # grok | gemini | claude
      grok_api_key: ""              # or XAI_API_KEY
      gemini_api_key: ""            # or GEMINI_API_KEY
      claude_api_key: ""            # or ANTHROPIC_API_KEY
      models:                       # override when providers rename models
        grok: grok-3-mini
        gemini: gemini-2.0-flash
        claude: claude-sonnet-4-5

Everything produced here is a DRAFT for her review -- captions get
pasted by her, chat help goes through the approval queue.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests


class AINotConfiguredError(Exception):
    """Raised when a provider has no API key configured."""


@dataclass
class AIResponse:
    provider: str
    model: str
    text: str


class AIProvider:
    """Base class. Subclasses implement complete()."""

    key: str = "?"
    env_vars: tuple[str, ...] = ()
    docs_url: str = ""
    models_hint: str = ""

    def __init__(self, api_key: str = "", model: str = ""):
        self.api_key = api_key or self._from_env()
        self.model = model or self.default_model()

    def _from_env(self) -> str:
        for var in self.env_vars:
            if os.environ.get(var):
                return os.environ[var]
        return ""

    @classmethod
    def default_model(cls) -> str:
        raise NotImplementedError

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _require_key(self) -> None:
        if not self.api_key:
            env = " or ".join(self.env_vars)
            raise AINotConfiguredError(
                f"{self.key} is not configured: set ai.{self.key}_api_key in "
                f"forge.yaml or the {env} environment variable. "
                f"Get a key: {self.docs_url}")

    def complete(self, prompt: str, system: str = "",
                 max_tokens: int = 500) -> AIResponse:
        raise NotImplementedError


class GrokProvider(AIProvider):
    """xAI Grok via its OpenAI-compatible chat API."""

    key = "grok"
    env_vars = ("XAI_API_KEY",)
    docs_url = "https://docs.x.ai"
    models_hint = "grok-3-mini is cheap/fast; check docs.x.ai for current names"

    @classmethod
    def default_model(cls) -> str:
        return "grok-3-mini"

    def complete(self, prompt: str, system: str = "",
                 max_tokens: int = 500) -> AIResponse:
        self._require_key()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        r = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": messages,
                  "max_tokens": max_tokens},
            timeout=60)
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"].strip()
        return AIResponse("grok", self.model, text)


class GeminiProvider(AIProvider):
    """Google Gemini via the Generative Language REST API."""

    key = "gemini"
    env_vars = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
    docs_url = "https://ai.google.dev"

    @classmethod
    def default_model(cls) -> str:
        return "gemini-2.0-flash"

    def complete(self, prompt: str, system: str = "",
                 max_tokens: int = 500) -> AIResponse:
        self._require_key()
        body: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent",
            params={"key": self.api_key}, json=body, timeout=60)
        r.raise_for_status()
        parts = r.json()["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
        return AIResponse("gemini", self.model, text)


class ClaudeProvider(AIProvider):
    """Anthropic Claude via the Messages API."""

    key = "claude"
    env_vars = ("ANTHROPIC_API_KEY",)
    docs_url = "https://docs.anthropic.com"

    @classmethod
    def default_model(cls) -> str:
        # Model names change; override in forge.yaml if this 404s.
        return "claude-sonnet-4-5"

    def complete(self, prompt: str, system: str = "",
                 max_tokens: int = 500) -> AIResponse:
        self._require_key()
        body: dict[str, Any] = {
            "model": self.model, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.api_key,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json=body, timeout=60)
        r.raise_for_status()
        blocks = r.json()["content"]
        text = "".join(b.get("text", "") for b in blocks
                       if b.get("type") == "text").strip()
        return AIResponse("claude", self.model, text)


PROVIDERS: dict[str, type[AIProvider]] = {
    "grok": GrokProvider,
    "gemini": GeminiProvider,
    "claude": ClaudeProvider,
}


def get_provider(name: str, config: Any = None) -> AIProvider:
    """Build a provider from config (or env vars)."""
    name = (name or "").strip().lower()
    if name not in PROVIDERS:
        raise KeyError(f"Unknown AI provider {name!r}; "
                       f"pick one of {sorted(PROVIDERS)}")
    cls = PROVIDERS[name]
    ai_cfg = (config.get("ai", {}) if config else {}) or {}
    model = ((ai_cfg.get("models") or {}).get(name)) or cls.default_model()
    key = ai_cfg.get(f"{name}_api_key", "")
    return cls(api_key=key, model=model)


def resolve_provider(name: str | None, config: Any = None) -> AIProvider:
    """Explicit --provider wins, else ai.default_provider, else grok."""
    ai_cfg = (config.get("ai", {}) if config else {}) or {}
    return get_provider(name or ai_cfg.get("default_provider") or "grok",
                        config)


def provider_status(config: Any = None) -> list[dict[str, Any]]:
    """Configured? report for every provider (never leaks key material)."""
    out = []
    for name in sorted(PROVIDERS):
        p = get_provider(name, config)
        out.append({"provider": name, "model": p.model,
                    "configured": p.is_configured(),
                    "docs": p.docs_url, "models_hint": p.models_hint})
    return out
