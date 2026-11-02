---
phase: 04-gmail-alerts-and-job-details
verified: 2026-11-02T00:00:00Z
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
  - "api/test_details.py"
  - "api/test_gmail.py"
  - "api/test_watcher.py"
  - "api/watcher.py"
covered_digest: "v3:sha256:fd7539b7975cbee6777df0c6105a6d9a5a91b4f9038a395b929606697a110c78"
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Live Gmail poll with the person's real account (04-05 Task 2 human-check). Confirm recent LinkedIn, Indeed, CV-Library and Totaljobs alerts are in INBOX (the app reads INBOX only). Create a Google App Password. Start the app with .venv/bin/python api/app.py. PUT http://127.0.0.1:8765/api/gmail with {address, app_password}; then POST /api/fetch, GET /api/watcher and GET /api/jobs; wait two minutes and GET /api/jobs again."
    expected: "PUT returns {address, connected: true}. POST /api/fetch returns 200 with a gmail count and no gmail key in errors. /api/watcher shows sources.gmail ok true, error null (or a named '... alert parsed 0 jobs' warning, meaning that site's format changed). /api/jobs lists jobs with source linkedin, indeed, cv-library or totaljobs; LinkedIn and Indeed jobs read details_status 'skipped'; CV-Library and Totaljobs jobs move from 'pending' to 'ok' or 'blocked'. Alerts that were unread in Gmail are still unread. A wrong password gives 400 with the App Password hint."
    why_human: "Needs the person's real Google account and App Password; Gmail's real login behaviour, INBOX filtering of alerts and read state cannot be faked. The person has not run it yet (not a failure of the phase)."
---

# Phase 4: Gmail Alerts and Job Details Verification Report

**Phase Goal:** Jobs from boards with no public API arrive via Gmail alerts, and any job can show its full description
**Verified:** 2026-11-02
**Status:** human_needed
**Re-verification:** No, initial verification

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | With Gmail credentials in `keyring`, alert emails are read over IMAP and their jobs appear in `GET /api/jobs`, scored and deduplicated | VERIFIED (live poll pending, see Human Verification) | `alerts.fetch_gmail_alerts` (api/alerts.py:310) reads the password via `gmail_password` (keyring), logs in over IMAP4_SSL with a verifying TLS context, `select("INBOX", readonly=True)`, `uid SEARCH FROM <sender> SINCE <DD-Mon-YYYY>`, `uid FETCH (BODY.PEEK[])`. `watcher._sources` yields `gmail` only when `gmail_account` finds a stored password; `run_fetch` calls `db.insert_jobs` (scored, UNIQUE(url) dedupe). Fake-IMAP end-to-end tests `test_gmail_alert_job_end_to_end`, `test_linkedin_sample_end_to_end`, `test_six_sample_poll_end_to_end`, `test_alert_dedupe_across_polls` pass. PUT/GET/DELETE `/api/gmail` present (app.py:138-184). |
| 2 | LinkedIn, Indeed, CV-Library, Totaljobs alerts each have their own parser, each passing against a saved sample | VERIFIED | `parse_linkedin/indeed/cv_library/totaljobs` plus `parse_indeed_match` and `parse_totaljobs_invite` registered in `ALERTS` with exact sender addresses matching each sample's From header. Run directly on the committed samples: linkedin 6 jobs, indeed 29, indeed-match 1, cv-library 10, totaljobs 19, totaljobs-invite 1; every parser returns `[]` for `''` and for HTML with no cards. Per-sample tests `test_parse_*_sample`, `test_alert_registry_matches_samples` pass. |
| 3 | `fetch_details` returns the full description from the JSON-LD `JobPosting` block, else the largest text block | VERIFIED | `sources.extract_description` (sources.py:179) handles list, `@graph`, `mainEntity`, list-typed `@type`, entity-escaped HTML, raw control chars (`strict=False`); falls through to `_block_text` largest direct-children block with `• ` list items. Tests `test_extract_jsonld_shapes`, `test_extract_largest_block`, `test_extract_empty`, `test_page_charset_decoding`, `test_details_end_to_end` pass. Worker wired: `watcher._details_step` -> `core.details_plan` -> `sources.fetch_details` -> `db.save_details`; thread started only in `watcher.start()`. |
| 4 | A blocked page is retried once in Playwright, then marked "open listing to read"; no CAPTCHA is ever attempted | VERIFIED | `fetch_details` (sources.py:215) judges the urllib result via `judge_page` (403/429/503, <200 chars, challenge phrase without JobPosting), then calls `browser.fetch_page` exactly once, else returns `("", "blocked")`. `browser.py` runs all Playwright on one daemon thread `browser` fed by `queue.Queue`, lazy start, channels msedge then chrome, no download, `BrowserUnavailable` memoised. The page task only does `goto`, `wait_for_load_state`, `content()`, close; grep finds no click/fill/type/evaluate/user-agent/evasion code. Live smoke test ran against real Chrome: "live browser: ok" (JS-rendered page -> ok, 403 page -> blocked). |

