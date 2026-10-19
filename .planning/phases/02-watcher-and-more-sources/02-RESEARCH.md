# Phase 2: Watcher and More Sources - Research

**Researched:** 2026-10-19
**Domain:** Flask + stdlib background polling thread; Reed and Adzuna REST adapters (stdlib urllib only)
**Confidence:** MEDIUM-HIGH (in-repo facts and the Adzuna/Reed endpoints were read or probed this session; field-level API response details come from docs plus third-party write-ups and are tagged)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Watcher start and timing**
- **D-01:** The first poll runs right at startup, then repeats on the API interval (default 60 min).
- **D-02:** With no career fields set, the watcher skips quietly and re-checks on the next tick (no error, no log spam).
- **D-03:** Start the watcher only in the real process: when debug is on, check `WERKZEUG_RUN_MAIN` so the reloader doesn't start two; when debug is off (Windows target), always start.
- **D-04:** Intervals are read from settings on every tick, so changing them changes cadence without a restart (WATCH-02). Gmail interval (5 min) stays a setting only; Phase 4 adds its poll.

**Reed and Adzuna queries**
- **D-05:** One search per career field, merged and deduplicated by URL, same as Remotive (D-14 of Phase 1). Location from settings is passed to the APIs; min salary is passed only where the API supports it.
- **D-06:** First page only (~50 newest) per source per field each poll.
- **D-07:** Adzuna uses two settings keys, `adzuna_app_id` and `adzuna_app_key`, added to the settings defaults and PUT validation (extends D-16/D-18 of Phase 1). Reed uses its single key. Adzuna country is fixed to `gb`.
- **D-08:** `fetch_reed` and `fetch_adzuna` live in `api/sources.py`, return the same job dict shape as `fetch_remotive`, and raise `SourceError` on failure.

**Failures and visibility**
- **D-09:** A source with no key saved (Reed/Adzuna) is skipped silently.
- **D-10:** Failures are logged to the console and recorded as per-source last-poll status (last_ok, last_error, time) exposed through the API (new `GET /api/watcher` or within stats; planner picks the shape). Status is in-memory, not persisted.
- **D-11:** One failing source never stops the others or the watcher; a failed source is simply retried on the next poll (no back-off).

**Fetch and watcher interplay**
- **D-12:** `run_fetch` runs all sources through one code path used by both the watcher and `POST /api/fetch`; the manual response returns per-source counts and per-source errors rather than failing whole.
- **D-13:** A single lock guards fetching. If a fetch is already running, `POST /api/fetch` returns 409 `{"error": "Fetch already running"}`.
- **D-14:** Saving settings that change keys or career fields wakes the watcher for an immediate poll; interval changes just apply on the next tick.

### Claude's Discretion
Exact Reed/Adzuna request parameters and response mapping (including how salary fields map into the job dict), the watcher's thread/wake mechanism (e.g. `threading.Event`), and the shape/location of the status endpoint.

### Deferred Ideas (OUT OF SCOPE)
- Gmail alert polling on the 5 min interval - Phase 4.
- Back-off after repeated failures - not needed now.
- Persisted watcher status/history - only if the UI needs it later.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SRC-03 | `fetch_reed` and `fetch_adzuna` (country `gb`) return jobs using keys saved in settings | Endpoints, auth, params and field mapping below; Adzuna URL canonicalisation (pitfall 1) is required for dedupe to work |
| WATCH-01 | Watcher thread polls on the configured interval and keeps running after a source fails | Tick-loop design, per-source try/except, tick-level catch-all, own DB connection per tick |
| WATCH-02 | Poll intervals (Gmail 5, APIs 60) read from settings | Already in `db.DEFAULTS`; re-read every tick; sub-minute tick so a changed interval takes effect within seconds |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Flask + stdlib `sqlite3`, one Python process; no new heavy dependencies (this phase needs none).
- Python 3.9 (dev, venv is 3.9.6) and 3.12 (target): use `typing.List/Dict/Optional`, no `X | Y` annotations, no `match`.
- Windows target, double-click `Start.bat`, debug off in production.
- Compliance: respect site terms; Reed/Adzuna are official keyed APIs, so fine. Never auto-submit.
- API errors: `{"error": ...}` with 4xx/5xx, never 200 with an error body (DATA-06). Note: a 200 manual fetch that carries a per-source `errors` map is NOT this case as long as at least one source succeeded; see Pattern 3.
- Playwright thread rule is irrelevant here (no browser work in Phase 2).
- `# ponytail:` comments mark deliberate simplifications.
- Tests are plain-assert scripts with a `__main__` runner (no pytest installed in `.venv`).
- GSD workflow: all edits go through GSD execution.

## Summary

Phase 2 is small and mostly wiring. The Phase 1 code already has the shape needed: `sources.py` (`get_json`, `SourceError`, `fetch_remotive` returning a flat job dict), `db.insert_jobs` (INSERT OR IGNORE on a UNIQUE `url`, scores on insert), and `db.DEFAULTS` which **already contains** `adzuna_app_id`, `adzuna_app_key`, `gmail_poll_minutes`, `api_poll_minutes` with validation (`_clean`, floor 1 for `*_poll_minutes`). D-07's "add Adzuna keys to settings" is therefore already done; the planner should only add a test assertion, not code. [VERIFIED: api/db.py:11-21 `"reed_api_key": "", "adzuna_app_id": "", "adzuna_app_key": "", "gmail_poll_minutes": 5, "api_poll_minutes": 60`]

