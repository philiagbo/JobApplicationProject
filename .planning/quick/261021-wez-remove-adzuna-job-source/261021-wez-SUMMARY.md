---
phase: quick-261021-wez
plan: 01
subsystem: api
tags: [sources, watcher, settings, docs]
requires: []
provides:
  - "Remotive and Reed are the only job sources; Adzuna code, settings and tests removed"
affects: [api/sources.py, api/watcher.py, api/db.py, api/app.py]
key-files:
  modified:
    - api/sources.py
    - api/watcher.py
    - api/test_watcher.py
    - api/db.py
    - api/app.py
    - api/test_api.py
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - .planning/PROJECT.md
    - .planning/phases/02-watcher-and-more-sources/COVERAGE.md
decisions:
  - "Adzuna removed; adapter and tests stay in git history"
status: complete
actuals:
  tokens: 15000
  tasks: 3
  commits: 3
plan_head_before: 1804e511220e9888f6ab9fe23ae698823f232395
plan_head_after: 4271a286e96ad2cdd764b292ac0fd1332125bfe0
---

# Quick 261021-wez: Remove Adzuna job source Summary

Adzuna is gone from `api/` (adapter, settings keys, wake keys, tests); Phase 2 docs now describe Remotive and Reed only.

## Tasks

| Task | Commit | Notes |
|------|--------|-------|
| 1 Remove from fetch path | 7f46022 | deleted fetch_adzuna/_canonical/_adzuna_type/ADZUNA_URL, watcher branch, 6 Adzuna tests; test_three_sources_one_poll renamed test_two_sources_one_poll |
| 2 Drop settings and wake keys | 2150104 | DEFAULTS, WAKE_KEYS, test_settings_save_wakes_watcher |
| 3 Docs | 4271a28 | REQUIREMENTS SRC-03, ROADMAP (5 edits), PROJECT, COVERAGE.md rewritten (gate passes) |

## Verification

test_core "ok: 30 tests", test_api "ok: 31 tests", test_watcher "ok: 15 tests"; `grep -rni adzuna api/` empty; api-coverage gate `"passed": true`; 02-04-PLAN.md untouched.

## Deviations from Plan

- The CRLF-to-LF restore of `api/app.py` (`git checkout -- api/app.py`, precondition confirmed by orchestrator) was run at the start of Task 1 rather than Task 2; it was left unstaged in Task 1 and committed in Task 2, so the Task 2 commit for app.py is the one-line WAKE_KEYS diff with LF endings.
- Commits were made on `master` (main working tree, as directed by the orchestrator).

## Known Stubs

None.

## Self-Check: PASSED

Commits 7f46022, 2150104, 4271a28 exist; all modified files present.
