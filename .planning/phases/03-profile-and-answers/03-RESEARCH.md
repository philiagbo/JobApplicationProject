# Phase 3: Profile and Answers - Research

**Researched:** 2026-10-19
**Domain:** Flask + stdlib sqlite3 API; CV text extraction (pypdf, python-docx); stdlib `difflib` fuzzy matching; template filling
**Confidence:** HIGH (all in-repo facts read this session; both libraries exercised in a scratch venv on Python 3.9; regexes and fuzzy ratios run, not guessed)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Profile and CV upload**
- **D-01:** The profile is one record with fixed fields (at least name, email, phone, linkedin, skills list), served by `GET /api/profile` (full shape with empty defaults) and `PUT /api/profile` (merge, type-checked, unknown keys → 400, same style as settings D-16/D-18 of Phase 1). Storage shape (new table vs. a settings key) is Claude's discretion. — **Reversibility:** costly — Phase 5 autofill's profile keyword map reads these field names.
- **D-02:** CV upload (`POST /api/profile/cv`, multipart) fills only empty profile fields; never overwrites hand edits. Extracted skills are merged into the existing list (deduped, case-insensitive). Response returns the updated profile.
- **D-03:** The uploaded CV file is kept (one file, under `api/data/`, gitignored with the DB) so Phase 5 can attach it to "Upload CV" fields. A new upload replaces it.
- **D-04:** Skills come from both the CV's "Skills" section lines (if a heading exists) and a built-in known-skills list matched across the whole CV text.
- **D-05:** Common application questions from PLAN.md (address, right to work, visa sponsorship, notice period/start date, salary expectation, relocation, driving licence, highest qualification, portfolio, how did you hear, equal-opportunities questions) are seeded into `answers` with `source='profile'` on startup if missing — empty answers, except equal-opportunities ones which default to "Prefer not to say". Seeding never overwrites an existing row. Empty seeded answers are not returned as matches by `find_answer`.
- **D-06:** Upload accepts PDF/DOCX only, max 10 MB. Wrong type, unreadable file, or a PDF with no extractable text → 400 `{"error": ...}` (e.g. "Couldn't read text from this CV").

**Skills scoring (lifts Phase 1 D-05 partly)**
- **D-07:** Turn on the skills-matched rule: count profile skills found in the job text; add a pro like "Matches 4 of your skills: Excel, SQL…" and a small boost that grows with the count and is capped. Salary stays the heaviest rule (Phase 1 D-02). No skills in profile → rule skipped (no pro, no effect).
- **D-08:** Experience-gap rule stays off (years from CV is unreliable). "Requirements the CV doesn't mention" con stays off (needs Phase 4 full descriptions).
- **D-09:** Profile changes (PUT /api/profile or CV upload) re-score all `new` jobs, same rule as Phase 1 D-08; queued/dismissed keep their score.

**Answer matching and saving**
- **D-10:** `find_answer(label, options=None)` normalises the label (existing `core.normalise`), tries exact match, then `difflib` fuzzy ≥ 0.85. Several fuzzy hits → highest ratio wins; ties → most recently updated.
- **D-11:** Option mapping order: case-insensitive exact option, then Yes/No prefix logic (saved "Yes" → "Yes, I have the right to work"), then best `difflib` option ≥ 0.85; otherwise no option (field left for the person — never a guess).
- **D-12:** The save-blocking rule checks both the question and the answer: blocked if the company name appears in either (case-insensitive), or the answer is longer than 300 characters. One shared function used by `/api/answers` and later by the Phase 5 learner. On direct `/api/answers` calls the company check applies only when a company is supplied in the request.
- **D-13:** A blocked save to `/api/answers` returns 400 with a reason (`{"error": "Not saved: mentions the company"}` / `"... longer than 300 characters"`).
- **D-14:** `/api/answers` supports list, create, edit, delete. Questions are stored normalised (UNIQUE already in schema). Unknown id → 404.

**Cover letter**
- **D-15:** Default template ships as `api/cover_letter.txt` (never written to). The person's edited version is a `cover_letter_template` setting; blank means use the default.
- **D-16:** Placeholders: `{name}`, `{email}`, `{phone}`, `{company}`, `{job_title}`, `{top_skills}` (matched skills, else first 3 profile skills), `{date}`. Unknown placeholders are left as typed; missing values become blank — never an error.
- **D-17:** `core.cover_letter(profile, job, template) -> str` is pure; `GET /api/jobs/<id>/cover-letter` returns the filled text (404 for unknown job). Nothing is stored per job.

### Claude's Discretion
- Profile storage shape (table vs. settings key) and the exact extra profile fields beyond D-01's minimum.
- Contents of the known-skills list and the seeded question wording.
- Skills-boost point values and cap (tests pin ordering: salary still dominates).
- CV parsing libraries per CLAUDE.md stack (`pypdf`, `python-docx`) and regexes for name/email/phone/LinkedIn.
- Whether saving an answer clears a matching `unanswered` row (cheap; consistent with PLAN.md).

### Deferred Ideas (OUT OF SCOPE)
- Experience-gap scoring rule — revisit after real CVs are seen.
- "Requirements the CV doesn't mention" con — after Phase 4 full descriptions.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROF-01 | CV upload (PDF or DOCX) pre-fills name, email, phone, LinkedIn and skills | New `api/cv.py` (pypdf/python-docx text) + pure `core.extract_profile(text)`; regexes and skills-section parser below were run on samples; error mapping verified against real library exceptions |
| PROF-02 | `/api/answers` supports list, create, edit, delete | `db.save_answer` (upsert + block check + clears `unanswered`), `db.update_answer`, `db.delete_answer`; SQLite 3.51 locally supports `ON CONFLICT DO UPDATE` |
| PROF-03 | `find_answer` matches exact then fuzzy (≥ 0.85) and maps onto dropdown/radio options | Pure `core.find_answer(label, answers, options)`; ratios for realistic wordings measured (see Pitfall 2 — wordy variants fall below 0.85, test with ones that clear it) |
| PROF-04 | Answers mentioning the company or > 300 chars are not saved | One pure `core.answer_block_reason(question, answer, company)`; word-boundary match on normalised text with legal-suffix stripping |
| PROF-05 | `cover_letter` fills an editable template from profile and job | Pure `core.cover_letter(profile, job, template, today=None)` using `re.sub` placeholder substitution (never `str.format`) |
</phase_requirements>

## Summary

This phase is almost entirely stdlib plus two small parsing libraries. Everything pure goes in `api/core.py` (extract_profile, matched_skills, skills score rule, find_answer, answer_block_reason, cover_letter). Everything that touches SQLite goes in `api/db.py` (profile get/save, seeding, answers CRUD, `find_answer` wrapper, `get_job`). The only library-dependent code (PDF/DOCX → text) goes in a new `api/cv.py`, so `test_core.py` stays dependency-free. `app.py` gets thin routes only.

