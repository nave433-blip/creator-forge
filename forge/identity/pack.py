"""Identity packs: consent-gated profiles describing the creator's likeness.

An identity pack is a YAML file that names the person whose likeness will
be used for AI video generation, plus a signed consent record (who, when,
scope of use). The video pipeline REFUSES to run without a pack that
passes :func:`validate_identity_pack`.

The pack stores a SHA-256 checksum of the signed consent statement so any
tampering with the pack after signing invalidates it.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml


class InvalidConsentError(Exception):
    """Raised when an identity pack's consent record is missing or invalid."""


REQUIRED_FIELDS = ["name", "consent"]
REQUIRED_CONSENT_FIELDS = ["signer", "date", "scope", "statement_checksum"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _checksum_of_statement(statement: str) -> str:
    return hashlib.sha256(statement.strip().encode("utf-8")).hexdigest()


def create_identity_pack(
    *,
    name: str,
    signer: str,
    scope: str,
    statement: str,
    statement_date: str | None = None,
    notes: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an identity pack dict from its parts.

    The ``statement`` is the full signed consent text (see
    ``docs/CONSENT.md`` for a template). A checksum of it is stored; the
    statement itself should be kept with the pack (``consent_statement``
    field) so validation can recompute the checksum.
    """
    statement_date = statement_date or date.today().isoformat()
    pack: dict[str, Any] = {
        "name": name,
        "created": date.today().isoformat(),
        "notes": notes,
        "consent": {
            "signer": signer,
            "date": statement_date,
            "scope": scope,
            "statement_checksum": _checksum_of_statement(statement),
        },
        "consent_statement": statement.strip(),
    }
    if extra:
        pack.update(extra)
    return pack


def write_identity_pack(pack: dict[str, Any], path: str | Path) -> Path:
    """Write a pack to YAML. Returns the path written."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(pack, fh, sort_keys=False, allow_unicode=True)
    return p


def load_identity_pack(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise InvalidConsentError(f"Identity pack at {p} is not a mapping.")
    return data


def validate_identity_pack(pack: dict[str, Any]) -> dict[str, Any]:
    """Validate a pack's consent record.

    Raises :class:`InvalidConsentError` describing the first problem found.
    Returns the pack unchanged when valid, so it can be used inline::

        pack = validate_identity_pack(load_identity_pack(path))
    """
    for field in REQUIRED_FIELDS:
        if not pack.get(field):
            raise InvalidConsentError(
                f"Identity pack missing required field '{field}'. "
                "Refusing to proceed without consent."
            )
    consent = pack["consent"]
    if not isinstance(consent, dict):
        raise InvalidConsentError("Identity pack 'consent' must be a mapping.")
    for field in REQUIRED_CONSENT_FIELDS:
        if not consent.get(field):
            raise InvalidConsentError(
                f"Consent record missing required field '{field}'. "
                "Refusing to proceed without consent."
            )
    signer = str(consent["signer"]).strip()
    if len(signer) < 2:
        raise InvalidConsentError("Consent signer name is empty or too short.")
    if not DATE_RE.match(str(consent["date"])):
        raise InvalidConsentError(
            "Consent 'date' must be in YYYY-MM-DD format "
            f"(got {consent['date']!r})."
        )
    scope = str(consent["scope"]).strip()
    if len(scope) < 10:
        raise InvalidConsentError(
            "Consent 'scope' is too short to describe the agreed use."
        )
    statement = pack.get("consent_statement", "")
    expected = _checksum_of_statement(str(statement))
    if str(consent["statement_checksum"]) != expected:
        raise InvalidConsentError(
            "Consent statement checksum mismatch: the consent statement or "
            "pack was modified after signing. Re-sign with a fresh statement."
        )
    # Optional comfort section (used by the scene director): which content
    # categories she films herself vs which are AI-only.
    comfort = pack.get("comfort", None)
    if comfort is not None:
        if not isinstance(comfort, dict):
            raise InvalidConsentError("'comfort' section must be a mapping.")
        for key in ("self_filmed", "ai_only"):
            vals = comfort.get(key, []) or []
            if not isinstance(vals, list) or not all(
                    isinstance(v, str) for v in vals):
                raise InvalidConsentError(
                    f"'comfort.{key}' must be a list of category names.")
    return pack


def consent_summary(pack: dict[str, Any]) -> str:
    c = pack["consent"]
    return (
        f"Identity: {pack.get('name')} | "
        f"Consent signed by {c['signer']} on {c['date']} | "
        f"Scope: {c['scope']}"
    )