**Score:** 4/4 truths verified (0 present, behavior-unverified). One live-integration human check remains for SC1.

### Plan-level must-haves (spot checks, beyond ROADMAP SCs)

| Truth | Status | Evidence |
|-------|--------|----------|
| 04-01: requirements.txt exactly six lines in order; bs4, keyring, playwright importable; playwright < 1.61 | VERIFIED | File read matches; `import bs4, keyring, playwright.sync_api` succeeds; playwright 1.60.0. Legitimacy checkpoint recorded as approved by the person in 04-01-SUMMARY. |
| 04-02: app password only in keyring, never in responses/DB/STATUS/logs | VERIFIED | `store_password` -> keyring only; `db` and `watcher` hold no password; `test_gmail_password_never_leaks`, `test_gmail_keys_hidden_from_settings` pass. |
| 04-02: read-only INBOX, BODY.PEEK only, FROM-restricted search | VERIFIED | alerts.py:322, 329, 333; no STORE/COPY/EXPUNGE anywhere; `test_imap_read_only`, `test_imap_search_from_and_since` pass. |
| 04-02: Gmail own tick; API tick never polls Gmail; Gmail-only manual fetch; D-08 warning is not an error | VERIFIED | `_tick_gmail`/`_tick_sources(needs_fields=False)`, `API_SOURCES`, app.py:111-125, warnings only into `STATUS.error`. Tests `test_gmail_tick_*`, `test_api_tick_never_polls_gmail`, `test_manual_fetch_includes_gmail`, `test_zero_job_alert_warns_once` pass. |
| 04-03: `details_status` migration guarded by PRAGMA; LinkedIn/Indeed skipped with no network; excluded-word and >=500-char shortcuts | VERIFIED | db.py:77-79; `core.details_plan` (core.py:126); `test_migration_adds_column_once`, `test_linkedin_indeed_never_fetched`, `test_details_plan_rules`, `test_never_fetch_and_unsafe_skip_browser` pass. |
| 04-03: dismiss/queue racing `save_details` never re-scores (backstop-tier truth) | VERIFIED (directly observed) | The score UPDATE carries `AND status = 'new'` (db.py:226). Observed in a scratch DB: a second connection dismissed the job inside `core.score` (between the row read and the write); afterwards status `dismissed`, `details_status` `ok`, score/pros/summary unchanged. |
| 04-03: blocked page stores nothing; interrupted fetch stays pending; one details thread | VERIFIED | `test_blocked_keeps_snippet`, `test_interrupted_fetch_stays_pending`, `test_details_start_once`, `test_only_pending_picked` pass; save_details writes only status for non-ok. |
| 04-04: samples have no To/Cc/Delivered-To/Received/Return-Path; no scrub-term hits; raw exports gitignored | VERIFIED | Header grep 0 on all six `.eml`; all 8 scrub terms from `api/data/alert-samples/scrub-terms.txt` return 0 hits across `api/samples/`; only addresses present are the sender addresses, `customerservices@totaljobs.com` and `person@example.com`; `api/data/` is gitignored (`git check-ignore` confirms) and tracked files are only under `api/samples/`. |
| 04-05: URLs canonical, no network in parsers | VERIFIED | `canonical_url`, `_linkedin_url`, `_indeed_url`, `_cv_url`, `_totaljobs_url` build URLs from href text only; `test_parsers_make_no_network_calls`, `test_canonical_url_rules`, `test_parsers_collapse_duplicate_links`, `test_parsers_keep_document_order` pass. |
| 04-06: single Playwright thread, lazy start, retry once, browser never reached by skipped/unsafe URLs | VERIFIED | `test_browser_single_thread`, `test_browser_not_started_on_import`, `test_fetch_details_retries_once`, `test_channel_order_and_memo`, `test_page_task_only_reads`, `test_page_closed_on_error`, `test_post_navigation_url_checked`, `test_browser_challenge_blocked` pass. |