The key integration decision: make `db.insert_jobs` and `db.rescore_new` load the profile themselves (`profile=None` → `get_profile(conn)`). This means the Phase 2 watcher/`run_fetch`/`settings_put` code (planned, not yet executed) needs no change for new jobs to get the skills rule, and the two phases cannot conflict on call signatures.

Two things will bite if not planned: (1) `api/data/` is **not** gitignored for non-`.db` files (`.gitignore` only has `*.db`) so the stored CV would be committable — add `api/data/`; (2) a 0.85 `difflib` threshold only catches near-variants ("Do you require sponsorship?" 0.912) not wordy rewrites ("Do you now or in the future require visa sponsorship?" 0.747) — tests must use wordings that actually clear it and the plan must not "fix" this by lowering the locked threshold.

**Primary recommendation:** Pure logic in `core.py` with TDD (extract_profile, find_answer, answer_block_reason, cover_letter, skills rule) first; then `db.py` helpers; then thin routes and `cv.py`; store profile as one JSON row in the existing `settings` table (key `profile`) so no schema change is needed.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CV text extraction (PDF/DOCX) | API / Backend (`cv.py`) | — | Library-dependent, I/O on untrusted bytes; keep out of pure `core.py` |
| Field extraction from CV text | API / Backend (`core.extract_profile`, pure) | — | Pure regex/heuristics, unit-testable without libs |
| Profile persistence | Database (`settings` row `profile`) | API (`db.get_profile/save_profile`) | Same typed merge-and-validate pattern as settings |
| CV file storage | API / filesystem (`api/data/cv.<ext>`) | — | Phase 5 attaches it; never served by the static route |
| Answer matching (`find_answer`) | API / Backend (`core`, pure) | Database (`db.find_answer` wrapper loads rows) | Matching is pure; DB wrapper keeps Phase 5 call simple |
| Save-blocking rule | API / Backend (`core.answer_block_reason`, pure) | `db.save_answer` enforces | One shared function for `/api/answers` and the Phase 5 learner (D-12) |
| Answers CRUD | API routes → `db.py` | Database (`answers`, `unanswered`) | Thin routes, errors as `{"error"}` |
| Skills scoring | API / Backend (`core.score`) | `db.insert_jobs`/`rescore_new` pass profile | Pure rule; DB layer supplies profile |
| Cover letter | API / Backend (`core.cover_letter`, pure) | Route reads job + template setting | Pure fill; nothing stored per job |
| Browser/Frontend | — | — | No UI this phase (scoped out) |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pypdf | 6.21.1 (>=3.9) | PDF → text | Named in CLAUDE.md stack. Pure Python, `requires_python >=3.9`. [VERIFIED: PyPI JSON, `pip index versions pypdf` run this session] |
| python-docx | 1.2.0 (>=3.9) | DOCX → text (paragraphs + tables) | Named in CLAUDE.md stack. Depends on `lxml>=3.1.0`, `typing_extensions>=4.9.0`; lxml 6.1.3 publishes `cp39` and `cp312` `win_amd64` wheels, so no compiler is needed on the Windows target. [VERIFIED: PyPI JSON] |
| difflib (stdlib) | — | Fuzzy match ≥ 0.85 | Locked by PROF-03; stdlib |
| re, json, sqlite3, pathlib (stdlib) | — | Everything else | Project constraint: Flask + stdlib sqlite3 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| werkzeug.utils.secure_filename | bundled with Flask | Only if showing the original upload name | Do NOT use it to build the on-disk path; store as fixed `cv.pdf`/`cv.docx` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pypdf | pdfminer.six / PyMuPDF | Not in CLAUDE.md stack; PyMuPDF is a heavy binary dependency. Not needed. |
| `difflib.get_close_matches` | manual loop | `get_close_matches` breaks ties by string order, not recency (D-10 needs most-recently-updated). Use a manual loop with `quick_ratio()` prefilter. |
| Separate `profile` table | `settings` row key `profile` | Table adds schema; settings row needs none and `get_settings` ignores keys not in `DEFAULTS`. **Recommend settings row.** |

**Installation:**
```bash
# add to api/requirements.txt, then:
.venv/bin/pip install -r api/requirements.txt
# requirements.txt becomes:
# flask>=3.0
# pypdf>=6.0,<7
# python-docx>=1.1,<2
```
`pypdf` and `docx` are currently NOT importable in `.venv` [VERIFIED: `ModuleNotFoundError` for both, run this session].

**Version verification:** `pip index versions pypdf` → 6.21.1; `pip index versions python-docx` → 1.2.0 (PyPI JSON: pypdf latest published 2026-10-17, python-docx 2025-06-16).

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| pypdf | PyPI | long-lived project; newest release 2026-10-17 | not reported by seam | github.com/py-pdf/pypdf | SUS (reasons: `too-new`, `unknown-downloads`) | Flagged — planner must add checkpoint |
| python-docx | PyPI | long-lived; newest release 2025-06-16 | not reported by seam | github.com/python-openxml/python-docx | SUS (reason: `unknown-downloads`) | Flagged — planner must add checkpoint |

`gsd-tools query package-legitimacy check --ecosystem pypi pypdf python-docx` returned SUS for both [VERIFIED: tool output this session]. The reasons are heuristic (a release two days old; the seam cannot read download counts), not signs of slopsquatting: both names come from the project's own CLAUDE.md stack, both have the expected upstream repos, and both installed and ran correctly in a scratch venv. They are still flagged per protocol.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** `pypdf` [WARNING: flagged as suspicious — verify before using.], `python-docx` [WARNING: flagged as suspicious — verify before using.] — planner inserts one `checkpoint:human-verify` before the `pip install` task (confirm the two names on pypi.org and the repo owners `py-pdf` / `python-openxml`).

## Architecture Patterns

### System Architecture Diagram

```
POST /api/profile/cv (multipart "cv")
   |
   v
 app.py route --(bytes, <=10MB, ext + magic bytes)--> cv.read_cv_text(bytes, kind) --[pypdf | python-docx]--> text
   |                                                        | any failure / empty text
   |                                                        v
   |                                                 ValueError -> 400 {"error": "Couldn't read text from this CV"}
   v
 core.extract_profile(text) -> {name,email,phone,linkedin,skills}
   |
   v
 merge: fill ONLY empty fields; skills = existing + new (case-insens. dedupe)
   |--> write api/data/cv.<ext> atomically (replace any old cv.*)
   |--> db.save_profile (settings row "profile")
   '--> db.rescore_new(conn, settings)  (loads profile itself)  --> 200 profile JSON

GET/PUT /api/profile -----> db.get_profile / save_profile --(PUT)--> rescore_new

Watcher / POST /api/fetch --> db.insert_jobs(conn, jobs, settings)   (loads profile itself)
                                  '--> core.score(job, settings, profile): skills rule

/api/answers (GET, POST, PUT/<id>, DELETE/<id>)
   |-- core.answer_block_reason(question, answer, company)  --blocked--> 400 {"error": "Not saved: ..."}
   '-- db.save_answer / update_answer / delete_answer  (+ DELETE FROM unanswered WHERE question = ?)

Phase 5 (later): db.find_answer(conn, label, options) -> core.find_answer(label, answers, options)
                    exact -> fuzzy >= 0.85 (skip empty answers) -> option map -> dict | None

GET /api/jobs/<id>/cover-letter --> db.get_job (404) -> template = setting or cover_letter.txt
                                 --> core.cover_letter(profile, job, template) -> {"text": ...}
```

