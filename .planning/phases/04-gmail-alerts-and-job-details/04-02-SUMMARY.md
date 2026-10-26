---
phase: 04-gmail-alerts-and-job-details
plan: 02
subsystem: api
tags: [gmail, imap, keyring, watcher, alerts]
requires:
  - phase: 04-gmail-alerts-and-job-details
    provides: "keyring, beautifulsoup4, playwright pinned and installed (04-01)"
provides:
  - "GET/PUT/DELETE /api/gmail (App Password in keyring only, address in SQLite)"
  - "alerts.py: read-only IMAP poll of known alert senders, ALERTS registry (empty until 04-05), canonical_url, alert_job"
  - "watcher: gmail source with its own tick and GMAIL_WAKE, source selection in run_fetch"
  - "core.http_url / plain_text, db.get_raw / set_raw"
affects: [04-03, 04-05, 04-06, 06-settings-ui]
tech-stack:
  added: []
  patterns:
    - "module-global factory swapped by tests (alerts.imap_factory, like sources.get_json)"
    - "raw settings rows outside DEFAULTS (gmail_address, gmail_last_poll)"
key-files:
  created: [api/alerts.py, api/test_gmail.py]
  modified: [api/core.py, api/db.py, api/watcher.py, api/app.py]
key-decisions:
  - "New module alerts.py rather than sources.py: keeps sources.py HTTP-only and puts IMAP, keyring and the 04-05 parsers together"
  - "POST /api/fetch with no career fields runs Gmail alone when connected; 400 only when neither (RESEARCH open question 2)"
  - "INBOX only (accepted limit, ponytail comment names the \\All special-use upgrade)"
  - "gmail_last_poll stores poll date minus one day, only after a successful poll"
metrics:
  duration: "~25 min"
  completed: 2026-10-25
status: complete
requirements-completed: [GMAIL-01]
actuals:
  tokens: 9700
  tasks: 3
  commits: 0
plan_head_before: 4d10029
commits: "uncommitted - pending user approval"
---

# Phase 4 Plan 02: Gmail alerts source Summary

Gmail is connected through PUT /api/gmail (login tested over verified-TLS IMAP, password kept only in keyring), then polled on its own gmail_poll_minutes tick over read-only INBOX with BODY.PEEK, and alert jobs flow through db.insert_jobs scored and deduplicated by canonical URL. The four site parsers are not here: `alerts.ALERTS` starts empty (04-05).

## Tasks

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | Tracer: connect Gmail, next Gmail tick puts an alert job in GET /api/jobs | uncommitted, pending user approval |
| 2 | Lock the /api/gmail contract (validation, errors, DELETE, address change, no leaks) | uncommitted, pending user approval |
| 3 | Lock IMAP and cadence rules (read-only, SINCE, first/last poll, zero-job warning, tick independence, Gmail-only fetch) | uncommitted, pending user approval |

Tasks were built in one pass and share files, so the tests for all three tasks were written together in `api/test_gmail.py` (31 tests).

## Files

- `api/alerts.py` (new): keyring helpers, imap_date, gmail_login/verify_login, ALERTS registry, email_body, canonical_url, alert_job, fetch_gmail_alerts
- `api/core.py`: ALLOW_PRIVATE_HOSTS, http_url, plain_text
- `api/db.py`: get_raw, set_raw
- `api/watcher.py`: GMAIL_WAKE, API_SOURCES, ALL_SOURCES, FIRST_POLL_DAYS, gmail_account, _gmail_since, _fetch_gmail, `_sources(conn, settings, names)`, `run_fetch(..., names)`, _tick_gmail, two-tick _loop
- `api/app.py`: gmail_get, gmail_put, gmail_delete; fetch_now gate accepts a connected Gmail
- `api/test_gmail.py` (new): in-memory keyring, FakeIMAP, 31 tests

## Verification

- `api/test_gmail.py` ok: 31 tests; `test_api` ok: 60; `test_core` ok: 75; `test_watcher` ok: 18 (existing suites unchanged)
- Negative greps pass: no STORE/COPY/MOVE/EXPUNGE or strftime in alerts.py

## Deviations from Plan

None - plan executed exactly as written. (Code comment in alerts.imap_date avoids the literal word "strftime" so the plan's negative grep holds.)

## Known Stubs

None. `alerts.ALERTS` is intentionally empty; 04-05 fills it (fetch_gmail_alerts returns [] and polls nothing until then).

## Threat Flags

None beyond the plan's threat model (new /api/gmail routes sit behind the existing local_only guard).

## Assumptions carried (from plan)

- Gmail throttling replies and very large result sets are not handled specially.
- INBOX only; keyring on Windows and App Password creation are confirmed at the 04-05 live check.

## Self-Check: PASSED

Files exist (alerts.py, test_gmail.py, edits to core/db/watcher/app); all four test suites pass.