### Prohibitions (must_haves.prohibitions)

| Prohibition | Tier | Status |
|-------------|------|--------|
| 04-01 no install before the blocking-human legitimacy checkpoint | judgment | Resolved: 04-01-SUMMARY records the person approved all three packages on pypi.org before pinning. NON-AUTHORITATIVE judge verdict; not independently reproducible from code. |
| 04-02 password only in keyring | test | Enforced by `test_gmail_password_never_leaks` (passes). |
| 04-02 never mark/move/delete mail | test | Enforced by `test_imap_read_only` (passes); code grep confirms only login/select(readonly)/uid SEARCH/uid FETCH PEEK/logout. |
| 04-02 no mail beyond known senders, no email content persisted | test | Every SEARCH carries FROM sender; only parsed job fields reach `insert_jobs`. |
| 04-03 never fetch LinkedIn/Indeed pages | test | `test_linkedin_indeed_never_fetched`, `test_never_fetch_and_unsafe_skip_browser` pass. |
| 04-03 blocked page text never stored | test | `test_blocked_keeps_snippet` passes. |
| 04-04 no raw export or delivery headers committed | test | Verified directly above (headers, scrub terms, gitignore, tracked files). |
| 04-05 parsers never follow links | test | `test_parsers_make_no_network_calls`; `! grep urlopen|get_page|fetch_page api/alerts.py` holds (alerts.py imports `sources` only for `SourceError`). |
| 04-06 browser never interacts with page | test | `test_page_task_only_reads`; code grep clean. |
| 04-06 never attempt/evade CAPTCHA | judgment | Resolved: code has no UA override, no launch flags, no waiting on challenge; challenge pages go to `blocked`. NON-AUTHORITATIVE judge verdict, no unresolved flag. |
| 04-06 never open LinkedIn/Indeed or non-public URLs in browser | test | `test_never_fetch_and_unsafe_skip_browser`, `test_post_navigation_url_checked` pass. |

