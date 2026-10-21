---
phase: 02-watcher-and-more-sources
reviewed: 2026-10-21T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - api/app.py
  - api/db.py
  - api/sources.py
  - api/test_api.py
  - api/test_watcher.py
  - api/watcher.py
findings:
  critical: 0
  warning: 6
  info: 3
  total: 9
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-10-21
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

The watcher, Reed source, wake-on-save and `GET /api/watcher` are mostly sound. Reed errors are built from the exception only, so the key does not leak into error text or `/api/watcher`. The local-only guard handles DNS rebinding and cross-site requests. Each test file passes when run on its own (31 and 15 tests). I found no blockers. I found six warnings, the most practically important being a missed-retry after failed polls, a stale-score race with settings saves, and test files that break each other when run in one process.

## Structural Findings (fallow)

None provided.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: A failed poll is not retried for a full `api_poll_minutes`

**File:** `api/watcher.py:70-75`
**Issue:** `_tick` returns `started` after `run_fetch` whatever the outcome. If every source fails (network down at launch, Reed 5xx, bad key), the next automatic poll is `api_poll_minutes` later, 60 minutes by default. For an app launched by double-click on a home PC, "Wi-Fi not up yet at startup" is the common case. It leaves the user with an empty list for an hour. The test named `test_failing_source_isolated_and_retried` only proves the retry through a manual `WAKE.set()`.
**Fix:** Back off to a short retry when the poll had errors, without hammering Remotive (it has a 31 s gap):
```python
RETRY_SECONDS = 300
result = run_fetch(conn, settings)
...
if result["errors"]:
    return started - settings["api_poll_minutes"] * SECONDS_PER_MINUTE + RETRY_SECONDS
return started
```

### WR-02: Jobs fetched during a settings save can keep a stale score for good

**File:** `api/watcher.py:61,72`, `api/app.py:78-81`, `api/db.py:122-137`
**Issue:** `_tick` snapshots `settings` before the fetch. A fetch can take minutes, because Remotive sleeps 31 s per career field while holding FETCH_LOCK. If the user saves settings meanwhile (for example changing `career_fields`), `rescore_new` only rescores rows that already exist. When the in-flight fetch finishes, `insert_jobs` inserts rows scored with the old settings. The re-poll triggered by `WAKE` returns the same URLs, and `INSERT OR IGNORE` skips them, so they are never rescored until the next settings save. The comment on `WAKE.clear()` ("a save during it triggers another poll") only covers fetching again. It does not cover the scoring.
**Fix:** In `_tick`, after `run_fetch`, if `WAKE.is_set()` was set during the fetch, call `db.rescore_new(conn, db.get_settings(conn))`. Alternatively, re-read settings inside `run_fetch` just before `insert_jobs`:
```python
counts[name] = db.insert_jobs(conn, call(), db.get_settings(conn))
```

### WR-03: Persistent error in `_tick` while `WAKE` is set becomes a busy loop

**File:** `api/watcher.py:58-63,80-87`
**Issue:** `WAKE.clear()` happens only after `db.connect()` and `db.get_settings()` succeed. If either fails persistently (locked or corrupt DB, a bad JSON value in `settings`) while `WAKE` is set, `_loop` logs the traceback and calls `WAKE.wait(TICK_SECONDS)`. That returns immediately because the event is still set. The thread then spins at full speed and floods the log until the DB recovers. The end-to-end test injects one transient failure, so it never sees this.
**Fix:** Clear the event in `_loop` rather than only on the happy path, or sleep unconditionally after an exception:
```python
except Exception:
    log.exception("Watcher tick failed")
    time.sleep(TICK_SECONDS)
    continue
```

### WR-04: `test_api.py` and `test_watcher.py` break each other when run in one process

