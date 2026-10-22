---
phase: 03-profile-and-answers
plan: 02
subsystem: api
tags: [flask, sqlite, difflib, answers, fuzzy-matching]
requires:
  - phase: 01-foundation
    provides: core.normalise, db schema (answers, unanswered), CheckedClient test harness
provides:
  - /api/answers list, create (upsert), edit, delete
  - core.find_answer / map_option / answer_block_reason (pure matching and blocking)
  - 16 common questions seeded on every startup
affects: [05-autofill, 03-03, 03-04]
actuals:
  tokens: 31000
  tasks: 3
  commits: 0
plan_head_before: afcfac0ad9afdbf315dc971eb6c434262e75ad3a
plan_head_after: afcfac0ad9afdbf315dc971eb6c434262e75ad3a
tech-stack:
  added: []
  patterns: ["single-statement upsert on UNIQUE column", "plain-loop fuzzy match with quick_ratio prefilter"]
key-files:
  created: []
  modified: [api/core.py, api/db.py, api/app.py, api/test_core.py, api/test_api.py]
key-decisions:
  - "find_answer returns None (not a dict with option None) when a saved answer maps to no option (A4)"
  - "POST /api/answers is an upsert: 201 new, 200 updated (A5)"
  - "An empty answer is never blocked by answer_block_reason, even if the question names the company"
requirements-completed: [PROF-02, PROF-03, PROF-04]
status: complete
---

# Phase 3 Plan 2: Saved answers Summary

Saved answers end to end: CRUD at `/api/answers`, exact-then-fuzzy (>= 0.85) `find_answer` that maps onto dropdown/radio options without guessing, a shared 300-char / company-name save block, and 16 seeded common questions.

## Accomplishments

- `core.py`: `FUZZY_MIN`, `MAX_ANSWER_CHARS`, `MAX_QUESTION_CHARS`, `answer_block_reason`, `map_option` (exact, yes/no prefix, fuzzy), `find_answer` (exact, then best ratio, ties by `updated_at` then id; `autojunk=False`; `quick_ratio` prefilter).
- `db.py`: `SEED_QUESTIONS` (16; five equal-opportunities default to "Prefer not to say"), `seed_answers` via `INSERT OR IGNORE` called from `init_db`, `save_answer` (one `ON CONFLICT(question) DO UPDATE` statement, clears matching `unanswered` row), `update_answer`, `delete_answer`, `list_answers`, `check_answer_body`, `find_answer` wrapper.
- `app.py`: GET/POST `/api/answers`, PUT/DELETE `/api/answers/<int:answer_id>` with 400 / 404 / 409 error mapping.
- Tests: 19 new in `test_core.py` (49 total), 10 new in `test_api.py` (42 total). `test_watcher.py` unchanged, 18 pass.

## Deviations from Plan

None - plan executed as written. Notes:
- The user rule "do not commit" applied, so all work is uncommitted working-tree changes; `commits: 0` above is true, not a halt (the plan's "0 with code changes" rule is overridden by the user's review-before-commit instruction).
- `test_api.py` already had a `sql()` helper that returns nothing; the new SELECT helper is named `select()` instead.
- `answer_block_reason` returns None up front for an empty answer (plan: "an empty answer is never blocked").

## Known Stubs

None. (Seeded questions with empty answers are intentional, per D-05; they never match in `find_answer`.)

## Threat Flags

None beyond the plan's threat model; new routes sit behind the existing `local_only` guard.

## Assumptions to check

A1 (SQLite >= 3.24 for `ON CONFLICT DO UPDATE` on the target Windows Python) is not testable here; local SQLite is fine.

## Self-Check: PASSED

`api/test_core.py` ok: 49 tests; `api/test_api.py` ok: 42 tests; `api/test_watcher.py` ok: 18 tests; all plan acceptance greps and the seed-count check pass.