### Recommended Project Structure
```
api/
├── core.py            # + KNOWN_SKILLS, has_term, matched_skills, extract_profile, find_answer,
│                      #   answer_block_reason, cover_letter; score() skills rule
├── cv.py              # NEW: read_cv_text(data: bytes, kind: str) -> str  (only module importing pypdf/docx)
├── db.py              # + PROFILE_DEFAULTS, get/save_profile, SEED_QUESTIONS, seed_answers (called from init_db),
│                      #   answers CRUD, find_answer wrapper, get_job, cv_dir/cv_file helpers;
│                      #   insert_jobs/rescore_new load the profile; DEFAULTS += cover_letter_template
├── app.py             # + /api/profile, /api/profile/cv, /api/answers..., /api/jobs/<id>/cover-letter
├── cover_letter.txt   # NEW default template (read with encoding="utf-8")
├── test_core.py       # extended
└── test_api.py        # extended (+ make_pdf / make_docx helpers)
.gitignore             # + api/data/
```

### Pattern 1: Profile as one JSON row in `settings`
**What:** `PROFILE_DEFAULTS = {"name": "", "email": "", "phone": "", "linkedin": "", "skills": []}`; stored as `settings` key `profile`. `get_settings` only copies keys that are in `DEFAULTS`, so the extra row is invisible to it. [VERIFIED: api/db.py:79-84, `if row["key"] in DEFAULTS:`]
Generalise `_clean(key, value)` to `_clean(key, value, defaults=DEFAULTS)` (it currently does `default = DEFAULTS[key]`, api/db.py:88) so the same list/int/str validation serves the profile. Skills: strip blanks, dedupe case-insensitively keeping first spelling.
`GET /api/profile` returns the five fields plus read-only `cv_file` (`"cv.pdf"`, `"cv.docx"` or `""`, computed from disk). `PUT` rejects `cv_file` as an unknown key (400), like any other.
**Example:**
```python
# db.py
PROFILE_DEFAULTS = {"name": "", "email": "", "phone": "", "linkedin": "", "skills": []}

def get_profile(conn) -> dict:
    out = copy.deepcopy(PROFILE_DEFAULTS)
    row = conn.execute("SELECT value FROM settings WHERE key = 'profile'").fetchone()
    if row:
        out.update({k: v for k, v in json.loads(row["value"]).items() if k in PROFILE_DEFAULTS})
    return out

def save_profile(conn, changes) -> dict:
    if not isinstance(changes, dict):
        raise ValueError("Profile must be a JSON object")
    for key in changes:
        if key not in PROFILE_DEFAULTS:
            raise ValueError("Unknown profile field: %s" % key)
    merged = dict(get_profile(conn), **{k: _clean(k, v, PROFILE_DEFAULTS) for k, v in changes.items()})
    merged["skills"] = core.dedupe_skills(merged["skills"])
    with conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('profile', ?)", (json.dumps(merged),))
    return merged
```

### Pattern 2: Load profile inside the DB scoring helpers
```python
def insert_jobs(conn, jobs, settings, profile=None):
    if profile is None:
        profile = get_profile(conn)
    ...
    total, pros, cons = core.score(dict(job, summary=summary), settings, profile)

def rescore_new(conn, settings, profile=None):
    if profile is None:
        profile = get_profile(conn)
    ...
    total, pros, cons = core.score(job_dict(row), settings, profile)
```
Existing signatures (api/db.py:124 `insert_jobs(conn, jobs: List[dict], settings: dict)`, api/db.py:164 `rescore_new(conn, settings: dict)`) stay call-compatible, so Phase 2's planned `run_fetch`/`settings_put`/watcher edits need no change. [VERIFIED: read api/db.py:124, 164]

### Pattern 3: Term matching that survives `C++`, `C#`, `.NET`, `Node.js`
`core.normalise` strips `+ # .` (`re.sub(r"[\W_]+", " ", ...)`, api/core.py:10) so `C++` and `C#` both become `c` — do NOT reuse the padded-normalise trick for skills. Use a lookaround regex on the raw text. All 11 cases below were run and passed in the scratch venv:
```python
def has_term(text: str, term: str) -> bool:
    return re.search(r"(?<![A-Za-z0-9+#])%s(?![A-Za-z0-9+#])" % re.escape(term), text, re.I) is not None
# C++ in "We use C++ and Node.js daily" True | "C" in "We use C# and .NET" False | "SQL" in "MySQL database" False
# ".NET" in "ASP.NET" False | ".NET" in "a .NET dev" True | "SQL" in "Experience with SQL." True
```
`re.escape` makes user-supplied skills safe; the pattern has no nested quantifiers (no ReDoS).
Job text for matching = `job["title"] + " " + " ".join(_text_lines(job["description"]))` (strips tags/entities; `_text_lines` at api/core.py:21).

### Pattern 4: Skills scoring rule
```python
SKILL_POINTS_EACH = 2     # recommended; Claude's discretion (D-07)
SKILL_POINTS_CAP = 10     # must stay < TITLE_POINTS (15) < SALARY_ABOVE_POINTS (30)

def matched_skills(profile_skills, job) -> List[str]:
    text = "%s %s" % (job.get("title") or "", " ".join(_text_lines(job.get("description") or "")))
    return [s for s in profile_skills if has_term(text, s)]

# in score(), before the clamp:
skills = (profile or {}).get("skills") or []
hits = matched_skills(skills, job) if skills else []
if hits:
    total += min(SKILL_POINTS_EACH * len(hits), SKILL_POINTS_CAP)
    pros.append("Matches %d of your skills: %s%s" % (len(hits), ", ".join(hits[:3]), "…" if len(hits) > 3 else ""))
```
Existing constants confirmed: `BASE_SCORE = 50`, `TITLE_POINTS = 15`, `SALARY_ABOVE_POINTS = 30`, `REMOTE_POINTS = 10`, `HYBRID_POINTS = 5`, `EXCLUDED_POINTS = 25`. [VERIFIED: api/core.py:5-6, 172-175] Remove the stale comment `# profile is accepted and ignored: ...` (api/core.py:183). No profile / no skills → rule skipped, so every existing score test is unaffected. The existing `test_score_profile_ignored` (api/test_core.py) must be rewritten: it still passes by accident (empty description matches nothing) but its name and intent are now wrong.

