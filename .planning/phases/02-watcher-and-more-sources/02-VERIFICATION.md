---
phase: 02-watcher-and-more-sources
verified: 2026-10-22T00:00:00Z
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
  - api/test_core.py
  - api/test_watcher.py
  - api/watcher.py
covered_digest: "v2:sha256:a3db8c37a595337279db6dada59d2caa8090a899cde9c7f531a8dd8d2e77956a"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 4/4
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 2: Watcher and More Sources Verification Report

**Phase Goal:** The job feed refreshes itself in the background from Remotive and Reed
**Verified:** 2026-10-22
**Status:** passed
**Re-verification:** Yes. The prior report went stale after code-review fix commits 4fba2ac..6b79251 changed `api/watcher.py`, `api/app.py`, `api/db.py` and the tests. This pass re-read the current code and re-ran the tests; it checked that no fix broke a must-have.

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | After saving a Reed key, Reed jobs appear in `GET /api/jobs`, scored and deduplicated | VERIFIED | `watcher._sources` yields `sources.fetch_reed(...)` when `reed_api_key` is set. `run_fetch` calls `db.insert_jobs`, which scores and dedupes on URL. `PUT /api/settings` sets `watcher.WAKE` for `reed_api_key`, `career_fields`, `location` and `min_salary` (`app.py` `WAKE_KEYS`). WR-05 masks the key in GET and PUT responses. PUT still saves a real key, and `run_fetch` reads the real key from the DB through `get_settings` (not `public()`), so Reed still works. `test_fetch_reed_jobs_scored_and_deduped` and `test_settings_key_masked_and_echo_keeps_real_key` pass. Live check in 02-04 (human-approved): 50 Reed jobs, second fetch added 0. |
| 2 | With the app running and nothing triggering a fetch, new jobs appear on the configured poll interval | VERIFIED | `app.py` `__main__` calls `watcher.start()` (daemon thread, own `db.connect()` per tick, settings re-read each tick). `test_tick_polls_immediately` and `test_watcher_thread_end_to_end` pass (real thread, no request). WR-04 now stops that thread at test end. That changes the test only, not the production path. |
| 3 | When one source fails, the watcher logs it, other sources still deliver, next poll runs as normal | VERIFIED | `run_fetch` keeps a per-source try (`SourceError` -> `log.warning`, other `Exception` -> `log.exception`) and records `STATUS[name].ok=false`. `_loop` catches tick exceptions. WR-03 changed the failure path to `time.sleep(TICK_SECONDS); continue`, so the thread survives and does not spin on a set `WAKE`. WR-01 retries a failed poll after `min(RETRY_SECONDS=300, interval)` rather than waiting a full interval. That makes recovery faster and does not break "next poll runs as normal". `test_failing_source_isolated_and_retried`, `test_unexpected_source_error_isolated`, `test_failed_poll_retried_soon`, `test_failing_tick_with_wake_set_does_not_spin` and `test_failure_text_never_contains_key` pass. |
| 4 | Intervals default to Gmail 5 min and APIs 60 min; changing them changes the cadence | VERIFIED | `db.DEFAULTS` has `gmail_poll_minutes: 5` and `api_poll_minutes: 60`. `_tick` reads `api_poll_minutes` from settings every tick. The retry backdating clamps with `min(RETRY_SECONDS, interval)`, so a 1-minute interval is still honoured. `test_poll_interval_defaults` and `test_interval_change_applies_without_restart` (sleep margin widened by IN-03) pass. Saves of intervals alone do not wake the watcher (`test_settings_save_wakes_watcher`). They apply on the next tick. |

**Score:** 4/4 truths verified, 0 present-but-behavior-unverified. Every behavior-dependent truth (failure isolation, retry timing, interval change, wake-on-save, non-spinning failure path) has a passing test that exercises the transition.

### Review-fix regression check (4fba2ac..6b79251)

