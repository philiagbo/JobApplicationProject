import copy
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import List

import core

DEFAULTS = {
    "career_fields": [],
    "excluded_words": [],
    "min_salary": 0,
    "location": "",
    "reed_api_key": "",
    "adzuna_app_id": "",
    "adzuna_app_key": "",
    "gmail_poll_minutes": 5,
    "api_poll_minutes": 60,
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY,
  url TEXT NOT NULL UNIQUE,
  source TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  company TEXT NOT NULL DEFAULT '',
  location TEXT NOT NULL DEFAULT '',
  salary TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  summary TEXT NOT NULL DEFAULT '{}',
  score INTEGER NOT NULL DEFAULT 0,
  pros TEXT NOT NULL DEFAULT '[]',
  cons TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'new',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  status_changed_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS answers (
  id INTEGER PRIMARY KEY,
  question TEXT NOT NULL UNIQUE,
  answer TEXT NOT NULL,
  field_type TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT 'learned',
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS unanswered (
  id INTEGER PRIMARY KEY,
  question TEXT NOT NULL UNIQUE,
  times_seen INTEGER NOT NULL DEFAULT 1,
  last_seen TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


def db_path() -> str:
    return os.environ.get("JOBHELPER_DB") or str(Path(__file__).parent / "data" / "jobhelper.db")


def connect() -> sqlite3.Connection:
    path = Path(db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(connect()) as conn:
        conn.executescript(SCHEMA)


def get_settings(conn) -> dict:
    out = copy.deepcopy(DEFAULTS)
    for row in conn.execute("SELECT key, value FROM settings"):
        if row["key"] in DEFAULTS:
            out[row["key"]] = json.loads(row["value"])
    return out


def _clean(key, value):
    default = DEFAULTS[key]
    if isinstance(default, list):
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ValueError("%s must be a list of strings" % key)
        return [v.strip() for v in value if v.strip()]
    if isinstance(default, int):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("%s must be a whole number" % key)
        floor = 0 if key == "min_salary" else 1 if key.endswith("_poll_minutes") else None
        if floor is not None and value < floor:
            raise ValueError("%s must be at least %d" % (key, floor))
        return value
    if not isinstance(value, str):
        raise ValueError("%s must be text" % key)
    return value


def save_settings(conn, changes) -> None:
    if not isinstance(changes, dict):
        raise ValueError("Settings must be a JSON object")
    for key in changes:
        if key not in DEFAULTS:
            raise ValueError("Unknown setting: %s" % key)
    changes = {k: _clean(k, v) for k, v in changes.items()}
    with conn:
        for key, value in changes.items():
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, json.dumps(value)))


def job_dict(row) -> dict:
    d = dict(row)
    for key in ("summary", "pros", "cons"):
        d[key] = json.loads(d[key])
    return d


def insert_jobs(conn, jobs: List[dict], settings: dict) -> int:
    new = 0
    with conn:
        for job in jobs:
            summary = core.summarize(job)
            total, pros, cons = core.score(dict(job, summary=summary), settings)
            cur = conn.execute(
                "INSERT OR IGNORE INTO jobs (url, source, title, company, location, salary, description,"
                " summary, score, pros, cons) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (job["url"], job["source"], job.get("title", ""), job.get("company", ""),
                 job.get("location", ""), job.get("salary", ""), job.get("description", ""),
                 json.dumps(summary), total, json.dumps(pros), json.dumps(cons)),
            )
            if cur.rowcount == 1:
                new += 1
    return new


def list_jobs(conn, status: str = "new") -> List[dict]:
    rows = conn.execute("SELECT * FROM jobs WHERE status = ? ORDER BY score DESC, id DESC", (status,))
    return [job_dict(r) for r in rows]


STATUSES = ("new", "dismissed", "queued", "filling", "ready", "needs_input", "applied", "skipped")
TRANSITIONS = {
    "dismiss": (("new",), "dismissed"),
    "queue": (("new",), "queued"),
    "undo": (("dismissed", "queued"), "new"),
}


def set_status(conn, job_id: int, action: str) -> dict:
    allowed, to = TRANSITIONS[action]
    with conn:
        cur = conn.execute(
            "UPDATE jobs SET status = ?, status_changed_at = datetime('now') WHERE id = ? AND status IN (%s)"
            % ",".join("?" * len(allowed)),
            (to, job_id) + allowed,
        )
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise KeyError(job_id)
    if cur.rowcount != 1:
        raise ValueError("Cannot %s a job that is %s" % (action, row["status"]))
    return job_dict(row)
