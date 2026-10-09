"""Canned response templates for chat.

Templates are short reusable replies she writes once and reuses:
greetings, tip-menu pointers, boundary statements, goodbyes. Stored
as JSON (./forge-data/chat-templates.json, override with
CHAT_TEMPLATES_PATH env var). The CLI and dashboard can insert a
template's text straight into the approval queue as a draft.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def _path() -> Path:
    p = Path(os.environ.get("CHAT_TEMPLATES_PATH",
                            "./forge-data/chat-templates.json"))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_templates() -> dict[str, dict]:
    """Return {name: {text, category}} (empty dict if none)."""
    p = _path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data.get("templates", {})


def save_templates(templates: dict[str, dict]) -> None:
    _path().write_text(json.dumps({"templates": templates}, indent=2),
                       encoding="utf-8")


def add_template(name: str, text: str, category: str = "general") -> None:
    templates = load_templates()
    if name in templates:
        raise KeyError(f"Template {name!r} already exists. Delete it first.")
    templates[name] = {"text": text, "category": category}
    save_templates(templates)


def delete_template(name: str) -> None:
    templates = load_templates()
    if name not in templates:
        raise KeyError(f"No template named {name!r}.")
    del templates[name]
    save_templates(templates)


def get_template(name: str) -> dict:
    templates = load_templates()
    if name not in templates:
        raise KeyError(
            f"No template named {name!r}. Known: "
            + ", ".join(sorted(templates)) or "(none)")
    return templates[name]


def render_template(name: str, sender: str = "",
                    persona_name: str = "") -> str:
    """Fill {sender} / {persona} placeholders in a template."""
    tpl = get_template(name)
    return tpl["text"].replace("{sender}", sender or "there").replace(
        "{persona}", persona_name or "me")


# A few sane defaults she can keep, edit, or delete.
DEFAULT_TEMPLATES = {
    "greeting": {
        "text": "Hey {sender}! Thanks for messaging me 💕",
        "category": "greeting",
    },
    "tip-menu": {
        "text": ("Here's my tip menu, babe 💕\n"
                 "{menu}\n"
                 "Just tell me which one and I'll set it up!"),
        "category": "sales",
    },
    "boundary-meet": {
        "text": ("I don't do in-person meetups, but I'm all yours "
                 "right here 💋"),
        "category": "boundary",
    },
    "goodbye": {
        "text": "Goodnight babe, talk tomorrow 💕",
        "category": "goodbye",
    },
}


def ensure_defaults() -> int:
    """Seed DEFAULT_TEMPLATES for names that don't exist yet.

    Returns the number of templates added. Never overwrites her edits.
    """
    templates = load_templates()
    added = 0
    for name, tpl in DEFAULT_TEMPLATES.items():
        if name not in templates:
            templates[name] = dict(tpl)
            added += 1
    if added:
        save_templates(templates)
    return added
