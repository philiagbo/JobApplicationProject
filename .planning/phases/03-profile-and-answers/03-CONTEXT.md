# Phase 3: Profile and Answers - Context

**Gathered:** 2026-10-19
**Status:** Ready for planning

<domain>
## Phase Boundary

API and core logic only (no UI): a profile pre-filled from an uploaded CV (PDF/DOCX) and editable; `/api/answers` CRUD over the existing `answers` table; `find_answer` (exact, then fuzzy ≥ 0.85, mapped onto dropdown/radio options); the rule that blocks saving company-specific or over-300-character answers; and `cover_letter` filling an editable template from profile + job. Also switches on the skills-matched scoring rule that Phase 1 deferred until a profile exists. Autofill (which consumes all of this) is Phase 5.

</domain>

<decisions>
## Implementation Decisions

### Profile and CV upload
- **D-01:** The profile is one record with fixed fields (at least name, email, phone, linkedin, skills list), served by `GET /api/profile` (full shape with empty defaults) and `PUT /api/profile` (merge, type-checked, unknown keys → 400, same style as settings D-16/D-18 of Phase 1). Storage shape (new table vs. a settings key) is Claude's discretion. — **Reversibility:** costly — Phase 5 autofill's profile keyword map reads these field names.
- **D-02:** CV upload (`POST /api/profile/cv`, multipart) fills only empty profile fields; never overwrites hand edits. Extracted skills are merged into the existing list (deduped, case-insensitive). Response returns the updated profile.
- **D-03:** The uploaded CV file is kept (one file, under `api/data/`, gitignored with the DB) so Phase 5 can attach it to "Upload CV" fields. A new upload replaces it.
- **D-04:** Skills come from both the CV's "Skills" section lines (if a heading exists) and a built-in known-skills list matched across the whole CV text.
- **D-05:** Common application questions from PLAN.md (address, right to work, visa sponsorship, notice period/start date, salary expectation, relocation, driving licence, highest qualification, portfolio, how did you hear, equal-opportunities questions) are seeded into `answers` with `source='profile'` on startup if missing — empty answers, except equal-opportunities ones which default to "Prefer not to say". Seeding never overwrites an existing row. Empty seeded answers are not returned as matches by `find_answer`.
- **D-06:** Upload accepts PDF/DOCX only, max 10 MB. Wrong type, unreadable file, or a PDF with no extractable text → 400 `{"error": ...}` (e.g. "Couldn't read text from this CV").

### Skills scoring (lifts Phase 1 D-05 partly)
- **D-07:** Turn on the skills-matched rule: count profile skills found in the job text; add a pro like "Matches 4 of your skills: Excel, SQL…" and a small boost that grows with the count and is capped. Salary stays the heaviest rule (Phase 1 D-02). No skills in profile → rule skipped (no pro, no effect).
- **D-08:** Experience-gap rule stays off (years from CV is unreliable). "Requirements the CV doesn't mention" con stays off (needs Phase 4 full descriptions).
- **D-09:** Profile changes (PUT /api/profile or CV upload) re-score all `new` jobs, same rule as Phase 1 D-08; queued/dismissed keep their score.

### Answer matching and saving
- **D-10:** `find_answer(label, options=None)` normalises the label (existing `core.normalise`), tries exact match, then `difflib` fuzzy ≥ 0.85. Several fuzzy hits → highest ratio wins; ties → most recently updated.
- **D-11:** Option mapping order: case-insensitive exact option, then Yes/No prefix logic (saved "Yes" → "Yes, I have the right to work"), then best `difflib` option ≥ 0.85; otherwise no option (field left for the person — never a guess).
- **D-12:** The save-blocking rule checks both the question and the answer: blocked if the company name appears in either (case-insensitive), or the answer is longer than 300 characters. One shared function used by `/api/answers` and later by the Phase 5 learner. On direct `/api/answers` calls the company check applies only when a company is supplied in the request.
- **D-13:** A blocked save to `/api/answers` returns 400 with a reason (`{"error": "Not saved: mentions the company"}` / `"... longer than 300 characters"`).
- **D-14:** `/api/answers` supports list, create, edit, delete. Questions are stored normalised (UNIQUE already in schema). Unknown id → 404.

