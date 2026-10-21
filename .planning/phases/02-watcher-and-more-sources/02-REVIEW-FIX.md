---
phase: 02-watcher-and-more-sources
fixed_at: 2026-10-22T00:00:00Z
review_path: .planning/phases/02-watcher-and-more-sources/02-REVIEW.md
iteration: 1
findings_in_scope: 9
fixed: 9
skipped: 0
status: all_fixed
---

# Phase 2: Code Review Fix Report

**Fixed at:** 2026-10-22
**Source review:** .planning/phases/02-watcher-and-more-sources/02-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 9 (fix_scope all)
- Fixed: 9
- Skipped: 0

**Verification:** WR-01..WR-06 were run in an isolated git worktree after every fix, then again in the main checkout after the fast-forward. IN-01..IN-03 were fixed and verified directly in the main checkout (no worktree). Each file in its own process: `test_core.py` 30, `test_api.py` 32, `test_watcher.py` 18, all printing `ok: N tests`, final run after IN-03. `pytest -q api/` (both files in one process) also passes, 80 tests, so the WR-04 collision is gone.

## Fixed Issues

### WR-01: A failed poll is not retried for a full `api_poll_minutes`

**Files modified:** `api/watcher.py`, `api/test_watcher.py`
**Commit:** 4fba2ac
**Applied fix:** Added `RETRY_SECONDS = 300`. When `run_fetch` reports errors, `_tick` backdates its return value so the next poll is due in `min(RETRY_SECONDS, interval)` seconds. A clean poll still waits the full interval. New test `test_failed_poll_retried_soon`.
**Status:** fixed: requires human verification (timing/logic change)

### WR-02: Jobs fetched during a settings save can keep a stale score

**Files modified:** `api/watcher.py`, `api/test_watcher.py`
**Commit:** d79f668
**Applied fix:** `run_fetch` now reads `db.get_settings(conn)` after `call()` returns and just before `insert_jobs`, so jobs are scored with the latest settings. Sources are still chosen from the caller's snapshot. This also covers the manual `/api/fetch` path. A tiny window remains between that read and the insert. New test `test_settings_saved_during_fetch_are_used_for_scoring`, which I confirmed fails without the fix.
**Status:** fixed: requires human verification (logic change)

### WR-03: Persistent error in `_tick` while `WAKE` is set becomes a busy loop

**Files modified:** `api/watcher.py`, `api/test_watcher.py`
**Commit:** d190d38
**Applied fix:** After a failed tick, `_loop` does `time.sleep(TICK_SECONDS)` and `continue` instead of `WAKE.wait`, so a set event cannot spin the thread. New test `test_failing_tick_with_wake_set_does_not_spin`, which I confirmed fails without the fix (477,734 iterations in 0.3 s).
**Status:** fixed: requires human verification (logic change)

### WR-04: `test_api.py` and `test_watcher.py` break each other when run in one process

**Files modified:** `api/test_api.py`, `api/test_watcher.py`
**Commit:** e03796b
**Applied fix:** `fresh_client()` and `fresh()` now re-install their own `sources.get_json` fake. The end-to-end watcher test now stops its daemon thread at the end (swaps `_tick` for one that exits, joins, resets `watcher._thread`), so it cannot poll other tests' databases and `running` is False again afterwards. `pytest -q` in `api/` and `pytest test_watcher.py test_api.py` both pass. pytest prints 2 `PytestUnhandledThreadExceptionWarning` warnings for the deliberate `SystemExit` used to end the test threads. They are harmless.

### WR-05: `GET /api/settings` returns `reed_api_key` in plain text

**Files modified:** `api/app.py`, `api/test_api.py`
**Commit:** 3ae09bd
**Applied fix:** GET and PUT responses now return a masked key (`mask()` and `public()` in `app.py`): empty when unset, four bullets plus the last four characters for keys longer than 8 characters, and 8 bullets for shorter keys. PUT still accepts a real key. If the body's `reed_api_key` equals the current mask, it is dropped from the save, so a form that echoes the GET response cannot overwrite the real key (and does not wake the watcher). `/api/fetch` and the watcher read the real key from the DB. Replaced `test_settings_keys_returned_in_full` with `test_settings_key_masked_and_echo_keeps_real_key`.
**Status:** fixed: requires human verification (behaviour change; any future UI must send the key only when the user types a new one)

### WR-06: `reed_api_key` is not trimmed

**Files modified:** `api/db.py`, `api/test_api.py`
**Commit:** a8ba54e
**Applied fix:** `_clean` returns `value.strip()` for text settings (`reed_api_key` and `location`). New test `test_text_settings_are_stripped`.

### IN-01: `location` and `min_salary` saves do not wake the watcher

**Files modified:** `api/app.py`, `api/test_api.py`
**Commit:** 4a593b0
**Applied fix:** Added `location` and `min_salary` to `WAKE_KEYS`, since both change the Reed query. `test_settings_save_wakes_watcher` now expects them to wake the watcher; `api_poll_minutes`, `gmail_poll_minutes` and `excluded_words` still do not.

### IN-02: Test helpers leave SQLite connections open

**Files modified:** `api/test_api.py`
**Commit:** 2edc528
**Applied fix:** The five `with db.connect() as conn:` helpers use `contextlib.closing(db.connect())`. The write helper `sql()` uses `with contextlib.closing(db.connect()) as conn, conn:` so it still commits before closing.

### IN-03: Timing-dependent assertions in the watcher tests

**Files modified:** `api/test_watcher.py`
**Commit:** 6b79251
**Applied fix:** `test_interval_change_applies_without_restart` sleeps 0.1 s instead of 0.02 s, and the two 5 s polling deadlines in the end-to-end test are 15 s. No fake clock was added. The 0.3 s spin-detection window in the WR-03 test was left as is, since its bound (under 20 ticks, against thousands if it spun) is loose.

---

_Fixed: 2026-10-22_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
