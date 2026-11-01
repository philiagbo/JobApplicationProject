---
phase: 04-gmail-alerts-and-job-details
plan: 03
subsystem: api
tags: [details, jsonld, beautifulsoup, urllib, sqlite-migration, worker-thread]
requires:
  - phase: 04-gmail-alerts-and-job-details
    provides: "core.http_url / plain_text, db helpers, watcher thread structure (04-02); beautifulsoup4 pinned (04-01)"
provides:
  - "jobs.details_status column (pending/ok/blocked/skipped), guarded migration in init_db (D-17)"
  - "db.next_pending, db.save_details with the D-13 re-score rule"
  - "core.details_plan: no-network skipped/ok/fetch decision (D-12, D-18)"
  - "sources.get_page, extract_description, judge_page, fetch_details (DETAIL-01, D-16)"
  - "watcher details worker thread: DETAILS_WAKE, 5 s gap after a real fetch only (D-11)"
affects: [04-06, 06-job-pages]
tech-stack:
  added: []
  patterns:
    - "module-global fetcher swapped by tests (sources.get_page, like get_json)"
    - "local http.server fixture with a PAGES dict and per-path request counts"
key-files:
  created: [api/test_details.py]
  modified: [api/db.py, api/core.py, api/sources.py, api/watcher.py, api/test_watcher.py]
key-decisions:
  - "D-17 gate answered 'add-column' by the person before execution; one PRAGMA-guarded ALTER, SCHEMA left unchanged"
  - "Redirects are checked per hop by a small HTTPRedirectHandler subclass (refuses non-http, localhost and private hosts), because urllib would otherwise follow a redirect to ftp:// on its own"
  - "Largest-block fallback also reads direct ul/ol children of a container, so a list inside an article is kept with its paragraphs"
metrics:
  duration: "~30 min"
  completed: 2026-10-29
status: complete
requirements-completed: [DETAIL-01, DETAIL-02]
actuals:
  tokens: 14000
  tasks: 3
  commits: 0
plan_head_before: 102675d
commits: "uncommitted - pending user approval"
---

# Phase 4 Plan 03: Full job descriptions in the background Summary

Every job now starts `pending`; a background "details" thread classifies each one with no network (LinkedIn/Indeed and excluded titles are `skipped`, descriptions of 500+ characters are `ok`), fetches the rest over urllib one every 5 seconds, reads the page's JSON-LD `JobPosting` (or the largest paragraph/list block), and saves plain text. New jobs are re-summarised and re-scored with source hints kept; queued and dismissed jobs keep their score. Blocked pages are marked `blocked` and store nothing.

## Tasks

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | D-17 go/hold checkpoint | answered "add-column" by the person before execution (no code) |
| 2 | Tracer: short Reed preview gets the full JSON-LD description, re-scored, `details_status` ok in GET /api/jobs | uncommitted, pending user approval |
| 3 | Lock extraction, blocked, classification, save and migration rules (25 further tests) | uncommitted, pending user approval |

Tasks 2 and 3 share files, so code and all tests were written in one pass.

## Files

- `api/db.py`: guarded `ALTER TABLE jobs ADD COLUMN details_status ...` in `init_db`, `DETAILS_STATUSES`, `next_pending`, `save_details` (score UPDATE carries `AND status = 'new'`)
- `api/core.py`: `NEVER_FETCH_SOURCES`, `NEVER_FETCH_DOMAINS`, `SHORT_DESCRIPTION_CHARS = 500`, `details_plan`
- `api/sources.py`: `MAX_PAGE_BYTES`, `BLOCKED_TEXT_CHARS = 200`, `BLOCKED_STATUSES`, `CHALLENGE_PHRASES`, `_SafeRedirect`, `get_page`, `extract_description` (text, from_jsonld, has_jobposting), `judge_page`, `fetch_details`
- `api/watcher.py`: `DETAILS_WAKE`, `DETAILS_GAP_SECONDS = 5`, `DETAILS_IDLE_SECONDS`, `_details_thread`, `_details_step`, `_details_loop`; `start()` starts the "details" thread; `run_fetch` wakes it when a source inserted jobs
- `api/test_details.py` (new): fixture HTTP server, 26 tests
- `api/test_watcher.py`: details knobs, `offline_page` installed as `sources.get_page`, details-thread assertions and shutdown (still 18 tests)

## Verification

- `test_details` ok: 26 tests; `test_watcher` ok: 18; `test_api` ok: 60; `test_core` ok: 75; `test_gmail` ok: 31 (run with `.venv/bin/python`, Python 3.9)
- All acceptance greps pass; `init_db` twice yields one `details_status` column
- Tests use temp databases only; no network access

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Redirect hops checked, not only the final URL**
- **Found during:** Task 2 (threat T-04-10)
- **Issue:** urllib follows redirects to `ftp://` itself, so checking only `resp.geturl()` after the fact would already have made the request.
- **Fix:** `_SafeRedirect.redirect_request` refuses any target `core.http_url` refuses (raises HTTPError, which `get_page` returns as `(302, "")`, so the job is `blocked`). The plan's final-URL check is kept too. `test_redirect_to_file_blocked` covers `file://` and `ftp://` and a safe redirect still working.
- **Files modified:** api/sources.py, api/test_details.py

**2. [Rule 1 - Correctness of the fixture requirement] Largest block includes direct `ul`/`ol` children**
- **Found during:** Task 3 (test_extract_largest_block requires list items of an article in the result)
- **Issue:** The plan text says a container scores its direct `p` and `li` children; a `<ul>` inside an `<article>` is not a direct `li` child, so the list would be dropped from the article's text.
- **Fix:** a container also takes the `li` children of its direct `ul`/`ol` children, as "• " lines, in document order.
- **Files modified:** api/sources.py

Otherwise the plan was executed as written. Thresholds (500, 200, 5 s) are unchanged.

## Known Stubs

None. The single Playwright retry between "urllib could not read it" and "blocked" is intentionally absent; `fetch_details` marks the spot and 04-06 adds it.

## Threat Flags

None beyond the plan's threat model (T-04-10 to T-04-15 are mitigated and tested).

## Assumptions carried (from plan)

- Old-summary `remote`/`job_type` win over text guesses on re-summary.
- A fetch that fails while offline is final (`blocked`; ponytail comment names the reset-to-pending upgrade).
- First start after upgrade back-fills legacy rows (one fetch per 5 s in score order).
- A public DNS name resolving to a private address is not caught.

## Self-Check: PASSED

Files exist (api/test_details.py plus edits to db, core, sources, watcher, test_watcher); all five test suites pass; nothing committed.
