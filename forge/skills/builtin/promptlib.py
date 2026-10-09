"""Skill: promptlib -- a reusable library of video generation prompts.

Usage:
  forge skills run promptlib add --name "golden-hour" --text "..." [--negative "..."] [--tags slow,closeup]
  forge skills run promptlib list [--tag slow]
  forge skills run promptlib use --name "golden-hour" [--set mood=soft]
  forge skills run promptlib delete --name "golden-hour"

Prompts can contain {variables} which `use` fills in via --set key=value
(or leaves untouched and warns you). Stored as JSON at
./forge-data/promptlib.json (override with PROMPTLIB_PATH env var).
"""

from __future__ import annotations

import argparse
import json
import os
import string
from pathlib import Path

from forge.skills import Skill, SkillError


def _path() -> Path:
    p = Path(os.environ.get("PROMPTLIB_PATH", "./forge-data/promptlib.json"))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load() -> dict:
    p = _path()
    if not p.is_file():
        return {"prompts": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"prompts": {}}


def _save(data: dict) -> None:
    _path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def _cmd_add(ns: argparse.Namespace) -> str:
    data = _load()
    tags = [t.strip() for t in (ns.tags or "").split(",") if t.strip()]
    data["prompts"][ns.name] = {
        "text": ns.text,
        "negative": ns.negative or "",
        "tags": tags,
    }
    _save(data)
    return f"Saved prompt template '{ns.name}' ({len(tags)} tags)."


def _cmd_list(ns: argparse.Namespace) -> str:
    data = _load()
    prompts = data["prompts"]
    if ns.tag:
        prompts = {k: v for k, v in prompts.items() if ns.tag in v.get("tags", [])}
    if not prompts:
        return "No prompt templates yet. Add one with: promptlib add ..."
    lines = []
    for name in sorted(prompts):
        p = prompts[name]
        tags = ",".join(p.get("tags", []))
        preview = p["text"][:80] + ("..." if len(p["text"]) > 80 else "")
        lines.append(f"- {name} [{tags}]: {preview}")
    return "\n".join(lines)


def _cmd_use(ns: argparse.Namespace) -> str:
    data = _load()
    if ns.name not in data["prompts"]:
        raise SkillError(f"No template named {ns.name!r}.")
    tpl = data["prompts"][ns.name]
    subs = {}
    for item in ns.set or []:
        if "=" not in item:
            raise SkillError(f"--set needs key=value, got {item!r}.")
        k, v = item.split("=", 1)
        subs[k.strip()] = v
    text = tpl["text"]
    fields = [f for _, f, _, _ in string.Formatter().parse(text) if f]
    missing = [f for f in fields if f not in subs]
    if missing:
        return ("Template has unfilled variables: " + ", ".join(missing)
                + "\nFill them with --set key=value. Raw text:\n" + text)
    filled = text.format(**subs)
    out = [f"PROMPT:\n{filled}"]
    if tpl.get("negative"):
        out.append(f"NEGATIVE:\n{tpl['negative']}")
    out.append("\nPaste the prompt into: forge video generate --prompt \"...\"")
    return "\n".join(out)


def _cmd_delete(ns: argparse.Namespace) -> str:
    data = _load()
    if ns.name not in data["prompts"]:
        raise SkillError(f"No template named {ns.name!r}.")
    del data["prompts"][ns.name]
    _save(data)
    return f"Deleted prompt template '{ns.name}'."


def _parse(args: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="promptlib")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add")
    a.add_argument("--name", required=True)
    a.add_argument("--text", required=True)
    a.add_argument("--negative", default="")
    a.add_argument("--tags", default="")

    li = sub.add_parser("list")
    li.add_argument("--tag", default="")

    u = sub.add_parser("use")
    u.add_argument("--name", required=True)
    u.add_argument("--set", action="append", default=[])

    d = sub.add_parser("delete")
    d.add_argument("--name", required=True)
    return p.parse_args(args)


def run(args: list[str]) -> str:
    ns = _parse(args)
    if ns.cmd == "add":
        return _cmd_add(ns)
    if ns.cmd == "list":
        return _cmd_list(ns)
    if ns.cmd == "use":
        return _cmd_use(ns)
    if ns.cmd == "delete":
        return _cmd_delete(ns)
    raise SkillError(f"Unknown subcommand {ns.cmd!r}.")  # pragma: no cover


SKILL = Skill(
    name="promptlib",
    version="1.0.0",
    description="Save, list, and reuse video generation prompt templates.",
    usage="forge skills run promptlib add --name NAME --text \"...\"",
    run=run,
)
