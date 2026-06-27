"""SQLite job ledger — the durable record behind the dashboard's run history.

This is the UI source of truth (status, timestamps, the run it produced), kept
separate from arq/Redis so history survives a Redis flush. SQLite in WAL mode is
safe across the FastAPI process and the arq worker process that share the file.
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Any

from src.paths import RESULTS, ensure_dir

DB_PATH = RESULTS / "jobs.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,              -- 'simulate' | 'continue'
    status      TEXT NOT NULL,              -- queued|running|done|failed|interrupted
    title       TEXT NOT NULL,
    region      TEXT, combo TEXT, label TEXT,
    config_json TEXT,                       -- RunConfig (simulate)
    extra_days  INTEGER,                    -- continue
    error       TEXT,
    created_at  REAL, started_at REAL, finished_at REAL
);
"""


@contextmanager
def _connect():
    ensure_dir(RESULTS)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as c:
        c.executescript(_SCHEMA)


def recover_stale() -> int:
    """On startup, any job left 'running' (a crashed worker) is marked
    'interrupted' so it never sticks as forever-running. Returns the count."""
    with _connect() as c:
        cur = c.execute(
            "UPDATE jobs SET status='interrupted', finished_at=? "
            "WHERE status IN ('running','queued')",
            (time.time(),),
        )
        return cur.rowcount


def create_job(kind: str, title: str, **fields: Any) -> str:
    job_id = uuid.uuid4().hex[:12]
    row = {
        "id": job_id, "kind": kind, "status": "queued", "title": title,
        "region": None, "combo": None, "label": None, "config_json": None,
        "extra_days": None, "error": None,
        "created_at": time.time(), "started_at": None, "finished_at": None,
        **fields,
    }
    cols = ",".join(row)
    marks = ",".join(["?"] * len(row))
    with _connect() as c:
        c.execute(f"INSERT INTO jobs ({cols}) VALUES ({marks})", list(row.values()))
    return job_id


def update_job(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    sets = ",".join(f"{k}=?" for k in fields)
    with _connect() as c:
        c.execute(f"UPDATE jobs SET {sets} WHERE id=?", [*fields.values(), job_id])


def mark_running(job_id: str) -> None:
    update_job(job_id, status="running", started_at=time.time())


def mark_done(job_id: str, region: str, combo: str, label: str) -> None:
    update_job(job_id, status="done", region=region, combo=combo, label=label,
               finished_at=time.time())


def mark_failed(job_id: str, error: str) -> None:
    update_job(job_id, status="failed", error=error[:2000], finished_at=time.time())


def get_job(job_id: str) -> dict | None:
    with _connect() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return dict(row) if row else None


def list_jobs(limit: int = 100) -> list[dict]:
    with _connect() as c:
        rows = c.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
