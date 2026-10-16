---
phase: 01-data-scoring-and-first-source
plan: 01
subsystem: api
tags: [flask, sqlite3, remotive, urllib]
requires: []
provides:
  - SQLite schema (jobs, answers, unanswered, settings) created on import of api/app.py
  - core.normalise / summarize / score with fixed signatures
  - sources.fetch_remotive (keyless, rate-spaced, deduped by URL)
  - GET/PUT /api/settings, POST /api/fetch, GET /api/jobs, app.run_fetch
affects: [01-02, 01-03, phase-2-watcher]
tech-stack:
  added: []
  patterns: [stdlib urllib instead of requests, per-app-context sqlite connection on flask.g, JOBHELPER_DB env override]
key-files:
  created: [api/db.py, api/core.py, api/sources.py, api/test_api.py]
  modified: [api/app.py]
key-decisions:
  - "stdlib urllib for HTTP; api/requirements.txt unchanged"
  - "Remotive throttle is a process-wide lock plus monotonic gap (31 s)"
status: complete
commits: 2
plan_head_before: b61fad68432366e1bc25d85260031456a3285020
plan_head_after: 1cc50d1392e5cb7c5e55a1845bd1dbedd0dd5b80
actuals:
  tokens: 9000
  tasks: 2
  commits: 2
requirements-completed: [DATA-01, DATA-02, DATA-04, DATA-06, SCORE-01, SRC-01, SRC-02]
---

# Phase 1 Plan 01: Data, scoring and first source Summary

Keyless Remotive fetch feeds a scored, URL-deduplicated SQLite store, served ranked via Flask with validated settings and an offline regression test.

## Tasks

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | Tracer: save field, fetch Remotive, ranked jobs | 539fd6c |
| 2 | Validation, 400/502 errors, offline test | 1cc50d1 |

## Verification

- Live e2e (one real Remotive request): `200 {'by_source': {'remotive': 15}, 'new': 15}`, `e2e ok 15`.
- `api/test_api.py`: `ok: 10 tests`.
- Interpreter: main checkout venv (Python 3.9.6), since the worktree has no `.venv`.

## Deviations from Plan

None - plan executed exactly as written. The tracer gate was satisfied by the Task 1 end-to-end verify, which passed before Task 2.

## Known Stubs

`core.summarize` returns None / [] for salary_annual, currency, years_experience and both bullet lists, and `core.score` applies only the title rule. Intentional: plan 01-02 completes them within the same functions.

## Threat Flags

None.

## Self-Check: PASSED

api/db.py, api/core.py, api/sources.py, api/test_api.py exist; commits 539fd6c and 1cc50d1 exist.
