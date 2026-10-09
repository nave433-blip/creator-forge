"""Analytics: post stats + earnings, stored locally.

Honest model: CreatorForge can't see inside OnlyFans/Fansly/Snapchat --
they have no stats API we can call. So stats are entered manually (or
imported from CSV exports you download from those sites), EXCEPT Reddit,
where the official API (PRAW) can fetch real submission stats.

- ``log_post_stat``: record views/likes/comments/earnings for one post.
- ``log_earning`` / ``import_earnings_csv``: money in, per platform/month.
- ``reddit_submission_stats``: live stats for a Reddit submission id.
"""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS post_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    post_ref TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    views INTEGER NOT NULL DEFAULT 0,
    likes INTEGER NOT NULL DEFAULT 0,
    comments INTEGER NOT NULL DEFAULT 0,
    earnings REAL NOT NULL DEFAULT 0.0,
    recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS earnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    kind TEXT NOT NULL DEFAULT '',
    month TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
"""


class AnalyticsStore:
    """SQLite store for post stats and earnings."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)  # dashboard serves requests from worker threads
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- post stats ------------------------------------------------------
    def log_post_stat(self, *, platform: str, post_ref: str, title: str = "",
                      views: int = 0, likes: int = 0, comments: int = 0,
                      earnings: float = 0.0) -> dict[str, Any]:
        cur = self._conn.execute(
            "INSERT INTO post_stats (platform, post_ref, title, views, likes,"
            " comments, earnings, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
            (platform, post_ref, title, views, likes, comments, earnings,
             datetime.now().isoformat(timespec="seconds")),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT * FROM post_stats WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)

    def post_stats(self, platform: str | None = None,
                   limit: int = 200) -> list[dict[str, Any]]:
        q = "SELECT * FROM post_stats"
        params: tuple = ()
        if platform:
            q += " WHERE platform = ?"
            params = (platform,)
        q += " ORDER BY recorded_at DESC LIMIT ?"
        return [dict(r) for r in self._conn.execute(q, params + (limit,))]

    # -- earnings ----------------------------------------------------------
    def log_earning(self, *, platform: str, amount: float,
                    currency: str = "USD", kind: str = "",
                    month: str = "") -> dict[str, Any]:
        month = month or datetime.now().strftime("%Y-%m")
        cur = self._conn.execute(
            "INSERT INTO earnings (platform, amount, currency, kind, month,"
            " recorded_at) VALUES (?,?,?,?,?,?)",
            (platform, amount, currency, kind, month,
             datetime.now().isoformat(timespec="seconds")),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT * FROM earnings WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)

    def import_earnings_csv(self, csv_path: str | Path) -> int:
        """Import earnings from CSV with columns: platform,amount[,currency,kind,month]."""
        count = 0
        with open(csv_path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if not row.get("platform") or not row.get("amount"):
                    continue
                try:
                    amount = float(row["amount"])
                except ValueError:
                    continue
                self.log_earning(
                    platform=row["platform"].strip(),
                    amount=amount,
                    currency=(row.get("currency") or "USD").strip(),
                    kind=(row.get("kind") or "").strip(),
                    month=(row.get("month") or "").strip(),
                )
                count += 1
        return count

    def earnings_by_platform_month(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT platform, month, currency, SUM(amount) AS total,"
            " COUNT(*) AS entries FROM earnings"
            " GROUP BY platform, month, currency"
            " ORDER BY month DESC, total DESC"
        )
        return [dict(r) for r in rows]

    def totals(self) -> dict[str, Any]:
        """Overall totals: earnings sum, post count, avg engagement."""
        earn = self._conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS total_earn FROM earnings"
        ).fetchone()
        posts = self._conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(views),0) AS views,"
            " COALESCE(SUM(likes),0) AS likes,"
            " COALESCE(SUM(comments),0) AS comments,"
            " COALESCE(SUM(earnings),0) AS post_earn FROM post_stats"
        ).fetchone()
        return {
            "total_earnings": earn["total_earn"],
            "posts_tracked": posts["n"],
            "total_views": posts["views"],
            "total_likes": posts["likes"],
            "total_comments": posts["comments"],
            "post_earnings": posts["post_earn"],
        }


def reddit_submission_stats(config: Any, submission_id: str) -> dict[str, Any]:
    """Fetch live stats for a Reddit submission via the official API.

    Needs platforms.reddit configured (see docs/PLATFORMS.md). This is
    real data from Reddit, not an estimate.
    """
    from forge.post.reddit import RedditNotConfiguredError, reddit_client

    try:
        reddit = reddit_client(config)
    except RedditNotConfiguredError as e:
        raise RedditNotConfiguredError(str(e)) from e
    sub = reddit.submission(id=submission_id)
    # Touch attributes to force a fetch; raises if the id is bad.
    return {
        "id": sub.id,
        "title": sub.title,
        "subreddit": str(sub.subreddit),
        "score": sub.score,
        "upvote_ratio": sub.upvote_ratio,
        "num_comments": sub.num_comments,
        "views": getattr(sub, "view_count", None),
        "url": f"https://reddit.com{sub.permalink}",
    }
