# Testing Patterns

**Analysis Date:** 2026-09-29

## Test Framework

**Runner:**
- Not detected — no testing framework installed
- Recommended options for TypeScript/React: Vitest, Jest

**Assertion Library:**
- Not detected

**Run Commands:**
- No test commands currently configured in `package.json`
- Lint command available: `npm run lint` (runs oxlint)

## Test File Organization

**Location:**
- No test files found in codebase
- Recommended pattern: co-located tests (`.test.tsx` next to source files)

**Naming:**
- No test files present to establish pattern
- Suggested convention: `ComponentName.test.tsx` for React components, `moduleName.test.ts` for utilities

**Structure:**
- No existing test structure in codebase
- Recommended for TypeScript/React projects:
  ```
  src/
  ├── App.tsx
  ├── App.test.tsx
  ├── main.tsx
  └── index.css
  ```

## Test Structure

**Suite Organization:**
- No test suites currently present

**Patterns (Recommended):**
- Setup: None required for simple React components without external dependencies
- Teardown: Not applicable
- Assertion pattern: Would follow chosen framework (Vitest/Jest conventions)

## Mocking

**Framework:**
- Not configured

**Patterns:**
- No mocking currently implemented
- Current code in `App.tsx` uses real `fetch()` to `/api/health` endpoint

**What to Mock:**
- API calls (e.g., fetch to `/api/health` in `App.tsx`)
- External dependencies once added
- Timer functions if async/debounce logic is added

**What NOT to Mock:**
- React hooks themselves (use React Testing Library or Vitest helpers)
- CSS/styling imports
- Simple component rendering

## Fixtures and Factories

**Test Data:**
- None defined
- No fixtures directory

**Location:**
- Suggested: `src/__fixtures__/` or `src/test-utils.ts`

## Coverage

**Requirements:**
- No coverage configuration present
- Coverage tools: pytest-cov (Python), c8 or Istanbul (TypeScript)

**View Coverage:**
- Not currently available
- Would need to configure after adding test framework

## Test Types

**Unit Tests:**
- Recommended for `App.tsx`:
  - Test initial render (status = 'checking')
  - Test successful API call (status = 'ok')
  - Test API failure (status = 'down')
  - Test conditional rendering based on status
- Recommended for `app.py`:
  - Test `/api/health` returns `{"ok": true}`
  - Test `/` route serves index.html when UI is built
  - Test `/` returns 503 when UI not built
  - Test 404 handling for unknown paths

**Integration Tests:**
- Recommended: Test React client → Flask API communication
- Test full health check flow: UI loads → API call succeeds → status displays 'ok'
- Would use fetch + mock Flask server or test environment

**E2E Tests:**
- Not currently configured
- Could use Playwright or Cypress once testing infrastructure is in place
- Scope: Test full application startup and API connection flow

## Common Patterns

**Async Testing:**
- Pattern not yet established in codebase
- React component `App.tsx` uses `fetch()` with `.then()` chains
- Recommended: Use `async`/`await` with test framework's async support
- Example test structure:
  ```typescript
  // Recommended pattern (not yet implemented)
  test('displays ok status when API succeeds', async () => {
    render(<App />)
    // Mock fetch or wait for state update
    await waitFor(() => expect(...).toHaveTextContent('API connected'))
  })
  ```

**Error Testing:**
- Current pattern in App.tsx: `.catch(() => setStatus('down'))`
- No test coverage for error path
- Recommended: Mock fetch to reject and verify error state displays

---

*Testing analysis: 2026-09-29*
