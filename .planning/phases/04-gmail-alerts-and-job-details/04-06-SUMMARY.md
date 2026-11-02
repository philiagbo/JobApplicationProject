---
phase: 04-gmail-alerts-and-job-details
plan: 06
subsystem: api
tags: [playwright, browser-thread, details, retry, queue]
requires:
  - phase: 04-gmail-alerts-and-job-details
    provides: "sources.fetch_details, judge_page, get_page and the details worker (04-03); playwright pinned (04-01)"
provides:
  - "api/browser.py: the single 'browser' daemon thread fed by a queue.Queue, submit(fn) -> Future, headless Edge-then-Chrome launch, read-only fetch_page"
  - "fetch_details retries once in the browser before 'blocked' (DETAIL-02)"
affects: [05-autofill]
tech-stack:
  added: []
  patterns:
    - "one thread owns Playwright; callers get a concurrent.futures.Future"
    - "tests replace browser.fetch_page / browser._start_playwright; fake Playwright objects record every call"
key-files:
  created: [api/browser.py]
  modified: [api/sources.py, api/test_details.py, api/test_watcher.py]
key-decisions:
  - "submit(fn) hands fn the Playwright object (fn(pw)); Phase 5 adds its own task functions on the same queue"
  - "A missing Edge/Chrome is remembered for the process (_unavailable); installing one needs an app restart"
  - "Test isolation: fresh() in test_details installs a raising no_browser fake as browser.fetch_page; only the live test and the fake-based tests reach a browser"
metrics:
  duration: "~20 min"
  completed: 2026-11-01
status: complete
requirements-completed: [DETAIL-02]
actuals:
  tokens: 5000
  tasks: 2
  commits: 0
plan_head_before: 9f2cb0c
commits: "uncommitted - pending user approval"
---

# Phase 4 Plan 06: One Playwright browser thread and the single DETAIL-02 retry Summary

A job page urllib cannot read (blocked status, challenge text, under 200 characters, network error, or a page filled in by JavaScript) is now retried exactly once in the installed Edge or Chrome, headless, on a single lazily started `browser` thread; if the browser's page also fails the D-16 rules the job is `blocked`.

## Tasks

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | Tracer: JS-rendered page becomes `ok` through the real browser thread, 403 stays `blocked` | uncommitted, pending user approval |
| 2 | Fakes-based rules: one thread, Futures, lazy start, channel order and memo, read-only page task, one retry, never LinkedIn/Indeed | uncommitted, pending user approval |

Both tasks share the same files, so code and all tests were written in one pass.

## Files

- `api/browser.py` (new): `BrowserUnavailable`, `Error` (re-exported), `CHANNELS`, `GOTO_TIMEOUT_MS` 20000, `IDLE_TIMEOUT_MS` 5000, `RESULT_TIMEOUT_SECONDS` 60, `_q`, `_thread`, `_lock`, `_unavailable`, `_start_playwright`, `_run`, `submit`, `launch_headless`, `_load_page`, `fetch_page`. Importing starts nothing. The page task only goto, wait_for_load_state, content and close; the post-navigation URL is re-checked with `core.http_url`. No user-agent override or launch args.
- `api/sources.py`: `fetch_details` calls `browser.fetch_page(url)` once when `judge_page` rejects the urllib result; `BrowserUnavailable`, `browser.Error`, `concurrent.futures.TimeoutError`, `OSError` give `("", "blocked")`.
- `api/test_details.py`: `reset_browser`, `no_browser`, `FakeResponse/Page/Browser/Chromium/PW`, fixture pages `/js` and `/403`, `test_browser_retry_live` and the 11 rule tests (26 -> 38 tests).
- `api/test_watcher.py`: `no_browser` installed as `browser.fetch_page` at import and in `fresh()` (still 18 tests).

## Verification

Run with `.venv/bin/python` (Python 3.9, Mac with Google Chrome.app; no Edge): `test_details` ok: 38 tests and prints `live browser: ok`; `test_watcher` ok: 18; `test_api` ok: 60; `test_core` ok: 75; `test_gmail` ok: 31. Negative greps (no page interaction calls, no `user_agent=`/`args=[`) in `api/browser.py` pass. No browser was downloaded and the Playwright CLI was not run.

## Deviations from Plan

**1. [Rule 3 - test isolation] `fresh()` in test_details installs a raising fake instead of the real `fetch_page`**
- **Issue:** the plan says `fresh()` restores the real `browser.fetch_page`; that would send every existing blocked/short/challenge test through a real Chrome launch and bump the fixture request counts.
- **Fix:** `fresh()` installs `no_browser` (raises `BrowserUnavailable`); the live test and `test_playwright_start_failure` set the real `fetch_page` explicitly. Behaviour under test is unchanged.
- **Files modified:** api/test_details.py

**2. [Rule 1 - noisy output] `test_playwright_start_failure` silences `browser.log`**
- The expected start failure is logged with `log.exception`, which printed a Traceback and would trip the plan's "output contains Traceback" check. The test sets `browser.log.disabled` during the case.

Otherwise the plan was executed as written.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model (T-04-22 to T-04-26 mitigated and tested).

## Assumptions carried

- A4/A5: Windows PC has Edge and Playwright's sync API on a non-main thread behaves on Windows 3.12 as on macOS 3.9; verified on macOS only (Chrome, not Edge). The `msedge` channel path was exercised only through fakes.
- A9: headless Chrome announces itself; more blocked pages are the designed outcome.

## Self-Check: PASSED

`api/browser.py` exists; all five test suites pass; nothing committed.
