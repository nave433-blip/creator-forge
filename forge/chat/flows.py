"""Welcome / win-back / online-nudge message flows.

A flow is an ordered list of steps: [{delay_hours, template}]. When a
flow is enrolled for a fan, each step becomes DUE after its delay; `forge
chat flows run` drafts due steps into the approval queue (personalized
with {handle}/{first}).

Nothing is ever auto-sent: drafts sit pending until she approves, under
the same rule as the rest of the chat engine (auto mode is an explicit
per-conversation opt-in). State lives in SQLite so runs survive
restarts.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS flow_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow TEXT NOT NULL,
    platform TEXT NOT NULL,
    handle TEXT NOT NULL,
    step_idx INTEGER NOT NULL DEFAULT 0,
    enrolled_at TEXT NOT NULL,
    due_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    UNIQUE(flow, platform, handle)
);
"""

BUILTIN_FLOWS: dict[str, list[dict[str, Any]]] = {
    "welcome": [
        {"delay_hours": 0,
         "template": "Hey {first}!! thanks for subscribing, I'm so glad "
                     "you're here"},
        {"delay_hours": 24,
         "template": "Hey {first}, just checking in -- my tip menu is "
                     "pinned if you wanna see what I offer"},
        {"delay_hours": 72,
         "template": "{first} I just dropped something new, lmk if you "
                     "want a sneak peek"},
    ],
    "winback": [
        {"delay_hours": 0,
         "template": "Miss you {first}!! come back and I'll make it worth "
                     "it"},
        {"delay_hours": 168,
         "template": "{first}, last chance -- I've got something with "
                     "your name on it"},
    ],
    "nudge": [
        {"delay_hours": 0,
         "template": "Hey {first}, I see you -- say hi so I know you're "
                     "really there"},
    ],
}


def _now() -> datetime:
    return datetime.now()


class FlowRunner:
    """Enroll fans in flows; draft due steps into the approval queue."""

    def __init__(self, db_path: str | Path,
                 flows: dict[str, list[dict[str, Any]]] | None = None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.flows = flows or BUILTIN_FLOWS
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def enroll(self, flow: str, platform: str,
               handle: str) -> dict[str, Any]:
        """Enroll a fan in a flow. Step 0 becomes due immediately."""
        if flow not in self.flows:
            raise ValueError(
                f"Unknown flow {flow!r}. Available: "
                + ", ".join(sorted(self.flows)))
        now = _now()
        try:
            self._conn.execute(
                "INSERT INTO flow_runs (flow, platform, handle, step_idx,"
                " enrolled_at, due_at, status) VALUES (?,?,?,?,?,?,?)",
                (flow, platform.strip(), handle.strip(), 0,
                 now.isoformat(timespec="seconds"),
                 now.isoformat(timespec="seconds"), "active"))
            self._conn.commit()
        except sqlite3.IntegrityError:
            pass  # already enrolled
        return {"flow": flow, "platform": platform, "handle": handle,
                "status": "enrolled"}

    def cancel(self, flow: str, platform: str, handle: str) -> None:
        self._conn.execute(
            "UPDATE flow_runs SET status = 'cancelled'"
            " WHERE flow = ? AND platform = ? AND handle = ?",
            (flow, platform.strip(), handle.strip()))
        self._conn.commit()

    def due_steps(self) -> list[dict[str, Any]]:
        """Steps whose due_at has passed and are still active."""
        rows = self._conn.execute(
            "SELECT * FROM flow_runs WHERE status = 'active'"
            " AND due_at <= ?",
            (_now().isoformat(timespec="seconds"),)).fetchall()
        return [dict(r) for r in rows]

    def pending(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM flow_runs WHERE status = 'active'"
            " ORDER BY due_at").fetchall()
        return [dict(r) for r in rows]

    def advance(self, run_id: int) -> dict[str, Any] | None:
        """Move a run to its next step; returns the next step or None.

        Returns None when the flow is finished (marks it done).
        """
        row = self._conn.execute(
            "SELECT * FROM flow_runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        steps = self.flows[row["flow"]]
        nxt = row["step_idx"] + 1
        if nxt >= len(steps):
            self._conn.execute(
                "UPDATE flow_runs SET status = 'done' WHERE id = ?",
                (run_id,))
            self._conn.commit()
            return None
        due = _now() + timedelta(
            hours=float(steps[nxt].get("delay_hours", 0)))
        self._conn.execute(
            "UPDATE flow_runs SET step_idx = ?, due_at = ? WHERE id = ?",
            (nxt, due.isoformat(timespec="seconds"), run_id))
        self._conn.commit()
        step = dict(steps[nxt])
        step["run_id"] = run_id
        step["handle"] = row["handle"]
        step["platform"] = row["platform"]
        step["step_idx"] = nxt
        return step

    def current_step(self, run: dict[str, Any]) -> dict[str, Any]:
        step = dict(self.flows[run["flow"]][run["step_idx"]])
        step.update({"run_id": run["id"], "handle": run["handle"],
                     "platform": run["platform"],
                     "step_idx": run["step_idx"]})
        return step

    def render(self, template: str, handle: str) -> str:
        first = handle.split()[0]
        return template.replace("{handle}", handle).replace("{first}",
                                                           first)


def run_due(runner: FlowRunner, engine: Any) -> list[Any]:
    """Draft every due flow step into the engine's approval queue.

    Returns the drafts created. Each draft's trigger is tagged
    "flow:<name>" so she can see where it came from.
    """
    drafts = []
    for run in runner.due_steps():
        step = runner.current_step(run)
        text = runner.render(step["template"], run["handle"])
        draft = engine.queue.add(platform=run["platform"],
                                 sender=run["handle"],
                                 incoming=f"[flow:{run['flow']} step "
                                          f"{run['step_idx'] + 1}]",
                                 reply=text,
                                 trigger=f"flow:{run['flow']}")
        drafts.append(draft)
        runner.advance(run["id"])
    return drafts
