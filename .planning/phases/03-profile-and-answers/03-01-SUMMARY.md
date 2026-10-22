---
phase: 03-profile-and-answers
plan: 01
subsystem: dependencies
tags: [pypdf, python-docx, lxml, requirements, package-legitimacy]
requires: []
provides:
  - "pypdf and python-docx pinned in api/requirements.txt and installed in .venv (unblocks PROF-01 in plan 03-03)"
affects: [03-03]
tech-stack:
  added: [pypdf 6.21.2, python-docx 1.2.0, lxml 6.1.3]
  patterns: []
key-files:
  created: []
  modified: [api/requirements.txt]
decisions:
  - "Upper-bounded pins (pypdf <7, python-docx <2) block unreviewed major releases; pypdf floor 6.0 excludes old parser bugs"
metrics:
  duration: "~5 min"
  completed: 2026-10-22
status: complete
requirements: [PROF-01]
actuals:
  tokens: 50
  tasks: 2
  commits: 0   # uncommitted by user's standing instruction (no git commits by agent)
plan_head_before: aa13305d1ef4ea2e02c9a9ac691426f8898778b9
plan_head_after: aa13305d1ef4ea2e02c9a9ac691426f8898778b9
---

# Phase 3 Plan 01: Install and pin CV-parsing libraries Summary

pypdf>=6.0,<7 and python-docx>=1.1,<2 are pinned in api/requirements.txt and installed in .venv (Python 3.9.6) after a human package-legitimacy approval.

## Tasks

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | Package-legitimacy checkpoint (blocking-human) | n/a (no file change) |
| 2 | Pin and install pypdf and python-docx | uncommitted — pending user approval |

**Task 1:** The user replied "approved" for both pypdf and python-docx on 2026-10-22. The checkpoint was resolved before this run began, so no package was installed without approval.

**Task 2:** `api/requirements.txt` is now exactly three lines (`flask>=3.0`, `pypdf>=6.0,<7`, `python-docx>=1.1,<2`). `.venv/bin/pip install -r api/requirements.txt` installed:

- pypdf 6.21.2
- python-docx 1.2.0
- lxml 6.1.3 (python-docx dependency; typing_extensions was already present)

## Verification

- Verify command printed `deps ok 6.21.2` (import of pypdf and docx, DOCX in-memory write and re-read round trip)
- `api/test_core.py`: `ok: 49 tests`
- `api/test_api.py`: `ok: 42 tests` (the "fetch failed" lines in its output are expected, from tests that simulate source failures)
- Exact-content check of requirements.txt passed; `pip show pypdf python-docx lxml` lists all three
- pypdf major version is 6

## Deviations from Plan

None - plan executed exactly as written. Per the user's standing instruction, no git commit was made, so `commits: 0` in the frontmatter reflects the uncommitted state, not an absence of changes. The only changed file is api/requirements.txt, pending user approval to commit.

## Known Stubs

None.

## Threat Flags

None. T-03-01 (version ranges) and T-03-SC (legitimacy gate) are both mitigated as planned.

## Self-Check: PASSED

- api/requirements.txt: FOUND, content matches the plan
- Installed versions confirmed with pip show
- Test suites green
