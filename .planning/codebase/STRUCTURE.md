# Codebase Structure

**Analysis Date:** 2026-09-29

## Directory Layout

```
JobApplicationProject/
├── api/                        # Python Flask backend
│   ├── app.py                  # Flask app, routes, static serving
│   ├── requirements.txt         # Python dependencies (Flask only currently)
│   └── static/                 # Built React app (Vite output, git-ignored)
│       ├── index.html
│       ├── assets/
│       └── ...
├── ui/                         # React TypeScript frontend
│   ├── src/                    # Source code
│   │   ├── App.tsx             # Root component
│   │   ├── main.tsx            # React DOM mount
│   │   ├── index.css           # Root CSS variables, dark mode
│   │   ├── api.ts              # Fetch helpers & types (future)
│   │   ├── usePoll.ts          # 30-second poll hook (future)
│   │   ├── pages/              # Page components (future)
│   │   │   ├── Jobs.tsx
│   │   │   ├── Queue.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Profile.tsx
│   │   │   └── Settings.tsx
│   │   ├── components/         # Reusable components (future)
│   │   │   ├── JobCard.tsx     # Shared by swipe & list views
│   │   │   ├── SwipeDeck.tsx   # Motion drag-to-swipe
│   │   │   ├── JobList.tsx
│   │   │   ├── FilterBar.tsx
│   │   │   └── UndoToast.tsx
│   │   └── app.css             # App-level styles (future)
│   ├── index.html              # HTML entry point
│   ├── vite.config.ts          # Build config, dev proxy
│   ├── tsconfig.json           # TypeScript references
│   ├── tsconfig.app.json       # App-specific TypeScript config
│   ├── tsconfig.node.json      # Build-time TypeScript config
│   ├── .oxlintrc.json          # Linter config (oxlint)
│   ├── package.json            # Dependencies, build scripts
│   ├── package-lock.json       # Locked dependency versions
│   └── node_modules/           # Installed npm packages (git-ignored)
├── .planning/
│   └── codebase/               # Architecture docs (this directory)
│       ├── ARCHITECTURE.md     # System design, layers, flows
│       ├── STRUCTURE.md        # This file — where to put new code
│       ├── CONVENTIONS.md      # Coding style (future)
│       └── TESTING.md          # Test patterns (future)
├── .claude/                    # Claude Code workspace settings
├── PLAN.md                     # Full project plan (reference for Phase design)
├── .gitignore                  # Exclude .venv, node_modules, api/static/, *.db
└── Start.bat                   # Windows batch file to start Flask (future)
```

## Directory Purposes

**`api/`:**
- Purpose: Python backend — Flask server, job sources, core logic, database
- Contains: Main app entry point, future modules for fetching, scoring, autofill
- Key files: `app.py` (routing), `sources.py` (job fetching — future), `core.py` (scoring/summarization — future), `autofill.py` (form filling — future)

**`ui/src/`:**
- Purpose: React TypeScript source code
- Contains: Components, hooks, API helpers, pages, styles
- Key files: `App.tsx` (root), `api.ts` (fetch types & helpers — future)

**`ui/public/`:**
- Purpose: Static assets (favicon, etc.)
- Contains: Files copied as-is to output, not processed by Vite
- Key files: `favicon.svg` (if present)

**`api/static/`:**
- Purpose: Built React app, served by Flask
- Contains: Output from `npm run build` in `ui/`
- Key files: `index.html`, `assets/` with `.js` and `.css` chunks
- Generated: Yes (do not edit)
- Committed: No (in `.gitignore`)

**`.venv/`:**
- Purpose: Python virtual environment
- Contains: Installed Flask, beautifulsoup4, requests, playwright, keyring, pypdf, python-docx, etc.
- Generated: Yes
- Committed: No (in `.gitignore`)

**`ui/node_modules/`:**
- Purpose: Installed npm packages
- Contains: React, Vite, TypeScript, OXLint, etc.
- Generated: Yes
- Committed: No (in `.gitignore`)

## Key File Locations

**Entry Points:**
- `api/app.py` — Python backend (run with `python api/app.py` or via `Start.bat`)
- `ui/src/main.tsx` — React entry (runs in browser)
- `ui/index.html` — HTML document root (loaded by Flask from `api/static/index.html` after build)

**Configuration:**
- `api/requirements.txt` — Python package versions
- `ui/package.json` — npm package versions, build scripts
- `ui/vite.config.ts` — Vite build settings, dev proxy to Flask
- `ui/tsconfig.app.json` — TypeScript compiler options
- `ui/.oxlintrc.json` — Linting rules

**Core Logic:**
- `api/app.py` — Flask app, routing, static serving (health check currently)
- `ui/src/App.tsx` — React root component (health check currently)
- `ui/src/index.css` — CSS variables, theme (used by all components)

**Database & Settings:**
- `api/app.db` (future) — SQLite file (jobs, answers, settings; create on first run)
- `.env` or keyring (future) — API keys for Reed, Adzuna, Gmail

**Testing:**
- `api/tests/` (future) — Unit tests for `core.py`, `sources.py`
- `ui/src/**/*.test.tsx` (future) — React component tests
- `api/test_core.py` (future) — Manual test file mentioned in PLAN

## Naming Conventions

**Files:**
- React components: PascalCase, `.tsx` or `.ts` (e.g., `JobCard.tsx`, `usePoll.ts`)
- Python modules: snake_case, `.py` (e.g., `app.py`, `sources.py`, `core.py`)
- Styles: lowercase, `.css` (e.g., `index.css`, `app.css`)
- Configuration: `.config.ts`, `.config.json`, `.json` (e.g., `vite.config.ts`, `tsconfig.app.json`)

