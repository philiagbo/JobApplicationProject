---
phase: 02-watcher-and-more-sources
plan: 04
subsystem: testing
tags: [reed, watcher, live-verification, manual-uat]
requires:
  - phase: 02-watcher-and-more-sources
    provides: run_fetch, watcher thread, settings-save wake, GET /api/watcher (plans 02-01 to 02-03)
provides:
  - Live confirmation of the Reed adapter and watcher against the real Reed API
  - Assumption A5 (Reed field names) confirmed on real data
affects: [later phases that mask or display settings, UI that reads /api/watcher]
actuals:
  tokens: 0
  tasks: 2
  commits: 0
plan_head_before: 6b7798c437c7141f4be6b3f347324ed3bf271aa5
plan_head_after: 6b7798c437c7141f4be6b3f347324ed3bf271aa5
tech-stack:
  added: []
  patterns: []
key-files:
  created: []
  modified: []
key-decisions:
  - "Phase 2 live check ran Reed-only (plus keyless Remotive) because Adzuna was removed by quick task 261021-wez"
requirements-completed: [SRC-03, WATCH-01, WATCH-02]
coverage:
  - id: D1
    description: "The real process (debug off) starts the watcher once and stays quiet with no career fields"
    requirement: "WATCH-01"
    verification:
      - kind: integration
        ref: "02-04-PLAN.md Task 1 automated command (test_core, test_api, test_watcher, then GET /api/watcher: running true, sources {})"
        status: pass
    human_judgment: false
  - id: D2
    description: "A real Reed key save wakes the watcher; Reed jobs arrive scored with no manual fetch"
    requirement: "SRC-03"
    verification: []
    human_judgment: true
    rationale: "Needs the person's own Reed key against the live API; verified by the person in Task 2 steps 2 to 5"
  - id: D3
    description: "A second fetch adds 0 new jobs (URL dedupe holds on real data)"
    requirement: "SRC-03"
    verification: []
    human_judgment: true
    rationale: "Real Reed data; verified by the person in Task 2 step 6"
  - id: D4
    description: "A wrong Reed key fails only Reed; Remotive still delivers; no key text in output"
    requirement: "WATCH-01"
    verification: []
    human_judgment: true
    rationale: "Live 401 from Reed; verified by the person in Task 2 step 7"
  - id: D5
    description: "Changing api_poll_minutes to 1 changes poll cadence with no restart"
    requirement: "WATCH-02"
    verification: []
    human_judgment: true
    rationale: "Needs wall-clock waiting against the running process; verified by the person in Task 2 step 8"
duration: 1 session
completed: 2026-10-21
status: complete
---

# Phase 2 Plan 04: Live Reed verification Summary

**Real Reed API check passed: a key save wakes the watcher, 50 Reed jobs arrive with no manual fetch, dedupe holds, a bad key fails only Reed, and a 1-minute interval takes effect without a restart**

## Performance

- **Duration:** one session (offline suite plus person's live check)
- **Completed:** 2026-10-21
- **Tasks:** 2 (1 auto, 1 human-verify checkpoint, approved)
- **Files modified:** 0 source files (verification only)

## Accomplishments

- Task 1: all three offline suites green and the real process (debug off) started the watcher once; GET /api/watcher showed running true and no sources with no career fields.
- Task 2 (human verification, "approved") against the real Reed API with the person's own key:
  - Step 2: settings PUT printed 200 (key loaded).
  - Step 3: GET /api/watcher showed reed ok true, error null, new 50, and remotive ok true, error null, new 10, with no key text. The settings save woke the watcher with no manual fetch (D-14).
  - Step 4: job sources were `Counter({'reed': 50, 'remotive': 10})`.
  - Step 5: sample job "Data Analyst | Harnham - Data & Analytics Recruitment | London | £50,000 - £55,000 | https://www.reed.co.uk/jobs/data-analyst/57355215". Assumption A5 (Reed field names) confirmed.
  - Step 6: POST /api/fetch returned `{"by_source":{"reed":0,"remotive":0},"errors":{},"new":0}`. URL dedupe holds on real data.
  - Step 7: with a wrong key, POST /api/fetch returned `{"by_source":{"remotive":0},"errors":{"reed":"Reed fetch failed: HTTP Error 401: Unauthorized"},"new":0}`. Reed failed alone, with no key text.
  - Step 8: key restored and api_poll_minutes set to 1; reed last_poll moved 22:03:48Z to 22:09:51Z with no restart and no manual fetch, reed ok true.
- ROADMAP Phase 2 success criteria 1 to 4 observed on the real API in the real process.

## Task Commits

1. **Task 1: Full suite green, real process starts watcher quietly** - no commit (verification only)
2. **Task 2: Real Reed key checkpoint** - no commit (human verification, approved)

**Plan metadata:** the docs commit that adds this SUMMARY.

## Files Created/Modified

None. This plan changes no source files.

## Decisions Made

None - followed plan as specified. The plan itself was already reduced to Reed-only by commit 6b7798c after Adzuna was removed (quick task 261021-wez).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The first attempt at step 2 did not save (settings empty, watcher sources `{}`). Re-running step 2 in the same terminal as `read -s REED` printed 200. Operator error (the variable was not set in that shell), not a code defect.

## Follow-ups (not a phase-02 gap)

- GET /api/settings returns `reed_api_key` in plain text. Worth masking in a later phase. GET /api/watcher does not leak it (confirmed in steps 3 and 7).

## User Setup Required

Reed jobseeker API key was supplied by the person for the check (read with `read -s`, never written to a file, throwaway database). No further setup.

## Next Phase Readiness

- Phase 2 is complete: Remotive and Reed deliver, the watcher polls on the configured interval, survives a failing source, and applies settings changes live.
- No blockers.

---
*Phase: 02-watcher-and-more-sources*
*Completed: 2026-10-21*

## Self-Check: PASSED