The real work: (1) two adapters in `sources.py` using stdlib `urllib` (Reed needs HTTP Basic auth with the key as username and an empty password, so `get_json` needs an optional `headers` argument); (2) a new `api/watcher.py` holding `run_fetch`, the fetch lock, in-memory per-source status, and a daemon thread whose loop wakes every ~30 s, re-reads settings, and polls when due or when woken; (3) route changes in `app.py` (`/api/fetch` goes through the shared path with a 409 lock, `settings_put` wakes the watcher, new `GET /api/watcher`, watcher started from the `__main__` block only).

The single biggest trap is Adzuna: its `redirect_url` carries per-request tracking params (`se`, `v`, `utm_*`), so the same ad produces a different URL every poll and `jobs.url UNIQUE` dedupe silently fails, flooding the feed with duplicates every 60 minutes. Canonicalise the URL (drop the query string) in `fetch_adzuna`. The second trap is call volume against Adzuna's free quota. A third is making sure a changed poll interval actually takes effect (a naive `sleep(interval)` would not).

**Primary recommendation:** Add `api/watcher.py` (shared `run_fetch` + lock + status + tick loop with `threading.Event` wake), add `fetch_reed`/`fetch_adzuna` to `sources.py` with `get_json(url, params, headers=None)`, canonicalise Adzuna URLs, and start the thread only from the `__main__` block.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Fetch jobs from Remotive/Reed/Adzuna | API / Backend (`sources.py`) | - | Keys live in SQLite on the server; browser must never call these APIs |
| Scheduling polls | API / Backend (watcher daemon thread) | - | No browser needed; app must refresh with no UI open |
| Dedupe + score on insert | Database / Storage (`jobs.url UNIQUE`) + `db.insert_jobs` | API / Backend (`core.score`) | Existing Phase 1 behaviour; reuse |
| Fetch mutual exclusion | API / Backend (process-wide `threading.Lock`) | - | One process, one lock is enough |
| Per-source status | API / Backend (in-memory dict) | - | D-10: not persisted |
| Exposing status | API / Backend (`GET /api/watcher`) | Browser (future UI) | UI is out of scope |
| Poll cadence config | Database / Storage (`settings`) | API / Backend (read each tick) | WATCH-02 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `urllib.request` / `urllib.parse` (stdlib) | Python 3.9 / 3.12 | HTTP calls, Basic auth header, URL canonicalisation | Already used by `get_json`; zero new dependencies [VERIFIED: api/sources.py:4,6 `import urllib.request`, `from urllib.parse import urlencode`] |
| `threading` (stdlib) | - | Watcher thread, `Event` wake, fetch `Lock` | Matches existing `_remotive_lock` pattern; one process [VERIFIED: api/sources.py:20] |
| `logging` (stdlib) | - | Console warnings for failed sources | Unconfigured `logging` falls back to the stderr last-resort handler at WARNING+, so failures show on the Windows console with no setup [ASSUMED: standard library behaviour] |
| Flask | 3.1.3 (installed) | Routes | Already in use; `app.run` defaults `threaded=True` so a long manual fetch does not block other requests [VERIFIED: .venv/lib/python3.9/site-packages/flask/app.py:655 `options.setdefault("threaded", True)`] |

### Supporting
None. No new packages.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| hand-rolled tick loop | APScheduler | New dependency for one repeating job; not worth it |
| `requests` | stdlib urllib | `requests` is in the project stack list but not in `api/requirements.txt` (only `flask>=3.0`); keep urllib, consistent with Remotive [VERIFIED: api/requirements.txt] |

**Installation:** none. `api/requirements.txt` stays `flask>=3.0`.

## Package Legitimacy Audit

No external packages are installed in this phase (stdlib only), so the audit table does not apply.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
 process start (python api/app.py, __main__ only)
        |
        v                                   POST /api/settings (PUT)
 [watcher.start()] -- daemon thread               |  keys / career_fields changed?
        |                                         v
        v                                  watcher.WAKE.set()
 +--------------------- tick loop (every TICK_SECONDS=30, or when WAKE set) ----+
 | conn = db.connect()  (own connection, this thread)                          |
 | settings = db.get_settings(conn)        <- intervals re-read every tick     |
 | due = first run OR WAKE set OR elapsed >= api_poll_minutes                  |
 | no career_fields? -> quiet skip (D-02)                                      |
 | FETCH_LOCK.acquire(blocking=False) busy? -> skip this tick                  |
 +--------------------------------------+--------------------------------------+
                                        v
        POST /api/fetch  --->  run_fetch(conn, settings)   (one shared code path, D-12)
        (lock busy -> 409)            |
                                      v
              for each source (remotive always; reed if key; adzuna if id+key):
                   try  fetch_x(...) -> [job dicts] -> db.insert_jobs (dedupe by url, score)
                   except -> log WARNING, status[source].error = msg, continue (D-11)
                                      |
                                      v
                  {"new", "by_source", "errors"}  +  in-memory STATUS  --> GET /api/watcher
