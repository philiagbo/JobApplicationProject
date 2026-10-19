---
phase: 02-watcher-and-more-sources
plan: 01
subsystem: api
tags: [flask, threading, sqlite, reed, watcher]
requires:
  - phase: 01-core-api
    provides: db.insert_jobs, db.get_settings, sources.fetch_remotive, core scoring
provides:
  - api/watcher.py shared run_fetch, FETCH_LOCK, WAKE, STATUS, tick loop, daemon thread
  - sources.fetch_reed (Basic auth, per-field search, salary text) and get_json headers
  - POST /api/fetch on the shared path with 409 and 502-only-if-all-failed
affects: [02-02 adzuna, 02-03 wake and status endpoint, 02-04 real-key check]
actuals:
  tokens: 4200
  tasks: 2
  commits: 2
plan_head_before: ffee8e87c3d716c85381dcb937d011981732d1b2
plan_head_after: 79a84606d437d097e6dbb92d467800a5406c1a79
tech-stack:
  added: []
  patterns: [one process-wide FETCH_LOCK taken non-blocking, per-tick own sqlite connection, per-source try in run_fetch]
key-files:
  created: [api/watcher.py, api/test_watcher.py]
  modified: [api/sources.py, api/app.py, api/test_api.py]
key-decisions:
  - "Tick returns None when FETCH_LOCK is busy so the watcher stays due and polls after the manual fetch ends"
  - "Watcher started only from the __main__ block (debug off, or WERKZEUG_RUN_MAIN=true child)"
  - "Failure text is exception text only; params, headers and URL never interpolated, so the Reed key cannot leak"
requirements-completed: [SRC-03, WATCH-01, WATCH-02]
duration: 15 min
completed: 2026-10-19
status: complete
---

# Phase 2 Plan 01: Watcher and Reed Summary

Background watcher thread polls Reed and Remotive on startup and every api_poll_minutes (re-read each tick) through one shared run_fetch, which POST /api/fetch also uses behind a single non-blocking lock.

## Accomplishments

- fetch_reed: Basic auth (key plus empty password), one search per career field, locationName and minimumSalary only when set, URL-deduped, SourceError on failures. Salary text reuses core.summarize.
- watcher.py: run_fetch with per-source isolation and in-memory STATUS, _tick/_loop that survive exceptions, idempotent start(), status().
- app.py: run_fetch moved out, 409 when a fetch is running, 502 only when every attempted source failed, watcher started only in `__main__`.
- 14 plain-assert tests in test_watcher.py (including a thread end-to-end test with an injected failing tick); test_api.py moved to a URL-routed fake.

## Task Commits

1. Task 1 (tracer): b771e8c feat(02-01): background watcher with Reed adapter and shared run_fetch
2. Task 2 (tdd): 79a8460 test(02-01): lock watcher rules and Reed adapter behaviour

## Deviations from Plan

None - plan executed exactly as written. Note on TDD for Task 2: the implementation already existed from the Task 1 tracer, so the new tests passed on first run (no RED commit); no behavior needed fixing.

## Verification

- `.venv/bin/python api/test_core.py` ok: 30 tests; `api/test_api.py` ok: 23 tests; `api/test_watcher.py` ok: 14 tests; no Traceback or AssertionError in output.
- All Task 1 and Task 2 acceptance criteria checked and pass; `api/requirements.txt` unchanged.
- Expected console lines ("Remotive/Reed fetch failed: ...") come from failure-path tests logging warnings.

## Known Stubs

None.

## Threat Flags

None. New surface (Reed outbound call, watcher thread) is covered by T-02-01 to T-02-06.

## Self-Check: PASSED

Created files exist (api/watcher.py, api/test_watcher.py); commits b771e8c and 79a8460 exist.
