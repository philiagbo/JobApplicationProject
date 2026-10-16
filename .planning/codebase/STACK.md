# Technology Stack

**Analysis Date:** 2026-09-29

## Languages

**Primary:**
- TypeScript 6.0.2 - Frontend UI (`ui/src/`)
- Python 3.9.6 - Backend API and services (`api/app.py`)

**Secondary:**
- JavaScript - Node.js build/dev tools
- CSS - Styling (`ui/src/index.css`)

## Runtime

**Environment:**
- Python 3.9.6 (via .venv)
- Node.js (version not pinned; oxlint requires Node 20.19.0 or 22.12.0+)

**Package Manager:**
- npm (manages Node dependencies via `ui/package-lock.json`)
- pip (manages Python dependencies via `api/requirements.txt`)
- Lockfiles: `ui/package-lock.json` present; Python uses minimal `requirements.txt`

## Frameworks

**Core:**
- Flask 3.0+ - HTTP server, JSON API, static file serving (`api/app.py`)
- React 19.2.8 - UI framework (`ui/src/`)
- React DOM 19.2.8 - DOM rendering (`ui/src/main.tsx`)

**Build/Dev:**
- Vite 8.3.0 - Frontend bundler and dev server (`ui/vite.config.ts`)
  - `@vitejs/plugin-react` 6.1.1 - React integration for Vite
- TypeScript 6.0.2 - Type checking and compilation (`ui/tsconfig.*.json`)

**Linting:**
- oxlint 1.81.0 - JavaScript/TypeScript linter (`npm run lint`)

## Key Dependencies

**Frontend (currently installed):**
- `react` 19.2.8 - UI framework
- `react-dom` 19.2.8 - DOM adapter
- `@types/react` 19.2.18 - TypeScript types for React
- `@types/react-dom` 19.2.7 - TypeScript types for React DOM
- `@types/node` 24.13.3 - TypeScript Node.js types
- `@vitejs/plugin-react` 6.1.1 - Vite React plugin
- `oxlint` 1.81.0 - Linter (dev)
- `typescript` 6.0.2 - TypeScript compiler (dev)
- `vite` 8.3.0 - Build tool (dev)

**Frontend (planned, not yet installed):**
- `react-router-dom` - Client-side routing
- `motion` (Framer Motion) - Animation library

**Backend (currently installed):**
- `flask` 3.0+ - Web framework

**Backend (planned, not yet installed per PLAN.md):**
- `pypdf` - PDF parsing for resume extraction
- `python-docx` - DOCX parsing for resume extraction
- `beautifulsoup4` - HTML parsing for job listings
- `requests` - HTTP client for job APIs
- `playwright` - Browser automation for form filling
- `keyring` - System keyring access for credentials

**Built-in Python modules used (per plan):**
- `sqlite3` - Local database
- `imaplib` - Gmail IMAP connection
- `email` - Email parsing
- `difflib` - String comparison for form filling
- `pathlib` - File system operations

## Configuration

**Environment:**
- `.venv/` directory present - isolated Python environment
- No `.env` files present - configuration planned via SQLite `settings` table
- `node_modules/` for frontend packages (committed to lock file, not to git)
- `api/static/` - Built React app output (generated, not committed)

**Frontend Build Configuration:**
- `ui/tsconfig.json` - Composite TypeScript config
  - `ui/tsconfig.app.json` - Application TypeScript config (target: ES2023, JSX: react-jsx)
  - `ui/tsconfig.node.json` - Vite config TypeScript config (target: ES2023)
- `ui/vite.config.ts` - Vite build config:
  - Dev proxy: `/api` → `http://localhost:8765` (Flask)
  - Build output: `../api/static/` (served by Flask)
  - Plugins: `@vitejs/plugin-react`

**Backend Configuration:**
- `api/app.py` - Flask app hardcoded to:
  - Port: 8765
  - Debug mode: enabled (development)
  - Static folder: `api/static/` (built React app)

## Platform Requirements

**Development:**
- macOS (current working directory)
- Python 3.9+ (using 3.9.6)
- Node.js 20.19.0 or 22.12.0+ (for oxlint)
- npm (for frontend tooling)

**Production/Target:**
- Windows PC (per PLAN.md) - app runs as double-click `Start.bat`
- Python 3.12 (planned per PLAN.md stack section)
- No Node.js required on target machine (UI pre-built)

---

*Stack analysis: 2026-09-29*
