"""Fan CRM: profiles, tags, notes, spend tracking, buyer-intent scoring.

Honest model: CreatorForge cannot see inside OnlyFans/Fansly/Snapchat --
none of them offer a stats API we can call. Fan records are built from
what SHE enters or imports (CSV from the site's own data export), plus
what the local chat engine observes (drafts created). Buyer-intent is a
simple RULES-BASED score (0-100), labeled as such everywhere: a
heuristic, not a prediction model.

Tables:
- fans: one row per (platform, handle).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fans (
    platform TEXT NOT NULL,
    handle TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    notes TEXT NOT NULL DEFAULT '',
    total_spend REAL NOT NULL DEFAULT 0.0,
    purchase_count INTEGER NOT NULL DEFAULT 0,
    message_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'new',
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    last_purchase_at TEXT,
    PRIMARY KEY (platform, handle)
);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class FanCRM:
    """SQLite-backed fan/customer relationship store."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- fans ------------------------------------------------------------
    def upsert_fan(self, *, platform: str, handle: str,
                   status: str = "new") -> dict[str, Any]:
        platform, handle = platform.strip(), handle.strip()
        row = self.get_fan(platform, handle)
        if row:
            return row
        now = _now()
        self._conn.execute(
            "INSERT INTO fans (platform, handle, status, first_seen,"
            " last_seen) VALUES (?,?,?,?,?)",
            (platform, handle, status, now, now),
        )
        self._conn.commit()
        return self.get_fan(platform, handle)  # type: ignore[return-value]

    def get_fan(self, platform: str, handle: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM fans WHERE platform = ? AND handle = ?",
            (platform.strip(), handle.strip()),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["tags"] = json.loads(d["tags"])
        return d

    def list_fans(self, *, platform: str | None = None,
                  status: str | None = None,
                  tag: str | None = None,
                  limit: int = 200) -> list[dict[str, Any]]:
        q = "SELECT * FROM fans"
        clauses, params = [], []
        if platform:
            clauses.append("platform = ?")
            params.append(platform)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY total_spend DESC LIMIT ?"
        out = []
        for r in self._conn.execute(q, params + [limit]):
            d = dict(r)
            d["tags"] = json.loads(d["tags"])
            if tag and tag not in d["tags"]:
                continue
            out.append(d)
        return out

    def add_tag(self, platform: str, handle: str, tag: str) -> dict[str, Any]:
        fan = self.upsert_fan(platform=platform, handle=handle)
        tags = fan["tags"]
        if tag not in tags:
            tags.append(tag)
        self._conn.execute(
            "UPDATE fans SET tags = ?, last_seen = ?"
            " WHERE platform = ? AND handle = ?",
            (json.dumps(tags), _now(), platform.strip(), handle.strip()))
        self._conn.commit()
        return self.get_fan(platform, handle)  # type: ignore[return-value]

    def remove_tag(self, platform: str, handle: str,
                   tag: str) -> dict[str, Any]:
        fan = self.upsert_fan(platform=platform, handle=handle)
        tags = [t for t in fan["tags"] if t != tag]
        self._conn.execute(
            "UPDATE fans SET tags = ? WHERE platform = ? AND handle = ?",
            (json.dumps(tags), platform.strip(), handle.strip()))
        self._conn.commit()
        return self.get_fan(platform, handle)  # type: ignore[return-value]

    def add_note(self, platform: str, handle: str, note: str) -> dict[str, Any]:
        fan = self.upsert_fan(platform=platform, handle=handle)
        notes = (fan["notes"] + "\n" if fan["notes"] else "") + \
            f"[{_now()}] {note}"
        self._conn.execute(
            "UPDATE fans SET notes = ?, last_seen = ?"
            " WHERE platform = ? AND handle = ?",
            (notes, _now(), platform.strip(), handle.strip()))
        self._conn.commit()
        return self.get_fan(platform, handle)  # type: ignore[return-value]

    def record_spend(self, platform: str, handle: str,
                     amount: float) -> dict[str, Any]:
        fan = self.upsert_fan(platform=platform, handle=handle)
        now = _now()
        self._conn.execute(
            "UPDATE fans SET total_spend = total_spend + ?,"
            " purchase_count = purchase_count + 1,"
            " last_purchase_at = ?, last_seen = ?,"
            " status = CASE WHEN status = 'new' THEN 'active' ELSE status END"
            " WHERE platform = ? AND handle = ?",
            (amount, now, now, platform.strip(), handle.strip()))
        self._conn.commit()
        return self.get_fan(platform, handle)  # type: ignore[return-value]

    def record_message(self, platform: str, handle: str) -> None:
        self.upsert_fan(platform=platform, handle=handle)
        self._conn.execute(
            "UPDATE fans SET message_count = message_count + 1,"
            " last_seen = ? WHERE platform = ? AND handle = ?",
            (_now(), platform.strip(), handle.strip()))
        self._conn.commit()

    def set_status(self, platform: str, handle: str,
                   status: str) -> dict[str, Any]:
        self.upsert_fan(platform=platform, handle=handle)
        self._conn.execute(
            "UPDATE fans SET status = ? WHERE platform = ? AND handle = ?",
            (status, platform.strip(), handle.strip()))
        self._conn.commit()
        return self.get_fan(platform, handle)  # type: ignore[return-value]

    def import_csv(self, csv_path: str | Path) -> int:
        """Import fans from CSV: platform,handle[,tags,notes,total_spend,status].

        Tags are ';'-separated. Use this with the fan list YOU export from
        each site -- CreatorForge can't pull it automatically.
        """
        import csv

        count = 0
        with open(csv_path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if not row.get("platform") or not row.get("handle"):
                    continue
                fan = self.upsert_fan(platform=row["platform"],
                                      handle=row["handle"])
                if row.get("tags"):
                    for t in row["tags"].split(";"):
                        t = t.strip()
                        if t:
                            fan = self.add_tag(row["platform"],
                                               row["handle"], t)
                if row.get("notes"):
                    fan = self.add_note(row["platform"], row["handle"],
                                        row["notes"])
                if row.get("total_spend"):
                    try:
                        fan = self.record_spend(row["platform"],
                                                row["handle"],
                                                float(row["total_spend"]))
                    except ValueError:
                        pass
                if row.get("status"):
                    fan = self.set_status(row["platform"], row["handle"],
                                          row["status"].strip())
                count += 1
        return count

    # -- buyer intent (rules-based, labeled as such) ----------------------
    def buyer_intent(self, platform: str,
                     handle: str) -> dict[str, Any]:
        """Rules-based buyer-intent score (0-100).

        HEURISTIC, not a prediction model: recent purchases, total spend,
        and recent activity add points. Shown with its reasons so she can
        judge it herself.
        """
        fan = self.get_fan(platform, handle)
        if not fan:
            return {"score": 0, "reasons": ["no fan record"],
                    "method": "rules-based heuristic"}
        score, reasons = 0, []
        spend = fan["total_spend"]
        if spend >= 200:
            score += 35
            reasons.append(f"high lifetime spend (${spend:.0f})")
        elif spend >= 50:
            score += 20
            reasons.append(f"moderate lifetime spend (${spend:.0f})")
        elif spend > 0:
            score += 10
            reasons.append("has purchased before")
        if fan["last_purchase_at"]:
            try:
                days = (datetime.now() - datetime.fromisoformat(
                    fan["last_purchase_at"])).days
                if days <= 7:
                    score += 20
                    reasons.append("purchased in the last 7 days")
                elif days <= 30:
                    score += 10
                    reasons.append("purchased in the last 30 days")
            except ValueError:
                pass
        if fan["last_seen"]:
            try:
                hours = (datetime.now() - datetime.fromisoformat(
                    fan["last_seen"])).total_seconds() / 3600
                if hours <= 48:
                    score += 15
                    reasons.append("active in the last 48h")
            except ValueError:
                pass
        if fan["message_count"] >= 10:
            score += 10
            reasons.append("chatty (10+ messages)")
        if "whale" in fan["tags"]:
            score += 10
            reasons.append("tagged whale")
        score = min(100, score)
        return {"score": score, "reasons": reasons,
                "method": "rules-based heuristic (not ML)"}

    # -- smart lists -------------------------------------------------------
    def smart_list(self, kind: str,
                   platform: str | None = None) -> list[dict[str, Any]]:
        """Pre-built segments. 'online' is manual: fans SHE marks online.

        Kinds: whales (spend>=200 or tag), new, active, expired, quiet
        (no activity 30d+), online (tag 'online' -- she manages it).
        """
        fans = self.list_fans(platform=platform, limit=10000)
        if kind == "whales":
            return [f for f in fans
                    if f["total_spend"] >= 200 or "whale" in f["tags"]]
        if kind == "new":
            return [f for f in fans if f["status"] == "new"]
        if kind == "active":
            return [f for f in fans if f["status"] == "active"]
        if kind == "expired":
            return [f for f in fans if f["status"] == "expired"]
        if kind == "online":
            return [f for f in fans if "online" in f["tags"]]
        if kind == "quiet":
            out = []
            for f in fans:
                try:
                    days = (datetime.now() - datetime.fromisoformat(
                        f["last_seen"])).days
                    if days >= 30:
                        out.append(f)
                except ValueError:
                    pass
            return out
        raise ValueError(
            f"Unknown smart list {kind!r}. Use whales/new/active/expired/"
            "quiet/online.")

    # -- conversation stats (her own review) -------------------------------
    def conversation_stats(self,
                           platform: str | None = None) -> list[dict[str, Any]]:
        """Per-fan reply/spend stats for HER review (chatter performance).

        Counts drafts from the chat queue file + spend from fan records.
        """
        fans = self.list_fans(platform=platform, limit=10000)
        return [{
            "platform": f["platform"],
            "handle": f["handle"],
            "messages": f["message_count"],
            "purchases": f["purchase_count"],
            "total_spend": f["total_spend"],
            "status": f["status"],
            "tags": f["tags"],
        } for f in fans]
