# Codebase Concerns

**Analysis Date:** 2026-09-29

## Tech Debt

**Flask Debug Mode Enabled in Production:**
- Issue: `app.run(port=8765, debug=True)` in `api/app.py:29` enables Flask's debug mode by default
- Files: `api/app.py`
- Impact: Debug mode reveals stack traces, allows arbitrary code execution via the debugger, and disables many security protections; exposes sensitive information if an error occurs
- Fix approach: Move debug mode to environment variable check; use `app.run(port=8765, debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')`

**Missing Error Handling in React API Calls:**
- Issue: `fetch('/api/health')` in `ui/src/App.tsx:7-10` catches network errors but provides no logging or debugging information
- Files: `ui/src/App.tsx`
- Impact: Silent failures make it difficult to diagnose connectivity issues; errors are swallowed with no visibility
- Fix approach: Add structured logging; capture error details (status, message) before setting state

**Incomplete Dependency Installation:**
- Issue: `package.json` in `ui/` lists only React, React-DOM, and dev tools; PLAN.md references react-router-dom, framer-motion, and other libraries not yet installed
- Files: `ui/package.json`
- Impact: Project cannot run features described in the plan until dependencies are added; builds will fail at runtime when code tries to import missing modules
- Fix approach: Install all dependencies listed in PLAN.md section on Stack; audit transitive dependencies for security issues

**Missing Backend Modules:**
- Issue: PLAN.md references `api/sources.py`, `api/core.py`, `api/autofill.py` which do not exist; only skeleton `api/app.py` exists
- Files: `api/` (missing files)
- Impact: All job fetching, scoring, summary generation, autofill functionality is unimplemented; applications will fail immediately when code attempts imports
- Fix approach: Implement modules in order of dependency: sources.py, then core.py, then autofill.py

**No Database Implementation:**
- Issue: PLAN.md describes SQLite schema with tables (`jobs`, `answers`, `unanswered`, `settings`) but no `db.py` or migrations exist
- Files: `api/` (missing files)
- Impact: All data persistence is missing; app cannot store or retrieve jobs, answers, or settings; every restart loses data
- Fix approach: Create `api/db.py` with schema definition and initialization; add migrations directory

**No Input Validation:**
- Issue: Flask endpoints accept arbitrary paths and serve files without validation; React component makes unvalidated API calls
- Files: `api/app.py:19-20` (path validation is minimal), `ui/src/App.tsx:7-10` (no request validation)
- Impact: Potential for path traversal attacks (`GET /..%2F..%2F.env`), server error responses leaking information, missing data validation on API responses
- Fix approach: Add path normalization, validate API responses with schemas (e.g., Pydantic), implement CORS if needed

## Known Bugs

**Unsafe Non-Null Type Assertion:**
- Symptoms: `document.getElementById('root')!` in `ui/src/main.tsx:6` uses non-null assertion without checking if element exists
- Files: `ui/src/main.tsx`
- Trigger: If `index.html` doesn't have a `<div id="root">`, the app crashes with "Cannot read property of null"
- Workaround: Manually verify `index.html` contains the root div; add a check: `const root = document.getElementById('root'); if (!root) throw new Error('Root element not found');`

**Index.html Fallback Masks Server Errors:**
- Symptoms: When `static/index.html` is missing or build fails, the 503 error message is shown, but subsequent requests for non-existent files still return `index.html` instead of 404
- Files: `api/app.py:23-25`
- Trigger: Make a request for a nonexistent static asset after the UI hasn't been built
- Workaround: Check the console for actual errors; rebuild the UI with `npm run build` in the `ui/` directory

## Security Considerations

**Debug Mode Exposes Information:**
- Risk: Stack traces leak file paths, internal code structure, and library versions to anyone accessing the app when an error occurs
- Files: `api/app.py:29`
- Current mitigation: None; debug is always on
- Recommendations: Disable debug in production; use environment variable to control; implement proper error logging to file instead of showing to users