| Fix | Touches must-have | Result |
|-----|-------------------|--------|
| WR-01 retry after failure (`_tick` returns a backdated value) | SC3, SC4, 02-01 truth "tick re-reads `api_poll_minutes`" | No break. Success returns `started` (full interval). Error returns `started - interval + min(300, interval)`. No career fields still returns `last` untouched, so zero source calls. Lock-busy still returns `None`. |
| WR-02 re-read settings before `insert_jobs` | SC1 scoring, dedupe | No break. Sources still come from the caller's snapshot. The latest settings only affect scoring. `test_settings_saved_during_fetch_are_used_for_scoring` passes. |
| WR-03 failed tick sleeps then continues | SC3 ("watcher keeps running") | No break. The thread survives a tick exception. |
| WR-04 test isolation | Test harness only | `pytest -q` in `api/` passes: 80 tests. |
| WR-05 masked key in GET/PUT | 02-03 truth "no endpoint contains a saved key"; SC1 | Strengthens the key-never-leaks truth. `fetch_now` and the watcher read the DB. Echoing the mask in PUT drops the field, so the real key is not overwritten and the watcher is not woken. Edge: clearing the key with `""` still saves when a key is set. |
| WR-06 strip text settings | SC1 (a pasted key with whitespace is accepted) | `db._clean` returns `value.strip()` for text settings. `test_text_settings_are_stripped` passes. |
| IN-01 `location` and `min_salary` in `WAKE_KEYS` | 02-03 truth that interval, `min_salary`, `location` and `excluded_words` saves do not wake | The 02-03 plan text said `min_salary` and `location` do not wake. The review changed that deliberately because both change the Reed query. The roadmap criteria are unaffected, and the test was updated to the new contract. This is documented plan drift, not a gap. Interval and `excluded_words` saves still do not wake. |
| IN-02 and IN-03 test hygiene and timing | None | Pass. |

### Plan must-haves (non-Adzuna)

| Must-have | Status | Evidence |
|-----------|--------|----------|
| `fetch_reed`: Basic auth (key + empty password), per-field search, `locationName` only if set, `minimumSalary` only if > 0, `resultsToTake` 50, merge by `jobUrl`, `SourceError` on failure | VERIFIED | `api/sources.py`; `test_reed_request_params`, `test_reed_mapping_and_salary`, `test_reed_failures_raise_source_error` pass |
| Watcher and `POST /api/fetch` share `run_fetch` under one `FETCH_LOCK`; 409 when held; 502 only if every attempted source failed | VERIFIED | `app.fetch_now`; the `result["errors"] and not result["by_source"]` check gives 502 only on total failure. Contract tests pass. |
| Reed skipped silently with no key | VERIFIED | `_sources` conditional; `test_reed_skipped_without_key` |
| Importing `app` never starts the watcher; `__main__` starts it once (debug child only) | VERIFIED | `app.py` `__main__` block; `test_import_does_not_start_watcher` |
| Key never in STATUS / errors / logs / `GET /api/watcher` / `GET /api/settings` | VERIFIED | `watcher_status` reads in-memory STATUS only; settings responses are masked via `public()`; `test_failure_text_never_contains_key`. I did not read any real key values. |
| `GET /api/watcher` returns `{running, fetching, sources}` | VERIFIED | `watcher.status()` |
| No career fields -> tick makes zero source calls | VERIFIED | `_tick` early return after `WAKE.clear()`; `test_tick_quiet_without_fields` |
| Settings save wakes the watcher only for accepted saves | VERIFIED | `db.save_settings` raises `ValueError` -> 400 before `WAKE.set()`; `test_settings_save_wakes_watcher` |

### Superseded (intentionally descoped, not gaps)

