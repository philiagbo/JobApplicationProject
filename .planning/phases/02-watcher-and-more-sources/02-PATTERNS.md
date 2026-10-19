# Phase 2: Watcher and More Sources - Pattern Map

**Mapped:** 2026-10-19
**Files analyzed:** 5 (1 new module, 1 new test, 3 modified)
**Analogs found:** 5 / 5 (all tracked in git)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `api/sources.py` (add `fetch_reed`, `fetch_adzuna`, `get_json(headers)`) | service/adapter | request-response (outbound HTTP) | `api/sources.py::fetch_remotive` | exact |
| `api/watcher.py` (NEW: `run_fetch`, lock, STATUS, tick loop) | service | event-driven/batch | `api/app.py::run_fetch` + `sources._remotive_lock` | role-match |
| `api/app.py` (routes, start watcher, 409, wake) | controller | request-response | itself (`fetch_now`, `settings_put`, `__main__`) | exact |
| `api/test_watcher.py` (NEW) | test | request-response | `api/test_api.py` | exact |
| `api/test_api.py` (fake `get_json`, `errors` key) | test | request-response | itself | exact |
| `api/db.py` | unchanged | | `DEFAULTS` already has adzuna keys and poll minutes (verified by research); only add a test assertion | |

## Pattern Assignments

### `api/sources.py` (adapter, outbound request-response)

**Analog:** `api/sources.py` lines 28-62 (`get_json`, `fetch_remotive`).

**Imports / constants** (lines 1-6; add `base64`, `Optional`, `urlsplit`):
```python
import json
import threading
import time
import urllib.request
from typing import Dict, List
from urllib.parse import urlencode
```

**get_json (extend with optional headers, keep 2-arg callers)** (lines 28-31):
```python
def get_json(url: str, params: dict):
    req = urllib.request.Request(url + "?" + urlencode(params), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)
```

**Core adapter pattern: per-field loop, dedupe by URL via `setdefault`, flat dict, wrap errors** (lines 36-62):
```python
found = {}  # type: Dict[str, dict]
try:
    for field in fields:
        ...
        for item in data["jobs"]:
            found.setdefault(item["url"], {
                "url": item["url"], "source": "remotive",
                "title": item.get("title") or "",
                "company": (item.get("company_name") or "").strip(),
                "location": item.get("candidate_required_location") or "",
                "salary": item.get("salary") or "",
                "description": item.get("description") or "",
                "job_type": REMOTIVE_JOB_TYPES.get(item.get("job_type")),
                "remote": "Remote",
            })
except (OSError, ValueError, KeyError, TypeError) as e:
    raise SourceError("Remotive fetch failed: %s" % e)
return list(found.values())
```
Copy this shape exactly for Reed and Adzuna; full bodies are in RESEARCH.md "Code Examples" (`fetch_reed`, `fetch_adzuna`, `_salary_text`, `_canonical`). Error text comes from the exception only, never from params/URL (Adzuna `app_key` is in the query string). No Remotive-style throttle for Reed/Adzuna (the throttle lock at lines 19-21, 39-47 is Remotive specific).

### `api/watcher.py` (NEW, service, event-driven)

**Analog:** `api/app.py::run_fetch` (lines 58-61) is the function being moved; `api/sources.py` lines 19-21 are the module-level lock style (`# ponytail:` comment).

```python
def run_fetch(conn, settings):
    jobs = sources.fetch_remotive(settings["career_fields"])
    counts = {"remotive": db.insert_jobs(conn, jobs, settings)}
    return {"new": sum(counts.values()), "by_source": counts}
```
Generalise to a per-source loop with its own try/except, inserting inside the loop, returning `{"new", "by_source", "errors"}` (RESEARCH Pattern 3). Own connection per tick: `db.connect()` (api/db.py:64-70), never the Flask `get_db()` (app.py:45-48, uses `g`). Module attributes `TICK_SECONDS` and `SECONDS_PER_MINUTE` so tests can shrink them. Import order: `import db, sources` (flat, no package; app.py:8-9). watcher must not import `app` (circular).

### `api/app.py` (controller)

**Analog:** itself.

**Error pattern** (lines 91-100, to be replaced by lock + shared run_fetch; keep the 400 for no fields, JSON `error` always):
```python
@app.post("/api/fetch")
def fetch_now():
    conn = get_db()
    settings = db.get_settings(conn)
    if not settings["career_fields"]:
        return jsonify(error="Choose at least one career field in settings"), 400
    try:
        return jsonify(run_fetch(conn, settings))
    except sources.SourceError as e:
        return jsonify(error=str(e)), 502
```
New body: `watcher.FETCH_LOCK.acquire(blocking=False)` else `jsonify(error="Fetch already running"), 409`; release in `finally`; 502 only if `errors` and no `by_source` (RESEARCH "Routes").

