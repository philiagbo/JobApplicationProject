---
phase: 03-profile-and-answers
verified: 2026-10-23T18:10:00Z
status: passed
score: 5/5 must-haves verified
covered_files:
  - api/app.py
  - api/core.py
  - api/cover_letter.txt
  - api/cv.py
  - api/db.py
  - api/requirements.txt
  - api/test_api.py
  - api/test_core.py
covered_digest: "v2:sha256:c7357d7ab231d9e0b55d6c0031a3bb0a9c1ae66caaa42ff2013158e477478641"
behavior_unverified: 0
overrides_applied: 0
---

# Phase 3: Profile and Answers Verification Report

**Phase Goal:** The person's profile and saved answers exist and can be matched to application form questions
**Verified:** 2026-10-23
**Status:** passed
**Re-verification:** No, initial verification

## Observable Truths

| # | Truth (ROADMAP success criterion) | Status | Evidence |
|---|---|---|---|
| 1 | Uploading a PDF or DOCX CV pre-fills name, email, phone, LinkedIn and skills in the profile returned by the API | VERIFIED | `app.py:209` `profile_cv` validates ext/size, `cv.read_cv_text` (pypdf / python-docx incl. tables), `core.extract_profile`, `db.save_profile(merge_profile)`, returns `_profile_json`. Independent run: a generated DOCX returned name "Jane Smith", jane@example.com, +44 7700 900123, https://linkedin.com/in/janesmith, skills Python/SQL/Docker; `GET /api/profile` returned the same. PDF path covered by `test_cv_upload_pdf_all_fields`. |
| 2 | `/api/answers` lists, creates, edits and deletes saved answers | VERIFIED | `app.py:148-186` GET/POST/PUT/DELETE backed by real SQL in `db.py`. Independent run: POST ok, PUT 200, DELETE 200. 16 answers seeded on startup. Tests: `test_answers_*`. |
| 3 | `find_answer` returns the saved answer by exact, then fuzzy (>= 0.85) match, and maps it onto the matching dropdown or radio option | VERIFIED | `core.find_answer` (`core.py:286`): single max over `SequenceMatcher` ratio, `FUZZY_MIN = 0.85`, then `map_option` (exact / yes-no polarity / fuzzy). Independent run: "Do you require visa sponsorship" with options ["Yes, I do","No, I do not"] returned answer "No" mapped to "No, I do not". A wordy label below 0.85 correctly returns None (`test_find_answer_wordy_variant_misses`). `db.find_answer` wrapper exists. |
| 4 | An answer that mentions the company name or is longer than 300 characters is not saved | VERIFIED | `core.answer_block_reason` called from both `db.save_answer` and `db.update_answer`. Independent run: company mention gives 400 "Not saved: mentions the company"; 301 chars gives 400 "Not saved: longer than 300 characters". `test_answers_blocked_writes_nothing` confirms nothing is written. |
| 5 | `cover_letter` returns an editable template filled from the profile and the job | VERIFIED | `core.cover_letter` (single regex pass, unknown placeholders left literal), `api/cover_letter.txt` default, `cover_letter_template` setting overrides, `GET /api/jobs/<id>/cover-letter` (404 for unknown job). Independent run produced a letter with job title, company, matched skills, phone, email, name and "23 October 2026". |

**Score:** 5/5 truths verified. No behavior-dependent truths left unexercised.

## Requirements Coverage

| Requirement | Status | Evidence |
|---|---|---|
| PROF-01 CV upload pre-fills name, email, phone, LinkedIn, skills | SATISFIED | Truth 1; `api/cv.py`, `core.extract_profile`, `/api/profile/cv`; pypdf and python-docx pinned in `requirements.txt` |
| PROF-02 `/api/answers` list/create/edit/delete | SATISFIED | Truth 2 |
| PROF-03 `find_answer` exact then fuzzy >= 0.85, maps onto options | SATISFIED | Truth 3 |
| PROF-04 company-mentioning or >300-char answers not saved | SATISFIED | Truth 4 |
| PROF-05 `cover_letter` fills editable template | SATISFIED | Truth 5 |

No orphaned requirements: all five PROF IDs are claimed by plans 03-01..03-04.

## Key Links

| From | To | Status |
|---|---|---|
| `app.profile_cv` | `cv.read_cv_text` -> `core.extract_profile` -> `db.save_profile` | WIRED |
| `app.answers_*` | `db.save/update/delete_answer` -> `core.answer_block_reason` | WIRED |
| `db.find_answer` | `core.find_answer` over `list_answers` | WIRED |
| `app.job_cover_letter` | `db.get_profile`, `db.get_job`, `core.cover_letter`, setting then `cover_letter.txt` | WIRED |
| profile save / CV upload / new jobs | `db.rescore_new` / `insert_jobs` pass profile to `core.score` (capped skills rule) | WIRED |

## Behavioral Spot-Checks

| Check | Command | Result | Status |
|---|---|---|---|
| Full suite (run once) | `.venv/bin/python -m pytest api -q` | 153 passed, 2 warnings (unhandled-thread warning from an existing `test_watcher.py` stub, not Phase 3) | PASS |
| End-to-end CV, answers, cover letter | ad-hoc script against temp DB via Flask test client | all outputs as described above | PASS |

## Anti-Patterns

Scanned `api/*.py` for TBD/FIXME/XXX: none. `ponytail:` comments in `core.py` and `app.py` are documented deliberate shortcuts (one-word-name heuristic, LinkedIn link-text not scanned), not stubs. `api/data/` is gitignored (confirmed with `git check-ignore`).

## Informational Notes (not gaps)

- Plan 03-04 work (cover letter, skills scoring, `api/cover_letter.txt`, `03-04-SUMMARY.md`) is uncommitted in the working tree. The code is present and tested; it needs committing for the phase to be durable.
- ROADMAP.md Phase 3 plan checkboxes and REQUIREMENTS.md PROF-01..05 / traceability rows still read "Pending" / unchecked. Bookkeeping to update on phase completion.
- Fuzzy matching is literal at 0.85: heavily reworded labels (for example "Will you now or in the future need visa sponsorship?") return no match. This is the specified behavior, with the miss pinned by a test.

## Gaps Summary

None. All five success criteria and all five requirements are met by real, wired, tested code.

---

_Verified: 2026-10-23_
_Verifier: Claude (gsd-verifier)_