**No CORS Configuration:**
- Risk: If this app is ever deployed to a domain other than `localhost:8765`, requests from external origins will fail silently or be blocked; no protection against cross-site request forgery if run on a shared network
- Files: `api/app.py` (no `@app.after_request` CORS handler)
- Current mitigation: Currently runs only on localhost, limiting exposure
- Recommendations: Add CORS headers explicitly; document that the app is designed for local-only use; add security headers (Content-Security-Policy, X-Frame-Options, etc.)

**No HTTPS/TLS:**
- Risk: If app is accessed from another machine on the local network, data is sent in plain text
- Files: `api/app.py:29`
- Current mitigation: Documented as local Windows PC app only
- Recommendations: Add option to enable TLS if accessed over network; document the security model clearly

**Keyring Access Not Implemented:**
- Risk: PLAN.md mentions `keyring` library for API keys but no implementation exists; keys may be stored unencrypted in database or config
- Files: `api/app.py` (no keyring code), `api/requirements.txt` (keyring not listed)
- Current mitigation: Keys not yet implemented
- Recommendations: Use keyring (or similar) for all API key storage; never commit API keys to git; implement environment variable fallback

## Performance Bottlenecks

**Synchronous Path Checking:**
- Problem: `api/app.py:21` calls `.is_file()` on every static file request, which blocks the request thread
- Files: `api/app.py`
- Cause: Using `Path.is_file()` makes a filesystem call per request; no caching of file existence
- Improvement path: Cache static file listing at startup or use Werkzeug's static file serving

**No Caching Headers:**
- Problem: Static assets (CSS, JS, images) have no cache headers, so every reload downloads everything again
- Files: `api/app.py` (send_from_directory call has no cache control)
- Cause: Flask's default `send_from_directory` doesn't set cache headers
- Improvement path: Add cache control headers for immutable assets (versioned JS/CSS); set short TTL for index.html

**Health Check Loop Has No Timeout:**
- Problem: `ui/src/App.tsx:7` fetch request has no timeout; if backend is hung, the page hangs waiting for response
- Files: `ui/src/App.tsx`
- Cause: Fetch API defaults to 30s+ timeout at browser level
- Improvement path: Add explicit `AbortController` with 5s timeout; retry on timeout

## Fragile Areas

**React App Health Check Is Single Point of Failure:**
- Files: `ui/src/App.tsx`
- Why fragile: Entire app status depends on one health endpoint; no retry logic, no offline support, no graceful degradation
- Safe modification: Add retry logic (exponential backoff), implement local fallback if API is unreachable, show different UI states (checking → ok → down → offline)
- Test coverage: No tests; health check flow is untested

**Flask Static File Serving Lacks Robustness:**
- Files: `api/app.py:15-25`
- Why fragile: Catch-all route with complex conditional logic; easy to accidentally serve wrong file or expose directories
- Safe modification: Extract to a proper static file middleware or use WhiteNoise; whitelist allowed static directories
- Test coverage: No tests; routing logic untested

**TypeScript Non-Null Assertions:**
- Files: `ui/src/main.tsx:6` (DOM element assertion)
- Why fragile: `!` operator bypasses type checking; if element is missing, crashes at runtime
- Safe modification: Add runtime checks before assertions; throw meaningful errors
- Test coverage: No DOM unit tests

**Undefined API Response Type:**
- Files: `ui/src/App.tsx:9` (type assertion to `{ ok: boolean }`)
- Why fragile: Response structure isn't validated; if API returns different shape, the app crashes or shows wrong state
- Safe modification: Create a `types.ts` file with `HealthResponse` type; use Zod or similar for runtime validation
- Test coverage: No API contract tests

## Scaling Limits

**Single Flask Process:**
- Current capacity: Handles one user, one request at a time (single-threaded by default)
- Limit: Cannot handle concurrent uploads, job fetching, and autofill in parallel; watcher thread (planned) will block API responses
- Scaling path: Use threading.Thread for watcher/autofill workers (as planned); consider moving to async Flask or Gunicorn for production

**SQLite for Multi-User:**
- Current capacity: Single-user local app only
- Limit: SQLite has write-locks; only one process can write at a time; not suitable for concurrent autofill + API requests
- Scaling path: If deployed as multi-user, migrate to PostgreSQL; redesign threading to use thread pool with connection pooling

