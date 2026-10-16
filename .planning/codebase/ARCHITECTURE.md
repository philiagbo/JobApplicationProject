<!-- refreshed: 2026-09-29 -->
# Architecture

**Analysis Date:** 2026-09-29

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    Browser (React/TypeScript)               │
│              `ui/src/App.tsx`, `main.tsx`                   │
│  - Health check, future pages (Jobs, Queue, Dashboard)      │
│  - Plain CSS with CSS variables, no UI kit                  │
└─────────────────────────────────┬───────────────────────────┘
         HTTP (fetch)              │
         /api/* endpoints          │
         Proxied in dev by Vite    │
         │                         │
         ▼                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Flask Backend (Python)                    │
│                      `api/app.py`                            │
│  - Serves built React app (api/static/index.html)           │
│  - Provides JSON API endpoints (/api/health, /api/...)      │
│  - Future: Watcher thread, autofill thread (queue.Queue)    │
│  - SQLite database (jobs, answers, unanswered, settings)    │
└─────────────────────────────────┬───────────────────────────┘
         SQLite, File I/O         │
         Playwright (separate thread)
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│              Data & External Services                        │
│  - SQLite database (.db file)                               │
│  - Job sources (Reed, Adzuna, Remotive, Gmail)             │
│  - Browser automation (Playwright) for autofill             │
│  - CV/PDF parsing, email extraction                         │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| React App | UI entry point, health check, future page routing | `ui/src/App.tsx` |
| React main | DOM mount point, StrictMode wrapper | `ui/src/main.tsx` |
| Flask app | HTTP server, API routing, UI serving, thread management | `api/app.py` |
| Vite config | Build output to `api/static/`, dev proxy to Flask | `ui/vite.config.ts` |
| CSS | Root theme variables, dark mode support | `ui/src/index.css` |

## Pattern Overview

**Overall:** Simple monolithic web app — one Python process (Flask) serves the built React UI and provides the JSON API. Data is local SQLite, no external database. Browser automation runs on a dedicated Playwright thread fed by `queue.Queue` to avoid threading issues.

**Key Characteristics:**
- **Separated concerns**: Python backend handles jobs, autofill, database; React frontend handles UI and fetch
- **Pre-built UI**: React is built once with Node (developer-only), then shipped as static files with the app
- **Local-first**: No login, no hosted database, all data stays on the user's PC
- **Single-threaded browser**: Playwright's sync API isn't thread-safe; dedicated worker thread + queue avoids race conditions
- **Development proxy**: Vite dev server proxies `/api` to Flask, so frontend dev doesn't need to rebuild between changes

## Layers

**Presentation (Browser):**
- Purpose: Render UI, collect user input, poll API for updates
- Location: `ui/src/`
- Contains: React components, TypeScript types, CSS
- Depends on: Fetch API to call `/api/` endpoints
- Used by: User's browser, Playwright for autofill review

**API (Flask):**
- Purpose: Route requests, serve React app for non-API paths, coordinate backend work
- Location: `api/app.py`
- Contains: Flask route handlers, static file serving, future thread creation
- Depends on: SQLite, job source libraries (requests, beautifulsoup4), Playwright, email/IMAP
- Used by: Browser (fetch), internal threads, Playwright

**Workers (Background Threads):**
- Purpose: Watch for new jobs, fill application forms without blocking HTTP
- Location: Future `api/sources.py` (watcher), `api/autofill.py` (filler)
- Contains: Job fetching logic, form automation
- Depends on: SQLite, external APIs, Playwright
- Used by: Flask app initialization

**Data (SQLite):**
- Purpose: Persist jobs, answers, settings, application state
- Location: `.db` file (location TBD, likely `api/app.db`)
- Contains: Tables for jobs, answers, unanswered questions, settings
- Depends on: Nothing
- Used by: Flask app, worker threads

## Data Flow

### Primary Request Path (User views jobs)

1. User opens browser to `http://localhost:8765/`
2. Flask catches `/` with no path (`app.py:16-25`), checks if `api/static/index.html` exists
3. If built, serves `index.html`; if not, returns error message
4. Browser loads `index.html`, runs `main.tsx` which mounts `App.tsx`
5. `App.tsx` calls `fetch('/api/health')` on mount
6. Flask `/api/health` endpoint (`app.py:10-12`) returns `{"ok": true}`
7. React displays "API connected" and will eventually fetch `/api/jobs`

**State Management:**
- React useState for UI state (checking/ok/down status)
- Browser localStorage for view preference (swipe vs list)
- SQLite for persistent job data, answers, settings

### Job Fetching (Background, future)

1. Watcher thread loops every 30 seconds (configurable)
2. Calls `fetch_reed()`, `fetch_gmail_alerts()`, etc. from `api/sources.py`
3. Writes new jobs to SQLite with status `new`
4. `score()` function in `api/core.py` calculates match score
5. React polls `/api/jobs` every 30 seconds, renders new cards
6. Live updates shown with "N new jobs" pill

### Application Queue (Autofill, future)

1. User clicks ✓ on a job, changes status to `queued`
2. Autofill thread starts (if not running), picks up queued jobs
3. For each job, Playwright opens form, calls `find_answer()` to match fields
4. Fills form with profile data, saved answers, cover letter
5. Jobs reach status `ready` or `needs_input`
6. React shows `/api/queue` page; user reviews and clicks Submit
7. Playwright listener detects submit, captures new answers, marks job `applied`

## Key Abstractions

**Job Object:**
- Purpose: Represents a single job posting
- Examples: `api/core.py` type definition (future), database row
- Pattern: Immutable data class with calculated properties (score, pros, cons come from `score()` function)

**Answer:**
- Purpose: Learned response to application question
- Examples: "First name" → "Philip", "How did you hear" → "LinkedIn"
- Pattern: Normalized question → answer mapping, fuzzy match for variations

**Queue Item:**
- Purpose: A job in the apply pipeline with browser state
- Examples: Status transitions (queued → filling → ready or needs_input → applied)
- Pattern: Atomic status updates, Playwright browser tab maps to queue item

**Settings:**
- Purpose: User configuration (career fields, excluded words, API keys, view preference)
- Examples: Stored in SQLite, read on startup, updated via `/api/settings`
- Pattern: Flat key-value map with types known in code

## Entry Points

**React App:**
- Location: `ui/src/main.tsx` (runtime) → `ui/src/App.tsx` (component)
- Triggers: Browser loads `/` or any path
- Responsibilities: Mount React tree, call health check, render current page based on URL fragment (future)

**Flask Server:**
- Location: `api/app.py` main block (lines 28-29)
- Triggers: `python api/app.py` or Windows batch file `Start.bat` (future)
- Responsibilities: Start Flask on port 8765, create watcher and autofill threads (future), initialize SQLite

**Watcher Thread (future):**
- Location: `api/sources.py` run loop (future)
- Triggers: Flask startup
- Responsibilities: Poll job APIs every 30 seconds, write new jobs, update SQLite

**Autofill Thread (future):**
- Location: `api/autofill.py` run loop (future)
- Triggers: Flask startup (always running, idle until jobs queued)
- Responsibilities: Check queue, open forms, fill with Playwright, detect submit

## Architectural Constraints

- **Single-threaded Flask**: No global request context issues; watcher and autofill run in separate threads managed by Flask startup
- **Playwright thread isolation**: All Playwright calls on one thread fed by `queue.Queue` to avoid sync API race conditions
- **Local SQLite**: No migrations, no schema versioning; schema version stored in settings table if needed
- **Pre-built UI delivery**: React built once with Node, shipped as static files; end user only needs Python
- **No external database**: All data in one `.db` file; makes the app portable and usable offline
- **Browser-only state for transients**: Match scores, pros/cons computed fresh on each render (not persisted)

## Anti-Patterns

### AI/Business logic in the front-end

**What happens:** Score calculation, cover letter generation, or form-field matching in JavaScript
**Why it's wrong:** Logic drifts between frontend and backend; hard to share with future API consumers; duplicates code
**Do this instead:** All scoring, summarization, answer matching in `api/core.py` functions. React calls `/api/jobs`, gets back pre-calculated scores and pros/cons. See `api/core.py:score()` contract (future).

### Storing form answers in the browser

**What happens:** React component holds answer state, never persists to backend
**Why it's wrong:** Answers lost on page refresh or app restart; can't be shared across browser tabs
**Do this instead:** React form feeds back to `/api/answers` POST on blur or submit. Answers fetched fresh on mount from `/api/answers` GET.

### Blocking the UI thread in Flask

**What happens:** Flask route handler runs `fetch_jobs()` directly, freezing `/` until results come back
**Why it's wrong:** User sees white screen; if job fetch is slow, UI appears hung
**Do this instead:** Watcher thread fetches jobs asynchronously, writes to SQLite. Flask routes only read from database. React polls `/api/jobs` every 30 seconds.

### Mixing browser automation with HTTP requests

**What happens:** Flask route opens Playwright browser for every autofill request
**Why it's wrong:** Playwright startup is slow (each adds 2–3 seconds); can't batch requests or reuse tabs across jobs
**Do this instead:** Dedicated autofill thread keeps browser instances open, feeds from `queue.Queue`. Flask route marks job queued, thread picks it up.

## Error Handling

**Strategy:** Fail open (let user see what's wrong), never silently drop data.

**Patterns:**
- Flask `/api/` routes return `{"error": "message"}` with HTTP error status (400, 404, 503), never 200 with error key
- React displays error in UI: "API not reachable. Is Flask running?" on fetch fail
- Job fetch failure: log to console (future), continue on next poll (don't stop the watcher)
- Form autofill failure: mark job `needs_input`, don't submit; user reviews and types missing fields
- SQLite errors: raise and crash (don't silently lose data); user should fix and restart

## Cross-Cutting Concerns

**Logging:** 
- Flask: `print()` for now (future: stdlib `logging` with level control in settings)
- Browser console: React logs via `console.log()`, React DevTools for component tree

**Validation:** 
- Frontend: TypeScript types prevent most errors; form validation for user input
- Backend: Type checking in core functions (e.g., `score()` expects Job dict with specific keys); SQLite schema enforces types

**Authentication:** 
- None for local app (user is trusted, single-user, runs on their PC)
- API keys (Gmail, Reed, Adzuna) stored in SQLite settings table or `.env` (future: keyring lib recommended in PLAN.md)

---

*Architecture analysis: 2026-09-29*