### Pattern 5: `find_answer` (pure) + DB wrapper
```python
FUZZY_MIN = 0.85

def _ratio(a, b):  # autojunk=False: default heuristics distort ratios on strings >= 200 chars
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()

def _polarity(norm_text):            # "yes i have the right to work" -> "yes"
    first = norm_text.split(" ", 1)[0]
    return first if first in ("yes", "no") else None

def map_option(answer, options):
    na = normalise(answer)
    norm = [(o, normalise(o)) for o in options]
    for o, no in norm:                               # 1. case-insensitive exact
        if no == na:
            return o
    pol = _polarity(na)                              # 2. yes/no, only when exactly one option shares it
    if pol:
        same = [o for o, no in norm if _polarity(no) == pol]
        if len(same) == 1:
            return same[0]
    best = max(((_ratio(na, no), o) for o, no in norm), default=(0, None))   # 3. fuzzy option
    return best[1] if best[0] >= FUZZY_MIN else None

def find_answer(label, answers, options=None):
    """answers: dicts with id, question (normalised), answer, updated_at. Returns dict or None."""
    q = normalise(label)
    if not q:
        return None
    rows = [a for a in answers if (a["answer"] or "").strip()]      # D-05: empty answers never match
    exact = [a for a in rows if a["question"] == q]
    if exact:
        hit, ratio = max(exact, key=lambda a: (a["updated_at"], a["id"])), 1.0
    else:
        hit, ratio = None, 0.0
        for a in rows:
            sm = difflib.SequenceMatcher(None, q, a["question"], autojunk=False)
            if sm.real_quick_ratio() < FUZZY_MIN or sm.quick_ratio() < FUZZY_MIN:
                continue
            r = sm.ratio()
            if r >= FUZZY_MIN and (hit is None or (r, a["updated_at"], a["id"]) > (ratio, hit["updated_at"], hit["id"])):
                hit, ratio = a, r
        if hit is None:
            return None
    option = None
    if options:
        option = map_option(hit["answer"], options)
        if option is None:
            return None            # never a guess (D-11): caller leaves the field for the person
    return {"id": hit["id"], "question": hit["question"], "answer": hit["answer"], "ratio": round(ratio, 3), "option": option}
```
Contract to pin in tests: `None` = nothing fillable; with `options`, `option` is the original option string; without `options`, `option` is `None` and `answer` is the free-text fill. (Returning `None` when the saved answer is found but maps to no option is the recommended reading of "never a guess"; Phase 5 treats it as unanswered.) `quick_ratio`/`real_quick_ratio` are upper bounds, so the prefilter never drops a true ≥ 0.85 hit. `updated_at` is `datetime('now')` text (second resolution), so `id` is the final tie-break.
`db.find_answer(conn, label, options=None)` = `core.find_answer(label, [dict(r) for r in conn.execute("SELECT * FROM answers")], options)`. Cap the label at ~500 normalised chars before fuzzy so a pasted paragraph cannot slow a form fill.

### Pattern 6: Save-blocking rule (shared, pure)
```python
MAX_ANSWER_CHARS = 300
_LEGAL = {"ltd", "limited", "plc", "inc", "llc", "llp", "corp", "corporation", "co", "uk"}

def answer_block_reason(question, answer, company="") -> Optional[str]:
    """None if saveable, else the reason fragment used in 'Not saved: <reason>'."""
    if len((answer or "").strip()) > MAX_ANSWER_CHARS:
        return "longer than %d characters" % MAX_ANSWER_CHARS
    words = [w for w in normalise(company).split() if w not in _LEGAL] or normalise(company).split()
    name = " ".join(words)
    if len(name) >= 2:
        for text in (question, answer):
            if " %s " % name in " %s " % normalise(text):
                return "mentions the company"
    return None
```
Why this shape: substring matching would make a company "BT" block anything containing "debt"; word-boundary on normalised text is the same technique `score` already uses for excluded words (api/core.py:219-220). Legal suffixes are stripped because an answer says "Acme", never "Acme Ltd". Boundary tests: 300 chars saves, 301 blocked. Job company strings can carry stray whitespace (test fixture uses `"Acme "`) — normalise handles it.
Messages: route returns `jsonify(error="Not saved: " + reason), 400` (D-13).

### Pattern 7: Cover letter — `re.sub`, never `str.format`
```python
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
_MONTHS = ["January", ..., "December"]      # not strftime("%B"): output is locale-dependent on Windows

def cover_letter(profile, job, template, today=None) -> str:
    d = today or datetime.date.today()
    skills = matched_skills(profile.get("skills") or [], job) or (profile.get("skills") or [])[:3]
    values = {"name": profile.get("name", ""), "email": ..., "phone": ..., "company": job.get("company", ""),
              "job_title": job.get("title", ""), "top_skills": _join_and(skills[:3]),
              "date": "%d %s %d" % (d.day, _MONTHS[d.month - 1], d.year)}
    return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), template)
```
Unknown `{foo}` stays as typed; known-but-empty becomes `""` (D-16). `str.format` would let a user-edited template run `{name.__class__}` and would raise on stray braces — avoid. `top_skills` joined as "A, B and C". Template read with `Path(__file__).parent / "cover_letter.txt"`, `encoding="utf-8"` (Windows default codec is cp1252).
Route: `template = settings["cover_letter_template"].strip() or default_file_text`; returns `{"text": ...}` (JSON, consistent with the rest of the API); unknown job → 404 `{"error": "Job not found"}` (same text as the existing route, api/app.py:116).
Default template draft (ship as `api/cover_letter.txt`):
```
Dear Hiring Manager,

I am writing to apply for the {job_title} role at {company}. My background in {top_skills} fits what you are looking for, and I would welcome the chance to bring it to your team.

I would be glad to talk through my experience in more detail. You can reach me on {phone} or at {email}.

Kind regards,
{name}

{date}
```

