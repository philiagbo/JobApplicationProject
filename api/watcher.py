import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional

import keyring.errors

import alerts
import core
import db
import sources

log = logging.getLogger("jobhelper.watcher")

# ponytail: one process-wide lock, fine for one process
FETCH_LOCK = threading.Lock()
WAKE = threading.Event()
GMAIL_WAKE = threading.Event()  # Gmail has its own tick, so connecting Gmail must not trigger an API poll
API_SOURCES = ("reed", "remotive")
ALL_SOURCES = API_SOURCES + ("gmail",)
FIRST_POLL_DAYS = 7  # D-03: a new connection looks back this far
STATUS = {}  # type: Dict[str, dict]
TICK_SECONDS = 30
SECONDS_PER_MINUTE = 60
RETRY_SECONDS = 300  # a poll with errors is retried this soon, not after a full api_poll_minutes
_thread = None  # type: Optional[threading.Thread]
DETAILS_WAKE = threading.Event()  # set when new jobs arrive so the details worker does not wait out its idle sleep
DETAILS_GAP_SECONDS = 5  # D-11: fixed, one real fetch every 5 seconds
DETAILS_IDLE_SECONDS = 30
_details_thread = None  # type: Optional[threading.Thread]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def gmail_account(conn) -> str:
    """The connected address, else "". keyring is only touched once an address row exists."""
    address = db.get_raw(conn, "gmail_address") or ""
    if not address:
        return ""
    try:
        return address if alerts.gmail_password(address) is not None else ""
    except keyring.errors.KeyringError as e:
        log.warning("Credential store unavailable: %s", type(e).__name__)
        return ""


def _gmail_since(conn, today: date) -> date:
    try:
        return date.fromisoformat(db.get_raw(conn, "gmail_last_poll") or "")
    except ValueError:
        return today - timedelta(days=FIRST_POLL_DAYS)


def _gmail_polled(conn, address, today):
    """Called only once the polled jobs are stored. Skipped if the account was changed or disconnected meanwhile,
    so that account keeps its 7-day lookback (D-03)."""
    # ponytail: check-then-write, not one transaction; a reconnect in the microseconds between is not caught
    if db.get_raw(conn, "gmail_address") == address:
        # SINCE is date-granular and the server's timezone may differ: step back a day, URL dedupe absorbs the overlap
        db.set_raw(conn, "gmail_last_poll", (today - timedelta(days=1)).isoformat())


def _sources(conn, settings, names):
    fields = settings["career_fields"]
    if "reed" in names and fields and settings["reed_api_key"]:
        yield "reed", lambda warn: sources.fetch_reed(fields, settings["reed_api_key"], settings["location"], settings["min_salary"]), None
    if "remotive" in names and fields:
        yield "remotive", lambda warn: sources.fetch_remotive(fields), None
    if "gmail" in names:  # only then: the API tick never touches keyring
        address = gmail_account(conn)
        if address:
            today = date.today()
            yield ("gmail", lambda warn: alerts.fetch_gmail_alerts(address, _gmail_since(conn, today), warn),
                   lambda: _gmail_polled(conn, address, today))


def run_fetch(conn, settings, names=ALL_SOURCES):
    counts, errors = {}, {}
    for name, call, stored in _sources(conn, settings, names):
        started = _now()
        prev = STATUS.get(name, {})
        warnings = []
        try:
            jobs = call(warnings.append)  # can take minutes; settings may be saved meanwhile
            counts[name] = db.insert_jobs(conn, jobs, db.get_settings(conn))  # so score with the latest
            if stored:
                stored()  # after the insert: a failed insert must not move the Gmail poll window
            if counts[name]:
                DETAILS_WAKE.set()
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
            "error": error or "; ".join(warnings) or None,  # warnings (D-08) never reach errors: that drives the 502 and retry
            "new": counts.get(name, 0),
        }
    return {"new": sum(counts.values()), "by_source": counts, "errors": errors}


def _tick_sources(last, names, minutes_key, wake, needs_fields):
    conn = db.connect()  # own connection: sqlite3 connections belong to their thread
    try:
        settings = db.get_settings(conn)
        interval = settings[minutes_key] * SECONDS_PER_MINUTE
        due = last is None or wake.is_set() or time.monotonic() - last >= interval
        if not due:
            return last
        wake.clear()  # before the fetch, so a save/connect during it triggers another poll
        if needs_fields and not settings["career_fields"]:
            return last
        if not FETCH_LOCK.acquire(blocking=False):
            return None  # manual fetch running: stay due, poll when it ends
        started = time.monotonic()
        try:
            result = run_fetch(conn, settings, names)  # Gmail: quiet no-op when not connected (D-05)
        finally:
            FETCH_LOCK.release()
        if result["errors"]:
            return started - interval + min(RETRY_SECONDS, interval)  # due again in RETRY_SECONDS
        return started
    finally:
        conn.close()


def _tick(last: Optional[float]) -> Optional[float]:
    return _tick_sources(last, API_SOURCES, "api_poll_minutes", WAKE, True)


def _tick_gmail(last: Optional[float]) -> Optional[float]:
    return _tick_sources(last, ("gmail",), "gmail_poll_minutes", GMAIL_WAKE, False)


def _loop():
    last = last_gmail = None
    while True:
        failed = False
        try:
            last = _tick(last)
        except Exception:
            log.exception("Watcher tick failed")
            failed = True
        try:
            last_gmail = _tick_gmail(last_gmail)
        except Exception:
            log.exception("Gmail tick failed")
            failed = True
        if failed:
            time.sleep(TICK_SECONDS)  # not WAKE.wait: a set WAKE would make a persistent failure a busy loop
        else:
            WAKE.wait(TICK_SECONDS)  # ponytail: GMAIL_WAKE is noticed on the next 30-second pass


def _details_step() -> Optional[bool]:
    """None = nothing pending, False = decided with no network, True = fetched (or failed trying)."""
    conn = db.connect()
    try:
        job = db.next_pending(conn)
        if job is None:
            return None
        try:
            plan = core.details_plan(job, db.get_settings(conn))
            if plan != "fetch":
                db.save_details(conn, job["id"], "", plan)
                return False
            text, status = sources.fetch_details(job["url"])
            db.save_details(conn, job["id"], text, status)
        except Exception:  # a bad row is marked blocked so the loop can never spin on it; SystemExit leaves it pending
            log.exception("Details fetch failed for job %s", job["id"])
            db.save_details(conn, job["id"], "", "blocked")
        return True
    finally:
        conn.close()


def _details_loop():
    while True:
        DETAILS_WAKE.clear()
        try:
            worked = _details_step()
        except Exception:
            log.exception("Details step failed")
            time.sleep(DETAILS_IDLE_SECONDS)
            continue
        if worked is None:
            DETAILS_WAKE.wait(DETAILS_IDLE_SECONDS)
        elif worked:
            time.sleep(DETAILS_GAP_SECONDS)  # only after a real fetch


def start() -> None:
    global _thread, _details_thread
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_loop, name="watcher", daemon=True)
        _thread.start()
    if _details_thread is None or not _details_thread.is_alive():
        _details_thread = threading.Thread(target=_details_loop, name="details", daemon=True)
        _details_thread.start()


def status() -> dict:
    return {"running": _thread is not None and _thread.is_alive(),
            "fetching": FETCH_LOCK.locked(),
            "sources": dict(STATUS)}
