<!-- GSD:project-start source:PROJECT.md -->

## Project

**Job Helper**

A local web app, built for someone else to run on their Windows PC, that finds and applies to jobs. The person picks career fields. The app watches job sources, ranks and summarises listings, and shows them as swipe cards or a list. Ticked jobs go into an Apply queue, which the app fills from the CV and saved answers. The person reviews each one and clicks Submit.

**Core Value:** Surface well-ranked jobs and pre-fill applications so the person only reviews and submits. The app never clicks Submit.

### Constraints

- **Tech stack**: Flask + stdlib `sqlite3`, one Python process — simple to run on someone else's PC
- **Distribution**: Double-click `Start.bat`, app at `http://localhost:8765`, all data local
- **Compatibility**: Code must run on Python 3.9 (dev) and 3.12 (target)
- **Compliance**: Respect site terms; no CAPTCHA bypass, no auto-submit

<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->

## Technology Stack

## Languages

- TypeScript 6.0.2 - Frontend UI (`ui/src/`)
- Python 3.9.6 - Backend API and services (`api/app.py`)
- JavaScript - Node.js build/dev tools
- CSS - Styling (`ui/src/index.css`)

## Runtime

- Python 3.9.6 (via .venv)
- Node.js (version not pinned; oxlint requires Node 20.19.0 or 22.12.0+)
- npm (manages Node dependencies via `ui/package-lock.json`)
- pip (manages Python dependencies via `api/requirements.txt`)
- Lockfiles: `ui/package-lock.json` present; Python uses minimal `requirements.txt`

## Frameworks

- Flask 3.0+ - HTTP server, JSON API, static file serving (`api/app.py`)
- React 19.2.8 - UI framework (`ui/src/`)
- React DOM 19.2.8 - DOM rendering (`ui/src/main.tsx`)
- Vite 8.3.0 - Frontend bundler and dev server (`ui/vite.config.ts`)
- TypeScript 6.0.2 - Type checking and compilation (`ui/tsconfig.*.json`)
- oxlint 1.81.0 - JavaScript/TypeScript linter (`npm run lint`)

## Key Dependencies

- `react` 19.2.8 - UI framework
- `react-dom` 19.2.8 - DOM adapter
- `@types/react` 19.2.18 - TypeScript types for React
- `@types/react-dom` 19.2.7 - TypeScript types for React DOM
- `@types/node` 24.13.3 - TypeScript Node.js types
- `@vitejs/plugin-react` 6.1.1 - Vite React plugin
- `oxlint` 1.81.0 - Linter (dev)
- `typescript` 6.0.2 - TypeScript compiler (dev)
- `vite` 8.3.0 - Build tool (dev)
- `react-router-dom` - Client-side routing
- `motion` (Framer Motion) - Animation library
- `flask` 3.0+ - Web framework
- `pypdf` - PDF parsing for resume extraction
- `python-docx` - DOCX parsing for resume extraction
- `beautifulsoup4` - HTML parsing for job listings
- `requests` - HTTP client for job APIs
- `playwright` - Browser automation for form filling
- `keyring` - System keyring access for credentials
- `sqlite3` - Local database
- `imaplib` - Gmail IMAP connection
- `email` - Email parsing
- `difflib` - String comparison for form filling
- `pathlib` - File system operations

## Configuration

- `.venv/` directory present - isolated Python environment
- No `.env` files present - configuration planned via SQLite `settings` table
- `node_modules/` for frontend packages (committed to lock file, not to git)
- `api/static/` - Built React app output (generated, not committed)
- `ui/tsconfig.json` - Composite TypeScript config
- `ui/vite.config.ts` - Vite build config:
- `api/app.py` - Flask app hardcoded to:

## Platform Requirements

- macOS (current working directory)
- Python 3.9+ (using 3.9.6)
- Node.js 20.19.0 or 22.12.0+ (for oxlint)
- npm (for frontend tooling)
- Windows PC (per PLAN.md) - app runs as double-click `Start.bat`
- Python 3.12 (planned per PLAN.md stack section)
- No Node.js required on target machine (UI pre-built)

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

## Naming Patterns

- React components: PascalCase with `.tsx` extension (`App.tsx`)
- TypeScript source: camelCase with `.ts` extension (`main.tsx`)
- Python modules: snake_case with `.py` extension (`app.py`)
- TypeScript/React: camelCase (`setStatus`, `createRoot`)
- Python: snake_case (`health`, `ui`)
- React components: PascalCase (`App`)
- TypeScript: camelCase for all variables and constants (`status`, `setStatus`)
- Python: snake_case (`STATIC`, `path`)
- CSS custom properties: kebab-case (`--muted`, `--ok`, `--bad`)
- TypeScript: PascalCase for types and interfaces (not used explicitly in current code)
- Union type literals: lowercase for type state values (`'checking' | 'ok' | 'down'`)

## Code Style

- No Prettier config present; formatting is implicit
- Two spaces for CSS properties
- No trailing semicolons in JSX but present in TypeScript
- Linter: oxlint v1.81.0
- Config file: `.oxlintrc.json`
- Plugins: react, typescript, oxc
- Key rules:
- Target: ES2023
- Module: ESNext
- `noUnusedLocals`: true
- `noUnusedParameters`: true
- `noFallthroughCasesInSwitch`: true
- `skipLibCheck`: true
- `allowArbitraryExtensions`: true
- JSX: react-jsx (automatic JSX transform)

## Import Organization

- None configured; using relative imports only

## Error Handling

- React: Promise `.catch()` for async operations, setting state to indicate error
- Python/Flask: Return error tuples with status codes
- Flask error responses use `jsonify()` for JSON responses
- Simple error states in React (status: 'down')
- No error classes or structured error objects currently defined

