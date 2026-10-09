"""SQLite-backed catalog store for CreatorForge media items."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    sha256 TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,            -- 'image' | 'video'
    mime TEXT,
    width INTEGER,
    height INTEGER,
    duration REAL,                 -- seconds, video only, may be NULL
    tags TEXT NOT NULL DEFAULT '[]',  -- JSON array
    notes TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_kind ON items(kind);
CREATE INDEX IF NOT EXISTS idx_items_sha ON items(sha256);
"""


class CatalogStore:
    """Thin CRUD wrapper around a SQLite catalog database."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- writes -----------------------------------------------------------
    def add_item(
        self,
        *,
        path: str,
        sha256: str,
        kind: str,
        mime: str = "",
        width: int | None = None,
        height: int | None = None,
        duration: float | None = None,
        tags: list[str] | None = None,
        notes: str = "",
    ) -> int:
        cur = self._conn.execute(
            """INSERT OR IGNORE INTO items
               (path, sha256, kind, mime, width, height, duration, tags, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (path, sha256, kind, mime, width, height, duration,
             json.dumps(tags or []), notes, time.time()),
        )
        self._conn.commit()
        if cur.lastrowid:
            return cur.lastrowid
        row = self.find_by_hash(sha256)
        assert row is not None
        return row["id"]

    def tag_item(self, item_id: int, tags: list[str]) -> None:
        row = self.get(item_id)
        existing = set(json.loads(row["tags"]))
        merged = sorted(existing | set(tags))
        self._conn.execute("UPDATE items SET tags = ? WHERE id = ?",
                           (json.dumps(merged), item_id))
        self._conn.commit()

    def delete_item(self, item_id: int) -> None:
        self._conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        self._conn.commit()

    # -- reads ------------------------------------------------------------
    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["tags"] = json.loads(d["tags"])
        return d

    def get(self, item_id: int) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            raise KeyError(f"No catalog item with id {item_id}")
        return self._row_to_dict(row)

    def find_by_hash(self, sha256: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM items WHERE sha256 = ?", (sha256,)).fetchone()
        return self._row_to_dict(row) if row else None

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]

    def list(self, kind: str | None = None, limit: int = 200,
             offset: int = 0) -> list[dict[str, Any]]:
        if kind:
            rows = self._conn.execute(
                "SELECT * FROM items WHERE kind = ? ORDER BY id LIMIT ? OFFSET ?",
                (kind, limit, offset)).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM items ORDER BY id LIMIT ? OFFSET ?",
                (limit, offset)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def search(self, query: str, limit: int = 200) -> list[dict[str, Any]]:
        """Substring search over path, notes, and tags."""
        like = f"%{query}%"
        rows = self._conn.execute(
            """SELECT * FROM items
               WHERE path LIKE ? OR notes LIKE ? OR tags LIKE ?
               ORDER BY id LIMIT ?""",
            (like, like, like, limit)).fetchall()
        return [self._row_to_dict(r) for r in rows]