**No Request Rate Limiting:**
- Current capacity: Frontend polls every 30s (mentioned in PLAN); no backend rate limit enforcement
- Limit: Malicious client could hammer API with rapid requests; no DoS protection
- Scaling path: Add rate limiting (e.g., per-IP or per-session); implement request queuing

## Dependencies at Risk

**Flask Version Floating:**
- Risk: `requirements.txt` specifies `flask>=3.0` without upper bound; major version changes could break compatibility
- Impact: `pip install` could grab Flask 4.x (when released) with breaking changes; unclear what version was tested
- Migration plan: Pin to `flask>=3.0,<4.0` and test before upgrading; consider using a `requirements.lock` file

**React 19 Prerelease Instability:**
- Risk: `package.json` uses `react@^19.2.8`; React 19 is recent and may have compatibility issues with third-party libraries
- Impact: When adding libraries (react-router-dom, framer-motion), they may not support React 19 yet; builds could fail
- Migration plan: Check compatibility matrix before adding dependencies; consider pinning to specific React minor version if issues arise

**Playwright Async/Sync Mismatch:**
- Risk: PLAN.md mentions "Playwright's sync API isn't thread-safe" but doesn't show how autofill.py handles this
- Impact: If thread management is wrong, browser automation will deadlock or corrupt state
- Migration plan: Implement dedicated browser thread with a queue.Queue (as planned); add integration tests for thread safety before deployment

**Undeclared Dependencies:**
- Risk: PLAN.md lists beautifulsoup4, python-docx, pypdf, requests, keyring but `requirements.txt` only has flask
- Impact: When `api/sources.py` or `api/core.py` are written and import these, pip install will fail
- Migration plan: Update `requirements.txt` now with all planned dependencies; pin versions; test install from scratch

## Test Coverage Gaps

**No Tests for API Routing:**
- What's not tested: File serving logic (`/`, `/<path:path>`), fallback to index.html, 503 error case
- Files: `api/app.py:15-25`
- Risk: Changes to routing could accidentally expose files or break static serving without detection
- Priority: High — routing is a security boundary

**No Tests for React Component:**
- What's not tested: Health check state transitions (checking → ok → down), fetch error handling, dom mounting
- Files: `ui/src/App.tsx`
- Risk: Changes to fetch logic or state handling could silently break the app; users would only discover failure in production
- Priority: High — this is the main entry point

**No Integration Tests:**
- What's not tested: Flask serving React build, dev-server proxy to API, dev build process, production build process
- Files: Full stack
- Risk: A missing build step or config change could cause app to fail in development or when shipped to user; no automated check
- Priority: Medium — caught manually during testing but should be automated

**No E2E Tests:**
- What's not tested: Full app flows from user perspective (viewing jobs, queueing applications, filling forms, etc.)
- Files: Full stack
- Risk: Regressions could silently break workflows; no automated smoke test that the app boots and shows a job list
- Priority: Medium — important for confidence in releases, but can be manual until feature-complete

## Missing Critical Features

**No Logging:**
- Problem: App has no observability; errors are swallowed or only shown to user as "API not reachable"
- Blocks: Debugging production issues; impossible to know if user's app is stuck in watcher thread, hanging on a request, or actually down
- Priority: High — add structured logging to Flask (startup, requests, errors) and React (errors, state changes)

**No Configuration Management:**
- Problem: Port 8765, file paths, and API endpoints are hardcoded throughout the codebase
- Blocks: Can't run multiple instances, can't override port for testing, can't point to different API servers
- Priority: High — extract to config.py or environment variables before adding features

**No Data Validation/Serialization:**
- Problem: API responses and database writes lack validation; no schemas defined
- Blocks: Can't safely add database operations or API endpoints; no contract between frontend and backend
- Priority: High — define Pydantic models for all API types before implementing sources.py and core.py

**No CI/CD Pipeline:**
- Problem: No automated checks on commit (linting, type checking, tests); could merge broken code
- Blocks: Confident releases; currently relying on manual testing
- Priority: Medium — set up GitHub Actions or similar to run `npm run build`, `npm run lint`, `python -m pytest` on every push

---

*Concerns audit: 2026-09-29*
