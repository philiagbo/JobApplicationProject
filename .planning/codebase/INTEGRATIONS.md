# External Integrations

**Analysis Date:** 2026-09-29

## APIs & External Services

**Job Boards (planned, not yet implemented per PLAN.md):**
- **Reed Jobs** - Free public API for UK job listings
  - SDK/Client: `requests` (Python HTTP client)
  - Function: `fetch_reed()` (planned in `api/sources.py`)
  - Auth: API key (to be stored in SQLite `settings` table)

- **Adzuna** - Job aggregator API
  - SDK/Client: `requests`
  - Function: `fetch_adzuna(country="gb")` (planned in `api/sources.py`)
  - Auth: API key (to be stored in SQLite `settings` table)

- **Remotive** - Remote job API
  - SDK/Client: `requests`
  - Function: `fetch_remotive()` (planned in `api/sources.py`)
  - Auth: No key required (public API)

**Email Job Alerts (planned, not yet implemented):**
- **Gmail** - Job alert email parser
  - Connection: IMAP (`imaplib` stdlib)
  - Function: `fetch_gmail_alerts()` (planned in `api/sources.py`)
  - Auth: Gmail OAuth via system keyring (`keyring` package)
  - Services parsed from email:
    - LinkedIn job alerts
    - Indeed job alerts
    - CV-Library job alerts
    - Totaljobs job alerts (or RSS feed as fallback)

**LinkedIn Job Alerts:**
- Delivery: Email-based alerts
- Parser: Custom email parser (planned in `api/sources.py`)
- No direct API (LinkedIn prohibits scraping)

**Indeed Job Alerts:**
- Delivery: Email-based alerts
- Parser: Custom email parser (planned in `api/sources.py`)
- No direct API

**CV-Library Job Alerts:**
- Delivery: Email-based alerts
- Parser: Custom email parser (planned in `api/sources.py`)
- No direct API

**Totaljobs Job Alerts:**
- Delivery: Email-based alerts OR RSS feed
- Parser: Custom email parser or RSS feed parser (planned in `api/sources.py`)
- No direct API

## Data Storage

**Primary Database:**
- SQLite (local filesystem only)
  - File location: `*.db` (in project root or API directory, exact path TBD)
  - Client: Python `sqlite3` (stdlib)
  - Schema (planned per PLAN.md):
    - `jobs`: job listings with URLs, source, title, company, location, salary, description, summary, score, pros, cons, status, status_changed_at
    - `answers`: user-provided answers to form questions (memory bank for autofill)
    - `unanswered`: tracking unanswered questions for profile gaps
    - `settings`: user configuration (career fields, excluded words, min salary, location, API keys, poll intervals, view preference)

**File Storage:**
- Local filesystem only - no cloud storage
- Resume/CV files: Parsed locally via `pypdf` and `python-docx` (not uploaded)
- Static files: Built React app in `api/static/` (generated on build, served by Flask)

**Caching:**
- None detected; planned implementation uses in-memory caching via application state

## Authentication & Identity

**Auth Provider:**
- Custom local authentication
  - No login required (single-user local app)
  - Gmail OAuth (planned for email access)
    - Delivery: via Python `keyring` for secure storage
    - Scope: `gmail.readonly` for reading job alert emails

**Credentials Storage:**
- System keyring via `keyring` package (planned)
- API keys: Stored in SQLite `settings` table (user-configurable in Settings page)

## Document Processing

**PDF Handling:**
- Library: `pypdf` (planned)
- Use: Resume/CV parsing for autofill
- Function: `extract_profile()` (planned in `api/core.py`)

**DOCX Handling:**
- Library: `python-docx` (planned)
- Use: Resume/CV parsing for autofill (Word format)

**HTML Parsing:**
- Library: `beautifulsoup4` (planned)
- Use: Parsing job listing HTML from job board websites

## Browser Automation

**Form Filling & Submission:**
- Library: Playwright (planned, sync API)
- Implementation: `api/autofill.py` (planned)
- Threading: Single dedicated thread (Playwright sync API is not thread-safe)
- Queue: `queue.Queue` for thread-safe work distribution
- Use cases:
  - Pre-fill job application forms from user profile and saved answers
  - Listen for form submission success
  - Submit listener (note: **app never clicks Submit** per PLAN.md; user reviews and clicks)

## Web Server

**Frontend Serving:**
- Flask static file serving (`api/app.py`)
  - Serves built React app from `api/static/`
  - Path: `/` routes to `api/static/index.html`
  - API paths: `/api/*` handled by Flask JSON endpoints
  - Fallback: Non-existent paths serve `index.html` for client-side routing

**Dev Server:**
- Vite dev server (local development only)
  - Proxy: `/api` routes to Flask at `http://localhost:8765`
  - Port: Default Vite port (typically 5173)
  - Config: `ui/vite.config.ts`

## Application Endpoints

**Current (implemented):**
- `GET /api/health` - Health check, returns `{"ok": true}`

**Planned (per PLAN.md):**
- `GET /api/jobs` - List all jobs
- `POST /api/jobs/<id>/dismiss` - Dismiss a job
- `POST /api/jobs/<id>/queue` - Queue a job for application
- `POST /api/jobs/<id>/undo` - Undo job status
- `GET /api/queue` - List jobs in apply queue
- `GET /api/answers` - Get saved answers
- `POST /api/answers` - Save answer
- `GET /api/stats` - Dashboard statistics

## Background Services (planned)

**Job Watcher Thread:**
- Continuously fetch jobs from configured sources
- Poll interval: User-configurable (stored in `settings`)
- Sources: Reed, Adzuna, Remotive, Gmail alerts
- Ranking: `score()` function from `api/core.py`
- Summarization: `summarize()` function from `api/core.py`

**Autofill Worker Thread:**
- Dedicated thread for Playwright browser automation
- Queue: Processes items from job queue
- Workflow: Pre-fill form → wait for user review → user clicks submit
- Answers: Pull from `answers` table; remember new answers for future jobs

## Error Handling & Logging

**Logging:**
- Not yet configured; planned implementation likely uses Python `logging` module
- Levels: TBD

**Error Sources:**
- API failures: Job board APIs may be down or rate-limited
- Email parsing errors: Malformed email alerts from job boards
- Form filling errors: Playwright may encounter unexpected form layouts
- Database errors: Handled via standard Python exception handling (TBD)

## Security Considerations

**Credentials:**
- API keys stored in SQLite `settings` table (local device only)
- Gmail OAuth: Stored in system keyring via `keyring` package
- No cloud transmission (local app)

**Data Privacy:**
- All data stays on user's local PC
- No external logging or telemetry detected
- Resume/CV: Parsed locally, not uploaded

**Deployment:**
- Single-user local application
- No HTTPS/TLS required (localhost only)
- Windows target uses double-click `Start.bat` (no installer complexity)

---

*Integration audit: 2026-09-29*
