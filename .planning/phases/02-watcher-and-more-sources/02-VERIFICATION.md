---
phase: 02-watcher-and-more-sources
verified: 2026-10-21T00:00:00Z
status: passed
score: 4/4 must-haves verified
covered_files:
  - .planning/phases/02-watcher-and-more-sources/02-01-PLAN.md
  - .planning/phases/02-watcher-and-more-sources/02-01-SUMMARY.md
  - .planning/phases/02-watcher-and-more-sources/02-02-PLAN.md
  - .planning/phases/02-watcher-and-more-sources/02-02-SUMMARY.md
  - .planning/phases/02-watcher-and-more-sources/02-03-PLAN.md
  - .planning/phases/02-watcher-and-more-sources/02-03-SUMMARY.md
  - .planning/phases/02-watcher-and-more-sources/02-04-PLAN.md
  - .planning/phases/02-watcher-and-more-sources/02-04-SUMMARY.md
  - api/app.py
  - api/db.py
  - api/sources.py
  - api/test_api.py
  - api/test_watcher.py
  - api/watcher.py
covered_digest: "v2:sha256:cc8d30a052e9c008e7a953bf137c14aa2851fc1506cfaebe59fa06d24ce8db1c"
behavior_unverified: 0
overrides_applied: 0
---

# Phase 2: Watcher and More Sources Verification Report

**Phase Goal:** The job feed refreshes itself in the background from Remotive and Reed
**Verified:** 2026-10-21
**Status:** passed
**Re-verification:** No, initial verification

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | After saving a Reed key, Reed jobs appear in `GET /api/jobs`, scored and deduplicated | VERIFIED | `watcher._sources` yields `sources.fetch_reed(...)` only when `reed_api_key` is set; `run_fetch` -> `db.insert_jobs` (INSERT OR IGNORE on UNIQUE url, scores via `core.score`). `app.settings_put` sets `watcher.WAKE` for `reed_api_key`/`career_fields`. `test_api.py` (`test_fetch_reed_jobs_scored_and_deduped`) passes. Live: 02-04 step 3-6 showed 50 Reed jobs, a second fetch adding 0. |
| 2 | With the app running and nothing triggering a fetch, new jobs appear on the configured poll interval | VERIFIED | `app.py` `__main__` calls `watcher.start()` (daemon thread, own `db.connect()` per tick, re-reads settings each tick). `test_tick_polls_immediately`, `test_watcher_thread_end_to_end` pass (real thread, no request). Live: 02-04 step 8 saw `last_poll` advance with no manual fetch. |
| 3 | When one source fails, the watcher logs it, other sources still deliver, next poll runs as normal | VERIFIED | `run_fetch` wraps each source in its own try (`SourceError` -> `log.warning`, other `Exception` -> `log.exception`); STATUS records `ok:false` + error; loop continues. `_loop` catches tick exceptions. `test_failing_source_isolated_and_retried`, `test_unexpected_source_error_isolated`, `test_failure_text_never_contains_key` pass. Live: 02-04 step 7 (bad key: Reed 401 only, Remotive still delivered, no key text). |
| 4 | Intervals default to Gmail 5 min and APIs 60 min; changing them changes the cadence | VERIFIED | `db.DEFAULTS`: `gmail_poll_minutes: 5`, `api_poll_minutes: 60`; `_tick` reads `api_poll_minutes` from settings every tick (no restart). `test_poll_interval_defaults`, `test_interval_change_applies_without_restart` pass. Live: 02-04 step 8. |

**Score:** 4/4 truths verified, 0 present-but-behavior-unverified. Behavior-dependent truths (failure isolation, interval change, wake-on-save) each have a passing test that exercises the transition.

### Plan must-haves (non-Adzuna)

| Must-have | Status | Evidence |
|-----------|--------|----------|
| `fetch_reed`: Basic auth (key + empty password), per-field search, `locationName` only if set, `minimumSalary` only if > 0, `resultsToTake` 50, merge by `jobUrl`, `SourceError` on failure | VERIFIED | `api/sources.py:76-104`; `test_reed_request_params`, `test_reed_mapping_and_salary`, `test_reed_failures_raise_source_error` pass |
| Watcher and `POST /api/fetch` share `run_fetch` under one `FETCH_LOCK`; 409 when held; 502 only if every attempted source failed | VERIFIED | `app.fetch_now` lines 87-106; `test_tick_skips_when_fetch_running` and the API contract tests pass |
| Reed skipped silently with no key | VERIFIED | `_sources` conditional; `test_reed_skipped_without_key` |
| Importing `app` never starts the watcher; `__main__` starts it once (debug child only) | VERIFIED | `app.py:143-149`; `test_import_does_not_start_watcher` |
| Key never in STATUS / errors / logs / `GET /api/watcher` | VERIFIED | Errors built from exception text only; `watcher_status` reads in-memory STATUS; test + live steps 3 and 7 |
| `GET /api/watcher` returns `{running, fetching, sources}` | VERIFIED | `watcher.status()`, `app.watcher_status` |
| No career fields -> tick makes zero source calls | VERIFIED | `_tick` early return; `test_tick_quiet_without_fields` |

### Superseded (intentionally descoped, not gaps)