**File:** `api/test_api.py:17,76`, `api/test_watcher.py:17-18,43`
**Issue:** Each file installs a different `sources.get_json` fake at import time, and each uses its own module-level `FAIL` and `calls`. Under `pytest` from `api/`, both modules are collected first and the later import (`test_watcher`) wins. I ran `pytest -q` in `api/`: 13 failures in `test_api.py` (`test_fetch_dedupes`, `test_jobs_listing`, `test_fetch_reed_jobs_scored_and_deduped`, `test_fetch_all_sources_failed_is_502` and others). Each file passes alone (31 and 15). `test_watcher_thread_end_to_end` also leaves a daemon thread polling for the rest of the process. `test_watcher_status_endpoint_empty` assumes `running` is False, which fails if the watcher test runs first. Nothing documents that the files must be run separately.
**Fix:** Move the fakes into per-test or per-fixture setup (patch `sources.get_json` inside `fresh()` / `fresh_client()` and restore it afterwards), or document and enforce one process per file in a test runner or CI step.

### WR-05: `GET /api/settings` returns `reed_api_key` in plain text (verified, classified low-severity)

**File:** `api/app.py:65-67`, `api/test_api.py:116-119`
**Issue:** Verified: `get_settings` returns the stored value untouched, and `test_settings_keys_returned_in_full` asserts it. It is mitigated: the `local_only` guard rejects non-local `Host` values (DNS rebinding) and non-local `Origin` values, and the server binds `127.0.0.1`. A cross-site page cannot read the response, and the project accepts a single trusted local user. It is still a secret that any local process or browser extension can read with one request, and it is written to the DB in clear text. The UI only needs to know whether a key is set, and to overwrite it. `/api/watcher` and the error paths do not leak it, which is good.
**Fix:** Defence in depth: return a masked value (`"•••• " + key[-4:]`, or a `reed_api_key_set` boolean) and treat an empty or unchanged mask on PUT as "keep current". Keyring storage (already planned in PLAN.md) is the longer-term fix. If the full value is kept deliberately, record that decision next to the test.

### WR-06: `reed_api_key` is not trimmed, so a pasted key with whitespace silently fails

**File:** `api/db.py:98-100`, `api/sources.py:81`
**Issue:** `_clean` accepts any string for text settings and does not strip it. A key copied with a trailing space or newline is Base64-encoded into the `Authorization` header as is. Reed answers 401, and the user sees only "Reed fetch failed: HTTP Error 401" with no hint at the cause.
**Fix:** Strip text settings in `_clean`:
```python
return value.strip()
```

## Info

### IN-01: `location` and `min_salary` saves do not wake the watcher

**File:** `api/app.py:13-14`
**Issue:** Both settings change the Reed query (`locationName`, `minimumSalary`), but `WAKE_KEYS` leaves them out. The tests assert this on purpose (`test_settings_save_wakes_watcher`). A new location only takes effect at the next hourly poll or a manual fetch. Confirm this is intended, or add them to `WAKE_KEYS` and update the test.
**Fix:** `WAKE_KEYS = frozenset({"reed_api_key", "career_fields", "location", "min_salary"})` if immediate refresh is wanted.

### IN-02: Test helpers leave SQLite connections open

**File:** `api/test_api.py:89-91,96,204-206,209-211`
**Issue:** `with db.connect() as conn:` only commits or rolls back. It does not close the connection. The handles linger until garbage collection. This is harmless on macOS. On the Windows target, an open handle can make temp-file cleanup noisy. `test_watcher.py` already uses `contextlib.closing`.
**Fix:** Use `with contextlib.closing(db.connect()) as conn:`, as `test_watcher.py` does.

### IN-03: Timing-dependent assertions in the watcher tests

**File:** `api/test_watcher.py:149-161,244-281`
**Issue:** `test_interval_change_applies_without_restart` relies on `time.sleep(0.02)` against a `SECONDS_PER_MINUTE = 0.01` override. The end-to-end test uses a 5 s wall-clock polling deadline. Both can flake on a slow CI box or a loaded Windows PC.
**Fix:** Widen the margins (for example sleep 0.1 s) or inject a fake clock into `_tick`.

---

_Reviewed: 2026-10-21_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