## Logging

- React: Console logging via browser DevTools (implicit)
- Python: Flask's built-in logging (implicit with `debug=True`)
- No structured logging framework in use

## Comments

- Single-line comments used only for significant architectural notes
- Example from `app.py`: `# Serve the built React app; unknown paths fall back to index.html so client-side routes work.`
- Not currently used in the codebase
- No function documentation present
- Types inferred from TypeScript annotations

## Function Design

- Small, single-responsibility functions
- `App()`: ~15 lines (component with hook)
- `health()`: 1 line (Flask route handler)
- `ui()`: ~8 lines (Flask route handler)
- React hooks: destructure with type annotations
- Flask routes: use Flask's automatic parameter injection
- React components: JSX elements with conditional rendering
- React hooks: TypeScript-typed tuple returns from `useState`
- Flask: `jsonify()` for JSON, `send_from_directory()` for files
- Fallback responses: text strings for error states

## Module Design

- React: Default exports for components
- No named exports in current code
- Python: No explicit exports; Flask decorator-based routing
- None used
- Direct imports from source files

<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

## System Overview

```text

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

- **Separated concerns**: Python backend handles jobs, autofill, database; React frontend handles UI and fetch
- **Pre-built UI**: React is built once with Node (developer-only), then shipped as static files with the app
- **Local-first**: No login, no hosted database, all data stays on the user's PC
- **Single-threaded browser**: Playwright's sync API isn't thread-safe; dedicated worker thread + queue avoids race conditions
- **Development proxy**: Vite dev server proxies `/api` to Flask, so frontend dev doesn't need to rebuild between changes

## Layers

- Purpose: Render UI, collect user input, poll API for updates
- Location: `ui/src/`
- Contains: React components, TypeScript types, CSS
- Depends on: Fetch API to call `/api/` endpoints
- Used by: User's browser, Playwright for autofill review
- Purpose: Route requests, serve React app for non-API paths, coordinate backend work
- Location: `api/app.py`
- Contains: Flask route handlers, static file serving, future thread creation
- Depends on: SQLite, job source libraries (requests, beautifulsoup4), Playwright, email/IMAP
- Used by: Browser (fetch), internal threads, Playwright
- Purpose: Watch for new jobs, fill application forms without blocking HTTP
- Location: Future `api/sources.py` (watcher), `api/autofill.py` (filler)
- Contains: Job fetching logic, form automation
- Depends on: SQLite, external APIs, Playwright
- Used by: Flask app initialization
- Purpose: Persist jobs, answers, settings, application state
- Location: `.db` file (location TBD, likely `api/app.db`)
- Contains: Tables for jobs, answers, unanswered questions, settings
- Depends on: Nothing
- Used by: Flask app, worker threads

## Data Flow

### Primary Request Path (User views jobs)

- React useState for UI state (checking/ok/down status)
- Browser localStorage for view preference (swipe vs list)
- SQLite for persistent job data, answers, settings

### Job Fetching (Background, future)

### Application Queue (Autofill, future)

## Key Abstractions

- Purpose: Represents a single job posting
- Examples: `api/core.py` type definition (future), database row
- Pattern: Immutable data class with calculated properties (score, pros, cons come from `score()` function)
- Purpose: Learned response to application question
- Examples: "First name" → "Philip", "How did you hear" → "LinkedIn"
- Pattern: Normalized question → answer mapping, fuzzy match for variations
- Purpose: A job in the apply pipeline with browser state
- Examples: Status transitions (queued → filling → ready or needs_input → applied)
- Pattern: Atomic status updates, Playwright browser tab maps to queue item
- Purpose: User configuration (career fields, excluded words, API keys, view preference)
- Examples: Stored in SQLite, read on startup, updated via `/api/settings`
- Pattern: Flat key-value map with types known in code

## Entry Points

- Location: `ui/src/main.tsx` (runtime) → `ui/src/App.tsx` (component)
- Triggers: Browser loads `/` or any path
- Responsibilities: Mount React tree, call health check, render current page based on URL fragment (future)
- Location: `api/app.py` main block (lines 28-29)
- Triggers: `python api/app.py` or Windows batch file `Start.bat` (future)
- Responsibilities: Start Flask on port 8765, create watcher and autofill threads (future), initialize SQLite
- Location: `api/sources.py` run loop (future)
- Triggers: Flask startup
- Responsibilities: Poll job APIs every 30 seconds, write new jobs, update SQLite
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

### Storing form answers in the browser

### Blocking the UI thread in Flask

### Mixing browser automation with HTTP requests

## Error Handling

- Flask `/api/` routes return `{"error": "message"}` with HTTP error status (400, 404, 503), never 200 with error key
- React displays error in UI: "API not reachable. Is Flask running?" on fetch fail
- Job fetch failure: log to console (future), continue on next poll (don't stop the watcher)
- Form autofill failure: mark job `needs_input`, don't submit; user reviews and types missing fields
- SQLite errors: raise and crash (don't silently lose data); user should fix and restart

## Cross-Cutting Concerns

- Flask: `print()` for now (future: stdlib `logging` with level control in settings)
- Browser console: React logs via `console.log()`, React DevTools for component tree
- Frontend: TypeScript types prevent most errors; form validation for user input
- Backend: Type checking in core functions (e.g., `score()` expects Job dict with specific keys); SQLite schema enforces types
- None for local app (user is trusted, single-user, runs on their PC)
- API keys (Gmail, Reed, Adzuna) stored in SQLite settings table or `.env` (future: keyring lib recommended in PLAN.md)

<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