```

### Recommended Project Structure
```
api/
├── app.py        # routes; imports watcher; starts it in __main__ only
├── watcher.py    # NEW: run_fetch, FETCH_LOCK, WAKE, STATUS, start(), tick helpers
├── sources.py    # + fetch_reed, fetch_adzuna, get_json(headers=None)
├── db.py         # unchanged (DEFAULTS already has adzuna keys)
├── test_api.py   # fake get_json must route by URL (see Pitfall 5)
└── test_watcher.py  # NEW: plain-assert tests, __main__ runner
```

`run_fetch` must move out of `app.py` into `watcher.py` (or a module both import) so the watcher thread does not import `app` (circular import: `app` imports `watcher`). Nothing in `test_api.py` references `app.run_fetch` [VERIFIED: grep of api/test_api.py found no `run_fetch`].

### Pattern 1: Adapter returns the Remotive job-dict shape
**What:** every adapter returns `List[dict]` with exactly the keys `fetch_remotive` produces: `url, source, title, company, location, salary, description, job_type, remote`. [VERIFIED: api/sources.py:49-59]. `db.insert_jobs` reads `url, source, title, company, location, salary, description` and `core.summarize` reads `salary, description, title, location, job_type, remote` [VERIFIED: api/db.py:133-135, api/core.py:151-165].

`job_type`/`remote` may be `None`; `summarize` then infers them from title/description (`job.get("job_type") or _first_label(...)`) [VERIFIED: api/core.py:164-165]. Only set `remote` when the source states it (Remotive always does). For Reed/Adzuna leave `remote` unset (`None`).

**Reed** [CITED: https://www.reed.co.uk/developers/jobseeker; field names corroborated by https://jobspipe.dev/blog/reed-api and a 401 probe]:
- `GET https://www.reed.co.uk/api/1.0/search?keywords=<field>&locationName=<loc>&minimumSalary=<n>&resultsToTake=50`
- Auth: HTTP Basic, API key as username, empty password: header `Authorization: Basic base64("<key>:")`. Verified header construction in Python 3.9 gives `Basic a2V5Og==` for key `key`. Bad key returns HTTP 401 (probed this session: HTTP 401, empty body).
- Response `{"results": [...]}`, each with `jobId, employerName, jobTitle, locationName, minimumSalary, maximumSalary, currency, date, jobDescription, jobUrl` [CITED: publicapi.dev/jobspipe via search; MEDIUM]. Salary fields are **absent** (not zero) when hidden [CITED: jobspipe.dev/blog/reed-api].
- `jobDescription` in the search response is a short preview; the full text needs one extra call per job (`/api/1.0/jobs/{id}`), i.e. 101 calls per page [CITED: jobspipe.dev/blog/reed-api]. Do NOT do the N+1 calls here; Phase 4 `fetch_details` reads the full page.
- Mapping: `url=jobUrl`, `source="reed"`, `title=jobTitle`, `company=employerName`, `location=locationName`, `description=jobDescription`, `salary` = formatted string (below), `job_type=None`.
- No documented sort parameter, so "~50 newest" (D-06) is best-effort: you get Reed's default ordering for the first 50 [ASSUMED].
- `resultsToTake` max is 100; use 50 [CITED: Reed docs].