02-02-PLAN.md must-haves about Adzuna (adapter, `adzuna_app_id`/`adzuna_app_key` settings and wake keys, three-source poll) were removed by quick task 261021-wez at the user's request. `grep -i adzuna api/*.py` returns nothing; ROADMAP, REQUIREMENTS (SRC-03 is Reed only), COVERAGE.md and 02-04-PLAN.md agree. Treated as descoped.

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `api/watcher.py` (100 lines) | VERIFIED | Substantive and wired: imported by `app.py`, started in `__main__`, `run_fetch` called from both app and `_tick` |
| `api/sources.py` | VERIFIED | `fetch_reed` and `fetch_remotive` both called from `watcher._sources` |
| `api/app.py` | VERIFIED | `WAKE_KEYS`, `/api/fetch`, `/api/watcher`, watcher start |
| `api/test_watcher.py` (15 tests), `api/test_api.py` (31 tests) | VERIFIED | Both run and pass |
| `COVERAGE.md` | VERIFIED | Reed-only, Adzuna recorded as removed |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `app.fetch_now` | `watcher.run_fetch` | acquires `FETCH_LOCK` then calls | WIRED |
| `watcher._sources` | `sources.fetch_reed` | yielded when key saved | WIRED |
| `watcher.run_fetch` | `db.insert_jobs` | inside per-source try | WIRED |
| `app.settings_put` | `watcher.WAKE` | `WAKE_KEYS & body.keys()` | WIRED |
| `app.__main__` | `watcher.start` | debug-aware | WIRED |

### Data-Flow Trace (Level 4)

Reed/Remotive HTTP response -> `fetch_*` job dicts -> `db.insert_jobs` (summarize + score) -> `jobs` table -> `db.list_jobs` -> `GET /api/jobs`. Real data flows end to end; confirmed on the live Reed API (50 reed + 10 remotive rows, sample job "Data Analyst | Harnham ... | https://www.reed.co.uk/jobs/data-analyst/57355215").

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Core logic | `.venv/bin/python api/test_core.py` | ok: 30 tests | PASS |
| API contract incl. Reed fetch, wake rule, 409/200/502 | `.venv/bin/python api/test_api.py` | ok: 31 tests | PASS |
| Watcher, Reed adapter, tick, thread end-to-end | `.venv/bin/python api/test_watcher.py` | ok: 15 tests | PASS |

Each file was run in its own process (see WR-04 below).

### Probe Execution

SKIPPED: no probes declared by the phase.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|--------------|-------------|--------|----------|
| SRC-03 | 02-01, 02-02, 02-03, 02-04 | `fetch_reed` returns jobs using the key saved in settings | SATISFIED | `sources.fetch_reed` + `watcher._sources`; tests + live run |
| WATCH-01 | 02-01, 02-03, 02-04 | Watcher thread polls on the configured interval and keeps running after a source fails | SATISFIED | `watcher._loop/_tick/run_fetch`; failure-isolation tests + live bad-key run |
| WATCH-02 | 02-01, 02-04 | Poll intervals (Gmail 5 min, APIs 60 min) read from settings | SATISFIED | `db.DEFAULTS`, per-tick `api_poll_minutes` read. `gmail_poll_minutes` is stored and defaulted but no Gmail source consumes it until Phase 4 (expected) |

All three phase IDs appear in PLAN frontmatter and are marked `[x]` / Complete in REQUIREMENTS.md. No orphaned Phase 2 requirements: REQUIREMENTS.md maps only SRC-03, WATCH-01, WATCH-02 to Phase 2.

### Anti-Patterns Found

No TBD/FIXME/XXX debt markers in phase files (`grep` on the six files). Code review (02-REVIEW.md) listed 6 warnings and 3 infos; none breaks a must-have, so they are advisory:

| Ref | Issue | Severity | Impact on goal |
|-----|-------|----------|----------------|
| WR-01 | A fully failed poll waits a full `api_poll_minutes` before retry (e.g. Wi-Fi not up at launch) | Warning | SC3 says "next poll runs as normal", which holds; UX cost only |
| WR-02 | Jobs inserted during a concurrent settings save keep a stale score | Warning | Scoring freshness edge case; not a SC |
| WR-03 | Persistent DB error with `WAKE` set can spin the loop | Warning | Edge case on a broken DB |
| WR-04 | `test_api.py` and `test_watcher.py` fail when collected in one process (pytest) | Warning | Each file passes alone; the project runs them as plain scripts |
| WR-05 | `GET /api/settings` returns `reed_api_key` in clear (local-only guard in place) | Warning | Also noted in 02-04 follow-ups; later-phase hardening |
| WR-06 | `reed_api_key` is not trimmed, so pasted whitespace gives a 401 | Warning | Usability only |
| IN-01 | `location`/`min_salary` saves do not wake the watcher (tests assert this deliberately) | Info | Matches plan decision D-04/D-14 |

### Human Verification Required

None outstanding. The plan 02-04 human checkpoint (real Reed key, live API) was approved by the person, with results recorded in 02-04-SUMMARY.md.

### Gaps Summary

No gaps. All four ROADMAP success criteria are implemented in code, wired, covered by passing tests I re-ran, and were observed on the live Reed API. Adzuna-related must-haves are intentionally superseded by quick task 261021-wez. Recommend tracking WR-01, WR-02 and WR-06 (small fixes) and WR-05 (mask the key) as follow-ups before the UI phase, but they do not block Phase 3.

---

_Verified: 2026-10-21_
_Verifier: Claude (gsd-verifier)_
