---
phase: 03-profile-and-answers
plan: 03
subsystem: api
tags: [flask, sqlite, pypdf, python-docx, cv-extraction, profile]
requires:
  - phase: 03-profile-and-answers
    provides: pypdf and python-docx installed (03-01); core.normalise and answers (03-02)
provides:
  - GET/PUT /api/profile and POST /api/profile/cv (PDF or DOCX upload pre-fills the profile)
  - core.extract_profile / merge_profile / dedupe_skills / has_term / KNOWN_SKILLS
  - db.get_profile / save_profile / store_cv / cv_file_name / cv_dir (profile as one settings row, one stored CV)
  - cv.read_cv_text (only module importing pypdf and docx)
affects: [03-04, 05-autofill]
requirements-completed: [PROF-01]
actuals:
  tokens: 40000
  tasks: 3
  commits: 0
plan_head_before: d59eee4db603b0dce901cfbbae6deb563d7b424f
plan_head_after: d59eee4db603b0dce901cfbbae6deb563d7b424f
tech-stack:
  added: []
  patterns: ["profile as a JSON row in settings (get_settings ignores it)", "validate and parse before storing, atomic os.replace for the CV file"]
key-files:
  created: [api/cv.py]
  modified: [api/core.py, api/db.py, api/app.py, api/test_core.py, api/test_api.py, .gitignore]
key-decisions:
  - "Phone regex uses [ \\t] instead of \\s so a number cannot span two lines"
  - "DOCX read walks iter_inner_content so table text stays in document order"
status: complete
---

# Phase 3 Plan 3: Profile and CV upload Summary

Uploading a PDF or DOCX CV to `POST /api/profile/cv` returns the profile pre-filled with name, email, phone, LinkedIn and skills; hand edits are never overwritten, the CV is kept as one fixed-name file, and bad files get a specific 400 with nothing changed.

## Commits

uncommitted — pending user approval (user's standing no-commit instruction; `commits: 0` is true, not a halt).

## Tasks and files touched

| Task | What | Files (all uncommitted) |
|------|------|-------------------------|
| 1 Tracer: PDF upload to GET /api/profile | cv.py, extract_profile (initially email and name), profile helpers, three-route skeleton, `make_pdf`, `test_cv_upload_end_to_end` | api/cv.py (new), api/core.py, api/db.py, api/app.py, api/test_api.py |
| 2 Full extraction (D-04) | phone, LinkedIn, KNOWN_SKILLS, has_term, skills section, 13 named tests | api/core.py, api/test_core.py |
| 3 DOCX tables, PUT, validation, gitignore | iter_inner_content with merged-cell dedupe, PUT /api/profile, `make_docx`, 9 tests, `api/data/` ignored | api/cv.py, api/app.py, api/test_api.py, .gitignore |

Tasks were written in one pass, so the tracer's intermediate state was not run on its own; the final code and every named test were run.

## Verification

- `api/test_core.py`: ok: 62 tests (49 before, +13)
- `api/test_api.py`: ok: 52 tests (42 before, +10)
- `api/test_watcher.py`: ok: 18 tests (unchanged)
- Acceptance greps pass; `git check-ignore api/data/cv.pdf` and `cv.docx` succeed; `cv.py` imports no network module.
- The 10 MB upload test runs in about 1 second total.

## Deviations from Plan

**1. [Rule 1 - Bug avoided] Phone regex whitespace class.** The RESEARCH.md Pattern 11 regex uses `\s` inside the digit run, which can join digits across a newline (for example a phone line followed by a year line). Changed to `[ \t]`. Same bounded shape, so ReDoS safety is unchanged.

**2. Test-output noise.** `test_cv_upload_rejects` silences logging with `logging.disable(logging.WARNING)` instead of toggling only `app.app.logger.disabled`, because pypdf's own logger also prints "EOF marker not found" for the junk PDF cases. It restores `logging.NOTSET` in `finally`.

Otherwise the plan was executed as written.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-03-07 (fixed server-side name, tested with `../../evil.pdf`), T-03-08 (10 MB cap, magic bytes, broad except, 200 000 char cap), T-03-10 (`api/data/` ignored, no network imports in cv.py) and T-03-11 (adversarial 200 000-char input under 2 s) are covered by tests or acceptance checks.

## Notes for later

- Real CV layouts vary; the Task 3 human-check (curl a real PDF and DOCX at `/api/profile/cv`) was not run here and is still outstanding.
- `/api/profile` PUT and the upload do not re-score `new` jobs yet; plan 03-04 adds the D-09 re-score as the plan states.
- Name rule known limit and LinkedIn-behind-link-text limit are marked with `ponytail:` comments in `core.py`.

## Self-Check: PASSED

Files exist (api/cv.py and all modified files), test suites green as listed above. No git history was changed.

## Post-execution change (user-requested, 2026-10-23)

- Removed the hard-coded, tech-only `core.KNOWN_SKILLS`. Whole-text matching now uses a new `known_skills` setting (`db.DEFAULTS`, editable via `PUT /api/settings`, **empty by default**), passed as `core.extract_profile(text, known_skills)`.
- Why: the person may not be in a tech role. With the default, skills come only from the CV's Skills section plus hand edits via `PUT /api/profile`.
- Tests: `test_known_skills_list` replaced by `test_known_skills_default_empty`; added `test_cv_upload_uses_known_skills_setting`. core 62, api 53, watcher 18 — all green.
