import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional

import db
import sources

log = logging.getLogger("jobhelper.watcher")

# ponytail: one process-wide lock, fine for one process
FETCH_LOCK = threading.Lock()
WAKE = threading.Event()
STATUS = {}  # type: Dict[str, dict]
TICK_SECONDS = 30
SECONDS_PER_MINUTE = 60
RETRY_SECONDS = 300  # a poll with errors is retried this soon, not after a full api_poll_minutes
_thread = None  # type: Optional[threading.Thread]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sources(settings):
    fields = settings["career_fields"]
    if settings["reed_api_key"]:
        yield "reed", lambda: sources.fetch_reed(fields, settings["reed_api_key"], settings["location"], settings["min_salary"])
    yield "remotive", lambda: sources.fetch_remotive(fields)


def run_fetch(conn, settings):
    counts, errors = {}, {}
    for name, call in _sources(settings):
        started = _now()
        prev = STATUS.get(name, {})
        try:
            jobs = call()  # can take minutes; settings may be saved meanwhile
            counts[name] = db.insert_jobs(conn, jobs, db.get_settings(conn))  # so score with the latest
            error = None
        except sources.SourceError as e:
            error = str(e)
            log.warning("%s", error)
        except Exception:
            error = "%s fetch failed unexpectedly (see console)" % name
            log.exception(error)
        if error:
            errors[name] = error
        STATUS[name] = {
            "last_poll": started,
            "ok": error is None,
            "last_ok_at": started if error is None else prev.get("last_ok_at"),
            "error": error,
            "new": counts.get(name, 0),
        }
    return {"new": sum(counts.values()), "by_source": counts, "errors": errors}


def _tick(last: Optional[float]) -> Optional[float]:
    conn = db.connect()  # own connection: sqlite3 connections belong to their thread
    try:
        settings = db.get_settings(conn)
        due = last is None or WAKE.is_set() or time.monotonic() - last >= settings["api_poll_minutes"] * SECONDS_PER_MINUTE
        if not due:
            return last
        WAKE.clear()  # before the fetch, so a save during it triggers another poll
        if not settings["career_fields"]:
            return last
        if not FETCH_LOCK.acquire(blocking=False):
            return None  # manual fetch running: stay due, poll when it ends
        started = time.monotonic()
        try:
            result = run_fetch(conn, settings)
        finally:
            FETCH_LOCK.release()
        if result["errors"]:
            interval = settings["api_poll_minutes"] * SECONDS_PER_MINUTE
            return started - interval + min(RETRY_SECONDS, interval)  # due again in RETRY_SECONDS
        return started
    finally:
        conn.close()


def _loop():
    last = None
    while True:
        try:
            last = _tick(last)
        except Exception:
            log.exception("Watcher tick failed")
        WAKE.wait(TICK_SECONDS)


def start() -> None:
    global _thread
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_loop, name="watcher", daemon=True)
        _thread.start()


def status() -> dict:
    return {"running": _thread is not None and _thread.is_alive(),
            "fetching": FETCH_LOCK.locked(),
            "sources": dict(STATUS)}