### Pattern 8: Answers CRUD and save semantics
- Table (read this session) — `answers`: `id INTEGER PRIMARY KEY, question TEXT NOT NULL UNIQUE, answer TEXT NOT NULL, field_type TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'learned', updated_at TEXT NOT NULL DEFAULT (datetime('now'))`; `unanswered`: `question TEXT NOT NULL UNIQUE, times_seen ..., last_seen ...`. [VERIFIED: api/db.py:41-54]
- `db.save_answer(conn, question, answer, field_type="", source="learned", company="")`: normalise question; empty normalised question → `ValueError("question is required")`; question > 500 chars → `ValueError`; run `core.answer_block_reason`; `INSERT ... ON CONFLICT(question) DO UPDATE SET answer=excluded.answer, field_type=excluded.field_type, updated_at=datetime('now')` (keeps `source`); `DELETE FROM unanswered WHERE question = ?`. Local SQLite is 3.51.0 [VERIFIED: `sqlite3.sqlite_version`]; upsert needs ≥ 3.24 (2018), satisfied by python.org builds for 3.9 and 3.12 [ASSUMED: Windows installer bundles ≥ 3.24 — safe, but cheap to sanity-check on the target PC].
- Recommended routes (Claude's discretion on details the decisions leave open):
  - `GET /api/answers` → list ordered by `id`; includes the empty seeded rows (the person fills them in).
  - `POST /api/answers` body `{question, answer, field_type?, company?}` → upsert as `source='profile'`; 201 when new, 200 when it updated an existing row (so typing an answer for a seeded empty question just works). Allowed keys only; unknown → 400. `company` is a transient, never stored.
  - `PUT /api/answers/<int:id>` partial merge of `question/answer/field_type/company`; re-normalise question; re-run block check; unknown id → 404; renaming onto another existing question → 409 `{"error": "An answer for that question already exists"}` (catch `sqlite3.IntegrityError`).
  - `DELETE /api/answers/<int:id>` → `{"ok": true}`; unknown id → 404. (Seeded rows reappear empty on next startup because seeding is "if missing" — acceptable and consistent with D-05.)
- Blocked save: 400 `{"error": "Not saved: mentions the company"}` or `"Not saved: longer than 300 characters"`.

### Pattern 9: Seeding (D-05)
`init_db()` runs `seed_answers(conn)` after `executescript(SCHEMA)`: for each `(question_text, default_answer, field_type)` → `INSERT OR IGNORE INTO answers (question, answer, field_type, source) VALUES (?, ?, ?, 'profile')` with `question = core.normalise(text)`. Recommended wording (natural ATS phrasing so fuzzy hits are likelier):

| Question text (normalised on store) | Default |
|---|---|
| What is your address? | "" |
| Do you have the right to work in the UK? | "" |
| Do you require visa sponsorship? | "" |
| What is your notice period? | "" |
| When can you start? | "" |
| What are your salary expectations? | "" |
| Are you willing to relocate? | "" |
| Do you have a full UK driving licence? | "" |
| What is your highest qualification? | "" |
| Portfolio or website URL | "" |
| How did you hear about this job? | "" |
| What is your gender? | Prefer not to say |
| What is your ethnicity? | Prefer not to say |
| Do you have a disability? | Prefer not to say |
| What is your sexual orientation? | Prefer not to say |
| What is your religion or belief? | Prefer not to say |

Existing tests assert the DB has the four tables only; none assert `answers` is empty (grep of api/test_api.py found only the table-name check at line 76), so seeding does not break them — but new tests must expect ≥ 16 seeded rows after `fresh_client()` (which calls `db.init_db()`).

### Pattern 10: CV extraction
```python
# cv.py
import io
import pypdf
import docx

def read_cv_text(data: bytes, kind: str) -> str:
    """kind is 'pdf' or 'docx'. Raises ValueError("Couldn't read text from this CV") on any failure or empty text."""
    try:
        if kind == "pdf":
            reader = pypdf.PdfReader(io.BytesIO(data))
            text = "\n".join((p.extract_text() or "") for p in reader.pages)
        else:
            d = docx.Document(io.BytesIO(data))
            parts = [p.text for p in d.paragraphs]
            for t in d.tables:                                   # CV templates put skills/contact in tables
                for row in t.rows:
                    seen = set()
                    for c in row.cells:
                        if id(c._tc) not in seen:               # merged cells repeat
                            seen.add(id(c._tc)); parts.append(c.text)
            text = "\n".join(parts)
    except Exception:                                            # noqa: BLE001 - see error table
        raise ValueError("Couldn't read text from this CV")
    text = text[:200000].strip()
    if not text:
        raise ValueError("Couldn't read text from this CV")
    return text
```
Real exceptions observed in the scratch venv (pypdf 6.21.1, python-docx 1.2.0) [VERIFIED: run this session]: non-PDF bytes → `PdfStreamError` (subclass of `PdfReadError`/`PyPdfError`); empty → `EmptyFileError`; encrypted PDF → `FileNotDecryptedError` raised at `extract_text()`; not-a-zip as DOCX → `zipfile.BadZipFile`; a blank-page PDF extracts `''` (no exception) — hence the empty-text check. One broad `except Exception` is correct here because the input is untrusted and the contract is a single 400 message (log with `app.logger.warning`, not the stack).

Route (`POST /api/profile/cv`): `f = request.files.get("cv")` (missing → 400 "No file uploaded"); ext from `os.path.splitext(f.filename.lower())[1]` in `{.pdf,.docx}` else 400 "Upload a PDF or DOCX file"; `data = f.stream.read(MAX_CV_BYTES + 1)`; `len(data) > 10*1024*1024` → 400 "CV is larger than 10 MB"; magic-byte check (`data[:5] == b"%PDF-"` for pdf, `data[:4] == b"PK\x03\x04"` for docx) else 400 "Upload a PDF or DOCX file". Order: validate → `read_cv_text` → extract → write file (temp name + `os.replace` to `cv_dir()/"cv.pdf"|"cv.docx"`, delete the other extension) → save profile → `rescore_new` → `jsonify(profile_with_cv_file)`. Never put the client filename in a path. `cv_dir()` = `Path(db_path()).parent` so tests (which set `JOBHELPER_DB` to a temp file) write the CV into the temp dir, not the real `api/data/`.
Why a read-cap rather than `MAX_CONTENT_LENGTH`: the config option would 413 *every* oversize request (also JSON PUTs) and the spec asks for a specific 400; Werkzeug already spools uploaded files to temp storage, and the host/origin guard (`local_only`, api/app.py:18-27) limits callers to the local machine. Mark with a `ponytail:` comment.

### Pattern 11: `extract_profile(text)` (pure) — regexes run on samples
```python
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){1,5}")
_LINKEDIN = re.compile(r"(?:https?://)?(?:[a-z]{2,3}\.|www\.)?linkedin\.com/in/[A-Za-z0-9_%-]{2,100}", re.I)
_PHONE = re.compile(r"(?<![\w+])\+?\(?\d[\d\s().-]{7,18}\d(?!\w)")
_YEAR = re.compile(r"^(?:19|20)\d\d$")
_NOT_NAME = {"cv", "resume", "curriculum vitae", "profile", "personal details", "contact"}
```
- Phone: take candidates with 10-13 digits, drop any whose digit groups are all years (`2019 2021 2023`), prefer one starting `+`, `0` or `(`. Measured on 5 samples: `07700 900123`, `+44 (0)20 7946 0958`, `+44 7700 900 123`, `(555) 123-4567` correct; `2019 - 2023` and a 14-digit reference number correctly rejected.
- LinkedIn: prepend `https://` if absent; trailing `/` falls out of the char class. Results: `https://linkedin.com/in/jane-doe-123`, `https://www.linkedin.com/in/jsmith`, `https://uk.linkedin.com/in/mjw`.
- Name: first of the first 8 non-empty lines that is 2-4 alphabetic words (hyphen/apostrophe/dot allowed), ≤ 40 chars, no digits `@` `:` `/`, not in `_NOT_NAME`; ALL CAPS → `.title()`. Correct on `Jane Doe`, `JOHN O'NEILL-SMITH` → `John O'Neill-Smith`, `Mary-Jane Watson`, `Dr. Ana Maria Lopez`. Known limit: a one-word name followed by a job title line ("Alex" / "Project Manager") yields the job title — acceptable because the profile is editable and upload never overwrites a non-empty field (`ponytail:` comment).
- Skills (D-04): (a) find a heading line whose `normalise` is one of `skills`, `key skills`, `core skills`, `technical skills`, `skills and tools`… (line ≤ 40 chars, not a bullet); collect following lines until a heading in a stop set (`experience`, `employment`, `work history`, `education`, `projects`, `certifications`, `references`, `interests`, `summary`, `profile`, `languages`) or 12 lines; split each on `[,;•·|]` (NOT `/`, which would break "CI/CD"); keep items ≤ 4 words and ≤ 40 chars (drops sentences); strip a trailing parenthesis group ("SQL (advanced)" → "SQL"); (b) `KNOWN_SKILLS` entries found by `has_term` over the whole text, using the list's canonical casing; merge (b) first so canonical casing wins on dedupe; cap 40. Tested extraction string: `'Jane Doe\njane@example.com | 07700 900123\nSkills\nExcel, SQL (advanced), Python\n'` (handmade PDF round trip).
- Cap input to 200 000 characters (done in `cv.py`) so a huge PDF cannot make the regex passes slow.
- `KNOWN_SKILLS` starter set (Claude's discretion; keep it technical, no soft skills, and exclude ambiguous tokens `R`, `C`, `Go` — use `Golang`): Excel, SQL, Python, JavaScript, TypeScript, Java, C#, C++, .NET, PHP, Ruby, Rust, Golang, React, Node.js, Django, Flask, HTML, CSS, Git, Docker, Kubernetes, AWS, Azure, GCP, Linux, Power BI, Tableau, Looker, pandas, NumPy, Jira, Salesforce, SAP, Word, PowerPoint, Photoshop, Figma, SEO, Google Analytics, Agile, Scrum, Machine Learning, Data Analysis, Project Management, Bookkeeping, Xero, Sage, QuickBooks, Customer Service.

### Anti-Patterns to Avoid
- **`str.format` / `format_map` on the template:** user-editable text; attribute access and stray braces. Use `re.sub`.
- **Padded-`normalise` matching for skills:** `C++`/`C#`/`.NET` collapse to `c`/`net`. Use `has_term`.
- **Building the CV path from `file.filename`:** path traversal; always `cv.pdf`/`cv.docx`.
- **`difflib.get_close_matches` for D-10:** wrong tie-break (string order, not recency).
- **Matching empty seeded answers:** filter `answer.strip() == ""` before exact/fuzzy.
- **Lowering 0.85 to make a test pass:** it is a locked requirement (PROF-03).
- **Passing `profile` through every caller:** load it inside `insert_jobs`/`rescore_new`.
- **`open()` without `encoding="utf-8"`** for `cover_letter.txt` (Windows cp1252).
- **Python 3.10+ syntax** (`X | Y`, `match`): code must run on 3.9; use `Optional`/`List` from `typing` and type comments as the existing code does.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF text extraction | A PDF parser | `pypdf.PdfReader` | Cross-reference tables, encodings, encryption |
| DOCX text extraction | zip + XML walking | `python-docx` | Paragraph/table structure; its XML parser is configured `resolve_entities=False` [VERIFIED: docx/oxml/parser.py read this session] |
| Fuzzy string similarity | Levenshtein code | `difflib.SequenceMatcher` | Locked spec; stdlib |
| Template engine | Jinja/`string.Template` | one `re.sub` | Seven fixed placeholders; unknown ones must stay as typed |
| Multipart parsing | manual body parsing | Flask `request.files` | Boundary/size edge cases |
| Upsert | SELECT-then-INSERT | `INSERT ... ON CONFLICT DO UPDATE` | Race-free, one statement |

**Key insight:** the only things worth writing are the thin heuristics (what counts as a name/phone/skill, how a saved answer maps to an option). Everything else is library or stdlib.

## Common Pitfalls

### Pitfall 1: `.gitignore` does not cover the stored CV
**What goes wrong:** `api/data/cv.pdf` (personal data) shows up as untracked and gets committed. `git check-ignore -v` matched only `*.db` for `api/data/jobhelper.db`; `api/data/cv.pdf` was not matched. [VERIFIED: run this session; .gitignore contains `.venv/ node_modules/ api/static/ *.db __pycache__/ .DS_Store`]
**How to avoid:** add `api/data/` to `.gitignore` in the same plan that adds the upload route.
**Warning signs:** `git status` shows `api/data/cv.*`.

### Pitfall 2: 0.85 fuzzy only catches near-variants
**What goes wrong:** a "differently worded" visa test fails because the wording is too different.
**Measured ratios** vs the seeded `do you require visa sponsorship` [VERIFIED: difflib run this session]: "Do you require sponsorship?" **0.912**; "Will you require visa sponsorship?" **0.906**; "Do you need visa sponsorship?" **0.881**; "Do you require a visa sponsorship" **0.969**; but "Do you require visa sponsorship to work in the UK?" **0.775**, "Do you now or in the future require visa sponsorship?" **0.747**, and the long legal wording **0.449** all MISS. Right to work: "Do you have the legal right to work in the UK?" 0.929 hits; "…in the United Kingdom?" 0.867 hits; "Are you eligible to work in the UK?" 0.712 misses.
**How to avoid:** unit tests use wordings that clear 0.85 and assert a miss for a clearly different one (e.g. the 0.747 wording → `None`). Misses are not a bug: Phase 5/6 puts them in `unanswered`, the person answers once, and that new phrasing is then an exact match. Do not lower the threshold.

### Pitfall 3: Yes/No mapping ambiguity
**What goes wrong:** options `["Yes - UK citizen", "Yes - with visa", "No"]` and saved "Yes" → guessing the first.
**How to avoid:** the polarity step only fires when exactly one option shares the saved answer's yes/no; otherwise fall through to fuzzy, then `None`. Test it.
**Also:** saved answer "Yes, I do" with options `["Yes", "No"]` works because polarity is read from the first word of both sides.

### Pitfall 4: Company check false positives/negatives
Short names (`BT`, `EE`) and substring matching ("debt"); legal suffixes ("Acme Ltd" never appears in an answer); stray whitespace in the stored company (`"Acme "`). Use normalised word-boundary matching with suffix stripping and ignore names shorter than 2 characters (Pattern 6).

### Pitfall 5: Generic skills inflate every job
Soft skills from a CV "Skills" section ("Communication", "Teamwork") match almost every listing. The cap (`SKILL_POINTS_CAP = 10`) bounds the damage; keep `KNOWN_SKILLS` technical.

### Pitfall 6: Profile change must re-score, with the new profile
`settings_put` already calls `rescore_new` (api/app.py:82); the profile routes must too, and `rescore_new` must read the *saved* profile — save first, then rescore.

### Pitfall 7: Windows locale and encoding
`strftime("%B")` follows the Windows locale; `open()` defaults to cp1252. Use the manual month list and `encoding="utf-8"`.

### Pitfall 8: PDF edge cases
Scanned/image PDFs and blank pages return `''` (no exception) → must return 400 via the empty-text check; encrypted PDFs raise on `extract_text()` not on open — keep the whole read inside the `try`. Hyperlink *labels* ("LinkedIn" as link text) hide the URL in the PDF `/Annots` / DOCX relationships; the regex will not see them (known limit, `ponytail:` comment; upgrade path: scan `/Annots` `/A` `/URI` for `linkedin.com/in`).

### Pitfall 9: Test helper realism
Build test fixtures in code, no binary files: DOCX with `python-docx` (`docx.Document()` → `BytesIO`), PDF with a ~15-line handmade writer (below). Both round-trip with the real libraries. Flask test-client upload needs a seekable object: `data={"cv": (io.BytesIO(b), "cv.pdf")}, content_type="multipart/form-data"`.

## Code Examples

### Handmade multi-line PDF for tests (verified round trip: extracts `'Jane Doe\njane@example.com | 07700 900123\nSkills\nExcel, SQL (advanced), Python\n'`)
```python
def make_pdf(lines):
    esc = lambda s: s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = "BT /F1 12 Tf 14 TL 72 720 Td " + " ".join("(%s) Tj T*" % esc(l) for l in lines) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            "<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out)); out += ("%d 0 obj\n%s\nendobj\n" % (i, o)).encode("latin-1")
    x = len(out)
    out += ("xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)).encode()
    for o in offs:
        out += ("%010d 00000 n \n" % o).encode()
    return out + ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, x)).encode()
```
Blank/"no text" PDF for the 400 test: `make_pdf([])` (extracts `''`). Wrong-type test: `b"not a pdf"` named `cv.pdf` → fails the magic-byte check; `PK\x03\x04junk` named `cv.docx` → `BadZipFile`/package error → 400.

### Multipart upload in a test
```python
r = c.post("/api/profile/cv", data={"cv": (io.BytesIO(make_pdf(CV_LINES)), "me.pdf")},
           content_type="multipart/form-data")
assert r.status_code == 200 and r.get_json()["email"] == "jane@example.com"
```
The `CheckedClient` in api/test_api.py already asserts every `/api/` response ≥ 400 carries `{"error"}` [VERIFIED: api/test_api.py:19-27] — new routes get DATA-06 coverage for free.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| PyPDF2 / PyPDF4 | `pypdf` (merged successor) | PyPDF2 deprecated | Use `pypdf`, import name `pypdf` [CITED: pypdf project history, ASSUMED-level recall — name confirmed by PyPI listing above] |
| `docx2txt` for text | `python-docx` paragraphs + tables | — | Tables matter for CV layouts |

**Deprecated/outdated:** PyPDF2 (do not use); `str.format` for user templates.

## Runtime State Inventory

Not a rename/refactor/migration phase — section omitted.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | python.org Windows builds for 3.9/3.12 bundle SQLite ≥ 3.24 (needed for `ON CONFLICT DO UPDATE`) | Pattern 8 | Upsert fails on target PC; fallback is SELECT-then-INSERT/UPDATE (two statements) |
| A2 | PyPDF2 is the deprecated predecessor of pypdf | State of the Art | None (informational) |
| A3 | Recommended point values (2 per skill, cap 10) and the known-skills / seed wording lists are acceptable | Patterns 4, 9, 11 | CONTEXT delegates these to Claude's discretion; user may want different numbers — low risk, easily changed |
| A4 | `find_answer` returns `None` when a saved answer exists but maps to no option (rather than a dict with `option: None`) | Pattern 5 | Phase 5 may want to distinguish "found but unmappable"; changing later is a small signature tweak but Phase 5 code depends on it |
| A5 | `POST /api/answers` is an upsert (201 new / 200 updated) rather than 409-on-duplicate | Pattern 8 | If the user expects strict create, a duplicate silently overwrites; chosen so seeded empty rows can be filled with one call |
| A6 | Windows installers/wheels: lxml cp312 `win_amd64` wheel exists (verified on PyPI listing) but actual install on the target PC not tested | Standard Stack | `pip install` on the Windows PC could still fail offline/with an old pip — Phase 6/UI-05 packaging (`Start.bat`) should install from requirements |

## Open Questions

1. **Should the Profile UI be able to fetch the default cover-letter text?**
   - What we know: `cover_letter_template` setting is blank = use the file; `GET /api/settings` will return `""`.
   - What's unclear: the future Profile page (UI-04) needs the default text to prefill the editor.
   - Recommendation: out of scope now (no UI); note it for the UI phase (e.g. `GET /api/cover-letter/template`). Do not add it in Phase 3.
2. **First/last name split for Phase 5.**
   - What we know: D-01 fixes one `name` field and Phase 5's keyword map reads it.
   - Recommendation: Phase 5 splits on the last space; do not add fields now (D-01 reversibility is "costly" — adding fields later is cheap, renaming is not).
3. **`test_watcher.py` does not exist yet** (Phase 2 is planned but not executed). The full-suite command should list only files that exist at execution time; Phase 3 can run before or after Phase 2 since the integration points are signature-compatible (Pattern 2).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (.venv) | everything | yes | 3.9.6 [VERIFIED: `.venv/bin/python --version`] | — |
| Python 3.12 | target-compat check | no (`command -v python3.12` empty) | — | Keep to 3.9-safe syntax; pypdf/python-docx/lxml all publish 3.12 support (`requires_python >=3.9`; lxml cp312 wheels) |
| Flask | routes | yes | 3.1.3 [VERIFIED: pip list] | — |
| pypdf | PROF-01 | no, not installed in `.venv` | latest 6.21.1 | none — install (Wave 0) |
| python-docx (+ lxml) | PROF-01 | no, not installed in `.venv` | latest 1.2.0 | none — install (Wave 0) |
| SQLite | upsert | yes | 3.51.0 | SELECT-then-write |
| Network for pip | install | yes (`pip index` worked) | — | — |

**Missing dependencies with no fallback:** pypdf, python-docx — blocking until `pip install -r api/requirements.txt` (behind the SUS checkpoint).
**Missing dependencies with fallback:** none.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Plain-assert scripts, no pytest (project convention D-25) |
| Config file | none |
| Quick run command | `.venv/bin/python api/test_core.py` |
| Full suite command | `.venv/bin/python api/test_core.py && .venv/bin/python api/test_api.py` (+ `api/test_watcher.py` once Phase 2 has created it) |

Each file collects `test_*` functions in `__main__` and calls them; new tests follow the same pattern (`tests = [v for k, v in list(globals().items()) if k.startswith("test_") ...]`). [VERIFIED: api/test_core.py tail]. API tests use `fresh_client()` which creates a temp DB and calls `db.init_db()` (api/test_api.py:60-64), so seeding and CV storage are isolated per test.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROF-01 | `extract_profile` pulls name/email/phone/linkedin/skills from sample text (UK mobile, +44, year-range not a phone, ALL-CAPS name, Skills section + known-skills merge, dedupe) | unit | `.venv/bin/python api/test_core.py` | edit existing |
| PROF-01 | PDF and DOCX upload pre-fills profile; second upload does not overwrite hand-edited fields; skills merged; wrong type / bad bytes / blank PDF / >10 MB → 400 with error; stored `cv.*` replaced; unknown PUT key → 400 | API | `.venv/bin/python api/test_api.py` | edit existing |
| PROF-02 | list (includes seeded), create (201), upsert existing (200), edit (200), duplicate-rename (409), delete, unknown id 404 (PUT/DELETE), non-JSON body 400; saving clears matching `unanswered` row | API | `.venv/bin/python api/test_api.py` | edit existing |
| PROF-03 | exact beats fuzzy; fuzzy ≥ 0.85 hits ("Do you require sponsorship?", "Will you require visa sponsorship?"); 0.747 wording misses; highest ratio wins; tie → most recent `updated_at`; empty seeded answer never matches; options: exact, yes/no unique, yes/no ambiguous → fuzzy → `None`, fuzzy option ≥ 0.85, no mapping → `None` | unit | `.venv/bin/python api/test_core.py` | edit existing |
| PROF-04 | `answer_block_reason`: 300 ok / 301 blocked; company in answer, in question, case-insensitive, with "Ltd" suffix stripped; no company supplied → only length check; "BT" does not block "debt"; API returns 400 `Not saved: ...` and writes no row | unit + API | both commands | edit existing |
| PROF-05 | placeholders filled; unknown `{foo}` left; missing values blank; `top_skills` matched else first 3; injected `today` date; `{name.__class__}` stays literal; route: 200 text, 404 unknown job, custom `cover_letter_template` setting used, blank → default file | unit + API | both commands | edit existing |
| D-07/D-09 | skills rule: pro text + capped boost; salary dominates (cap < 30); no skills → identical score; `C++`/`.NET` matching; profile PUT and CV upload re-score `new` jobs only (queued job keeps score) | unit + API | both commands | edit existing |

### Sampling Rate
- **Per task commit:** `.venv/bin/python api/test_core.py` (and `api/test_api.py` when the task touches db/app)
- **Per wave merge:** full suite command
- **Phase gate:** full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `api/requirements.txt` + `.venv/bin/pip install -r api/requirements.txt` (pypdf, python-docx) — behind the SUS checkpoint
- [ ] `.gitignore`: add `api/data/`
- [ ] `api/cover_letter.txt` default template
- [ ] `make_pdf` / DOCX-builder helpers in `api/test_api.py`
- [ ] Rewrite `test_score_profile_ignored` in `api/test_core.py` (obsolete)

## Security Domain

`security_enforcement` is enabled (ASVS level 1, block on high).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Single-user local app; no login (CLAUDE.md) |
| V3 Session Management | no | No sessions |
| V4 Access Control | yes (existing) | `local_only` before_request already blocks non-localhost Host/Origin for every `/api/` route [VERIFIED: api/app.py:18-27]; new routes inherit it. CV in `api/data/` is outside `STATIC`, so the `ui()` file route cannot serve it |
| V5 Input Validation | yes | Type-check every JSON body (reject non-dict, unknown keys, wrong types) via `_clean`; question ≤ 500 chars; skills list of strings; bounded regexes; `re.escape` on user terms |
| V6 Cryptography | no | None added; Gmail/`keyring` is Phase 4 |
| V12 Files and Resources | yes | Extension + magic-byte check, 10 MB read cap, fixed server-side filename, atomic replace, parse before storing, no execution of file content |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via upload filename | Tampering | Never use client filename in a path; store as `cv.pdf`/`cv.docx` |
| Malformed/malicious PDF or DOCX (crash, huge memory, hang) | DoS | 10 MB cap, 200 000-char text cap, broad `except` → 400; keep pypdf current (pin `>=6.0`) |
| XXE via DOCX XML | Info disclosure | python-docx parser uses `resolve_entities=False` [VERIFIED: docx/oxml/parser.py] |
| Template injection via user-edited cover letter | Tampering | `re.sub` over a fixed placeholder set; no `str.format`, no `eval` |
| ReDoS via crafted CV/job text or user terms | DoS | Bounded quantifiers (`{1,64}` etc.), `re.escape`d user terms, no nested quantifiers (same discipline as T-01-07 in core.py) |
| SQL injection | Tampering | Parameterised queries only (existing style); never interpolate question/answer |
| PII exposure (CV, phone, email) | Info disclosure | Local-only host guard; `api/data/` gitignored; JSON API returns data to localhost only |
| Stored XSS via answers/profile | Tampering | API returns JSON; the future React UI escapes by default — no HTML rendering of these fields |

## Project Constraints (from CLAUDE.md)

- Flask + stdlib `sqlite3`, one Python process; double-click `Start.bat` target on Windows; no new infrastructure.
- Code must run on Python 3.9 (dev) and 3.12 (target): `typing.Optional/List`, no `X | Y`, no `match`.
- Pure logic in `core.py`, DB helpers in `db.py`, thin Flask routes in `app.py`; `/api/` errors are `{"error": "message"}` with 4xx/5xx, never 200.
- snake_case Python; `jsonify()` for responses; small single-responsibility functions; comments only for significant notes (`ponytail:` comments for deliberate shortcuts, as existing code does).
- Compliance: respect site terms, no CAPTCHA bypass, never auto-submit (not touched this phase).
- Tests are plain-assert scripts run as shown; temp DB via `JOBHELPER_DB`.
- GSD workflow enforcement: file changes go through a GSD command (`/gsd-execute-phase`).
- No project skills are applied: `.claude/skills/` and `.agents/skills/` contain only generic engineering skills (api-and-interface-design, security-and-hardening, test-driven-development, etc.), no project-specific SKILL.md patterns relevant to this phase.

## Sources

### Primary (HIGH confidence)
- In-repo files read this session: `api/core.py`, `api/db.py`, `api/app.py`, `api/test_api.py` (lines 1-80), `api/test_core.py` (helpers and tail), `.gitignore`, `.planning/config.json`, CONTEXT/REQUIREMENTS/STATE, PLAN.md excerpts
- PyPI JSON for pypdf 6.21.1, python-docx 1.2.0, lxml 6.1.3 (requires_python, dependencies, wheel list)
- Scratch-venv experiments (Python 3.9.6, pypdf 6.21.1, python-docx 1.2.0): exception types, text extraction, difflib ratios, regex/term-matching cases
- `gsd-tools query package-legitimacy check` output (both SUS)
- python-docx source `docx/oxml/parser.py` (`resolve_entities=False`)

### Secondary (MEDIUM confidence)
- None used

### Tertiary (LOW confidence)
- Training knowledge only for the PyPDF2 history note (A2) and Windows SQLite bundling (A1)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — libraries named in CLAUDE.md, versions and Python support read from PyPI, behaviour exercised
- Architecture: HIGH — integration points read directly from current `db.py`/`core.py`/`app.py`
- Pitfalls: HIGH — fuzzy ratios, regex and library errors measured; `.gitignore` gap confirmed

**Research date:** 2026-10-19
**Valid until:** 2026-11-18 (pypdf releases frequently; re-check the version pin at install time)
