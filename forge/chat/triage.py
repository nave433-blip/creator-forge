"""Incoming media triage: pre-screening assistance for fan-sent pics.

Honest scope, stated up front: this module queues incoming media with
BLURRED thumbnails for HER one-tap approve/skip review, and can draft an
auto-reply ("got it babe, checking it out") into the approval queue. It
does NOT do magic AI vision and does NOT auto-judge content.

An optional NSFW classifier adapter interface is provided so she can
plug one in later (see :class:`NSFWClassifier`). With no classifier
configured -- the default -- every item is manual review.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS triage_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    sender TEXT NOT NULL,
    media_path TEXT NOT NULL,
    thumb_path TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    nsfw_label TEXT NOT NULL DEFAULT 'unknown',
    nsfw_score REAL NOT NULL DEFAULT 0.0,
    note TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL
);
"""

STATUSES = ("pending", "approved", "skipped")


@dataclass
class TriageItem:
    id: int
    platform: str
    sender: str
    media_path: str
    thumb_path: str
    status: str
    nsfw_label: str
    nsfw_score: float
    note: str
    created: str


def make_blurred_thumbnail(src: str | Path, dst: str | Path,
                            size: tuple[int, int] = (320, 320)) -> Path:
    """Write a heavily blurred thumbnail of an image.

    Falls back to a neutral gray placeholder when Pillow is missing or
    the file can't be read -- never crashes triage.
    """
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageFilter
        img = Image.open(src).convert("RGB")
        img.thumbnail(size)
        blurred = img.filter(ImageFilter.GaussianBlur(radius=28))
        # extra pixelation pass so nothing recognizable remains
        small = blurred.resize((16, 16), Image.BILINEAR)
        pix = small.resize(blurred.size, Image.NEAREST)
        pix.save(dst, "JPEG", quality=60)
    except Exception:
        try:
            from PIL import Image
            Image.new("RGB", size, (40, 40, 46)).save(dst, "JPEG")
        except Exception:
            dst.write_bytes(b"")
    return dst


# -- NSFW classifier adapter interface ---------------------------------------

class NSFWClassifier:
    """Optional plug-in: label incoming media before she reviews it.

    Implement :meth:`classify` and register the instance with
    :func:`register_classifier`. The default (and only built-in) is
    :class:`NullNSFWClassifier`, which labels everything "unknown" and
    defers to manual review. Docs (docs/SPICY.md) explain how to wire a
    real model later.
    """

    name = "none"

    def classify(self, media_path: str | Path) -> dict[str, Any]:
        """Return {"label": str, "score": float 0..1, "note": str}."""
        raise NotImplementedError


class NullNSFWClassifier(NSFWClassifier):
    """No classifier configured: everything is manual review."""

    name = "none"

    def classify(self, media_path: str | Path) -> dict[str, Any]:
        return {"label": "unknown", "score": 0.0,
                "note": "No NSFW classifier configured -- manual review."}


_CLASSIFIERS: dict[str, NSFWClassifier] = {"none": NullNSFWClassifier()}


def register_classifier(classifier: NSFWClassifier) -> None:
    _CLASSIFIERS[classifier.name] = classifier


def get_classifier(name: str = "none") -> NSFWClassifier:
    try:
        return _CLASSIFIERS[name]
    except KeyError:
        raise KeyError(f"Unknown NSFW classifier {name!r}. "
                       f"Known: {sorted(_CLASSIFIERS)}")


# -- triage queue --------------------------------------------------------------

class TriageQueue:
    """SQLite-backed queue of incoming media awaiting her review."""

    def __init__(self, db_path: str | Path,
                 thumbs_dir: str | Path = "./forge-data/triage-thumbs",
                 classifier: NSFWClassifier | None = None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.thumbs_dir = Path(thumbs_dir)
        self.thumbs_dir.mkdir(parents=True, exist_ok=True)
        self.classifier = classifier or NullNSFWClassifier()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)  # dashboard serves requests from worker threads
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def add(self, *, platform: str, sender: str, media_path: str,
            note: str = "") -> TriageItem:
        thumb = self.thumbs_dir / f"triage-{int(time.time()*1000)}.jpg"
        make_blurred_thumbnail(media_path, thumb)
        try:
            verdict = self.classifier.classify(media_path)
            label = str(verdict.get("label", "unknown"))
            score = float(verdict.get("score", 0.0))
        except Exception:
            label, score = "unknown", 0.0
        cur = self._conn.execute(
            "INSERT INTO triage_items (platform, sender, media_path,"
            " thumb_path, nsfw_label, nsfw_score, note, created)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (platform, sender, str(media_path), str(thumb), label, score,
             note, time.strftime("%Y-%m-%dT%H:%M:%S")),
        )
        self._conn.commit()
        return self.get(cur.lastrowid)

    def get(self, item_id: int) -> TriageItem:
        row = self._conn.execute(
            "SELECT * FROM triage_items WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            raise KeyError(f"No triage item #{item_id}.")
        return TriageItem(**dict(row))

    def list(self, status: str | None = None,
             limit: int = 200) -> list[TriageItem]:
        q = "SELECT * FROM triage_items"
        params: tuple = ()
        if status:
            if status not in STATUSES:
                raise ValueError(f"status must be one of {STATUSES}")
            q += " WHERE status = ?"
            params = (status,)
        q += " ORDER BY id ASC LIMIT ?"
        return [TriageItem(**dict(r))
                for r in self._conn.execute(q, params + (limit,))]

    def _set_status(self, item_id: int, status: str) -> TriageItem:
        self._conn.execute(
            "UPDATE triage_items SET status = ? WHERE id = ?",
            (status, item_id))
        self._conn.commit()
        return self.get(item_id)

    def approve(self, item_id: int) -> TriageItem:
        """She looked (at the blurred thumb or the real thing) and it's fine."""
        return self._set_status(item_id, "approved")

    def skip(self, item_id: int) -> TriageItem:
        """She doesn't want to deal with this one."""
        return self._set_status(item_id, "skipped")


def triage_auto_reply_text(config: Any) -> str:
    """Configurable 'got your pic' reply, drafted into the approval queue
    (never auto-sent)."""
    try:
        text = config.get_path("chat.triage.auto_reply", "")
    except Exception:
        text = ""
    return text or "Got your pic babe, let me take a look 👀"
