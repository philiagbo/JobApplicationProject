---
phase: 04-gmail-alerts-and-job-details
verified: 2026-11-12T00:00:00Z
status: human_needed
score: 4/4 must-haves verified
covered_files:
  - ".planning/phases/04-gmail-alerts-and-job-details/04-01-PLAN.md"
  - ".planning/phases/04-gmail-alerts-and-job-details/04-01-SUMMARY.md"
  - ".planning/phases/04-gmail-alerts-and-job-details/04-02-PLAN.md"
  - ".planning/phases/04-gmail-alerts-and-job-details/04-02-SUMMARY.md"
  - ".planning/phases/04-gmail-alerts-and-job-details/04-03-PLAN.md"
  - ".planning/phases/04-gmail-alerts-and-job-details/04-03-SUMMARY.md"
  - ".planning/phases/04-gmail-alerts-and-job-details/04-04-PLAN.md"
  - ".planning/phases/04-gmail-alerts-and-job-details/04-04-SUMMARY.md"
  - ".planning/phases/04-gmail-alerts-and-job-details/04-05-PLAN.md"
  - ".planning/phases/04-gmail-alerts-and-job-details/04-05-SUMMARY.md"
  - ".planning/phases/04-gmail-alerts-and-job-details/04-06-PLAN.md"
  - ".planning/phases/04-gmail-alerts-and-job-details/04-06-SUMMARY.md"
  - "api/alerts.py"
  - "api/app.py"
  - "api/browser.py"
  - "api/core.py"
  - "api/db.py"
  - "api/requirements.txt"
  - "api/samples/cv-library.eml"
  - "api/samples/indeed-match.eml"
  - "api/samples/indeed.eml"
  - "api/samples/linkedin.eml"
  - "api/samples/totaljobs-invite.eml"
  - "api/samples/totaljobs.eml"
  - "api/sources.py"
  - "api/test_core.py"
  - "api/test_details.py"
  - "api/test_gmail.py"
  - "api/test_watcher.py"
  - "api/watcher.py"
covered_digest: "v3:sha256:6e54899afdfa90142400f2a1bfd3ed4e69cb9ade995e3fb7075fbc25b5d633c0"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 4/4
  gaps_closed: []
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "DEFERRED by the person (04-UAT.md test 1: result skipped, 2026-11-12). Live Gmail poll with the person's real account (04-05 Task 2 human-check). Confirm recent LinkedIn, Indeed, CV-Library and Totaljobs alerts are in INBOX (the app reads INBOX only). Create a Google App Password. Start the app with .venv/bin/python api/app.py. PUT http://127.0.0.1:8765/api/gmail with {address, app_password}; then POST /api/fetch, GET /api/watcher and GET /api/jobs; wait two minutes and GET /api/jobs again."
    expected: "PUT returns {address, connected: true}. POST /api/fetch returns 200 with a gmail count and no gmail key in errors. /api/watcher shows sources.gmail ok true, error null (or a named '... alert parsed 0 jobs' warning, meaning that site's format changed). /api/jobs lists jobs with source linkedin, indeed, cv-library or totaljobs; LinkedIn and Indeed jobs read details_status 'skipped'; CV-Library and Totaljobs jobs move from 'pending' to 'ok' or 'blocked'. Alerts that were unread in Gmail are still unread. A wrong password gives 400 with the App Password hint."
    why_human: "Needs the person's real Google account and App Password; Gmail's real login behaviour, INBOX filtering of alerts and read state cannot be faked. Deferred by the person, to be run later with a real App Password. Not a phase gap."
---

# Phase 4: Gmail Alerts and Job Details Verification Report

**Phase Goal:** Jobs from boards with no public API arrive via Gmail alerts, and any job can show its full description
**Verified:** 2026-11-12
**Status:** human_needed
**Re-verification:** Yes. The earlier report (2026-11-02, human_needed 4/4) went stale when review fixes bbf1076 and security fix 5e10f26 changed covered files. Every truth was re-checked against the current code; no regression found.

## What changed since the baseline

`git diff c4380ad HEAD -- api` touches eight files: `alerts.py`, `browser.py`, `core.py`, `sources.py`, `watcher.py` and the tests `test_core.py`, `test_details.py`, `test_gmail.py`. Each change was read in full. Summary:

