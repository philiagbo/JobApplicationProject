# Phase 4: Gmail Alerts and Job Details - Pattern Map

**Mapped:** 2026-10-25
**Files analyzed:** 12 (5 new modules/tests, 1 samples dir, 6 modified)
**Analogs found:** 10 / 12 (all analogs are git-tracked: api/*.py)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `api/alerts.py` (NEW: SENDERS, 4 parsers, parse_email) | utility (pure parsers) | transform | `api/sources.py` fetch_reed job-dict mapping + `core._text_lines` | role-match |
| `api/sources.py` (+gmail_login, fetch_gmail_alerts, extract_description, fetch_details) | service | request-response / batch | `api/sources.py` fetch_reed / get_json | exact |
| `api/browser.py` (NEW: Playwright thread + queue) | service (worker thread) | event-driven | `api/watcher.py` thread/Event/`start()` | partial |
| `api/watcher.py` (+_tick_gmail, gmail source, details worker) | service | event-driven / batch | `api/watcher.py` `_tick`, `_loop`, `start` | exact |
| `api/db.py` (+ALTER in init_db, gmail raw-settings helpers, next_pending, save_details) | model | CRUD | `db.py` init_db, get_profile/save_profile, rescore_new | exact |
| `api/app.py` (+/api/gmail GET/PUT/DELETE) | controller | request-response | `app.py` settings_put, profile_put | exact |
| `api/requirements.txt` | config | n/a | itself | exact |
| `api/samples/*.eml` | fixture | file-I/O | none | none |
| `api/test_gmail.py` (NEW) | test | request-response | `api/test_watcher.py` | exact |
| `api/test_details.py` (NEW) | test | request-response | `api/test_watcher.py` | exact |
| `api/test_watcher.py` (extend) | test | event-driven | itself | exact |
| `api/test_api.py` (extend /api/gmail) | test | request-response | itself | exact |

## Pattern Assignments

### `api/sources.py` additions (service)

**Analog:** `api/sources.py`

**Imports/constants** (lines 1-24): stdlib only, `# type:` comments for 3.9, `# ponytail:` for shortcuts.
```python
import base64, json, threading, time, urllib.request
from typing import Dict, List, Optional
USER_AGENT = "JobHelper/1.0 (local job search app)"
class SourceError(Exception):
    pass
```

**Job dict shape** (lines 91-101), what every alert parser must return (set `source` to site name):
```python
found.setdefault(item["jobUrl"], {
    "url": item["jobUrl"], "source": "reed", "title": ..., "company": (...).strip(),
    "location": ..., "salary": ..., "description": ..., "job_type": None, "remote": None,
})
```

**Error handling** (lines 65-66, 102-104): catch narrow tuple, re-raise as `SourceError` with message from the exception only, never params/headers/secrets. For `fetch_gmail_alerts`, map `imaplib.IMAP4.error` at login to a fixed App Password hint (args[0] is bytes, never echo).
```python
except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
    raise SourceError("Reed fetch failed: %s" % e)
```

**urllib request** (lines 31-36), reuse headers/timeout for `fetch_details`:
```python
req = urllib.request.Request(url + "?" + urlencode(params), headers=all_headers)
with urllib.request.urlopen(req, timeout=20) as resp:
```
Throttle precedent (lines 22-24, 43-52): module-level lock + gap constant tests set to 0 (`sources.REMOTIVE_GAP_SECONDS = 0`). Copy for `DETAILS_GAP_SECONDS`.

### `api/alerts.py` (utility, transform)

No file-level analog. Copy: job-dict shape above; HTML-to-text via `core._text_lines` (`core.py` 23-35; call `html.unescape` first for JSON-LD). Parsers pure (html str in, list of dict out), tested against `api/samples/`. Canonicalise URLs per parser (RESEARCH Pitfall 2).

### `api/browser.py` (service, event-driven)

**Analog (thread lifecycle):** `api/watcher.py` lines 97-101
```python
def start() -> None:
    global _thread
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_loop, name="watcher", daemon=True)
        _thread.start()
```
Use RESEARCH "Queue-fed Playwright thread" excerpt for the queue + Future body (lazy start, `submit(fn)` hands `pw`). Never start at import.

### `api/watcher.py` additions

**Analog:** same file.

**Status/event/lock constants** (lines 12-19): add `GMAIL_WAKE = threading.Event()`, `DETAILS_WAKE`, `DETAILS_GAP_SECONDS = 5`.

**run_fetch per-source loop** (lines 33-57), gmail plugs in as a `_sources` yield (only when connected, so existing exact `by_source == {"reed":0,"remotive":0}` assertions stay valid). Keep STATUS shape:
```python
STATUS[name] = {"last_poll": started, "ok": error is None,
    "last_ok_at": started if error is None else prev.get("last_ok_at"),
    "error": error, "new": counts.get(name, 0)}
```
Note `_sources` reads `settings["career_fields"]` at line 27; Gmail must not depend on it (D-04).

**Tick pattern** (lines 60-82), model `_tick_gmail` on it, but WITHOUT the line 68 `if not settings["career_fields"]` gate:
```python
due = last is None or WAKE.is_set() or time.monotonic() - last >= settings["api_poll_minutes"] * SECONDS_PER_MINUTE
...
WAKE.clear()  # before the fetch
if not FETCH_LOCK.acquire(blocking=False):
    return None  # manual fetch running: stay due
```
Use `gmail_poll_minutes` and `GMAIL_WAKE`. Own `db.connect()` per tick, closed in `finally`.

**Loop** (lines 85-94): call both ticks each wrapped in own try/except; keep `_tick(last)` signature (tests monkeypatch `watcher._tick = lambda last: sys.exit()`).
```python
except Exception:
    log.exception("Watcher tick failed")
    time.sleep(TICK_SECONDS)  # not WAKE.wait: ...
    continue
```
`status()` (lines 104-107) unchanged; start details worker from `start()` so it is only started in the `WERKZEUG_RUN_MAIN` child.

### `api/db.py` additions

**init_db migration** (lines 74-77), add guarded ALTER after `executescript(SCHEMA)`; leave `SCHEMA` alone:
```python
cols = [r[1] for r in conn.execute("PRAGMA table_info(jobs)")]
if "details_status" not in cols:
    conn.execute("ALTER TABLE jobs ADD COLUMN details_status TEXT NOT NULL DEFAULT 'pending'")
```

**Raw settings row helpers** (lines 318-336, profile precedent), for `gmail_address` and `gmail_last_poll` (keys not in `DEFAULTS`, so hidden from `get_settings` and rejected by `PUT /api/settings`):
```python
row = conn.execute("SELECT value FROM settings WHERE key = 'profile'").fetchone()
with conn:
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('profile', ?)", (json.dumps(merged),))
```

**save_details**, model on `insert_jobs` scoring (lines 125-142) and `rescore_new` (174-181):
```python
summary = core.summarize(job)
total, pros, cons = core.score(dict(job, summary=summary), settings, profile)
...
with conn:
    conn.execute("UPDATE jobs SET score = ?, pros = ?, cons = ? WHERE id = ?", ...)
```
Do NOT reuse `rescore_new` (it scores from the stored summary). Recompute summary, merge old `remote`/`job_type` hints, only when row `status == 'new'` (D-13). Read fresh `get_settings`/`get_profile` at save time. `job_dict` (118-122) does `dict(row)`, so `details_status` appears in `GET /api/jobs` with no change.

**Atomic status update with WHERE guard** (lines 192-205) is the precedent for `next_pending`/status writes.

### `api/app.py` `/api/gmail` (controller)

**Analog:** `settings_put` (lines 85-99) and `profile_put` (198-206).
```python
@app.put("/api/profile")
def profile_put():
    conn = get_db()
    try:
        db.save_profile(conn, request.get_json(silent=True))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    ...
    return jsonify(_profile_json(conn))
```
Delete + 404 precedent (lines 180-186): `except KeyError: return jsonify(error=...), 404` / `jsonify(ok=True)`. Secret handling precedent: `mask()`/`public()` (71-77), never return the secret; `GET` returns only `{address, connected}`. Validate body keys exactly (400), strip spaces from password, ASCII, test login before storing (400 auth, 502 network), catch `keyring.errors.KeyringError` -> 503. `DELETE` swallows `PasswordDeleteError`. After a successful PUT set `watcher.GMAIL_WAKE`. Other routes stay thin: `{"error"}` + 4xx/5xx.

`/api/fetch` (lines 107-121) has the career_fields 400 gate; flag in plan, leave unless Gmail-only manual polls are wanted.

### Tests: `api/test_gmail.py`, `api/test_details.py`

**Analog:** `api/test_watcher.py`

**Header/bootstrap** (lines 1-29):
```python
os.environ["JOBHELPER_DB"] = os.path.join(tempfile.mkdtemp(), "boot.db")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app, db, sources, watcher  # noqa: E402
sources.REMOTIVE_GAP_SECONDS = 0
watcher.TICK_SECONDS = 0.05
```
**Fake injection** (lines 31-44): module-level `fake_get_json` swapped in `sources.get_json`; `fresh()` (47-55) makes a temp DB and re-installs fakes. Do same with a fake IMAP class via `factory=`, an in-memory keyring backend (RESEARCH code example), and a fake `browser.submit`; set `DETAILS_GAP_SECONDS = 0`.
**Thread stop** (end of file): replace `watcher._tick` with `sys.exit`, join, restore, reset `_thread = None`.
**Runner** (last lines):
```python
if __name__ == "__main__":
    tests = [f for n, f in list(globals().items()) if n.startswith("test_") and callable(f)]
    for t in tests: t()
    print("ok: %d tests" % len(tests))
```
Test for `init_db` migration: hand-built legacy `jobs` table, run `init_db()` twice, assert one column and legacy rows `pending`. Local fixture server via `http.server` for `fetch_details` (loopback must be allowed by the `_http_url` gate).

### `api/requirements.txt`

Current style (`>=,<`): `pypdf>=6.0,<7`. Add:
```
beautifulsoup4>=4.13,<5
keyring>=25.6,<26
playwright>=1.49,<1.61
```
Planner inserts a `checkpoint:human-verify` before install (package audit flagged SUS due to data limits).

## Shared Patterns

### Secrets never leak
**Source:** `api/sources.py` 102-104 and `api/app.py` 71-77. Error text from exception only; app password only in keyring; not in STATUS, logs, responses, or SQLite.

### Per-thread DB connection
**Source:** `api/watcher.py` 61 / 81-82 (`conn = db.connect()` ... `finally: conn.close()`). Apply to `_tick_gmail` and the details worker.

### Source failure isolation
**Source:** `api/watcher.py` 42-48. `SourceError` -> message; any other `Exception` -> generic message + `log.exception`. D-08 zero-job warnings go to STATUS `error` but not the returned `errors` dict.

### Python 3.9 typing and ponytail
`# type:` comments, `typing.List/Optional`, no `X | Y`; mark ceilings with `# ponytail:`.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `api/samples/*.eml` | fixture | file-I/O | User-supplied, redacted by hand (D-06/D-07); checkpoint before parser tasks only |
| bs4 JSON-LD / largest-block extraction (in sources.py) | utility | transform | No HTML parsing exists yet; use RESEARCH Pattern 4 prototype |
| Playwright queue/Future bridge | service | event-driven | No browser code yet; use RESEARCH Pattern 7 prototype |

## Metadata

**Analog search scope:** `api/` (all tracked files via `git ls-files`; ui not relevant)
**Files scanned:** sources.py, watcher.py, db.py, app.py, core.py (`_text_lines`), test_watcher.py, requirements.txt
**Pattern extraction date:** 2026-10-25
