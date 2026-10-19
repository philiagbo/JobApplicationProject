# Phase 2: Watcher and More Sources - Context

**Gathered:** 2026-10-19
**Status:** Ready for planning

<domain>
## Phase Boundary

A background watcher thread refreshes the job feed on its own from Remotive, Reed and Adzuna (country `gb`), and `POST /api/fetch` covers all three. No Gmail polling (Phase 4 wires it into this watcher), no profile, no UI.

</domain>

<decisions>
## Implementation Decisions

### Watcher start and timing
- **D-01:** The first poll runs right at startup, then repeats on the API interval (default 60 min).
- **D-02:** With no career fields set, the watcher skips quietly and re-checks on the next tick (no error, no log spam).
- **D-03:** Start the watcher only in the real process: when debug is on, check `WERKZEUG_RUN_MAIN` so the reloader doesn't start two; when debug is off (Windows target), always start.
- **D-04:** Intervals are read from settings on every tick, so changing them changes cadence without a restart (WATCH-02). Gmail interval (5 min) stays a setting only; Phase 4 adds its poll.

### Reed and Adzuna queries
- **D-05:** One search per career field, merged and deduplicated by URL, same as Remotive (D-14 of Phase 1). Location from settings is passed to the APIs; min salary is passed only where the API supports it.
- **D-06:** First page only (~50 newest) per source per field each poll.
- **D-07:** Adzuna uses two settings keys, `adzuna_app_id` and `adzuna_app_key`, added to the settings defaults and PUT validation (extends D-16/D-18 of Phase 1). Reed uses its single key. Adzuna country is fixed to `gb`.
- **D-08:** `fetch_reed` and `fetch_adzuna` live in `api/sources.py`, return the same job dict shape as `fetch_remotive`, and raise `SourceError` on failure.

### Failures and visibility
- **D-09:** A source with no key saved (Reed/Adzuna) is skipped silently.
- **D-10:** Failures are logged to the console and recorded as per-source last-poll status (last_ok, last_error, time) exposed through the API (new `GET /api/watcher` or within stats; planner picks the shape). Status is in-memory, not persisted.
- **D-11:** One failing source never stops the others or the watcher; a failed source is simply retried on the next poll (no back-off).

### Fetch and watcher interplay
- **D-12:** `run_fetch` runs all sources through one code path used by both the watcher and `POST /api/fetch`; the manual response returns per-source counts and per-source errors rather than failing whole.
- **D-13:** A single lock guards fetching. If a fetch is already running, `POST /api/fetch` returns 409 `{"error": "Fetch already running"}`.
- **D-14:** Saving settings that change keys or career fields wakes the watcher for an immediate poll; interval changes just apply on the next tick.

### Claude's Discretion
- Exact Reed/Adzuna request parameters and response mapping (including how salary fields map into the job dict), the watcher's thread/wake mechanism (e.g. `threading.Event`), and the shape/location of the status endpoint.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project definition
- `.planning/ROADMAP.md` — Phase 2 goal and success criteria
- `.planning/REQUIREMENTS.md` — SRC-03, WATCH-01, WATCH-02
- `.planning/PROJECT.md` — constraints (Python 3.9/3.12, stdlib, no AI in v1)
- `.planning/phases/01-data-scoring-and-first-source/01-CONTEXT.md` — Phase 1 decisions this phase extends (D-13 fetch, D-14, D-16..D-18 settings)
- `PLAN.md` — original design: sources and watcher

### Codebase maps
- `.planning/codebase/ARCHITECTURE.md` — thread and error-handling rules
- `.planning/codebase/CONVENTIONS.md` — naming and style

No external API specs in repo; researcher should read current Reed and Adzuna API docs.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `api/sources.py`: `fetch_remotive`, `get_json` (urllib + User-Agent), `SourceError`, Remotive throttle lock pattern.
- `api/app.py`: `run_fetch(conn, settings)` already the shared fetch call; `fetch_now` route; per-request `get_db()` (watcher thread needs its own `db.connect()`).
- `api/db.py`: `insert_jobs`, `get_settings`, `save_settings`, `rescore_new`.

### Established Patterns
- Errors: `SourceError` → 502 with `{"error": ...}`.
- `# ponytail:` comments mark deliberate simplifications.
- Must run on Python 3.9 and 3.12.

### Integration Points
- Start the watcher from `api/app.py` main block (and guard for debug reloader).
- `settings_put` signals the watcher after save.
- `db.get_settings` defaults/validation gain `adzuna_app_id` / `adzuna_app_key`.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

- Gmail alert polling on the 5 min interval — Phase 4.
- Back-off after repeated failures — not needed now.
- Persisted watcher status/history — only if the UI needs it later.

</deferred>

---

*Phase: 2-Watcher and More Sources*
*Context gathered: 2026-10-19*
