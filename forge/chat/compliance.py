"""Compliance checker: flag risky drafts before approval.

She defines the lists in forge.yaml under chat.compliance:
  banned_terms: [words/phrases the platform punishes]
  patterns: [regexes, e.g. external links, off-platform payment mentions]
  require_review: [topics that always need her eyes]

check_draft() returns a list of findings; empty = clean. The dashboard
shows a badge on flagged drafts, and `forge chat check` prints findings.
This is a dumb wordlist matcher, stated plainly -- it catches what she
tells it to catch, nothing more.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

DEFAULT_BANNED_TERMS = [
    # Common OnlyFans/Fansly no-go zones -- SHE should extend this with
    # the current restricted-word list for each platform she uses.
    "meet up", "meetup", "in person", "escort",
]

DEFAULT_PATTERNS = [
    r"https?://(?!onlyfans\\.com|fansly\\.com)[\\w.-]+",  # off-platform links
]


@dataclass
class Finding:
    category: str  # banned_term | pattern | require_review
    match: str
    detail: str


@dataclass
class ComplianceConfig:
    banned_terms: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    require_review: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ComplianceConfig":
        data = data or {}
        return cls(
            banned_terms=[str(t) for t in data.get("banned_terms", [])],
            patterns=[str(p) for p in data.get("patterns", [])],
            require_review=[str(t) for t in data.get("require_review", [])],
        )

    def with_defaults(self) -> "ComplianceConfig":
        terms = list(DEFAULT_BANNED_TERMS)
        for t in self.banned_terms:
            if t not in terms:
                terms.append(t)
        pats = list(DEFAULT_PATTERNS)
        for p in self.patterns:
            if p not in pats:
                pats.append(p)
        return ComplianceConfig(terms, pats, self.require_review)


def check_text(text: str, cfg: ComplianceConfig) -> list[Finding]:
    """Check one piece of text. Returns findings (empty = clean)."""
    cfg = cfg.with_defaults()
    findings: list[Finding] = []
    lowered = text.lower()
    for term in cfg.banned_terms:
        if term.lower() in lowered:
            findings.append(Finding(
                "banned_term", term,
                f"Contains banned term {term!r} -- platforms punish this."))
    for pat in cfg.patterns:
        try:
            m = re.search(pat, text, re.IGNORECASE)
        except re.error:
            continue
        if m:
            findings.append(Finding(
                "pattern", m.group(0),
                f"Matches risky pattern {pat!r}."))
    for topic in cfg.require_review:
        if topic.lower() in lowered:
            findings.append(Finding(
                "require_review", topic,
                f"Touches {topic!r} -- needs her eyes before sending."))
    return findings


def check_draft_text(text: str,
                     config_dict: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Convenience wrapper: raw config dict -> serializable findings."""
    cfg = ComplianceConfig.from_dict(config_dict)
    return [{"category": f.category, "match": f.match,
             "detail": f.detail} for f in check_text(text, cfg)]
