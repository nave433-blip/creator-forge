"""Configuration loading for CreatorForge.

Looks for ``forge.yaml`` in (in order):
1. the path passed explicitly,
2. the ``FORGE_CONFIG`` environment variable,
3. the current working directory,
4. ``~/.config/creator-forge/forge.yaml``.

Individual values can be overridden with environment variables prefixed
``FORGE_`` (e.g. ``FORGE_REDDIT_CLIENT_ID``). See examples/forge.yaml.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_PATHS = [
    Path.cwd() / "forge.yaml",
    Path.home() / ".config" / "creator-forge" / "forge.yaml",
]


class ForgeConfig(dict):
    """A dict-like config with dotted-key lookup."""

    def get_path(self, dotted: str, default: Any = None) -> Any:
        node: Any = self
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node


def _find_config(explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None
    env = os.environ.get("FORGE_CONFIG")
    if env and Path(env).is_file():
        return Path(env)
    for p in _DEFAULT_PATHS:
        if p.is_file():
            return p
    return None


def _apply_env_overrides(cfg: dict) -> dict:
    """Map FORGE_SECTION_KEY=... onto cfg[section][key.lower()]."""

    def deep_set(node: dict, keys: list[str], value: str) -> None:
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = value

    for name, value in os.environ.items():
        if not name.startswith("FORGE_") or name == "FORGE_CONFIG":
            continue
        rest = name[len("FORGE_"):].lower()
        parts = rest.split("_", 1)
        # Single-word names land at the top level; two-part names map to
        # section.key. Longer nesting is not supported via env.
        deep_set(cfg, parts, value)
    return cfg


def load_config(explicit: str | None = None) -> ForgeConfig:
    path = _find_config(explicit)
    data: dict[str, Any] = {}
    if path is not None:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    data = _apply_env_overrides(data)
    data.setdefault("_config_path", str(path) if path else None)
    return ForgeConfig(data)