- SSRF hardening: `core.fetchable()` (DNS-resolved, every address must be global, plus `never_fetch`) now guards `fetch_details`, each urllib redirect hop, the final URL, the browser route guard and `page.url`. `_public_ip` uses `ip.is_global and not ip.is_multicast` (covers 100.64.0.0/10, commit 5e10f26).
- `sources.RedirectRefused`: a refused redirect returns `blocked` and never reaches the browser (previously the Playwright retry undid the guard).
- `judge_page` accepts only 2xx; 404/410 go straight to `blocked`; `http.client.HTTPException` and `RecursionError` are handled.
- `watcher`: `gmail_last_poll` is written only after `db.insert_jobs` succeeds and only if the account is unchanged (`_gmail_polled`); `_fetch_gmail` removed with no dangling references (grep clean).
- `browser`: launch timeout, cancel of timed-out queued tasks, transient launch failures no longer remembered for the process, route guard and navigation-hop listener.
- `alerts._CHROME` now matches whole chrome labels (`fullmatch`), so titles like "Contact Centre Advisor" survive.

None of these touch the DB schema, `app.py`, `requirements.txt` or the committed samples (empty diff for those paths).

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | With Gmail credentials in `keyring`, alert emails are read over IMAP and their jobs appear in `GET /api/jobs`, scored and deduplicated | VERIFIED (live poll deferred, see Human Verification) | `alerts.fetch_gmail_alerts` (alerts.py:311) reads the password via `gmail_password` (keyring), logs in with `gmail_login`, `client.select("INBOX", readonly=True)`, `uid SEARCH FROM "<sender>" SINCE <date>`, `uid FETCH (BODY.PEEK[])`; no STORE/COPY/EXPUNGE/delete anywhere (grep clean). `watcher._sources` yields `gmail` only when `gmail_account` finds a stored password; `run_fetch` calls `db.insert_jobs` (scored, UNIQUE(url) dedupe), then the new `stored()` callback. Fake-IMAP end-to-end tests pass (test_gmail 47 tests, including `test_failed_insert_keeps_poll_window` and `test_account_change_during_poll_keeps_lookback`). |
| 2 | LinkedIn, Indeed, CV-Library, Totaljobs alerts each have their own parser, each passing against a saved sample | VERIFIED | Ran directly on the committed samples: linkedin 6 jobs, indeed 29, indeed-match 1, cv-library 10, totaljobs 19, totaljobs-invite 1; every parser returns `[]` for `''`. Six senders registered in `ALERTS`. The `_CHROME` change is covered by the invite test with four title variants. |
| 3 | `fetch_details` returns the full description from the JSON-LD `JobPosting` block, else the largest text block | VERIFIED | `sources.extract_description` unchanged except for the added `RecursionError` guard; `fetch_details` -> `judge_page` -> `extract_description`. `test_extract_jsonld_shapes`, `test_extract_largest_block`, `test_details_end_to_end` pass (test_details 43 tests). Worker chain `watcher._details_step` -> `core.details_plan` -> `sources.fetch_details` -> `db.save_details` intact. |
| 4 | A blocked page is retried once in Playwright, then marked "open listing to read"; no CAPTCHA is ever attempted | VERIFIED | `fetch_details` judges the urllib result, then calls `browser.fetch_page` once, else `("", "blocked")`. New guards only narrow what the browser may open (refused redirects and gone pages skip it). `_load_page` still only does `route` guard, `goto`, `wait_for_load_state`, `content()`, close; grep for click/fill/type/evaluate/user_agent/add_init finds only the docstring "Never clicks". Live-browser test "live browser: ok" against real Chrome, which also exercises the new `page.route` guard with real Playwright. |

**Score:** 4/4 truths verified (0 present, behavior-unverified). One live-integration human check remains for SC1 (deferred by the person).

### Plan-level must-haves (spot checks)

| Truth | Status | Evidence |
|-------|--------|----------|
| 04-01: requirements.txt pinned, bs4/keyring/playwright importable | VERIFIED | `api/requirements.txt` unchanged since baseline; tests import all three. |
| 04-02: app password only in keyring, never in responses/DB/STATUS/logs | VERIFIED | `test_gmail_password_never_leaks`, `test_gmail_keys_hidden_from_settings` pass; app.py unchanged. |
| 04-02: read-only INBOX, BODY.PEEK only, FROM-restricted search | VERIFIED | alerts.py select(readonly=True), `BODY.PEEK[]`, every SEARCH carries FROM; `test_imap_read_only` passes. |
| 04-02: Gmail own tick, API tick never polls Gmail, D-08 warning not an error | VERIFIED | `names` gate in `_sources`; `test_api_tick_never_polls_gmail`, `test_zero_job_alert_warns_once` pass. |
| 04-03: migration guarded; LinkedIn/Indeed skipped; excluded-word/>=500-char shortcuts | VERIFIED | db.py unchanged; `core.details_plan` now routes through `never_fetch` (behaviour-preserving, tests pass). |
| 04-03: dismiss/queue racing `save_details` never re-scores | VERIFIED | db.py unchanged since baseline, where it was directly observed (score UPDATE carries `AND status = 'new'`); regression tests in test_details pass. |
| 04-03: blocked page stores nothing; interrupted fetch stays pending; one details thread | VERIFIED | `test_blocked_keeps_snippet`, `test_interrupted_fetch_stays_pending`, `test_details_start_once`, plus new `test_gone_page_never_stored` pass. |
| 04-04: samples redacted, raw exports gitignored | VERIFIED | Header grep (To/Cc/Delivered-To/Received/Return-Path) 0 on all six `.eml`; all 8 scrub terms 0 hits across `api/samples/`; `api/data` ignored (`git check-ignore`); 6 tracked files in `api/samples`; sample diff since baseline is empty. |
| 04-05: URLs canonical, no network in parsers | VERIFIED | `grep urlopen|get_page|fetch_page api/alerts.py` empty; `test_parsers_make_no_network_calls` passes. |
| 04-06: single Playwright thread, lazy start, retry once; skipped/unsafe URLs never reach the browser | VERIFIED | `test_browser_single_thread`, `test_browser_not_started_on_import`, `test_fetch_details_retries_once`, `test_never_fetch_and_unsafe_skip_browser`, new `test_redirect_to_file_blocked` (asserts no browser call) and `test_browser_guard_aborts_refused_requests` pass. |

