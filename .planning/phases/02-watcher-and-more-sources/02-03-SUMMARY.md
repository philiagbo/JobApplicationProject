---
phase: 02-watcher-and-more-sources
plan: 03
subsystem: api
tags: [flask, watcher, settings, status-endpoint]
requires:
  - phase: 02-watcher-and-more-sources
    provides: watcher.WAKE, FETCH_LOCK, STATUS, status(), run_fetch (plan 02-01)
provides:
  - WAKE_KEYS and a watcher wake in PUT /api/settings (D-14)
  - GET /api/watcher returning in-memory per-source status (D-10)
  - Integration tests locking the manual POST /api/fetch contract (409, partial 200, all-failed 502, no-key skip)
affects: [02-04 real-key check, later UI that reads /api/watcher]
actuals:
  tokens: 1450
  tasks: 2
  commits: 4
plan_head_before: 545fdfbe5fcd8bee724a36b42262d14814eb336d
plan_head_after: aa665c176eddd33c2752ab2baa8fc95596960c22
tech-stack:
  added: []
  patterns: [wake computed from request keys not old/new diff, status endpoint reads memory only]
key-files:
  created: []
  modified: [api/app.py, api/test_api.py]
key-decisions:
  - "Wake is computed from the keys present in the PUT body, so an unchanged re-save may trigger one extra poll (accepted)"
  - "Interval, min_salary, location and excluded_words saves do not wake; the watcher re-reads intervals every tick"
  - "GET /api/watcher returns watcher.status() only and never touches settings, so a saved key cannot leak"
requirements-completed: [SRC-03, WATCH-01]
coverage:
  - id: D1
    description: "Saving a key or career fields wakes the watcher; interval, filter and rejected saves do not"
    requirement: "WATCH-01"
    verification:
      - kind: integration
        ref: "api/test_api.py#test_settings_save_wakes_watcher, test_rejected_settings_save_does_not_wake"
        status: pass
    human_judgment: false
  - id: D2
    description: "GET /api/watcher shows per-source last poll, success and error, behind the local-only guard, without keys"
    requirement: "WATCH-01"
    verification:
      - kind: integration
        ref: "api/test_api.py#test_watcher_status_endpoint_empty, test_fetch_partial_failure_is_200"
        status: pass
    human_judgment: false
  - id: D3
    description: "Manual fetch contract: Reed jobs scored and deduped, 409 busy, partial failure 200, all-failed 502, silent Reed skip without key"
    requirement: "SRC-03"
    verification:
      - kind: integration
        ref: "api/test_api.py#test_fetch_reed_jobs_scored_and_deduped, test_fetch_partial_failure_is_200, test_fetch_all_sources_failed_is_502, test_fetch_busy_is_409, test_fetch_skips_reed_without_key"
        status: pass
    human_judgment: false
duration: 6 min
completed: 2026-10-19
status: complete
---

# Phase 2 Plan 03: Watcher Wake and Status Endpoint Summary

PUT /api/settings now wakes the watcher when a source key or career fields are saved, GET /api/watcher exposes per-source poll status from memory, and the manual fetch contract is locked by integration tests.

## Accomplishments

- `WAKE_KEYS` (reed_api_key, adzuna_app_id, adzuna_app_key, career_fields) and `watcher.WAKE.set()` in `settings_put`, after a successful save only; rejected saves return 400 before any wake.
- `GET /api/watcher` (`watcher_status`) returns `watcher.status()`; it is covered by the existing local-only guard (foreign Origin gets 403).
- 8 new tests in `api/test_api.py` (23 to 31). The fetch contract needed no change to `fetch_now`: the 02-01 implementation already satisfied all six fetch tests.

## Task Commits

1. Task 1 RED: f21a952 test(02-03): failing tests for settings save waking the watcher
2. Task 1 GREEN: de73adb feat(02-03): saving keys or career fields wakes the watcher
3. Task 2 RED: 147f46f test(02-03): failing tests for watcher status endpoint and fetch contract
4. Task 2 GREEN: aa665c1 feat(02-03): GET /api/watcher exposes per-source status

## Deviations from Plan

None - plan executed exactly as written. Note: in Task 2 only the status-endpoint test failed at RED (404); the five fetch-contract tests passed immediately because 02-01 already implemented that behavior, so they act as lock-in tests.

## Verification

- `api/test_core.py` ok: 30 tests; `api/test_api.py` ok: 31 tests; `api/test_watcher.py` ok: 21 tests.
- All acceptance criteria for both tasks pass (greps and test counts at least 25 and 31).
- Console lines such as "Reed fetch failed: down" come from failure-path tests logging warnings.

## Known Stubs

None.

## Threat Flags

None. T-02-11 (no key in /api/watcher or fetch responses) is asserted in test_fetch_partial_failure_is_200; T-02-12 (local-only guard) in test_watcher_status_endpoint_empty; T-02-13 by the single WAKE Event and FETCH_LOCK 409.

## Self-Check: PASSED

api/app.py and api/test_api.py modified; commits f21a952, de73adb, 147f46f, aa665c1 exist.
