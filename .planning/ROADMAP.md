# Roadmap: Job Helper

## Overview

Job Helper is built API-first and bottom-up: pure logic and data before threads, and threads before Playwright. Phase 1 gets real, ranked jobs visible through the Flask API from one keyless source. Phase 2 adds the watcher thread and the keyed sources so the feed refreshes itself. Phase 3 adds the profile, CV extraction and saved answers that the autofill will draw on. Phase 4 adds Gmail job-alert sources and full job descriptions. Phase 5 adds the single-thread Playwright autofill worker, which fills forms and never clicks Submit. Phase 6 exposes the Apply queue API, including the unanswered-questions flow. UI pages (v2) come after this roadmap and are not included here.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Data, Scoring and First Source** - SQLite schema, jobs/settings/stats API, rule-based scoring and Remotive, so real ranked jobs show up through the API (completed 2026-10-16)
- [x] **Phase 2: Watcher and More Sources** - Background watcher thread polling Remotive and Reed on configurable intervals (completed 2026-10-21)
- [ ] **Phase 3: Profile and Answers** - CV upload extraction, saved answers with matching, and cover letter template
- [ ] **Phase 4: Gmail Alerts and Job Details** - LinkedIn, Indeed, CV-Library and Totaljobs alerts via Gmail, plus full job descriptions
- [ ] **Phase 5: Autofill Worker** - Single Playwright thread that fills application forms and detects (never performs) Submit
- [ ] **Phase 6: Apply Queue API** - Queue listing, unanswered-questions flow and skip

## Phase Details

### Phase 1: Data, Scoring and First Source

**Goal**: Real, ranked jobs from Remotive are stored locally and visible through the API, with settings, stats and clear errors
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, SCORE-01, SCORE-02, SCORE-03, SCORE-04, SRC-01, SRC-02
**Success Criteria** (what must be TRUE):
  1. Starting the app on a fresh machine creates the SQLite database with the `jobs`, `answers`, `unanswered` and `settings` tables, with no manual setup step
  2. After a Remotive fetch (no API key), `GET /api/jobs` returns real listings sorted by score highest first, each with pros/cons and a summary (salary, type, remote status, years of experience, up to 3 "what you'd do" and 3 "what they want" bullets)
  3. Fetching the same Remotive jobs twice does not create duplicate rows (deduplicated by URL), and every new job is scored on insert
  4. `POST /api/jobs/<id>/dismiss`, `/queue` and `/undo` change a job's status and record `status_changed_at`, and `GET /api/stats` returns weekly found/queued/applied/dismissed counts with a per-source breakdown
  5. `GET` then `PUT /api/settings` round-trips career fields, excluded words, minimum salary, location, API keys and poll intervals, and any API error returns an `{"error": ...}` body with a 4xx/5xx status, never 200
  6. `python test_core.py` passes, covering the salary regex, score ordering, pros/cons and excluded words

**Plans:** 3/3 plans complete

Plans:
- [x] 01-01-PLAN.md — Tracer: settings to Remotive fetch to scored, deduplicated jobs in SQLite to ranked GET /api/jobs, plus settings/fetch errors and offline tests (wave 1)
- [x] 01-02-PLAN.md — Full summarize (salary, type, remote, years, bullets) and score rules with pros/cons; api/test_core.py (wave 2)
- [x] 01-03-PLAN.md — Dismiss/queue/undo, ?status filter, weekly stats, re-score on settings save, JSON errors everywhere, local-only guard (wave 2)

### Phase 2: Watcher and More Sources

**Goal**: The job feed refreshes itself in the background from Remotive and Reed
**Depends on**: Phase 1
**Requirements**: SRC-03, WATCH-01, WATCH-02
**Success Criteria** (what must be TRUE):
  1. After saving a Reed key in settings, Reed jobs appear in `GET /api/jobs`, scored and deduplicated
  2. With the app running and nothing triggering a fetch, new jobs appear in the API on the configured poll interval
  3. When one source fails (bad key, network down), the watcher logs it, the other sources still deliver jobs, and the next poll runs as normal
  4. Poll intervals default to Gmail 5 min and APIs 60 min, and changing them in settings changes the polling cadence

**Plans:** 4/4 plans complete

