"""Video batch queue: queue up generations, run them one by one.

Each job goes through the SAME consent-gated pipeline as a single
generation (``forge.video.pipeline.generate_video``) -- the queue adds
no bypass. After a job succeeds, an optional post-processing step runs
skills (watermark, aspect-ratio) per ``video.postprocess`` config, and
finished outputs are imported back into the catalog tagged
``ai_generated`` so she can find them later.

A job whose backend isn't configured (or whose consent fails) is marked
``failed`` with the honest error -- never faked.
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from forge.config import ForgeConfig

_SCHEMA = """
CREATE TABLE IF NOT EXISTS video_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt TEXT NOT NULL,
    negative_prompt TEXT NOT NULL DEFAULT '',
    adapter TEXT NOT NULL DEFAULT '',
    pack_path TEXT NOT NULL,
    duration_s INTEGER NOT NULL DEFAULT 5,
    status TEXT NOT NULL DEFAULT 'queued',
    outputs TEXT NOT NULL DEFAULT '[]',
    error TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL,
    finished_at TEXT
);
"""

STATUSES = ("queued", "running", "done", "failed")


class VideoQueue:
    """SQLite-backed batch queue for video generation jobs."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)  # dashboard serves requests from worker threads
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def add(self, *, prompt: str, pack_path: str, negative_prompt: str = "",
            adapter: str = "", duration_s: int = 5) -> dict[str, Any]:
        cur = self._conn.execute(
            "INSERT INTO video_jobs (prompt, negative_prompt, adapter,"
            " pack_path, duration_s, created) VALUES (?,?,?,?,?,?)",
            (prompt, negative_prompt, adapter, pack_path, duration_s,
             datetime.now().isoformat(timespec="seconds")),
        )
        self._conn.commit()
        return self.get(cur.lastrowid)

    def get(self, job_id: int) -> dict[str, Any]:
        import json
        row = self._conn.execute(
            "SELECT * FROM video_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"No video job #{job_id}.")
        d = dict(row)
        d["outputs"] = json.loads(d["outputs"] or "[]")
        return d

    def list(self, status: str | None = None,
             limit: int = 200) -> list[dict[str, Any]]:
        import json
        q = "SELECT * FROM video_jobs"
        params: tuple = ()
        if status:
            if status not in STATUSES:
                raise ValueError(f"status must be one of {STATUSES}")
            q += " WHERE status = ?"
            params = (status,)
        q += " ORDER BY id ASC LIMIT ?"
        rows = []
        for r in self._conn.execute(q, params + (limit,)):
            d = dict(r)
            d["outputs"] = json.loads(d["outputs"] or "[]")
            rows.append(d)
        return rows

    def _set(self, job_id: int, **fields: Any) -> None:
        import json
        if "outputs" in fields:
            fields["outputs"] = json.dumps(fields["outputs"])
        cols = ", ".join(f"{k} = ?" for k in fields)
        self._conn.execute(
            f"UPDATE video_jobs SET {cols} WHERE id = ?",
            tuple(fields.values()) + (job_id,),
        )
        self._conn.commit()

    def run_next(self, config: ForgeConfig) -> dict[str, Any] | None:
        """Run the oldest queued job. Returns the finished job dict."""
        from forge.video.pipeline import ConsentGateError, generate_video
        from forge.video.adapters import NotConfiguredError

        row = self._conn.execute(
            "SELECT * FROM video_jobs WHERE status = 'queued'"
            " ORDER BY id ASC LIMIT 1").fetchone()
        if row is None:
            return None
        job_id = row["id"]
        self._set(job_id, status="running")
        try:
            result = generate_video(
                config=config,
                identity_pack_path=row["pack_path"],
                prompt=row["prompt"],
                negative_prompt=row["negative_prompt"],
                adapter_name=row["adapter"] or None,
                duration_s=row["duration_s"],
            )
            outputs = postprocess_outputs(config, result.outputs,
                                          job_id=job_id)
            import_outputs_to_catalog(config, outputs,
                                      prompt=row["prompt"],
                                      identity=row["pack_path"])
            self._set(job_id, status="done", outputs=outputs,
                      finished_at=datetime.now().isoformat(timespec="seconds"))
        except (ConsentGateError, NotConfiguredError,
                FileNotFoundError, ValueError) as e:
            # Honest failure: the exact reason, no fake output.
            self._set(job_id, status="failed", error=str(e),
                      finished_at=datetime.now().isoformat(timespec="seconds"))
        except Exception as e:  # pragma: no cover - safety net
            self._set(job_id, status="failed",
                      error=f"Unexpected error: {e}",
                      finished_at=datetime.now().isoformat(timespec="seconds"))
        return self.get(job_id)

    def run_all(self, config: ForgeConfig,
                delay_s: float = 0) -> list[dict[str, Any]]:
        """Run every queued job sequentially. Returns finished jobs."""
        done = []
        while True:
            job = self.run_next(config)
            if job is None:
                break
            done.append(job)
            if delay_s:
                time.sleep(delay_s)
        return done


def postprocess_outputs(config: ForgeConfig, outputs: list[str],
                        job_id: int = 0) -> list[str]:
    """Run ``video.postprocess`` skills over finished outputs.

    Config example::

        video:
          postprocess:
            - watermark --text "@herhandle"
            - aspect --ratio 9:16

    Each entry is "<skill-name> <extra args...>". The skill receives the
    input path and a derived output path (``<stem>.post<N><ext>``).
    Skills that fail are skipped with a printed warning -- the original
    output is kept either way.
    """
    from forge.skills import run_skill, SkillError

    steps: list[str] = config.get_path("video.postprocess", []) or []
    if not steps:
        return list(outputs)
    final: list[str] = []
    for out in outputs:
        current = out
        for i, step in enumerate(steps):
            parts = step.split()
            if not parts:
                continue
            name, extra = parts[0], parts[1:]
            src = Path(current)
            dst = src.with_name(f"{src.stem}.post{i}{src.suffix}")
            try:
                msg = run_skill(name, extra + [str(src), str(dst)], config)
                print(f"[postprocess] {msg}")
                current = str(dst)
            except SkillError as e:
                print(f"[postprocess] WARNING: skill {name!r} skipped: {e}")
        final.append(current)
    return final


def import_outputs_to_catalog(config: ForgeConfig, outputs: list[str],
                              prompt: str = "",
                              identity: str = "") -> int:
    """Import finished outputs into the catalog with the ai_generated tag.

    Returns the number of items added (dedupes by hash like a scan).
    """
    from forge.catalog.scanner import scan_one_file
    from forge.catalog.store import CatalogStore

    store = CatalogStore(config.get_path("catalog.db_path",
                                         "./forge-data/catalog.db"))
    added = 0
    try:
        for out in outputs:
            p = Path(out)
            if not p.is_file():
                continue
            if scan_one_file(p, store,
                             tags=["ai_generated"],
                             notes=f"AI-generated via CreatorForge. "
                                   f"Prompt: {prompt[:200]}") is not None:
                added += 1
    finally:
        store.close()
    return added
