---
phase: 04-gmail-alerts-and-job-details
plan: 04
subsystem: test-fixtures
tags: [gmail, alerts, samples, redaction]
requires: [04-02]
provides:
  - "Six redacted real alert samples under api/samples/ for the 04-05 parsers"
affects: [04-05]
key-files:
  created: [api/samples/linkedin.eml, api/samples/indeed.eml, api/samples/indeed-match.eml, api/samples/cv-library.eml, api/samples/totaljobs.eml, api/samples/totaljobs-invite.eml]
  modified: []
decisions:
  - "Six samples instead of four: the person chose to keep both Indeed senders (jobalert and match) and both Totaljobs emails (2018 alert and 2026 invite)"
  - "Forwarded samples carry the ORIGINAL From/Date/Subject recovered from the Gmail forward block; the gmail_attr preamble is stripped, the gmail_quote wrapper remains"
  - "Hand redaction (Task 3) was delegated to the orchestrator by the person ('redact for me', including Salford and Leeds)"
metrics:
  completed: 2026-11-01
status: complete
requirements: [GMAIL-01, GMAIL-02]
actuals:
  tasks: 3
  commits: 0   # pending user approval
---

# Phase 4 Plan 04: Redacted alert samples Summary

Six real job-alert emails are now small single-part UTF-8 `.eml` samples under `api/samples/`, with the person's identity, tracking tokens, unsubscribe links and home locations removed.

## Samples

| Sample | Original sender | Notes |
| --- | --- | --- |
| linkedin.eml | jobs-noreply@linkedin.com | Direct links `/comm/jobs/view/<id>` (6 IDs kept) |
| indeed.eml | donotreply@jobalert.indeed.com | Gmail forward; `jk=` job keys kept (6); `pagead/clk` click-wrapped |
| indeed-match.eml | donotreply@match.indeed.com | Gmail forward; job links are opaque `cts.indeed.com/v3/REDACTED` |
| cv-library.eml | admin@cv-library.co.uk | 2020; job IDs readable in `refer/...?url=%2Fjob%2F<id>` |
| totaljobs.eml | totaljobs@totaljobsmail.com | 2018 layout; `JobID=` kept (19) |
| totaljobs-invite.eml | totaljobs@recruit.totaljobsmail.co.uk | Gmail forward; job links opaque `o-REDACTED` |

## Redaction

- Task 2 (executor): recipient/outer-From addresses -> person@example.com; name words (Tamara, Addison, Philip, Agbo, local parts) -> Person; headers reduced to From, Date, Subject, MIME-Version, Content-Type, Content-Transfer-Encoding.
- Task 3 (orchestrator, at the person's request): tracking query values -> REDACTED (ad, alert, alid, aluidhash, bb, camk, qd, rd, rgtk, subId, tk, tmtk, token, xkcb, aid, lipi, loid, midSig, midToken, otpToken, refId, trackingId, trk, trkEmail, eid, GUID, memberid, emaildomain, c, ta_redirect, LinkedIn image t, geoId); the Totaljobs member GUID everywhere; long opaque path tokens on cts.indeed.com and web.totaljobsmail.co.uk; unsubscribe/manage/preferences/tracking-pixel URLs -> https://example.com/redacted; Salford and Leeds -> Sampletown, LS3 -> ST1.
- Kept: job titles, companies, salaries, job IDs and link structure. `M1 6DE` in cv-library.eml is a job location, not the person's, and is kept.

## Verification

- Plan check extended to six files: `samples ok [...]`; `grep -iwFf scrub-terms.txt` finds nothing.
- No member GUID, alert ID, user hash, gmail.com, Salford, Leeds or LS3 remains.
- `api/samples/` is committable; `git status --porcelain api/data` is empty.

## Notes for 04-05

- Forwards keep Gmail's `gmail_quote` wrapper and may have `m_<digits>` class prefixes; parsers must not depend on outer markup.
- indeed-match and totaljobs-invite links carry no job ID (RESEARCH A2): dedupe must fall back to title+company.
- Six senders to register in `alerts.ALERTS`.

## Self-Check: PASSED
