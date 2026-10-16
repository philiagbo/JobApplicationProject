# Requirements: Job Helper

**Defined:** 2026-09-29
**Core Value:** Surface well-ranked jobs and pre-fill applications so the person only reviews and submits. The app never clicks Submit.

## v1 Requirements

Scope: the API (Flask, SQLite, background threads). UI pages come after. Built bottom-up: pure logic before threads and Playwright.

### Data & Jobs API

- [x] **DATA-01**: SQLite schema is created on startup with `jobs`, `answers`, `unanswered` and `settings` tables
- [x] **DATA-02**: `GET /api/jobs` returns jobs sorted by score, highest first
- [x] **DATA-03**: `POST /api/jobs/<id>/dismiss`, `/queue` and `/undo` change a job's status and record `status_changed_at`
- [x] **DATA-04**: `GET` and `PUT /api/settings` read and save career fields, excluded words, minimum salary, location, API keys and poll intervals
- [x] **DATA-05**: `GET /api/stats` returns weekly counts of jobs found, queued, applied and dismissed, with per-source breakdown
- [x] **DATA-06**: API errors return an `{"error": ...}` body with a 4xx/5xx status, never 200

### Scoring

- [x] **SCORE-01**: `normalise` turns a question or label into a stable lookup key
- [x] **SCORE-02**: `score(job, settings, profile)` returns a score plus pros and cons from rules (salary vs minimum, remote, CV skills matched, title matches a field, excluded words, experience gap)
- [x] **SCORE-03**: `summarize` extracts salary, type, remote status, years of experience and up to 3 "what you'd do" and 3 "what they want" bullets
- [x] **SCORE-04**: `python test_core.py` covers the salary regex, score ordering, pros/cons and excluded words

### Sources & Watcher

- [x] **SRC-01**: `fetch_remotive` returns jobs with no API key
- [x] **SRC-02**: New jobs are inserted deduplicated by URL and scored on insert
- [ ] **SRC-03**: `fetch_reed` and `fetch_adzuna` (country `gb`) return jobs using the keys saved in settings
- [ ] **WATCH-01**: A watcher thread polls the APIs on the configured interval and keeps running after a source fails
- [ ] **WATCH-02**: Poll intervals (Gmail 5 min, APIs 60 min by default) are read from settings

### Profile & Answers

- [ ] **PROF-01**: CV upload (PDF or DOCX) pre-fills name, email, phone, LinkedIn and skills
- [ ] **PROF-02**: `/api/answers` supports list, create, edit and delete of saved answers
- [ ] **PROF-03**: `find_answer` matches a label by exact then fuzzy (≥ 0.85) lookup and maps the answer onto dropdown or radio options
- [ ] **PROF-04**: Answers that mention the company name or exceed 300 characters are not saved
- [ ] **PROF-05**: `cover_letter` fills an editable template from the profile and job

### Gmail Alerts & Job Details

- [ ] **GMAIL-01**: `fetch_gmail_alerts` reads job-alert emails over IMAP using credentials from `keyring`
- [ ] **GMAIL-02**: Separate parsers handle LinkedIn, Indeed, CV-Library and Totaljobs alerts, each tested against a saved sample email
- [ ] **DETAIL-01**: `fetch_details` reads the JSON-LD `JobPosting` block, else the largest text block on the page
- [ ] **DETAIL-02**: If a page is blocked, retry once in Playwright, then mark it "open listing to read"; never attempt CAPTCHAs

### Autofill

- [ ] **FILL-01**: One dedicated Playwright thread, fed by a `queue.Queue`, runs all browser work
- [ ] **FILL-02**: A form is filled from the profile, saved answers and (if the form has the field) a cover letter, tested on local fixture forms
- [ ] **FILL-03**: Each job ends as `ready` or `needs_input`, with unknown fields outlined
- [ ] **FILL-04**: Up to 5 applications fill at once, each in its own tab, and the cap is a setting
- [ ] **FILL-05**: Submit is detected by a listener, the job becomes `applied`, and typed answers are captured; the app never clicks Submit
- [ ] **FILL-06**: On linkedin.com and indeed.com the app opens the page and shows copy-paste answers instead of filling

### Apply Queue API

- [ ] **QUEUE-01**: `GET /api/queue` lists queued jobs with status, and the queue survives restarts
- [ ] **QUEUE-02**: The API lists unique unanswered questions across the queue, ordered by how often they were seen
- [ ] **QUEUE-03**: Answering a question saves it and fills it in every open form that asks it
- [ ] **QUEUE-04**: A job can be skipped to drop it from the queue

## v2 Requirements

### UI

- **UI-01**: Jobs page with swipe and list views, filter chips and Undo toast
- **UI-02**: Apply queue page with per-job Review & submit
- **UI-03**: Dashboard with weekly stats and profile gaps
- **UI-04**: Profile and Settings pages
- **UI-05**: `Start.bat`, `README.txt` and a pre-built UI bundle for the Windows PC

## Out of Scope

| Feature | Reason |
|---------|--------|
| AI scoring, summaries or cover letters | Rules and templates in v1; one function each so a model can replace them later |
| Clicking Submit | The person always submits |
| Filling LinkedIn/Indeed forms | Breaks their terms |
| CAPTCHA bypass | Never attempted |
| Greenhouse/Lever feeds, notifications, outcome tracker | Deferred |
| Hosted multi-user deployment | Local, single user |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 1 | Complete |
| DATA-03 | Phase 1 | Complete |
| DATA-04 | Phase 1 | Complete |
| DATA-05 | Phase 1 | Complete |
| DATA-06 | Phase 1 | Complete |
| SCORE-01 | Phase 1 | Complete |
| SCORE-02 | Phase 1 | Complete |
| SCORE-03 | Phase 1 | Complete |
| SCORE-04 | Phase 1 | Complete |
| SRC-01 | Phase 1 | Complete |
| SRC-02 | Phase 1 | Complete |
| SRC-03 | Phase 2 | Pending |
| WATCH-01 | Phase 2 | Pending |
| WATCH-02 | Phase 2 | Pending |
| PROF-01 | Phase 3 | Pending |
| PROF-02 | Phase 3 | Pending |
| PROF-03 | Phase 3 | Pending |
| PROF-04 | Phase 3 | Pending |
| PROF-05 | Phase 3 | Pending |
| GMAIL-01 | Phase 4 | Pending |
| GMAIL-02 | Phase 4 | Pending |
| DETAIL-01 | Phase 4 | Pending |
| DETAIL-02 | Phase 4 | Pending |
| FILL-01 | Phase 5 | Pending |
| FILL-02 | Phase 5 | Pending |
| FILL-03 | Phase 5 | Pending |
| FILL-04 | Phase 5 | Pending |
| FILL-05 | Phase 5 | Pending |
| FILL-06 | Phase 5 | Pending |
| QUEUE-01 | Phase 6 | Pending |
| QUEUE-02 | Phase 6 | Pending |
| QUEUE-03 | Phase 6 | Pending |
| QUEUE-04 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 34 total
- Mapped to phases: 34
- Unmapped: 0 ✓

---
*Requirements defined: 2026-09-29*
*Last updated: 2026-09-29 after roadmap creation (v1 total corrected from 33 to 34)*