### Prohibitions (must_haves.prohibitions)

| Prohibition | Tier | Status |
|-------------|------|--------|
| 04-01 no install before the legitimacy checkpoint | judgment | Resolved per 04-01-SUMMARY (person approved) and 04-SECURITY T-04-SC closed. NON-AUTHORITATIVE judge verdict. |
| 04-02 password only in keyring | test | `test_gmail_password_never_leaks` passes. |
| 04-02 never mark/move/delete mail | test | `test_imap_read_only` passes; code grep clean. |
| 04-02 no mail beyond known senders, no email content persisted | test | Every SEARCH carries FROM; only parsed job fields reach `insert_jobs`. |
| 04-03 never fetch LinkedIn/Indeed pages | test | Strengthened: `never_fetch` on first URL, every hop, final URL, browser routes and `page.url`; tests pass. |
| 04-03 blocked page text never stored | test | `test_blocked_keeps_snippet`, `test_gone_page_never_stored` pass. |
| 04-04 no raw export or delivery headers committed | test | Verified directly (headers, scrub terms, gitignore, tracked files). |
| 04-05 parsers never follow links | test | `test_parsers_make_no_network_calls`; grep clean. |
| 04-06 browser never interacts with page | test | `test_page_task_only_reads`; grep clean. |
| 04-06 never attempt/evade CAPTCHA | judgment | Resolved: no UA override, no launch evasion flags, no waiting on challenge; challenge pages go to `blocked`. NON-AUTHORITATIVE judge verdict, no unresolved flag. |
| 04-06 never open LinkedIn/Indeed or non-public URLs in browser | test | `test_never_fetch_and_unsafe_skip_browser`, `test_post_navigation_url_checked`, `test_browser_guard_aborts_refused_requests` pass. |

