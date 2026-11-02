---
phase: 04-gmail-alerts-and-job-details
plan: 05
subsystem: gmail-alerts
tags: [gmail, alerts, parsers, beautifulsoup, linkedin, indeed, cv-library, totaljobs]
requires:
  - phase: 04-gmail-alerts-and-job-details
    provides: "04-02 alerts helpers and fetch_gmail_alerts; 04-04 six redacted real samples"
provides:
  - "Six alert parsers (LinkedIn, Indeed alert, Indeed job match, CV-Library, Totaljobs 2018 alert, Totaljobs invite) registered in alerts.ALERTS with exact sender addresses"
  - "Per-sample parser tests, a six-sample end-to-end poll and the D-08 regression test"
affects: [04-06, phase verification]
actuals:
  tokens: 21000
  tasks: 2
  commits: 0   # uncommitted - pending user approval
plan_head_before: 9f2cb0c9b44a10c4e172e9ad6c9d7c129c4e7d81
plan_head_after: 9f2cb0c9b44a10c4e172e9ad6c9d7c129c4e7d81
tech-stack:
  added: []
  patterns:
    - "_groups(): a job link's own text plus the text after it up to the next link; no reliance on wrapper markup or class names"
key-files:
  created: []
  modified: [api/alerts.py, api/test_gmail.py]
key-decisions:
  - "Six ALERTS keys (linkedin, indeed, indeed-match, cv-library, totaljobs, totaljobs-invite): one parser per key, so the two Indeed and the two Totaljobs senders get separate keys but share the job source ('indeed'/'totaljobs') and the label, and D-08 warns once per label"
  - "Links with no job ID keep their own URL (path only for the opaque job-match/invite links, all non-utm query for sponsored Indeed links); no title+company dedupe was added because insert_jobs dedupes on UNIQUE(url) only and db.py is outside this plan"
requirements-completed: [GMAIL-02]
status: complete
---

# Phase 4 Plan 05: Alert parsers Summary

Six pure HTML-in, job-dicts-out parsers turn the person's real alert samples into canonical, deduplicated, document-ordered jobs with title, company, location, salary, work type, work mode and snippet text, and the Gmail source now searches six exact sender addresses. The live Gmail check is still open (human verification below).

## What was built

- `api/alerts.py`
  - `parse_linkedin`: job ID read from `/comm/jobs/view/<id>` and reduced to `https://www.linkedin.com/jobs/view/<id>`; card lines `title`, `Company · Location (Hybrid|Remote)`, salary (`£80K-£90K / year`); the parenthesis becomes `remote`.
  - `parse_indeed` (jobalert sender, 29 jobs from 30 cards): `https://{host}/viewjob?jk=<jk>`; lines `title, company, location, salary, tags`. Sponsored `/pagead/clk` links carry no `jk`.
  - `parse_indeed_match` (match sender, one job): title, company, location, then the labelled `Salary`, `Job types` (-> job_type), `Work settings` (-> remote) and `Job description preview` blocks; the AI intro paragraph is added to the description, the greeting is dropped.
  - `parse_cv_library`: click-wrapper `/refer/<id>?url=%2Fjob%2F<id>%2F<slug>` decoded from the href text to `https://www.cv-library.co.uk/job/<id>/<slug>`; the card carries title, location and a snippet only (no company, no salary).
  - `parse_totaljobs` (2018 layout): `EmailLink.aspx?JobID=<id>` (the job ID lives in the query, so `JobID` is the one kept key); bullets are location, salary, company ("Salary unspecified" becomes no salary).
  - `parse_totaljobs_invite` (2026 "invited you to apply", one job): first non-chrome link with text; the two lines after the title are company and location; the recruiter's covering note is not stored (it is not job text).
  - Shared: `_groups`, `_extras` (short lines are tags, 60+ characters is snippet text), `_keep_all`, `_label` (reuses `core._first_label`, `core._TYPES`, `core._REMOTES` plus "in person" -> On-site). `alert_job` gained optional `job_type` and `remote` (default None, so existing callers and tests are unchanged). `fetch_gmail_alerts` now collects empty sites by label so two senders of one site warn once.
- `api/test_gmail.py`: 14 new tests (45 total, was 31). `fresh()` now empties `ALERTS` before registering its test board (the older tests assume one registered site); `real_sites()` restores the shipped registry for the sample tests.

## Person-directed adjustments (from 04-04, not deviations)