Plans:
**Wave 1**
- [x] 02-01-PLAN.md — Tracer: saved Reed key to watcher thread startup poll to scored Reed jobs in GET /api/jobs; shared run_fetch + lock for POST /api/fetch; watcher behaviour tests (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 02-02-PLAN.md — Adzuna (gb) adapter wired into the watcher, plus COVERAGE.md; Adzuna was later removed by quick task 261021-wez and the code stays in git history (wave 2)
- [x] 02-03-PLAN.md — Settings save wakes the watcher, GET /api/watcher status, manual fetch contract tests (409 / 200 with errors / 502) (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 02-04-PLAN.md — Real-process check plus human verification with a real Reed key (wave 3, checkpoint)

### Phase 3: Profile and Answers

**Goal**: The person's profile and saved answers exist and can be matched to application form questions
**Depends on**: Phase 1
**Requirements**: PROF-01, PROF-02, PROF-03, PROF-04, PROF-05
**Success Criteria** (what must be TRUE):
  1. Uploading a PDF or DOCX CV pre-fills name, email, phone, LinkedIn and skills in the profile returned by the API
  2. `/api/answers` lists, creates, edits and deletes saved answers
  3. `find_answer` returns the saved answer for a label by exact match, then fuzzy match (similarity 0.85 or higher), and maps it onto the matching dropdown or radio option
  4. An answer that mentions the company name or is longer than 300 characters is not saved
  5. `cover_letter` returns an editable template filled from the profile and the job

**Plans:** 4 plans

Plans:
**Wave 1**
- [ ] 03-01-PLAN.md — Package-legitimacy checkpoint (blocking-human), then pin and install pypdf and python-docx (wave 1, checkpoint)
- [ ] 03-02-PLAN.md — Tracer: POST /api/answers to find_answer mapping a differently worded visa label onto a Yes/No option; matching and blocking rules; answers CRUD, seeding and unanswered clearing (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 03-03-PLAN.md — Profile and CV upload: api/cv.py, extract_profile (name, email, phone, LinkedIn, skills), GET/PUT /api/profile, POST /api/profile/cv validation, api/data/ gitignored (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 03-04-PLAN.md — Cover letter (template file, setting, GET /api/jobs/<id>/cover-letter) plus the capped skills scoring rule and profile-change re-score (wave 3)

### Phase 4: Gmail Alerts and Job Details

**Goal**: Jobs from boards with no public API arrive via Gmail alerts, and any job can show its full description
**Depends on**: Phase 2 (watcher), Phase 3 (skills for scoring alert jobs)
**Requirements**: GMAIL-01, GMAIL-02, DETAIL-01, DETAIL-02
**Success Criteria** (what must be TRUE):
  1. With Gmail credentials stored in `keyring`, job-alert emails are read over IMAP and their jobs appear in `GET /api/jobs`, scored and deduplicated
  2. LinkedIn, Indeed, CV-Library and Totaljobs alerts each have their own parser, and each parser's test passes against a saved sample email
  3. `fetch_details` returns the full description from the page's JSON-LD `JobPosting` block, or the largest text block when there is none
  4. When a page is blocked, it is retried once in Playwright and then marked "open listing to read", and no CAPTCHA is ever attempted

**Plans**: TBD

### Phase 5: Autofill Worker

**Goal**: Queued jobs get their application forms filled from the profile and saved answers, ready for the person to review and submit
**Depends on**: Phase 3 (profile, answers, cover letter), Phase 4 (job details, Playwright retry)
**Requirements**: FILL-01, FILL-02, FILL-03, FILL-04, FILL-05, FILL-06
**Success Criteria** (what must be TRUE):
  1. All browser work runs on one dedicated Playwright thread fed by a `queue.Queue`, with no cross-thread Playwright calls
  2. A local fixture form is filled from the profile, saved answers and (if the form has the field) a cover letter
  3. Each job ends as `ready` or `needs_input`, and unknown fields are outlined on the page
  4. Up to 5 applications fill at once, each in its own tab, and the cap is a setting
  5. When the person clicks Submit, the app detects it, the job becomes `applied` and the typed answers are captured; the app never clicks Submit itself
  6. On linkedin.com and indeed.com the app opens the page and shows copy-paste answers instead of filling

**Plans**: TBD

### Phase 6: Apply Queue API

**Goal**: The person can manage the Apply queue and resolve unanswered questions through the API
**Depends on**: Phase 5
**Requirements**: QUEUE-01, QUEUE-02, QUEUE-03, QUEUE-04
**Success Criteria** (what must be TRUE):
  1. `GET /api/queue` lists queued jobs with their status, and the same queue is there after restarting the app
  2. The API lists unique unanswered questions across the queue, most frequently seen first
  3. Answering a question saves it and fills it into every open form that asks it
  4. Skipping a job drops it from the queue

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Data, Scoring and First Source | 3/3 | Complete    | 2026-10-16 |
| 2. Watcher and More Sources | 4/4 | Complete    | 2026-10-21 |
| 3. Profile and Answers | 0/TBD | Not started | - |
| 4. Gmail Alerts and Job Details | 0/TBD | Not started | - |
| 5. Autofill Worker | 0/TBD | Not started | - |
| 6. Apply Queue API | 0/TBD | Not started | - |
