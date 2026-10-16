# Coding Conventions

**Analysis Date:** 2026-09-29

## Naming Patterns

**Files:**
- React components: PascalCase with `.tsx` extension (`App.tsx`)
- TypeScript source: camelCase with `.ts` extension (`main.tsx`)
- Python modules: snake_case with `.py` extension (`app.py`)

**Functions:**
- TypeScript/React: camelCase (`setStatus`, `createRoot`)
- Python: snake_case (`health`, `ui`)
- React components: PascalCase (`App`)

**Variables:**
- TypeScript: camelCase for all variables and constants (`status`, `setStatus`)
- Python: snake_case (`STATIC`, `path`)
- CSS custom properties: kebab-case (`--muted`, `--ok`, `--bad`)

**Types:**
- TypeScript: PascalCase for types and interfaces (not used explicitly in current code)
- Union type literals: lowercase for type state values (`'checking' | 'ok' | 'down'`)

## Code Style

**Formatting:**
- No Prettier config present; formatting is implicit
- Two spaces for CSS properties
- No trailing semicolons in JSX but present in TypeScript

**Linting:**
- Linter: oxlint v1.81.0
- Config file: `.oxlintrc.json`
- Plugins: react, typescript, oxc
- Key rules:
  - `react/rules-of-hooks`: error
  - `react/only-export-components`: warn (allows constant exports)

**TypeScript Strictness:**
- Target: ES2023
- Module: ESNext
- `noUnusedLocals`: true
- `noUnusedParameters`: true
- `noFallthroughCasesInSwitch`: true
- `skipLibCheck`: true
- `allowArbitraryExtensions`: true
- JSX: react-jsx (automatic JSX transform)

## Import Organization

**Order:**
1. React hooks and utilities (`import { useEffect, useState } from 'react'`)
2. Relative imports (`./<path>`)
3. Internal components (`./<ComponentName>.tsx`)

**Path Aliases:**
- None configured; using relative imports only

**Example from `App.tsx`:**
```typescript
import { useEffect, useState } from 'react'

export default function App() {
  // component code
}
```

**Example from `main.tsx`:**
```typescript
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
```

## Error Handling

**Patterns:**
- React: Promise `.catch()` for async operations, setting state to indicate error
  - Example: `.catch(() => setStatus('down'))` in `App.tsx`
- Python/Flask: Return error tuples with status codes
  - Example: `return jsonify(error="not found"), 404` in `app.py`
- Flask error responses use `jsonify()` for JSON responses

**No Custom Exceptions:**
- Simple error states in React (status: 'down')
- No error classes or structured error objects currently defined

## Logging

**Framework:** None configured

**Patterns:**
- React: Console logging via browser DevTools (implicit)
- Python: Flask's built-in logging (implicit with `debug=True`)
- No structured logging framework in use

## Comments

**When to Comment:**
- Single-line comments used only for significant architectural notes
- Example from `app.py`: `# Serve the built React app; unknown paths fall back to index.html so client-side routes work.`

**JSDoc/TSDoc:**
- Not currently used in the codebase
- No function documentation present
- Types inferred from TypeScript annotations

## Function Design

**Size:**
- Small, single-responsibility functions
- `App()`: ~15 lines (component with hook)
- `health()`: 1 line (Flask route handler)
- `ui()`: ~8 lines (Flask route handler)

**Parameters:**
- React hooks: destructure with type annotations
  - Example: `const [status, setStatus] = useState<'checking' | 'ok' | 'down'>('checking')`
- Flask routes: use Flask's automatic parameter injection
  - Example: `def ui(path)` with Flask decorators providing `path`

**Return Values:**
- React components: JSX elements with conditional rendering
- React hooks: TypeScript-typed tuple returns from `useState`
- Flask: `jsonify()` for JSON, `send_from_directory()` for files
- Fallback responses: text strings for error states

## Module Design

**Exports:**
- React: Default exports for components
  - `export default function App() { ... }`
- No named exports in current code
- Python: No explicit exports; Flask decorator-based routing

**Barrel Files:**
- None used
- Direct imports from source files

---

*Convention analysis: 2026-09-29*