**Settings wake hook** (lines 74-83): after the `except ValueError` return and successful save, `if WAKE_KEYS & set(body): watcher.WAKE.set()`. Note `request.get_json(silent=True)` is currently inline at line 78; bind it to `body` first (it can be a non-dict, already rejected by `save_settings`, so only touch `body` after save succeeds).
```python
    try:
        db.save_settings(conn, request.get_json(silent=True))
    except ValueError as e:
        return jsonify(error=str(e)), 400
```

**New route:** `@app.get("/api/watcher")` returning `jsonify(watcher.status())`; protected automatically by the `local_only` before_request (lines 18-27).

**Main block** (lines 134-135, replace):
```python
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8765, debug=os.environ.get("JOBHELPER_DEBUG") == "1")
```
with debug var, `if not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true": watcher.start()`, then `app.run(...)`. Optionally `logging.basicConfig(level=logging.INFO)` there. Never start at import (tests import `app`). Remove `run_fetch` and the now-unused `import sources` only if nothing else uses it (check before deleting; `noUnused` style applies).

### `api/test_watcher.py` (NEW) and `api/test_api.py` (modify)

**Analog:** `api/test_api.py`.

**Bootstrap** (lines 1-16): temp DB env var set before importing, `sys.path.insert`, `sources.REMOTIVE_GAP_SECONDS = 0`:
```python
os.environ["JOBHELPER_DB"] = os.path.join(tempfile.mkdtemp(), "boot.db")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app  # noqa: E402
import db  # noqa: E402
import sources  # noqa: E402
sources.REMOTIVE_GAP_SECONDS = 0
```

**Fake HTTP and fresh DB per test** (lines 52-64): must change to `fake_get_json(url, params, headers=None)` routed on `url` substring (`remotive.com`/`reed.co.uk`/`adzuna.com`), since current fake does `params["search"]`. Also reset `watcher.STATUS` (and make sure the lock is free) in `fresh_client()`.
```python
def fake_get_json(url, params):
    calls.append(params["search"])
    return {"jobs": CANNED[params["search"]]}
sources.get_json = fake_get_json

def fresh_client():
    os.environ["JOBHELPER_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
    db.init_db()
    del calls[:]
    return app.app.test_client()
```

**Lines to edit:**
- line 125: `{"new": 4, "by_source": {"remotive": 4}}` becomes `{"new": 4, "by_source": {"remotive": 4}, "errors": {}}`.
- lines 150 and 157: the `boom(url, params)` and `lambda url, params` stand-ins need `headers=None`.
- `CheckedClient` (lines 19-27) already asserts every 4xx/5xx `/api/` body has `error`; the 409 and 502 bodies satisfy it.

**Runner** (lines 327-330): copy verbatim to `test_watcher.py`:
```python
if __name__ == "__main__":
    tests = [f for n, f in list(globals().items()) if n.startswith("test_") and callable(f)]
    for t in tests:
        t()
    print("ok: %d tests" % len(tests))
```
Plain asserts only, no pytest. For thread tests, shrink `watcher.TICK_SECONDS`/`SECONDS_PER_MINUTE` and poll with a timeout rather than fixed sleeps.

## Shared Patterns

### Error contract
**Source:** `api/app.py` 30-42 and `sources.SourceError`. Every `/api/` error is `jsonify(error=...)` with 4xx/5xx; adapters raise `SourceError("<Name> fetch failed: %s" % e)`; `except (OSError, ValueError, KeyError, TypeError)`. Applies to `fetch_reed`, `fetch_adzuna`, and the fetch route.

### DB access off the request thread
**Source:** `api/db.py` `connect()` (64-70) plus `db.get_settings`, `db.insert_jobs(conn, jobs, settings)` (124). Thread code opens and closes its own connection (`try/finally conn.close()`).

### Python 3.9 compatibility
Type comments (`# type: Dict[str, dict]`, as sources.py:36) and `typing.Optional`, no `X | Y`, use `datetime.now(timezone.utc)` not `utcnow()`.

### Deliberate simplifications
Mark with `# ponytail:` (sources.py:19), e.g. cross-source fuzzy dedupe skipped, no back-off.

## No Analog Found

| File/Piece | Role | Reason |
|---|---|---|
| Watcher tick loop / `threading.Event` wake / daemon thread | service | No thread or scheduler exists yet; use RESEARCH Pattern 4 and 5 |
| HTTP Basic header for Reed | utility | No existing auth-header code; use RESEARCH `fetch_reed` snippet (trailing colon required) |

## Metadata

**Analog search scope:** `api/` (all tracked: app.py, sources.py, db.py, core.py, test_api.py, test_core.py); `ui/` not relevant.
**Files scanned:** 6 Python files; all analogs confirmed via `git ls-files`.
**Pattern extraction date:** 2026-10-19