1. Six samples and six senders instead of four; every sender registered; each sample has its own parser test.
2. Every field the alert carries is extracted onto the existing job-dict keys (`title, company, location, salary, description, job_type, remote`), not just title and link.
3. Parsers use no outer wrapper markup and no class names (forwards keep `gmail_quote` and may have `m_<digits>` prefixes).
4. Links with no job ID (indeed-match, totaljobs-invite, sponsored Indeed): the existing dedupe is `UNIQUE(url)` with `INSERT OR IGNORE` in `db.insert_jobs`, nothing on title+company. I kept the link's own stable part: opaque links keep their path only, sponsored links keep every non-`utm_` query key, so re-reading the same email gives the same URL and the same row. The same job arriving in two different emails will be two rows for these three link types. Within one email, repeated links collapse by URL.
5. Tests assert on real job data; REDACTED tokens, Sampletown/ST1 and "Person" are never asserted (the match/invite URLs are checked by prefix only).
6. The live Gmail check was not run (human verification below).

## Results

| Run | Result |
| --- | --- |
| api/test_gmail.py | ok: 45 tests |
| api/test_api.py | ok: 60 tests |
| api/test_core.py | ok: 75 tests |
| api/test_watcher.py | ok: 18 tests |
| api/test_details.py | ok: 38 tests (other executor's file, was 26) |

A mutation check (disabling the seen-URL guard) failed the Indeed count test, so the dedupe tests do bite. `! grep -nE 'urlopen|get_page|fetch_page' api/alerts.py` passes; `test_parsers_make_no_network_calls` patches `urlopen` and `socket.create_connection` to raise.

## Deviations from Plan

None beyond the person-directed adjustments above. Two small, in-scope consequences:

- `fresh()` in the test file now clears the registry (the plan said tests keep adding their site through `fresh()`; with six real senders registered the older search-count tests would otherwise see seven SEARCH calls).
- The empty-site set in `fetch_gmail_alerts` holds labels instead of keys (needed so the two Indeed senders warn once).

## Notes for the verifier and 04-06

- The Indeed sample holds 30 job cards but 29 jobs: two sponsored links are byte-identical once redacted, so they collapse. Live mail has distinct tokens.
- The match/invite jobs have source `indeed`/`totaljobs`. Indeed stays skipped for details (D-18); the Totaljobs invite URL is an opaque tracker link, so its details fetch may end `blocked` or `failed` rather than `ok`. Totaljobs 2018 `EmailLink.aspx?JobID=` URLs redirect to the real page.
- LinkedIn and Indeed alert cards carry no description, so only the invite/match/CV-Library alerts add snippet text; LinkedIn and Indeed rank on title, company, location, salary and work mode.
- Every mail from a registered sender is treated as an alert (04-02 ponytail); if the live check shows false "parsed 0 jobs" warnings from non-alert mail of a sender, add a subject check for that site.

## Human verification needed

Task 2 `<human-check>` (blocking human gate, harvested into the end-of-phase UAT; 04-05 is not signed off until the person confirms it):

1. In Gmail, confirm recent LinkedIn, Indeed, CV-Library and Totaljobs alerts are in INBOX (archived alerts are never seen).
2. Create a Google App Password; start `.venv/bin/python api/app.py`.
3. `curl -s -X PUT http://127.0.0.1:8765/api/gmail -H "Content-Type: application/json" -d '{"address": "YOUR_ADDRESS@gmail.com", "app_password": "YOUR APP PASSWORD"}'`, then `curl -s -X POST http://127.0.0.1:8765/api/fetch`, `curl -s http://127.0.0.1:8765/api/watcher`, `curl -s http://127.0.0.1:8765/api/jobs`; wait two minutes and fetch `/api/jobs` again.
4. Expect: PUT returns `connected: true`; fetch 200 with a `gmail` count and no `gmail` error; `sources.gmail` ok with no error (or a named "format may have changed" warning); jobs with source linkedin/indeed/cv-library/totaljobs; LinkedIn/Indeed `details_status` "skipped"; unread alerts still unread; a wrong password gives 400 with the App Password hint.

## Commits

Uncommitted - pending user approval (the user approves every commit). `actuals.commits: 0`.

## Self-Check: PASSED

`api/alerts.py` and `api/test_gmail.py` modified and tests green; samples exist in `api/samples/`; no commit was made, so there are no hashes to verify.
