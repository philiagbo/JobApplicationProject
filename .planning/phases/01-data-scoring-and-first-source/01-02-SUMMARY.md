---
phase: 01-data-scoring-and-first-source
plan: 02
subsystem: api
tags: [scoring, regex, stdlib]
requires: [01-01]
provides:
  - core.summarize with annualised currency-tagged salary, job type, remote, years and bullets
  - core.score with salary, title, remote and excluded-word rules plus pros/cons sentences
  - api/test_core.py (30 plain-assert tests)
affects: [01-03]
tech-stack:
  added: []
  patterns: [bounded regexes for untrusted text, stdlib re/html only]
key-files:
  created: [api/test_core.py]
  modified: [api/core.py]
key-decisions:
  - "Salary +30 above minimum, -15 to -45 below (scaled), title +15, remote +10, hybrid +5, excluded -25 once"
  - "score falls back to summarize(job) when job has no summary"
status: complete
commits: 2
plan_head_before: 0790179505bb817052df445e3c42e3dbf1b64eb6
plan_head_after: 4e289787d27341c5acc238cf3f4eff9f130e9869
actuals:
  tokens: 9000
  tasks: 2
  commits: 2
requirements-completed: [SCORE-01, SCORE-02, SCORE-03, SCORE-04]
---

# Phase 1 Plan 02: Summarize and score rules Summary

Rule-based summarize (salary annualised and currency-tagged, type, remote, years, 3+3 bullets) and score (salary-heaviest, excluded words penalised but kept) pinned by 30 plain-assert tests.

## Tasks

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | summarize extracts salary, type, remote, years, bullets | af07d40 |
| 2 | score ranks by salary, title, remote, excluded words | 4e28978 |

## Verification

- `python api/test_core.py`: `ok: 30 tests` (includes the real Remotive `$35,3k- $52k` = 43650 case and a 200 KB adversarial input under 2 s).
- `python api/test_api.py`: `ok: 10 tests` (01-01 contract intact).
- Interpreter: main checkout venv (Python 3.9.6), since the worktree has no `.venv`.

## Deviations from Plan

None - plan executed exactly as written. Only api/core.py and api/test_core.py were touched. Tests were written first for each task; the score tests were held out of the Task 1 commit so each task commit is green on its own.

## Known Stubs

None. Skills and experience-gap rules are intentionally not applied (D-05, Phase 3); `profile` is accepted and ignored.

## Threat Flags

None. T-01-07 mitigated: all tag/salary/years regexes use bounded quantifiers and the adversarial test asserts under 2 s.

## Self-Check: PASSED

api/core.py and api/test_core.py exist; commits af07d40 and 4e28978 exist.
