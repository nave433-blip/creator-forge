"""SQLite storage for custom video orders."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fan_handle TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT '',
    scene_name TEXT NOT NULL,
    scene_path TEXT NOT NULL,
    price_label TEXT NOT NULL DEFAULT '',
    price TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending_payment',
    video_job_id INTEGER,
    output_path TEXT NOT NULL DEFAULT '',
    delivery_note TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
"""

STATUSES = (
    "pending_payment", "queued", "rendering", "awaiting_review",
    "delivered", "cancelled", "refunded",
)


@dataclass
class Order:
    id: int
    fan_handle: str
    platform: str
    scene_name: str
    scene_path: str
    price_label: str
    price: str
    status: str
    video_job_id: int | None
    output_path: str
    delivery_note: str
    created: str
    updated: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "fan_handle": self.fan_handle,
            "platform": self.platform, "scene_name": self.scene_name,
            "scene_path": self.scene_path, "price_label": self.price_label,
            "price": self.price, "status": self.status,
            "video_job_id": self.video_job_id,
            "output_path": self.output_path,
            "delivery_note": self.delivery_note,
            "created": self.created, "updated": self.updated,
        }


class OrderStore:
    """SQLite-backed order storage."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def create(self, *, fan_handle: str, platform: str = "",
               scene_name: str, scene_path: str,
               price_label: str = "", price: str = "") -> Order:
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        cur = self._conn.execute(
            "INSERT INTO orders (fan_handle, platform, scene_name,"
            " scene_path, price_label, price, status, created, updated)"
            " VALUES (?,?,?,?,?,?,'pending_payment',?,?)",
            (fan_handle, platform, scene_name, str(scene_path),
             price_label, price, now, now),
        )
        self._conn.commit()
        return self.get(cur.lastrowid)

    def get(self, order_id: int) -> Order:
        row = self._conn.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if row is None:
            raise KeyError(f"No order #{order_id}.")
        return Order(**dict(row))

    def list(self, status: str | None = None,
             limit: int = 200) -> list[Order]:
        q = "SELECT * FROM orders"
        params: tuple = ()
        if status:
            if status not in STATUSES:
                raise ValueError(f"status must be one of {STATUSES}")
            q += " WHERE status = ?"
            params = (status,)
        q += " ORDER BY id ASC LIMIT ?"
        return [Order(**dict(r))
                for r in self._conn.execute(q, params + (limit,))]

    def update(self, order_id: int, **fields: Any) -> Order:
        fields["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        cols = ", ".join(f"{k} = ?" for k in fields)
        self._conn.execute(
            f"UPDATE orders SET {cols} WHERE id = ?",
            tuple(fields.values()) + (order_id,),
        )
        self._conn.commit()
        return self.get(order_id)