### Cover letter
- **D-15:** Default template ships as `api/cover_letter.txt` (never written to). The person's edited version is a `cover_letter_template` setting; blank means use the default.
- **D-16:** Placeholders: `{name}`, `{email}`, `{phone}`, `{company}`, `{job_title}`, `{top_skills}` (matched skills, else first 3 profile skills), `{date}`. Unknown placeholders are left as typed; missing values become blank — never an error.
- **D-17:** `core.cover_letter(profile, job, template) -> str` is pure; `GET /api/jobs/<id>/cover-letter` returns the filled text (404 for unknown job). Nothing is stored per job.

### Claude's Discretion
- Profile storage shape (table vs. settings key) and the exact extra profile fields beyond D-01's minimum.
- Contents of the known-skills list and the seeded question wording.
- Skills-boost point values and cap (tests pin ordering: salary still dominates).
- CV parsing libraries per CLAUDE.md stack (`pypdf`, `python-docx`) and regexes for name/email/phone/LinkedIn.
- Whether saving an answer clears a matching `unanswered` row (cheap; consistent with PLAN.md).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Original design
- `PLAN.md` — Data section (`answers`, `unanswered`), Apply queue steps 4–6 (`find_answer`, save rules), Profile page section (common questions list), test list (`find_answer` visa example, cover-letter placeholders, company-answer rule)

### Requirements and roadmap
- `.planning/REQUIREMENTS.md` — PROF-01..PROF-05
- `.planning/ROADMAP.md` — Phase 3 success criteria

### Prior phase decisions
- `.planning/phases/01-data-scoring-and-first-source/01-CONTEXT.md` — scoring rules (D-01..D-08, esp. D-05 deferral and D-08 re-score), settings API shape (D-16..D-18), DB/test conventions (D-23..D-25)
- `.planning/phases/02-watcher-and-more-sources/02-CONTEXT.md` — settings changes wake the watcher (D-14)

### Codebase maps
- `.planning/codebase/CONVENTIONS.md`, `.planning/codebase/TESTING.md`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `api/db.py` `answers` and `unanswered` tables already exist (question UNIQUE, field_type, source, updated_at).
- `api/db.py` `get_settings` / `save_settings` / `_clean` / `DEFAULTS`: pattern for typed merge-and-validate; add `cover_letter_template` here.
- `api/db.py` `rescore_new(conn, settings)`: reuse for D-09 (will need the profile passed through).
- `api/core.py` `normalise(text)`: label normalisation for D-10.
- `api/core.py` `score(job, settings, profile=None)`: already takes `profile` and ignores it — D-07 plugs in here; `_text_lines` helps scan job text.

### Established Patterns
- Pure functions in `core.py`, DB helpers in `db.py`, thin Flask routes in `app.py`; errors as `{"error"}` with 400/404/409.
- Plain-assert tests run as scripts (`api/test_core.py`, `api/test_api.py`), temp DB via `JOBHELPER_DB`.
- Python 3.9-compatible typing (`typing.Optional`, no `X | Y`).

### Integration Points
- `api/requirements.txt` currently only has `flask>=3.0` — `pypdf` and `python-docx` must be added.
- Phase 2 watcher calls `insert_jobs` / scoring — it must pass the profile so new jobs get the skills rule.
- Phase 5 autofill will call `find_answer`, the save-blocking check, `cover_letter`, and use the stored CV file.

</code_context>

<specifics>
## Specific Ideas

- PLAN.md test: differently worded visa sponsorship questions must match the same saved answer, and the answer must map onto a Yes/No dropdown.
- Equal-opportunities answers default to "Prefer not to say".

</specifics>

<deferred>
## Deferred Ideas

- Experience-gap scoring rule — revisit after real CVs are seen.
- "Requirements the CV doesn't mention" con — after Phase 4 full descriptions.

</deferred>

---

*Phase: 03-profile-and-answers*
*Context gathered: 2026-10-19*
