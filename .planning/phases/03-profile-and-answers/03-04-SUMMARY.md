---
phase: 03-profile-and-answers
plan: 04
subsystem: api
tags: [scoring, cover-letter, profile, flask, sqlite]
requires:
  - phase: 03-profile-and-answers (03-03)
    provides: profile storage, has_term, GET/PUT /api/profile, CV upload
provides:
  - skills rule in core.score (2 points per matched skill, capped at 10) with a "Matches N of your skills" pro
  - core.matched_skills and core.cover_letter (pure, single-regex placeholder fill)
  - GET /api/jobs/<id>/cover-letter and api/cover_letter.txt default template
  - profile-aware db.insert_jobs / db.rescore_new, db.get_job, cover_letter_template setting
  - D-09 re-score of status-new jobs on profile save and CV upload
affects: [phase-5-autofill, ui-04]
key-files:
  created: [api/cover_letter.txt]
  modified: [api/core.py, api/db.py, api/app.py, api/test_core.py, api/test_api.py]
decisions:
  - "Skills boost 2 per skill, cap 10 (below TITLE_POINTS 15 and SALARY_ABOVE_POINTS 30), so salary dominates"
status: complete
commits: 0
plan_head_before: aa13305
plan_head_after: aa13305
requirements: [PROF-05]
actuals:
  tasks: 3
  commits: 0
---

# Phase 3 Plan 04: Skills scoring and cover letter Summary

Profile skills now lift matching jobs by a capped 2 points each with a "Matches N of your skills" pro, and `GET /api/jobs/<id>/cover-letter` returns an editable template filled from the profile and job, with nothing stored.

## Commits

None, by instruction: all changes are uncommitted working-tree changes for the user to review. `commits: 0` above is therefore not a sign of missing work.

## Tasks (files changed per task, uncommitted)

All three tasks touch overlapping files, so the per-task split below is by concern:

1. **Task 1 (tracer): cover-letter end to end.** `api/cover_letter.txt` (new), `api/core.py` (`matched_skills`, `_PLACEHOLDER`, `_MONTHS`, `_join_and`, `cover_letter`), `api/db.py` (`cover_letter_template` default, `get_job`), `api/app.py` (`DEFAULT_COVER_LETTER`, `job_cover_letter` route), `api/test_api.py` (`add_job`, `test_cover_letter_end_to_end`).
2. **Task 2: skills scoring and re-score.** `api/core.py` (`SKILL_POINTS_EACH`, `SKILL_POINTS_CAP`, skills rule in `score`, stale "ignored" comment replaced), `api/db.py` (`insert_jobs` and `rescore_new` take `profile=None` and load it once), `api/app.py` (`db.rescore_new` after `save_profile` in `profile_put` and `profile_cv`), `api/test_core.py` (6 new tests, `test_score_profile_ignored` deleted), `api/test_api.py` (3 re-score tests).
3. **Task 3: lock cover-letter rules.** `api/test_core.py` (7 cover-letter tests), `api/test_api.py` (3 route tests: template setting, unknown job 404, nothing stored).

## Verification

Run from the worktree with the main checkout's venv (it imports pypdf and docx fine):

- `.venv/bin/python -m pytest api -q`: 153 passed (133 before this plan).
- `api/test_core.py` prints `ok: 75 tests`, `api/test_api.py` prints `ok: 60 tests`, `api/test_watcher.py` prints `ok: 18 tests` (the watcher path through the profile-aware `insert_jobs` still works).
- `grep -c 'db.rescore_new(' api/app.py` gives 3.

## Deviations from Plan

**1. [Rule 3 - Blocking] Worktree base was stale.** The worktree was created at `aa13305` (03-02), before the 03-01 and 03-03 commits (`d59eee4`, `119753a`). To get the 03-03 code the plan builds on, the diff `aa13305..119753a` was applied to the working tree only (`git apply`, no index or history change). Consequence: `git status` in this worktree also shows the 03-01/03-03 changes (`.gitignore`, `api/cv.py`, `api/requirements.txt`, the 03-01 and 03-03 SUMMARY files, and their share of `app.py`, `core.py`, `db.py`, `test_api.py`, `test_core.py`). A patch containing only the 03-04 changes is at `/private/tmp/claude-501/-Users-philipagbo-Desktop-JobApplicationProject/d9f8679b-5ae0-4c97-a981-5b5117646659/scratchpad/03-04-only.patch` (paths prefixed `a/` and `b/`, apply in the main checkout with `patch -p1` or `git apply -p1`, no overlap with 119753a).

**2. [Rule 1 - Bug in plan] `test_matched_skills_title_and_description` input.** The plan's description `<li>Excel</li><b>sql</b>` runs the words together after tag stripping ("Excelsql"), so SQL cannot match. The test uses `<li>Excel</li><li><b>sql</b></li>` instead. It still checks tag-stripped, case-insensitive, profile-order matching. No code change needed.

**3. Minor, ponytail style.** `cover_letter` builds the values dict inline (no `_join_and` special cases beyond a one-line expression), and `test_cover_letter_template_setting` locates `cover_letter.txt` next to `app.__file__`. The per-task commit step and `PLAN_HEAD_BEFORE` ledger were skipped per the no-commit rule.

The plan's test-count floors (75 core, 50 API) are met (75 and 60).

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-03-13 is mitigated: one `re.sub` over `\{[a-z_]+\}` with a dict lookup, proven by `test_cover_letter_braces_literal`.

## Self-Check: PASSED

Files exist (`api/cover_letter.txt`, edited sources, this SUMMARY) and the full suite passes. No commit hashes are claimed.