No `unverified-prohibition` flags: every test-tier prohibition has wired enforcement.

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| api/requirements.txt | VERIFIED | unchanged |
| api/alerts.py | VERIFIED | all planned exports; `_CHROME` fix; used by app.py/watcher.py |
| api/browser.py | VERIFIED | wired from `sources.fetch_details`; guard, cancel and retry logic present |
| api/sources.py extractors / `fetch_details` / `RedirectRefused` | VERIFIED | wired from `watcher._details_step` |
| api/core.py `http_url`, `fetchable`, `never_fetch`, `plain_text`, `details_plan` | VERIFIED | used by alerts, sources, browser, watcher |
| api/db.py migration and helpers | VERIFIED | unchanged since baseline |
| api/app.py `/api/gmail`, Gmail-aware `/api/fetch` | VERIFIED | unchanged since baseline |
| api/samples/*.eml (six) | VERIFIED | unchanged |
| api/test_*.py | VERIFIED | substantive, all pass |

### Key Link Verification

| From | To | Status |
|------|----|--------|
| app.gmail_put | alerts.gmail_login (before store_password) | WIRED |
| watcher._sources | alerts.fetch_gmail_alerts | WIRED (lambda in `_sources`; stale `_fetch_gmail` fully removed, no dangling reference) |
| run_fetch | db.insert_jobs, then `stored()` -> `_gmail_polled`, DETAILS_WAKE.set | WIRED |
| _details_step | core.details_plan, sources.fetch_details, db.save_details | WIRED |
| sources.fetch_details | core.fetchable, RedirectRefused handling, browser.fetch_page | WIRED |
| browser._load_page | core.fetchable via route `_guard`, request listener and `page.url` | WIRED |
| db.init_db | PRAGMA guard + ALTER | WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|----------|------|--------|-----------|--------|
| GET /api/jobs gmail rows | job dicts | parsers on real redacted sample bodies via fake IMAP into `insert_jobs` | yes | FLOWING |
| jobs.description after details | text | JSON-LD / largest block from the fetched page via `save_details` | yes | FLOWING |
| jobs.details_status | column | default 'pending' -> worker writes ok/blocked/skipped | yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| core tests | `.venv/bin/python api/test_core.py` | ok: 77 tests | PASS |
| api tests | `.venv/bin/python api/test_api.py` | ok: 60 tests | PASS |
| watcher tests | `.venv/bin/python api/test_watcher.py` | ok: 18 tests | PASS |
| gmail tests | `.venv/bin/python api/test_gmail.py` | ok: 47 tests | PASS |
| details tests (real Chrome) | `.venv/bin/python api/test_details.py` | "live browser: ok", ok: 43 tests | PASS |
| Parsers on committed samples | direct run | 6 / 29 / 1 / 10 / 19 / 1 jobs; `[]` on empty input | PASS |

Counts match the expected suites (core 77, api 60, watcher 18, gmail 47, details 43).

### Probe Execution

SKIPPED: phase declares no `probe-*.sh` scripts and none exist under `scripts/`.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|--------------|-------------|--------|----------|
| GMAIL-01 | 04-01, 04-02, 04-04 | `fetch_gmail_alerts` reads alert emails over IMAP using keyring credentials | SATISFIED in code and fake-IMAP tests; live account check deferred (human) | alerts.py:311-354, app.py gmail endpoints |
| GMAIL-02 | 04-01, 04-04, 04-05 | Separate parsers for LinkedIn, Indeed, CV-Library, Totaljobs, each tested against a saved sample | SATISFIED | six parsers, six samples, per-sample tests |
| DETAIL-01 | 04-01, 04-03 | `fetch_details` reads JSON-LD JobPosting else largest text block | SATISFIED | sources.py `extract_description` / `fetch_details` |
| DETAIL-02 | 04-01, 04-03, 04-06 | Blocked -> retry once in Playwright -> "open listing to read"; never CAPTCHAs | SATISFIED | `sources.fetch_details` + browser.py; stored marker `blocked` |

All four IDs appear in PLAN frontmatter and REQUIREMENTS.md; no ORPHANED requirements. Bookkeeping note: REQUIREMENTS.md still shows these as `[ ]` / "Pending" (lines 44-47, 110-113); updating the checkboxes and traceability is an orchestrator step.

### Anti-Patterns Found

None. No TBD/FIXME/XXX/TODO/HACK in any phase-modified source file. Deliberate shortcuts carry `ponytail:` comments with ceilings (INBOX-only search, DNS-rebinding window between `fetchable` and the request, refused server-redirect hop sent before the page is discarded, check-then-write on `gmail_last_poll`, sponsored/tracker links without a job ID).

### Informational notes (not gaps)

- Person-directed adjustments, not deviations: six samples from six senders, full field extraction, orchestrator-scripted redaction.
- 04-SECURITY.md: 27/27 threats closed, `threats_open: 0`. Residual non-blocking notes (DNS rebinding, redirect hop sent before discard, `getaddrinfo` has no timeout, T-04-12 relies on Phase 6 rendering descriptions as text) are consistent with what the code shows.
- Indeed-match and Totaljobs-invite links are opaque tracker URLs: the same job in two emails is two rows (documented limit).
- Deferred items: none. Overrides: none.

### Human Verification Required

#### 1. Live Gmail poll with the person's real account (DEFERRED by the person)

**Test:** Confirm the alert emails are in INBOX; create a Google App Password; run `.venv/bin/python api/app.py`; `PUT /api/gmail` with `{address, app_password}`; then `POST /api/fetch`, `GET /api/watcher`, `GET /api/jobs`; wait two minutes and `GET /api/jobs` again.
**Expected:** PUT returns `{address, connected: true}`; fetch returns 200 with a `gmail` count and no `gmail` error; watcher shows `sources.gmail.ok` true; jobs from linkedin/indeed/cv-library/totaljobs listed, LinkedIn and Indeed `details_status` `skipped`, CV-Library and Totaljobs moving from `pending` to `ok`/`blocked`; unread alerts remain unread; a wrong password gives 400 with the App Password hint.
**Why human:** Needs the person's real Google account and App Password. 04-UAT.md test 1 is recorded as `skipped` (deferred by the person on 2026-11-12, to be tested later). This is a deferred human check, not a phase failure or gap.

### Gaps Summary

No gaps. All four ROADMAP success criteria and the plan-level must-haves are backed by current code and passing tests (core 77, api 60, watcher 18, gmail 47, details 43). The code-review and security fixes strengthened the SSRF, redirect and poll-window behaviour without regressing any verified truth. The only open item is the person's deferred live Gmail check, which keeps the phase at `human_needed`.

---

_Verified: 2026-11-12_
_Verifier: Claude (gsd-verifier)_