The 02-02-PLAN.md must-haves about Adzuna were removed by quick task 261021-wez. `grep -i adzuna api/*.py` returns nothing. 02-03-PLAN.md still mentions Adzuna keys in one truth, which is the same descoped item.

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `api/watcher.py` | VERIFIED | Substantive and wired. `app.py` imports it and calls `watcher.start()`, `watcher.run_fetch`, `watcher.WAKE`, `watcher.FETCH_LOCK` and `watcher.status()`. |
| `api/sources.py` | VERIFIED | `fetch_reed` and `fetch_remotive` are both called from `watcher._sources`. |
| `api/app.py` | VERIFIED | `WAKE_KEYS`, `/api/fetch`, `/api/watcher`, `mask`/`public`, watcher start. |
| `api/db.py` | VERIFIED | Interval defaults, text strip, `insert_jobs`, `rescore_new`. |
| `api/test_core.py` (30), `api/test_api.py` (32), `api/test_watcher.py` (18) | VERIFIED | All pass. |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `app.fetch_now` | `watcher.run_fetch` | acquires `FETCH_LOCK` then calls | WIRED |
| `watcher._sources` | `sources.fetch_reed` | yielded when key saved | WIRED |
| `watcher.run_fetch` | `db.insert_jobs` | inside per-source try, with fresh `db.get_settings` | WIRED |
| `app.settings_put` | `watcher.WAKE` | `WAKE_KEYS & body.keys()` | WIRED |
| `app.__main__` | `watcher.start` | debug-aware | WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `GET /api/jobs` | rows from `db.list_jobs` | `db.insert_jobs` from Remotive and Reed (live Reed check approved in 02-04) | Yes | FLOWING |
| `GET /api/watcher` | `STATUS` | written by `run_fetch` per source | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Core logic | `.venv/bin/python api/test_core.py` | `ok: 30 tests` | PASS |
| API contract | `.venv/bin/python api/test_api.py` | `ok: 32 tests` | PASS |
| Watcher behaviour | `.venv/bin/python api/test_watcher.py` | `ok: 18 tests` | PASS |
| All files in one process | `cd api && ../.venv/bin/python -m pytest -q` | 80 passed, 2 warnings (deliberate `SystemExit` ending test threads) | PASS |

The "Reed fetch failed: down" lines in the output are logs from the failure-isolation tests.

### Probe Execution

SKIPPED: no `probe-*.sh` declared or present.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|--------------|-------------|--------|----------|
| SRC-03 | 02-01, 02-02, 02-03, 02-04 | `fetch_reed` returns jobs using the key saved in settings | SATISFIED | `sources.fetch_reed`, wired through `_sources`. Tests pass and the live check was approved. Adzuna is descoped, and REQUIREMENTS.md SRC-03 is Reed only. |
| WATCH-01 | 02-01, 02-03, 02-04 | A watcher thread polls the APIs on the configured interval and keeps running after a source fails | SATISFIED | `watcher._loop` and `_tick`; isolation, retry and tick-failure survival tests pass |
| WATCH-02 | 02-01, 02-04 | Poll intervals (Gmail 5 min, APIs 60 min by default) are read from settings | SATISFIED | `db.DEFAULTS`, `_tick` re-reads each tick; tests pass |

All IDs in the plan frontmatter (SRC-03, WATCH-01, WATCH-02) appear in REQUIREMENTS.md (lines 30-32, traceability rows 102-104). No orphaned requirements are mapped to Phase 2.

### Anti-Patterns Found

None. `TBD|FIXME|XXX|TODO` grep over `api/watcher.py`, `api/sources.py`, `api/app.py` and `api/db.py` returned no matches.

### Human Verification Required

None outstanding. The 02-04 live Reed check was human-approved earlier. REVIEW-FIX marks WR-01, WR-02, WR-03 and WR-05 "requires human verification", but each has a passing test that exercises the changed logic and I re-read the code. One note for later phases: a future settings UI must send `reed_api_key` only when the user types a new one. Sending the mask back is tolerated, because PUT drops the exact mask echo.

### Gaps Summary

No gaps. All 4 roadmap success criteria are verified against current code, the review fixes preserve every must-have, and all three requirement IDs are satisfied. The only plan drift is IN-01, where `location` and `min_salary` saves now also wake the watcher, which is an intentional improvement.

---

_Verified: 2026-10-22_
_Verifier: Claude (gsd-verifier)_
