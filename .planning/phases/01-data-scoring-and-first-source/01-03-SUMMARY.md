---
phase: 01-data-scoring-and-first-source
plan: 03
subsystem: api
tags: [flask, sqlite3, errorhandler, local-only]
requires: [01-01]
provides:
  - db.STATUSES, TRANSITIONS, set_status, stats, rescore_new
  - POST /api/jobs/<id>/<dismiss|queue|undo>, GET /api/jobs?status=, GET /api/stats
  - JSON error handlers for every /api failure, local-only before_request guard
key-files:
  modified: [api/app.py, api/db.py, api/test_api.py]
key-decisions:
  - "Stats count by current status within a 7-day window (ponytail note: events table if history is needed)"
  - "Flask logger silenced only inside the 500 test so expected traceback stays out of test output"
status: complete
commits: 3
plan_head_before: 0790179505bb817052df445e3c42e3dbf1b64eb6
plan_head_after: 9d9137554e6e7f6da3eb3d8568d96b7727d6dff7
actuals:
  tokens: 9000
  tasks: 3
  commits: 3
requirements-completed: [DATA-02, DATA-03, DATA-04, DATA-05, DATA-06]
---

# Phase 1 Plan 03: Actions, stats and error handling Summary

Dismiss/queue/undo with atomic guarded UPDATEs, rolling 7-day per-source stats, re-scoring of new jobs on settings save, JSON errors on every API failure, and a local-only guard with the debugger off by default.

## Tasks

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | Dismiss, queue, undo and ?status= listing | e810422 |
| 2 | Weekly stats and re-score on settings save | 6a6cced |
| 3 | JSON errors everywhere and local-only guard | 9d91375 |

## Verification

- `api/test_api.py` (main checkout venv, Python 3.9.6): `ok: 23 tests`.
- `grep -c 'debug=True' api/app.py` prints 0.
- Tests assert score direction only, so they hold under both the 01-01 and 01-02 core.py. Not re-run against merged 01-02 (parallel plan).

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None. T-01-08 to T-01-12 mitigations implemented as planned.

## Self-Check: PASSED

api/app.py, api/db.py, api/test_api.py modified; commits e810422, 6a6cced, 9d91375 exist.