**Directories:**
- Feature folders: lowercase, plural for collections (e.g., `pages/`, `components/`, `tests/`)
- CSS scope: colocated with component or in root `app.css` (no separate `styles/` folder unless many shared files)

**Functions:**
- React components: PascalCase (e.g., `JobCard`, `SwipeDeck`)
- React hooks: camelCase, prefix `use` (e.g., `usePoll`, `useAnswers`)
- Python functions: snake_case (e.g., `fetch_reed()`, `score()`, `find_answer()`)
- API endpoints: lowercase with hyphens (e.g., `/api/health`, `/api/jobs`, `/api/queue`)

**Variables & Types:**
- TypeScript types: PascalCase (e.g., `Job`, `Answer`, `QueueItem`)
- Component props: PascalCase (e.g., `<JobCard job={...} />`)
- CSS custom properties: lowercase with hyphens (e.g., `--bg`, `--text`, `--ok`)
- Python constants: UPPER_SNAKE_CASE (e.g., `STATIC`, `PORT`)

## Where to Add New Code

**New Feature (e.g., Jobs page):**
- Primary component: `ui/src/pages/Jobs.tsx`
- Shared components: `ui/src/components/JobCard.tsx` (used by swipe and list views)
- API types and helpers: `ui/src/api.ts` (add `Job` type, `getJobs()` fetch helper)
- Styling: Import CSS in component or add to `ui/src/app.css`
- Backend route: Add to `api/app.py` (e.g., `@app.get("/api/jobs")`)

**New React Component (e.g., SwipeDeck for drag-to-swipe):**
- Location: `ui/src/components/SwipeDeck.tsx`
- Pattern: Accept `jobs` prop, render with Framer Motion `drag="x"`, handle swipe threshold
- Import in page: `import SwipeDeck from '../components/SwipeDeck'`
- See PLAN.md for swipe interaction details

**New React Hook (e.g., 30-second polling):**
- Location: `ui/src/usePoll.ts`
- Pattern: `export function usePoll(url: string, interval: number = 30000) { ... }`
- Returns: `[data, loading, error]` or `data | null`
- Import in component: `const jobs = usePoll('/api/jobs')`

**New Python Module (e.g., Job fetching):**
- Location: `api/sources.py`
- Pattern: One function per source (`fetch_reed()`, `fetch_gmail_alerts()`, `fetch_adzuna()`)
- Signature: Returns list of Job dicts with keys: `url, source, title, company, location, salary, description, status`
- Called by: Watcher thread in startup code
- See PLAN.md for detailed data structure

**New API Endpoint:**
- Location: `api/app.py`
- Pattern: Use `@app.get()` or `@app.post()` decorator, return `jsonify()` response
- Example from current code: `@app.get("/api/health")` returns `{"ok": true}`
- Error handling: Return `jsonify(error="message"), 404` for not-found, etc.
- CORS: Not needed (same-origin in dev, same host in production)

**New Database Schema:**
- Location: SQLite setup code (future, likely `api/app.py` on first run)
- Pattern: CREATE TABLE statements in Python, not migrations
- Examples from PLAN: `jobs`, `answers`, `unanswered`, `settings` tables
- Initialization: Check if table exists, create if missing (no versioning needed for single-user)

**Utilities & Helpers:**
- Shared TypeScript utilities: `ui/src/api.ts` (fetch helpers, types)
- Shared Python utilities: `api/core.py` (`score()`, `summarize()`, `find_answer()`)
- CSS variables: `ui/src/index.css` (--bg, --text, --muted, --ok, --bad, etc.)

**Styles:**
- Component styles: Inline `style={}` prop for small, component-specific CSS
- Shared styles: `ui/src/index.css` (root variables, body, dark mode)
- Page or feature-wide styles: Create `ui/src/pages/jobs.css` or add to `ui/src/app.css`
- No CSS-in-JS libraries (PLAN calls for plain CSS with variables)

**Testing:**
- Unit tests for Python: `api/tests/test_core.py` (mocking job inputs, checking `score()` output)
- Manual testing: `api/test_core.py` (top-level test cases, run with `python api/test_core.py`)
- Component tests (future): `ui/src/App.test.tsx` (use Jest or Vitest if added)
- No snapshot tests (keep tests readable and maintainable)

## Special Directories

**`api/static/`:**
- Purpose: Built React app output
- Generated: By `npm run build` in `ui/`, output goes to `api/static/`
- Committed: No (listed in `.gitignore`)
- When to regenerate: After every UI code change before deployment; dev uses Vite dev server proxy instead

**`.venv/`:**
- Purpose: Python virtual environment (isolated dependencies)
- Generated: By `python -m venv .venv`, then `pip install -r api/requirements.txt`
- Committed: No (listed in `.gitignore`)
- Activation: `. .venv/bin/activate` (macOS/Linux) or `.venv\Scripts\activate` (Windows)

**`ui/node_modules/`:**
- Purpose: Installed npm packages
- Generated: By `npm install`
- Committed: No (listed in `.gitignore`)
- Lock file: `package-lock.json` is committed; `node_modules` rebuilt from it

**`ui/.vite/` & `ui/.vite-temp/`:**
- Purpose: Vite internal cache for faster rebuilds
- Generated: Automatically by Vite
- Committed: No (in `.gitignore`)

---

*Structure analysis: 2026-09-29*
