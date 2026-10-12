"""Affiliate / promo-link tracking for shoutouts and collabs.

Honest scope: a self-hosted tool cannot see clicks on someone else's
platform. What it CAN do:

- generate UTM-tagged links per campaign (``link-create``) so traffic is
  attributable in the platform's own analytics,
- store every link with a short reference code,
- let her log earnings she attributes to a campaign (manual entry from
  the platform's payout reports -- the only honest source),
- report per-campaign totals so she knows which shoutouts paid off.

No URL-shortener service is bundled (that needs hosted redirect
infrastructure); the tagged URL itself is the deliverable.
"""

from __future__ import annotations

import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_SCHEMA = """
CREATE TABLE IF NOT EXISTS promo_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    base_url TEXT NOT NULL,
    full_url TEXT NOT NULL,
    campaign TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    medium TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS promo_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id INTEGER NOT NULL REFERENCES promo_links(id),
    amount REAL NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    logged_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_promo_campaign ON promo_links(campaign);
CREATE TABLE IF NOT EXISTS promo_clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id INTEGER NOT NULL REFERENCES promo_links(id),
    clicked_at REAL NOT NULL,
    user_agent TEXT NOT NULL DEFAULT '',
    referrer TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_promo_clicks_link ON promo_clicks(link_id);
"""


def tag_url(base_url: str, *, campaign: str, source: str = "",
            medium: str = "shoutout") -> str:
    """Append UTM params to a URL, preserving existing query params."""
    parsed = urlparse(base_url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(
            f"Bad URL {base_url!r}: must start with http:// or https://")
    if not campaign.strip():
        raise ValueError("campaign must not be empty")
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params["utm_source"] = source or "creatorforge"
    params["utm_medium"] = medium
    params["utm_campaign"] = campaign.strip()
    return urlunparse(parsed._replace(query=urlencode(params)))


class PromoTracker:
    """SQLite-backed promo link + earnings attribution store."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_path),
                                     check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def create_link(self, base_url: str, campaign: str, source: str = "",
                    medium: str = "shoutout",
                    notes: str = "") -> dict[str, Any]:
        """Generate a UTM-tagged link and store it. Returns the row."""
        full_url = tag_url(base_url, campaign=campaign, source=source,
                           medium=medium)
        with self._lock:
            for _ in range(10):  # code collision retry (paranoia)
                code = secrets.token_hex(3).upper()
                try:
                    cur = self._conn.execute(
                        "INSERT INTO promo_links (code, base_url, full_url,"
                        " campaign, source, medium, notes, created_at)"
                        " VALUES (?,?,?,?,?,?,?,?)",
                        (code, base_url.strip(), full_url, campaign.strip(),
                         source, medium, notes, time.time()))
                    self._conn.commit()
                    return self.get(cur.lastrowid)
                except sqlite3.IntegrityError:
                    continue
            raise RuntimeError("Could not generate a unique promo code.")

    def get(self, link_id: int) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM promo_links WHERE id = ?", (link_id,)).fetchone()
            if row is None:
                raise KeyError(f"No promo link #{link_id}.")
            return dict(row)

    def get_by_code(self, code: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM promo_links WHERE code = ?",
                (code.strip().upper(),)).fetchone()
            if row is None:
                raise KeyError(f"No promo link with code {code!r}.")
            return dict(row)

    def list_links(self, campaign: str | None = None,
                   limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            if campaign:
                rows = self._conn.execute(
                    "SELECT * FROM promo_links WHERE campaign = ?"
                    " ORDER BY id DESC LIMIT ?", (campaign, limit)).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM promo_links ORDER BY id DESC LIMIT ?",
                    (limit,)).fetchall()
            return [dict(r) for r in rows]

    def log_earning(self, code: str, amount: float,
                    note: str = "") -> dict[str, Any]:
        """Attribute earnings to a promo link (manual entry from the
        platform's payout reports -- the only honest source)."""
        try:
            amount = float(amount)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Bad amount {amount!r}: must be a number.") from e
        if amount < 0:
            raise ValueError("amount must not be negative")
        link = self.get_by_code(code)
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO promo_results (link_id, amount, note, logged_at)"
                " VALUES (?,?,?,?)",
                (link["id"], amount, note, time.time()))
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM promo_results WHERE id = ?",
                (cur.lastrowid,)).fetchone()
            return dict(row)

    def report(self) -> list[dict[str, Any]]:
        """Per-campaign totals: links, clicks, attributed earnings."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT l.campaign AS campaign,
                          COUNT(DISTINCT l.id) AS links,
                          COALESCE(SUM(r.amount), 0) AS earnings,
                          (SELECT COUNT(*) FROM promo_clicks c
                           JOIN promo_links l2 ON l2.id = c.link_id
                           WHERE l2.campaign = l.campaign) AS clicks
                   FROM promo_links l
                   LEFT JOIN promo_results r ON r.link_id = l.id
                   GROUP BY l.campaign
                   ORDER BY earnings DESC""").fetchall()
            return [dict(r) for r in rows]

    def log_click(self, code: str, user_agent: str = "",
                  referrer: str = "") -> dict[str, Any]:
        """Record one click-through on a short link.

        Honest scope: this only counts clicks that come through HER OWN
        short links (``/promo/go/<code>`` on a dashboard that is reachable
        from the internet). It cannot see clicks on the raw UTM URL. Counts
        are raw hits, not deduplicated uniques -- bots and double-taps
        count.
        """
        link = self.get_by_code(code)
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO promo_clicks (link_id, clicked_at, user_agent,"
                " referrer) VALUES (?,?,?,?)",
                (link["id"], time.time(), user_agent or "",
                 referrer or ""))
            self._conn.commit()
            return {"code": link["code"], "link_id": link["id"],
                    "click_id": cur.lastrowid}

    def click_count(self, code: str) -> int:
        """Raw hit count for one link's short code."""
        link = self.get_by_code(code)
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM promo_clicks WHERE link_id = ?",
                (link["id"],)).fetchone()
            return int(row["n"])