No `unverified-prohibition` flags: every test-tier prohibition has wired enforcement.

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| api/requirements.txt | VERIFIED | six pinned lines |
| api/alerts.py (354 lines) | VERIFIED | all planned exports present and used by app.py/watcher.py |
| api/browser.py (102 lines, min 40) | VERIFIED | wired from sources.fetch_details |
| api/sources.py extractors/fetch_details | VERIFIED | wired from watcher._details_step |
| api/core.py `http_url`, `plain_text`, `details_plan` | VERIFIED | used by alerts, sources, browser, watcher |
| api/db.py `get_raw/set_raw/next_pending/save_details` + migration | VERIFIED | used by app/watcher |
| api/app.py `/api/gmail` GET/PUT/DELETE, Gmail-aware `/api/fetch`, keyring error handler | VERIFIED | |
| api/samples/*.eml (six) | VERIFIED | four planned plus two extra senders (person-directed) |
| api/test_gmail.py, test_details.py, test_watcher.py | VERIFIED | substantive, all pass |

### Key Link Verification

| From | To | Status |
|------|----|--------|
| app.gmail_put | alerts.gmail_login (login tested before store_password) | WIRED (app.py:159 before :166) |
| watcher._sources | alerts.fetch_gmail_alerts via `_fetch_gmail` | WIRED |
| fetch_gmail_alerts | keyring via `gmail_password` | WIRED |
| run_fetch | db.insert_jobs, DETAILS_WAKE.set | WIRED |
| _details_step | core.details_plan, sources.fetch_details, db.save_details | WIRED |
| sources.fetch_details | browser.fetch_page -> submit | WIRED |
| browser._load_page | core.http_url on post-navigation URL | WIRED |
| db.init_db | PRAGMA table_info(jobs) guard + ALTER | WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|----------|------|--------|-----------|--------|
| GET /api/jobs gmail rows | job dicts | parsers run on real redacted sample bodies via fake IMAP into `insert_jobs` | yes | FLOWING |
| jobs.description after details | text | JSON-LD/largest-block from fetched page, saved via `save_details` | yes | FLOWING |
| jobs.details_status | column | migration default 'pending' -> worker writes ok/blocked/skipped | yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| core tests | `.venv/bin/python api/test_core.py` | ok: 75 tests | PASS |
| api tests | `.venv/bin/python api/test_api.py` | ok: 60 tests | PASS |
| details tests (incl. real Chrome) | `.venv/bin/python api/test_details.py` | "live browser: ok", ok: 38 tests | PASS |
| gmail tests | `.venv/bin/python api/test_gmail.py` | ok: 45 tests | PASS |
| watcher tests | `.venv/bin/python api/test_watcher.py` | ok: 18 tests | PASS |
| Parsers on committed samples | direct run | counts listed under SC2 | PASS |
| save_details race with dismiss | scratch DB script | score/pros/summary unchanged | PASS |

### Probe Execution

SKIPPED: phase declares no `probe-*.sh` scripts and none exist under `scripts/`.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|--------------|-------------|--------|----------|
| GMAIL-01 | 04-01, 04-02, 04-04 | `fetch_gmail_alerts` reads alert emails over IMAP using credentials from keyring | SATISFIED in code and fake-IMAP tests; live account check pending (human) | alerts.py:310-354, app.py gmail endpoints |
| GMAIL-02 | 04-01, 04-04, 04-05 | Separate parsers for LinkedIn, Indeed, CV-Library, Totaljobs, each tested against a saved sample | SATISFIED | six parsers, six samples, per-sample tests |
| DETAIL-01 | 04-01, 04-03 | `fetch_details` reads JSON-LD JobPosting else largest text block | SATISFIED | sources.py:179-231 |
| DETAIL-02 | 04-01, 04-03, 04-06 | Blocked -> retry once in Playwright -> "open listing to read"; never CAPTCHAs | SATISFIED | sources.fetch_details + browser.py; status `blocked` is the stored marker for the person's "open listing to read" label |

All four IDs appear in PLAN frontmatter and in REQUIREMENTS.md. No ORPHANED requirements (REQUIREMENTS.md maps only these four to Phase 4). Note: REQUIREMENTS.md still shows these four as `[ ]` / "Pending"; updating the checkboxes and traceability table is an orchestrator bookkeeping step. ROADMAP.md Phase 4 checkbox is also still `[ ]` (ROADMAP.md has uncommitted edits).

### Anti-Patterns Found

None. No TBD/FIXME/XXX/TODO/HACK markers in any phase-modified file. Deliberate shortcuts are marked `ponytail:` with ceilings (INBOX-only search, sponsored/tracker links without a job ID dedupe per email, offline fetch is final `blocked`, browser-unavailable remembered per process). Informational only.

### Informational notes (not gaps)

- 04-01-SUMMARY says "commits: 0" but `4d10029 chore(04-01)` exists in git history; bookkeeping only.
- 04-05 acceptance text names `test_four_site_poll_end_to_end`; the shipped test is `test_six_sample_poll_end_to_end` (follows the person-directed six-sender change, not a deviation).
- The `indeed-match` and `totaljobs-invite` alert links are opaque tracker URLs with no job ID, so the same job in two emails is two rows (documented `ponytail:` limit). Indeed jobs are never fetched; a Totaljobs-invite job's details fetch goes to the tracker URL and may land as `blocked`.
- Deferred items: none. Overrides: none.

### Human Verification Required

#### 1. Live Gmail poll with the person's real account

**Test:** Confirm the alert emails are in INBOX; create a Google App Password; run `.venv/bin/python api/app.py`; `PUT /api/gmail` with `{address, app_password}`; then `POST /api/fetch`, `GET /api/watcher`, `GET /api/jobs`; wait two minutes and `GET /api/jobs` again.
**Expected:** PUT returns `{address, connected: true}`; fetch returns 200 with a `gmail` count and no `gmail` error; watcher shows `sources.gmail.ok` true; jobs from linkedin/indeed/cv-library/totaljobs listed, LinkedIn and Indeed `details_status` `skipped`, CV-Library and Totaljobs moving from `pending` to `ok`/`blocked`; unread alerts remain unread; a wrong password gives 400 with the App Password hint.
**Why human:** Needs the person's real Google account and App Password; real Gmail login, INBOX filtering and read-state cannot be faked. Not yet run by the person; not a phase failure.

### Gaps Summary

No gaps. All four ROADMAP success criteria and the plan-level must-haves are backed by code and passing tests (core 75, api 60, details 38, gmail 45, watcher 18). The only open item is the person's live Gmail check, which keeps the phase at `human_needed`.

---

_Verified: 2026-11-02_
_Verifier: Claude (gsd-verifier)_
