import copy
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import List, Optional, Tuple

import core

DEFAULTS = {
    "career_fields": [],
    "known_skills": [],
    "excluded_words": [],
    "min_salary": 0,
    "location": "",
    "reed_api_key": "",
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
        seed_answers(conn)


def get_settings(conn) -> dict:
    out = copy.deepcopy(DEFAULTS)
    for row in conn.execute("SELECT key, value FROM settings"):
        if row["key"] in DEFAULTS:
            out[row["key"]] = json.loads(row["value"])
    return out


def _clean(key, value, defaults=DEFAULTS):
    default = defaults[key]
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
    return value.strip()  # a pasted API key often carries a trailing space or newline


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


def stats(conn) -> dict:
    # ponytail: counts use current status, so a queued job that later moves on stops counting as queued;
    # an events table would track history if the dashboard needs it.
    def metric(where, column):
        rows = conn.execute(
            "SELECT source, COUNT(*) FROM jobs WHERE %s AND %s >= datetime('now', '-7 days') GROUP BY source"
            % (where, column)
        )
        by_source = {r[0]: r[1] for r in rows}
        return {"total": sum(by_source.values()), "by_source": by_source}

    out = {"days": 7, "found": metric("1", "created_at")}
    for status in ("queued", "dismissed", "applied"):
        out[status] = metric("status = '%s'" % status, "status_changed_at")
    return out


def rescore_new(conn, settings: dict) -> None:
    with conn:
        for row in conn.execute("SELECT * FROM jobs WHERE status = 'new'").fetchall():
            total, pros, cons = core.score(job_dict(row), settings)
            conn.execute("UPDATE jobs SET score = ?, pros = ?, cons = ? WHERE id = ?",
                         (total, json.dumps(pros), json.dumps(cons), row["id"]))


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


# --- saved answers ----------------------------------------------------------

_OPT_OUT = "Prefer not to say"
# Wording is a guess at common ATS phrasing so fuzzy hits are likelier (RESEARCH Pattern 9); empty = person fills in.
SEED_QUESTIONS = [
    ("What is your address?", ""),
    ("Do you have the right to work in the UK?", ""),
    ("Do you require visa sponsorship?", ""),
    ("What is your notice period?", ""),
    ("When can you start?", ""),
    ("What are your salary expectations?", ""),
    ("Are you willing to relocate?", ""),
    ("Do you have a full UK driving licence?", ""),
    ("What is your highest qualification?", ""),
    ("Portfolio or website URL", ""),
    ("How did you hear about this job?", ""),
    ("What is your gender?", _OPT_OUT),
    ("What is your ethnicity?", _OPT_OUT),
    ("Do you have a disability?", _OPT_OUT),
    ("What is your sexual orientation?", _OPT_OUT),
    ("What is your religion or belief?", _OPT_OUT),
]  # type: List[Tuple[str, str]]


def seed_answers(conn) -> None:
    with conn:  # OR IGNORE on the UNIQUE question: seeding never overwrites what the person typed
        conn.executemany("INSERT OR IGNORE INTO answers (question, answer, source) VALUES (?, ?, 'profile')",
                         [(core.normalise(q), a) for q, a in SEED_QUESTIONS])


def list_answers(conn) -> List[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM answers ORDER BY id")]


def check_answer_body(body, partial: bool) -> dict:
    if not isinstance(body, dict):
        raise ValueError("Answer must be a JSON object")
    for key, value in body.items():
        if key not in ("question", "answer", "field_type", "company"):
            raise ValueError("Unknown answer field: %s" % key)
        if not isinstance(value, str):
            raise ValueError("%s must be text" % key)
    if not partial:
        for key in ("question", "answer"):
            if key not in body:
                raise ValueError("%s is required" % key)
    return body


def _check_question(question: str) -> str:
    q = core.normalise(question)
    if not q:
        raise ValueError("question is required")
    if len(q) > core.MAX_QUESTION_CHARS:
        raise ValueError("question is longer than %d characters" % core.MAX_QUESTION_CHARS)
    return q


def save_answer(conn, question: str, answer: str, field_type: str = "", source: str = "learned",
                company: str = "") -> Tuple[dict, bool]:
    q = _check_question(question)
    if (reason := core.answer_block_reason(question, answer, company)):
        raise ValueError("Not saved: " + reason)
    with conn:
        existed = conn.execute("SELECT 1 FROM answers WHERE question = ?", (q,)).fetchone() is not None
        # one statement, so two simultaneous saves of a question cannot make two rows; last write wins
        conn.execute(
            "INSERT INTO answers (question, answer, field_type, source) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(question) DO UPDATE SET answer = excluded.answer,"
            " field_type = COALESCE(NULLIF(excluded.field_type, ''), answers.field_type),"
            " updated_at = datetime('now')",
            (q, answer.strip(), field_type, source))
        conn.execute("DELETE FROM unanswered WHERE question = ?", (q,))
        row = conn.execute("SELECT * FROM answers WHERE question = ?", (q,)).fetchone()
    return dict(row), not existed


def update_answer(conn, answer_id: int, changes: dict) -> dict:
    if not any(k in changes for k in ("question", "answer", "field_type")):
        raise ValueError("Nothing to change")
    row = conn.execute("SELECT * FROM answers WHERE id = ?", (answer_id,)).fetchone()
    if row is None:
        raise KeyError(answer_id)
    question = changes.get("question", row["question"])
    answer = changes.get("answer", row["answer"])
    q = _check_question(question)
    if (reason := core.answer_block_reason(question, answer, changes.get("company", ""))):
        raise ValueError("Not saved: " + reason)
    with conn:  # a rename onto another row's question raises sqlite3.IntegrityError
        conn.execute("UPDATE answers SET question = ?, answer = ?, field_type = ?, updated_at = datetime('now')"
                     " WHERE id = ?", (q, answer.strip(), changes.get("field_type", row["field_type"]), answer_id))
        conn.execute("DELETE FROM unanswered WHERE question = ?", (q,))
        return dict(conn.execute("SELECT * FROM answers WHERE id = ?", (answer_id,)).fetchone())


def delete_answer(conn, answer_id: int) -> None:
    with conn:
        if conn.execute("DELETE FROM answers WHERE id = ?", (answer_id,)).rowcount == 0:
            raise KeyError(answer_id)


def find_answer(conn, label: str, options: Optional[List[str]] = None) -> Optional[dict]:
    return core.find_answer(label, list_answers(conn), options)


# --- profile and stored CV --------------------------------------------------

PROFILE_DEFAULTS = {"name": "", "email": "", "phone": "", "linkedin": "", "skills": []}


def get_profile(conn) -> dict:
    out = copy.deepcopy(PROFILE_DEFAULTS)
    row = conn.execute("SELECT value FROM settings WHERE key = 'profile'").fetchone()
    if row:
        out.update({k: v for k, v in json.loads(row["value"]).items() if k in PROFILE_DEFAULTS})
    return out


def save_profile(conn, changes) -> dict:
    if not isinstance(changes, dict):
        raise ValueError("Profile must be a JSON object")
    for key in changes:
        if key not in PROFILE_DEFAULTS:
            raise ValueError("Unknown profile field: %s" % key)
    merged = dict(get_profile(conn), **{k: _clean(k, v, PROFILE_DEFAULTS) for k, v in changes.items()})
    merged["skills"] = core.dedupe_skills(merged["skills"])
    with conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('profile', ?)", (json.dumps(merged),))
    return merged


def cv_dir() -> Path:
    return Path(db_path()).parent


def cv_file_name() -> str:
    return next((n for n in ("cv.pdf", "cv.docx") if (cv_dir() / n).is_file()), "")


def store_cv(data: bytes, ext: str) -> None:
    """Keep one CV under a fixed name (D-03); the name never comes from the client."""
    d = cv_dir()
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / ("cv." + ext + ".tmp")
    tmp.write_bytes(data)
    os.replace(str(tmp), str(d / ("cv." + ext)))  # atomic: an interrupted upload never leaves half a file
    for other in ("pdf", "docx"):
        if other != ext:
            (d / ("cv." + other)).unlink(missing_ok=True)