**Adzuna** [CITED: https://developer.adzuna.com/docs/search; endpoint and error shape probed this session]:
- `GET https://api.adzuna.com/v1/api/jobs/gb/search/1?app_id=..&app_key=..&what=<field>&where=<loc>&salary_min=<n>&results_per_page=50&sort_by=date&content-type=application/json`
- HTTPS works (probe with fake creds returned HTTP 401 and body `{"exception":"AUTH_FAIL",...,"display":"Authorisation failed"}`). The docs show `http://`; use `https://`.
- Response `{"results": [...]}` each with `id, title, company{display_name}, location{display_name}, description (snippet only), salary_min, salary_max, salary_is_predicted, contract_type, contract_time, created, redirect_url` [CITED: docs.adzuna.com search page; description is a snippet per docs].
- Mapping: `url=canonical(redirect_url)`, `source="adzuna"`, `title`, `company=company.display_name`, `location=location.display_name`, `description`, `salary` formatted, `job_type`: `contract_type == "contract"` -> `"Contract"`, else `contract_time` `"full_time"` -> `"Full-time"`, `"part_time"` -> `"Part-time"`, else `None` [ASSUMED: enum strings `full_time`, `part_time`, `permanent`, `contract` are Adzuna's usual values; the code must tolerate any other value by falling through to None].
- Guard nested objects: `(item.get("company") or {}).get("display_name")`; the existing `except (OSError, ValueError, KeyError, TypeError)` catches shape surprises.

**Salary string.** Build a text string the existing regex already parses (`£50,000 - £60,000`), since `summarize` parses the `salary` field when non-empty [VERIFIED: api/core.py:151-154]:

```python
def _salary_text(lo, hi):
    lo, hi = lo or 0, hi or 0
    if not (lo or hi):
        return ""
    if lo and hi and round(lo) != round(hi):
        return "£{:,.0f} - £{:,.0f}".format(lo, hi)
    return "£{:,.0f}".format(lo or hi)
```
Both are UK sources so `£` is correct. Adzuna: if `salary_is_predicted` is truthy (it arrives as `"1"`/`"0"`-style flag; compare `str(v) == "1"`), set `salary=""` so a guessed number is never scored as a real pro [ASSUMED: flag type; `str(...)=="1"` handles int or string]. Reed daily/hourly rates (e.g. 300-400) fall below the 1,000 annual window in `_parse_salary` and become "Salary not listed"; acceptable, noted as a ceiling [VERIFIED: api/core.py:76 `if not 1000 <= annual <= 1000000: continue`].

**Min salary pass-through (D-05):** Reed `minimumSalary`, Adzuna `salary_min`, only when `settings["min_salary"] > 0`. Side effect to know: server-side salary filters drop jobs with no salary, which sits slightly against Phase 1 D-04's "never hide" spirit. D-05 is locked, so implement it; mention in the plan so it is a conscious choice.

### Pattern 2: `get_json` gains optional headers (backwards compatible)
```python
def get_json(url: str, params: dict, headers: Optional[dict] = None):
    h = {"User-Agent": USER_AGENT}
    h.update(headers or {})
    req = urllib.request.Request(url + "?" + urlencode(params), headers=h)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)
```
Remotive keeps calling `get_json(url, params)` (2 args). Only Reed passes `headers=`. `urlencode` percent-encodes user text (career fields, location), so no injection into the query string.

### Pattern 3: One shared `run_fetch`, per-source isolation, result shape
```python
# api/watcher.py
import logging, threading
from datetime import datetime, timezone
import db, sources

log = logging.getLogger("jobhelper.watcher")
FETCH_LOCK = threading.Lock()
WAKE = threading.Event()
STATUS = {}  # type: dict   # source -> {"last_poll", "ok", "last_ok_at", "error", "new"}

def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _sources(s):
    f = s["career_fields"]
    yield "remotive", lambda: sources.fetch_remotive(f)
    if s["reed_api_key"]:                                   # D-09: silent skip
        yield "reed", lambda: sources.fetch_reed(f, s["reed_api_key"], s["location"], s["min_salary"])
    if s["adzuna_app_id"] and s["adzuna_app_key"]:
        yield "adzuna", lambda: sources.fetch_adzuna(f, s["adzuna_app_id"], s["adzuna_app_key"], s["location"], s["min_salary"])

def run_fetch(conn, settings):
    counts, errors = {}, {}
    for name, call in _sources(settings):
        st = STATUS.setdefault(name, {"last_ok_at": None})
        st.update(last_poll=_now(), new=0)
        try:
            counts[name] = db.insert_jobs(conn, call(), settings)
            st.update(ok=True, error=None, last_ok_at=st["last_poll"], new=counts[name])
        except Exception as e:  # SourceError expected; anything else must not stop the other sources (D-11)
            if isinstance(e, sources.SourceError):
                msg = str(e)
                log.warning("%s", msg)
            else:
                msg = "%s failed unexpectedly (see console)" % name
                log.exception(msg)
            errors[name] = msg
            st.update(ok=False, error=msg)
    return {"new": sum(counts.values()), "by_source": counts, "errors": errors}
```
Insert per source immediately (inside the loop) so a later source's failure never discards an earlier source's jobs.

**Manual route result rule (resolves a D-12 vs DATA-06 tension; planner confirm):** `POST /api/fetch` -> 409 if lock busy; 400 if no career fields (unchanged, Phase 1 D-15); if **every attempted** source failed return `502 {"error": "<first message>", "errors": {...}}`; otherwise `200` with the full result including `errors`. This keeps `test_fetch_source_failure_is_502` valid (Remotive is the only attempted source when no keys are saved) and satisfies "per-source errors rather than failing whole" when some sources worked. The existing assertion `r.get_json() == {"new": 4, "by_source": {"remotive": 4}}` in `test_fetch_dedupes` must change to include `"errors": {}` (or the planner omits `errors` when empty; prefer always including it, one clear contract) [VERIFIED: api/test_api.py:119-127 and 145-161].

### Pattern 4: Tick loop with re-read intervals and wake event
```python
TICK_SECONDS = 30
SECONDS_PER_MINUTE = 60   # tests shrink these two

def _loop():
    last = None                       # monotonic of last poll; None = poll now (D-01)
    while True:
        try:
            conn = db.connect()       # own connection: sqlite3 conns are per-thread
            try:
                s = db.get_settings(conn)
                due = (last is None or WAKE.is_set()
                       or time.monotonic() - last >= s["api_poll_minutes"] * SECONDS_PER_MINUTE)
                if due:
                    WAKE.clear()      # clear BEFORE fetching so a save during the fetch triggers another poll
                    if s["career_fields"]:                         # D-02: quiet skip, stays due
                        if FETCH_LOCK.acquire(blocking=False):
                            try:
                                last = time.monotonic()
                                run_fetch(conn, s)
                            finally:
                                FETCH_LOCK.release()
            finally:
                conn.close()
        except Exception:
            log.exception("Watcher tick failed")   # sqlite locked etc.: thread must survive (WATCH-01)
        WAKE.wait(TICK_SECONDS)

def start():
    global _thread
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_loop, name="watcher", daemon=True)
        _thread.start()
```
Why a short tick: D-04 says intervals are read from settings every tick. A single `time.sleep(60 min)` would ignore a change to "5 min" for up to an hour, failing success criterion 4. With a 30 s tick and an elapsed-time comparison against the freshly read interval, a change applies within ~30 s and no restart is needed. The `Event.wait(timeout)` doubles as the wake mechanism (D-14). With no career fields, `last` stays `None`, so the watcher stays "due" and re-checks silently each tick, and starts immediately when the user saves fields (WAKE). Note `WAKE.wait` returns immediately while set; the code clears it before the career-field check so there is no busy loop.

### Pattern 5: Start the watcher only in the real process (D-03)
```python
if __name__ == "__main__":
    debug = os.environ.get("JOBHELPER_DEBUG") == "1"
    if not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        watcher.start()
    app.run(host="127.0.0.1", port=8765, debug=debug)
```
Werkzeug's reloader child sets `WERKZEUG_RUN_MAIN=true` [VERIFIED: .venv/lib/python3.9/site-packages/werkzeug/serving.py:961 `return os.environ.get("WERKZEUG_RUN_MAIN") == "true"`]; Flask's `app.run` sets `use_reloader` from `debug` [VERIFIED: flask/app.py:653]. Start in the `__main__` block, never at import: `test_api.py` imports `app` and must not spawn a thread.

### Pattern 6: Settings save wakes the watcher (D-14)
```python
WAKE_KEYS = {"reed_api_key", "adzuna_app_id", "adzuna_app_key", "career_fields"}
# in settings_put, after save_settings succeeds:
body = request.get_json(silent=True)
...
if WAKE_KEYS & set(body): watcher.WAKE.set()
```
Compute from the request keys (cheap, no diff of old/new). Only after a successful save (the existing `except ValueError` returns before). An unchanged re-save would still trigger a poll; acceptable.

### Pattern 7: Status endpoint (planner's pick; recommended)
`GET /api/watcher` -> `{"running": bool, "fetching": FETCH_LOCK.locked(), "sources": {"remotive": {"last_poll": iso|null, "ok": bool, "last_ok_at": iso|null, "error": str|null, "new": int}, ...}}`. A separate endpoint avoids changing `db.stats` (which `test_api.py` may assert on exactly). `running` = `_thread is not None and _thread.is_alive()`. Skipped sources (no key) simply do not appear.

### Anti-Patterns to Avoid
- **Dedupe on Adzuna's raw `redirect_url`:** produces new "jobs" on every poll (Pitfall 1).
- **One `try` around all sources:** one failure discards the rest; per-source `try` (D-11).
- **Sharing the request-scoped `get_db()` connection with the watcher:** use `db.connect()` in the thread (sqlite3 connections are bound to their creating thread) [VERIFIED: api/app.py:45-48 uses `g.db`; api/db.py:66-71 `connect()`].
- **Starting the thread at import time** (breaks tests, doubles under the reloader).
- **Logging URLs or exception reprs that include the request URL:** Adzuna's `app_key` is in the query string (Pitfall 3).
- **N+1 Reed detail calls** to get full descriptions (Phase 4's job).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Basic auth header | manual string concat of base64 | `base64.b64encode(("%s:" % key).encode()).decode()` (3 lines, stdlib) | The trailing colon (empty password) is easy to forget; omitting it yields 401 even with a valid key [CITED: jobspipe.dev/blog/reed-api] |
| URL encoding of params | f-string query building | `urlencode` (already used) | career fields and location are user text |
| Wake/sleep | `time.sleep` + flag polling | `threading.Event.wait(timeout)` | Single primitive does both sleep and wake |
| Scheduler | APScheduler / cron emulation | the 30 s tick loop above | One job, one process |
| Salary parsing | new regex for Reed/Adzuna | format a `£a - £b` string and let `core.summarize` parse it | Reuses tested Phase 1 code |
| Dedup | custom "seen" table | `jobs.url UNIQUE` + `INSERT OR IGNORE` | Already there; only the Adzuna URL needs canonicalising |

**Key insight:** every hard part (dedupe, scoring, salary parsing, settings validation) already exists; Phase 2 adds two thin adapters and a scheduler.

## Common Pitfalls

### Pitfall 1: Adzuna `redirect_url` changes on every request
**What goes wrong:** `https://www.adzuna.co.uk/jobs/land/ad/<id>?se=...&utm_medium=api&utm_source=...&v=...` has `se`/`v`/`utm_*` that change per API call, so `INSERT OR IGNORE` on `url` never matches and every poll re-inserts the same ads [CITED: search result summarising adzuna URL format `.../land/ad/<adId>?se=…&utm_*=…&v=…` where "se and v change per API call"; MEDIUM, single secondary source].
**How to avoid:** canonicalise: `urlsplit` then rebuild `scheme://netloc/path` dropping query and fragment. Add a unit test with two redirect URLs that differ only in query params and assert one deduped job.
**Warning signs:** `found` stats climbing by ~50 per poll for source `adzuna`.
**Open assumption:** that the bare `/jobs/land/ad/<id>` path still redirects to the listing (A2). Verify manually with one real key during phase verification (human check).

### Pitfall 2: Poll interval change ignored until the old sleep ends
Covered in Pattern 4; use a 30 s tick plus elapsed comparison. Test it by shrinking `SECONDS_PER_MINUTE`/`TICK_SECONDS`.

### Pitfall 3: API key leakage
Adzuna puts `app_id`/`app_key` in the query string; Reed's key is in a header. `urllib.error.HTTPError.__str__` is `HTTP Error 401: Unauthorized` (no URL), and `URLError` strings do not include the URL, but never log `url`/`params`/`e.url`/`repr(request)`. Keep `SourceError` messages to `"Adzuna fetch failed: %s" % e`. Status/`errors` text is returned by the API, so it must never contain keys. Add a test: with a fake `get_json` that raises `OSError("boom app_key=SECRET")`... only if you choose to scrub; simpler is the rule "messages come from exception text only, params never interpolated".

### Pitfall 4: Free-tier quota exhaustion (Adzuna)
Adzuna free tier is reported as 2,500 calls/month and 250/day [CITED: https://jobspipe.dev/alternatives/adzuna, third party; MEDIUM]. At one call per career field per poll: 720 polls/month x fields. 3 fields ~ 2,160/month; 4+ fields exceeds 2,500. A 429 or auth-style error surfaces as `HTTPError` -> `SourceError` -> logged and shown in status; the other sources still run. Do not add back-off (deferred). Tell the person in the settings help text/README (later phases) that few career fields are best; add to Open Questions. Reed documents no limit (treat as undocumented, not unlimited).

### Pitfall 5: Existing test fake breaks
`test_api.py` replaces `sources.get_json` with `fake_get_json(url, params)` that does `CANNED[params["search"]]` [VERIFIED: api/test_api.py:52-57]. Reed/Adzuna calls (different URLs, `headers=` kwarg, no `search` param) would KeyError. The planner must update the fake to `(url, params, headers=None)` and route on `url` (`remotive.com` / `reed.co.uk` / `adzuna.com`). Also `fresh_client()` must reset `watcher.STATUS` and release/reset state between tests.

### Pitfall 6: Remotive throttle makes a poll slow, and lock is held for the duration
`REMOTIVE_GAP_SECONDS = 31` between Remotive requests [VERIFIED: api/sources.py:10]. With 3 fields a poll takes about 1 to 2 minutes, and the fetch lock is held that long, so manual `POST /api/fetch` returns 409 during that window and a manual fetch request itself can run >1 min. That is existing behaviour; the 409 is correct. Consider running Reed and Adzuna before Remotive so keyed sources are not stuck behind the throttle (order of `_sources`); recommended: yield Reed and Adzuna first, Remotive last.

### Pitfall 7: Watcher thread dies silently
An uncaught exception (e.g. `sqlite3.OperationalError: database is locked` from a concurrent `PUT /api/settings`) would end the thread and WATCH-01 would silently fail. The tick body must be wrapped in a catch-all (Pattern 4). Python's default `sqlite3` busy timeout is 5 s [ASSUMED: documented stdlib default], which is ample for this app's tiny writes; WAL mode is optional hardening, not required.

### Pitfall 8: Reed location semantics
`locationName` is a UK place name with a default 10-mile radius [CITED: Reed docs]. The settings `location` is free text; values like "Remote" or "UK" will narrow or empty Reed results. Pass it through as D-05 says; do not invent mapping. Adzuna `where` is more forgiving. Mention in plan as a known behaviour, not a bug.

### Pitfall 9: Cross-source duplicates
Same ad on Reed and Adzuna has different URLs, so both appear. Success criterion 1 "deduplicated" means by URL (SRC-02). Title+company fuzzy dedupe is out of scope; add a `# ponytail:` note.

## Code Examples

### fetch_reed
```python
# Source: Reed docs https://www.reed.co.uk/developers/jobseeker (auth, params); mapping per Pattern 1
REED_URL = "https://www.reed.co.uk/api/1.0/search"

def fetch_reed(fields, api_key, location="", min_salary=0):
    auth = {"Authorization": "Basic " + base64.b64encode(("%s:" % api_key).encode()).decode()}
    found = {}  # type: Dict[str, dict]
    try:
        for field in fields:
            params = {"keywords": field, "resultsToTake": 50}
            if location:
                params["locationName"] = location
            if min_salary:
                params["minimumSalary"] = min_salary
            for item in get_json(REED_URL, params, auth)["results"]:
                found.setdefault(item["jobUrl"], {
                    "url": item["jobUrl"], "source": "reed",
                    "title": item.get("jobTitle") or "",
                    "company": (item.get("employerName") or "").strip(),
                    "location": item.get("locationName") or "",
                    "salary": _salary_text(item.get("minimumSalary"), item.get("maximumSalary")),
                    "description": item.get("jobDescription") or "",
                    "job_type": None, "remote": None,
                })
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise SourceError("Reed fetch failed: %s" % e)
    return list(found.values())
```
Note `get_json(url, params, headers)` passes headers positionally: the test fake needs the third parameter.

### fetch_adzuna
```python
# Source: https://developer.adzuna.com/docs/search ; URL canonicalisation per Pitfall 1
ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/gb/search/1"

def _canonical(url):
    p = urlsplit(url)
    return "%s://%s%s" % (p.scheme, p.netloc, p.path)

def fetch_adzuna(fields, app_id, app_key, location="", min_salary=0):
    found = {}  # type: Dict[str, dict]
    try:
        for field in fields:
            params = {"app_id": app_id, "app_key": app_key, "what": field, "results_per_page": 50,
                      "sort_by": "date", "content-type": "application/json"}
            if location:
                params["where"] = location
            if min_salary:
                params["salary_min"] = min_salary
            for item in get_json(ADZUNA_URL, params)["results"]:
                url = _canonical(item["redirect_url"])
                predicted = str(item.get("salary_is_predicted")) == "1"
                found.setdefault(url, {
                    "url": url, "source": "adzuna",
                    "title": item.get("title") or "",
                    "company": ((item.get("company") or {}).get("display_name") or "").strip(),
                    "location": (item.get("location") or {}).get("display_name") or "",
                    "salary": "" if predicted else _salary_text(item.get("salary_min"), item.get("salary_max")),
                    "description": item.get("description") or "",
                    "job_type": _adzuna_type(item), "remote": None,
                })
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise SourceError("Adzuna fetch failed: %s" % e)
    return list(found.values())
```

### Routes
```python
@app.post("/api/fetch")
def fetch_now():
    conn = get_db()
    settings = db.get_settings(conn)
    if not settings["career_fields"]:
        return jsonify(error="Choose at least one career field in settings"), 400
    if not watcher.FETCH_LOCK.acquire(blocking=False):
        return jsonify(error="Fetch already running"), 409
    try:
        result = watcher.run_fetch(conn, settings)
    finally:
        watcher.FETCH_LOCK.release()
    if result["errors"] and not result["by_source"]:
        return jsonify(error=next(iter(result["errors"].values())), errors=result["errors"]), 502
    return jsonify(result)

@app.get("/api/watcher")
def watcher_status():
    return jsonify(watcher.status())
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fetch only on manual `POST /api/fetch` (Phase 1 D-13) | Same shared `run_fetch` also driven by a watcher thread | Phase 2 | One code path, lock-guarded |
| Single source 502-on-failure | Per-source errors; 502 only if all attempted sources failed | Phase 2 | Keeps Phase 1 test valid |

**Deprecated/outdated:** none relevant. Adzuna docs show `http://`; HTTPS works (probed).

## Runtime State Inventory

Not a rename/refactor/migration phase. Omitted. (Schema unchanged: no new tables, no migrations.)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Adzuna `redirect_url` query params (`se`, `v`, `utm_*`) change per API call | Pitfall 1 | If stable, canonicalising is harmless but unnecessary; if they carry meaning, stripping loses nothing needed for dedupe |
| A2 | Bare `https://www.adzuna.co.uk/jobs/land/ad/<id>` (no query) still redirects to the listing | Pitfall 1 / Pattern 1 | Stored link might 404; mitigation: verify with real keys; fallback is to keep the full URL for display and add a separate dedupe key (needs schema change) |
| A3 | `salary_is_predicted` is `"1"`/`"0"` (or int); compare `str(v) == "1"` | Pattern 1 | Predicted salaries leak into scoring as real |
| A4 | Adzuna `contract_time` in {`full_time`, `part_time`}, `contract_type` in {`permanent`, `contract`} | Pattern 1 | `job_type` falls through to None and is inferred by core; harmless |
| A5 | Reed search results carry `jobUrl`, `jobTitle`, `employerName`, `locationName`, `minimumSalary`, `maximumSalary`, `jobDescription` (field names from third-party write-ups, not the official page excerpt) | Pattern 1 | `KeyError` -> `SourceError`; must be confirmed against one real response during verification; note `jobUrl` as the dedupe key is required |
| A6 | Reed default result order is usable for "newest ~50" (no sort param) | Pattern 1 | Slightly stale feed |
| A7 | Adzuna free quota 2,500/month, 250/day | Pitfall 4 | Different cap changes advice on number of career fields |
| A8 | Adzuna `results_per_page=50` accepted | Pattern 1 | HTTP 400 -> SourceError; drop to 20 (docs examples use 20) |
| A9 | Unconfigured stdlib `logging` prints WARNING+ to stderr | Standard Stack | Failures invisible on console; fix by `logging.basicConfig(level=logging.INFO)` in `__main__` (safe either way, recommended) |
| A10 | sqlite3 default busy timeout 5 s | Pitfall 7 | Rare "database is locked"; tick catch-all absorbs it |

## Open Questions

1. **Manual fetch HTTP status when some sources fail**
   - What we know: D-12 wants per-source errors, not whole-request failure; DATA-06 forbids 200 with an error body; Phase 1 test expects 502 when Remotive fails.
   - Unclear: user preference.
   - Recommendation: 200 with `errors` map if any source succeeded, 502 if all attempted sources failed (Pattern 3).

2. **Quota advice for the person** - few career fields (<=3) recommended with hourly polling on Adzuna free tier; where to surface (README/UI) belongs to a later phase. No code now.

3. **Real-key verification** - A2 and A5 can only be confirmed with real Reed/Adzuna keys. Plan one `checkpoint:human-verify` at end of phase (supplies keys, runs `POST /api/fetch`, checks both sources return jobs and a second fetch yields 0 new Adzuna jobs).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (venv) | everything | yes | 3.9.6 | - |
| Flask | routes | yes | 3.1.3 | - |
| pytest | tests | no | - | Not needed; repo uses plain-assert scripts with `__main__` runner |
| Internet to api.adzuna.com / www.reed.co.uk | live verification only | yes (both endpoints reachable, returned 401 for fake creds) | - | Tests use a faked `sources.get_json` |
| Reed and Adzuna API keys | live end-to-end check | unknown (user-supplied) | - | Unit tests with canned responses; human-verify checkpoint for live check |

Python 3.12 is not installed locally; code must avoid anything 3.9-incompatible and 3.12-removed. Nothing here is version-sensitive (no `datetime.utcnow()` use: use `datetime.now(timezone.utc)`, which is why Pattern 3 does).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | plain-assert scripts with `__main__` runner (no pytest) [VERIFIED: api/test_api.py `if __name__ == "__main__":` runner] |
| Config file | none |
| Quick run command | `.venv/bin/python api/test_watcher.py` |
| Full suite command | `.venv/bin/python api/test_core.py && .venv/bin/python api/test_api.py && .venv/bin/python api/test_watcher.py` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SRC-03 | `fetch_reed` sends Basic auth header, maps fields, salary text, skips nothing, raises `SourceError` on `OSError`/bad shape | unit (fake `get_json`) | `.venv/bin/python api/test_watcher.py` | Wave 0 |
| SRC-03 | `fetch_adzuna` hits `/jobs/gb/`, maps fields, drops predicted salary, canonicalises URL (two URLs differing only in `se`/`v`/`utm_*` -> one job) | unit | same | Wave 0 |
| SRC-03 | Keys saved in settings -> `POST /api/fetch` returns jobs from reed + adzuna, scored, deduped on second fetch | integration (Flask client, fake `get_json` routed by URL) | `.venv/bin/python api/test_api.py` | edit existing |
| SRC-03 | No reed key / no adzuna id or key -> source silently skipped (not in `by_source`, not in `errors`) | integration | same | Wave 0 |
| WATCH-01 | Watcher tick polls on startup with fields set; with no fields makes zero source calls and no error | unit (`SECONDS_PER_MINUTE`/`TICK_SECONDS` shrunk, thread started, poll with timeout) | `test_watcher.py` | Wave 0 |
| WATCH-01 | One source raising (bad key / `OSError`) -> others still insert, error recorded in `STATUS`, next tick still polls | unit | same | Wave 0 |
| WATCH-01 | Unexpected exception inside a tick does not kill the thread (`is_alive()` stays true) | unit | same | Wave 0 |
| WATCH-02 | Changing `api_poll_minutes` in settings changes cadence without restart (set large, then small, assert a poll occurs within a few ticks) | unit | same | Wave 0 |
| WATCH-02 | `gmail_poll_minutes` default 5 and `api_poll_minutes` default 60 round-trip via settings | unit | `test_api.py` (existing `test_settings_defaults` covers via `db.DEFAULTS`) | exists |
| D-12/D-13 | `POST /api/fetch` -> 409 `{"error": "Fetch already running"}` while lock held; response has `errors` map; 502 only if all attempted sources fail | integration | `test_api.py` | edit existing |
| D-14 | `PUT /api/settings` with a key/career_fields sets `WAKE`; with only `min_salary` does not | integration | `test_api.py` | Wave 0 |
| D-10 | `GET /api/watcher` returns per-source status; failing source shows error, no key text | integration | `test_api.py` | Wave 0 |
| D-03 | Watcher not started on `import app` | unit | `test_watcher.py`: assert `watcher._thread is None` after import | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/python api/test_watcher.py`
- **Per wave merge:** full suite command above
- **Phase gate:** full suite green; plus human-verify with real keys before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `api/test_watcher.py` - covers SRC-03 adapters, WATCH-01, WATCH-02, D-10, D-14
- [ ] `api/test_api.py` - generalise `fake_get_json` to `(url, params, headers=None)` routed by URL; update the exact-equality assertion in `test_fetch_dedupes` for the new `errors` key; reset `watcher.STATUS` in `fresh_client()`
- [ ] Framework install: none needed

Tests should run in seconds: shrink `watcher.TICK_SECONDS` (e.g. 0.05) and `watcher.SECONDS_PER_MINUTE` (e.g. 0.05) as module attributes, and `sources.REMOTIVE_GAP_SECONDS = 0` as existing tests do [VERIFIED: api/test_api.py:16].

## Security Domain

### Applicable ASVS Categories (level 1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (local single-user; no login) | - |
| V3 Session Management | no | - |
| V4 Access Control | yes (existing) | `local_only` before_request guard already protects `/api/*` including the new `GET /api/watcher` and `POST /api/fetch` [VERIFIED: api/app.py:18-27] |
| V5 Input Validation | yes | `db._clean` validates settings; `urlencode` for outbound params; treat API JSON as untrusted (shape errors -> `SourceError`) |
| V6 Cryptography | no | keys stored plain in SQLite by design (Phase 1 D-17) |
| V7 Error handling / logging | yes | no keys or URLs in logs or `errors` bodies; generic message for unexpected exceptions |
| V12/V13 SSRF-type outbound | low | outbound hosts are fixed constants (`remotive.com`, `reed.co.uk`, `adzuna.com`); user text only goes into query values, never the host or path |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key disclosure via logs/status | Information disclosure | Never interpolate `params`/URL into log or error text; use exception text only |
| Malicious HTML/JS in job descriptions (XSS later in UI) | Tampering | Descriptions are stored raw as in Phase 1; the later UI must escape/render as text (React escapes by default). `core` text helpers are already bounded-regex (T-01-07) [VERIFIED: api/core.py:14] |
| Oversized/hostile API response | DoS | 20 s timeout already in `get_json`; limit to 50 results per call; keep `json.load` (consider no change) |
| Cross-site trigger of `POST /api/fetch` (quota burn) | DoS / CSRF | Existing `local_only` guard (Host and Origin checks) |
| Watcher thread crash leaving feed stale | DoS | Tick-level catch-all + per-source `except Exception` |

## Sources

### Primary (HIGH confidence)
- In-repo files read this session: `api/app.py`, `api/sources.py`, `api/db.py`, `api/core.py`, `api/test_api.py`, `api/requirements.txt`, `.planning/phases/02-.../02-CONTEXT.md`, `REQUIREMENTS.md`, `STATE.md`, `.planning/config.json`
- Werkzeug/Flask installed source (`serving.py:961`, `app.py:653-655`) for reloader/threaded behaviour
- Live probes this session: Adzuna `https://api.adzuna.com/v1/api/jobs/gb/search/1` with fake creds -> 401 `AUTH_FAIL`; Reed `https://www.reed.co.uk/api/1.0/search` with Basic auth and fake key -> 401

### Secondary (MEDIUM confidence)
- https://www.reed.co.uk/developers/jobseeker - auth, endpoint, parameters (response-field list is summarised, not the full schema)
- https://developer.adzuna.com/docs/search - endpoint, parameters, response fields, snippet-only descriptions
- https://jobspipe.dev/blog/reed-api - Reed auth gotcha, absent salary fields, N+1 for full descriptions (third-party)
- https://jobspipe.dev/alternatives/adzuna - Adzuna quota figures and `salary_is_predicted` (third-party)

### Tertiary (LOW confidence)
- Web search summary stating Adzuna `se`/`v`/`utm_*` URL params change per call (a GitHub issue/PR in a job-aggregation repo and result snippets); confirm with real keys (A1, A2)
- Third-party scraper listings for the Reed JSON example (field names; A5)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - stdlib only, matches existing code
- Architecture: HIGH - derived from the read code and locked decisions
- Adapter field mapping: MEDIUM - official docs plus third-party; needs one real-key check
- Pitfalls: MEDIUM-HIGH - Adzuna URL churn and quota are from secondary sources but plausible and cheap to guard

**Research date:** 2026-10-19
**Valid until:** 30 days (public API shapes are stable; re-check if Reed/Adzuna change auth)
