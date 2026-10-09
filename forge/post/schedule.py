"""Posting scheduler + content calendar.

Honest model: for platforms with no posting API (Snapchat, OnlyFans,
TikTok, Fansly), CreatorForge cannot post for you. What it CAN do is
remember what is due when, and remind you. ``schedule_packet`` records
a manual-assist packet (built by ``forge post packet``) with a due
time; ``due_packets`` lists everything whose time has come; the
dashboard surfaces due items as reminders.

Times are ISO-8601 strings, e.g. "2026-10-10T19:00:00". Naive times are
treated as local time.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scheduled_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    packet_dir TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    scheduled_for TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    notes TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL,
    done_at TEXT
);
"""


def _parse_when(value: str) -> datetime:
    """Parse an ISO-8601 time; date-only becomes 09:00 local."""
    v = value.strip()
    try:
        dt = datetime.fromisoformat(v)
    except ValueError as e:
        raise ValueError(
            f"Bad time {value!r}: use ISO-8601 like '2026-10-10T19:00' "
            f"or '2026-10-10'.") from e
    if len(v) == 10:  # date only
        dt = dt.replace(hour=9, minute=0)
    return dt


class Scheduler:
    """SQLite-backed schedule of posting packets."""

    STATUSES = ("scheduled", "done", "skipped")

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def schedule_packet(self, *, platform: str, packet_dir: str | Path,
                        scheduled_for: str, title: str = "",
                        notes: str = "") -> dict[str, Any]:
        """Schedule a packet dir for a future time. Returns the row."""
        when = _parse_when(scheduled_for)
        cur = self._conn.execute(
            "INSERT INTO scheduled_posts (platform, packet_dir, title,"
            " scheduled_for, notes, created) VALUES (?,?,?,?,?,?)",
            (platform, str(packet_dir), title, when.isoformat(timespec="seconds"),
             notes, datetime.now().isoformat(timespec="seconds")),
        )
        self._conn.commit()
        return self.get(cur.lastrowid)

    def get(self, post_id: int) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM scheduled_posts WHERE id = ?", (post_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"No scheduled post #{post_id}.")
        return dict(row)

    def list(self, status: str | None = None,
             limit: int = 200) -> list[dict[str, Any]]:
        if status and status not in self.STATUSES:
            raise ValueError(f"status must be one of {self.STATUSES}")
        q = "SELECT * FROM scheduled_posts"
        params: tuple = ()
        if status:
            q += " WHERE status = ?"
            params = (status,)
        q += " ORDER BY scheduled_for ASC LIMIT ?"
        return [dict(r) for r in self._conn.execute(q, params + (limit,))]

    def due(self, now: datetime | None = None,
            limit: int = 200) -> list[dict[str, Any]]:
        """Scheduled posts whose time has come and aren't done/skipped."""
        now = now or datetime.now()
        rows = self._conn.execute(
            "SELECT * FROM scheduled_posts WHERE status = 'scheduled'"
            " AND scheduled_for <= ? ORDER BY scheduled_for ASC LIMIT ?",
            (now.isoformat(timespec="seconds"), limit),
        )
        return [dict(r) for r in rows]

    def upcoming(self, limit: int = 50) -> list[dict[str, Any]]:
        """Future scheduled posts (not yet due)."""
        now = datetime.now().isoformat(timespec="seconds")
        rows = self._conn.execute(
            "SELECT * FROM scheduled_posts WHERE status = 'scheduled'"
            " AND scheduled_for > ? ORDER BY scheduled_for ASC LIMIT ?",
            (now, limit),
        )
        return [dict(r) for r in rows]

    def mark(self, post_id: int, status: str) -> dict[str, Any]:
        """Mark a post done/skipped/scheduled again."""
        if status not in self.STATUSES:
            raise ValueError(f"status must be one of {self.STATUSES}")
        done_at = (datetime.now().isoformat(timespec="seconds")
                   if status in ("done", "skipped") else None)
        cur = self._conn.execute(
            "UPDATE scheduled_posts SET status = ?, done_at = ? WHERE id = ?",
            (status, done_at, post_id),
        )
        if cur.rowcount == 0:
            raise KeyError(f"No scheduled post #{post_id}.")
        self._conn.commit()
        return self.get(post_id)

    def delete(self, post_id: int) -> None:
        cur = self._conn.execute(
            "DELETE FROM scheduled_posts WHERE id = ?", (post_id,))
        if cur.rowcount == 0:
            raise KeyError(f"No scheduled post #{post_id}.")
        self._conn.commit()
