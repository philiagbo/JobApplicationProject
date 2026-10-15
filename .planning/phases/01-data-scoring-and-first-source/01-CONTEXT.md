# Phase 1: Data, Scoring and First Source - Context

**Gathered:** 2026-10-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Real Remotive jobs are fetched on demand, stored in SQLite, scored by rules, and served through the Flask API with settings, stats and clear errors. No watcher thread (Phase 2), no CV/profile (Phase 3), no UI.

</domain>

<decisions>
## Implementation Decisions

### Scoring
- **D-01:** Score is a 0–100 integer: base value plus/minus points per rule, clamped.
- **D-02:** Salary vs minimum is the heaviest rule, ahead of title match, remote and excluded words.
- **D-03:** Salary below minimum gets a penalty scaled by how far below. Salary not listed is neutral on score but adds a con ("Salary not listed").
- **D-04:** Excluded words give a big penalty but the job stays visible, with a con naming the word.
- **D-05:** Skills-matched rule and experience-gap rule are skipped (no score effect, no con) until a profile/CV exists in Phase 3.
- **D-06:** Pros/cons are fixed short sentences with values filled in (e.g. "Pays £45k, above your £40k minimum"). All that apply are kept, no cap.
- **D-07:** Score, pros, cons and summary are stored as columns on `jobs`. Pros/cons are JSON arrays in SQLite, returned as real arrays by the API.
- **D-08:** `PUT /api/settings` re-scores all `new` jobs. Queued/dismissed jobs keep their score.

### Summary extraction (`summarize`)
- **D-09:** Salary is converted to an annual number (hourly ≈ ×2000, daily ≈ ×230) and the original text is kept for display.
- **D-10:** Currency is parsed and tagged; only £ salaries are compared to the minimum. Other currencies are shown but treated as "can't compare".
- **D-11:** "What you'd do"/"what they want" bullets: heading-based (Responsibilities/Requirements), keyword fallback; empty is acceptable. Max 3 each.
- **D-12:** Remote status and job type use source structured fields first, then keywords.

### Fetching
- **D-13:** Fetch is triggered by `POST /api/fetch` only (no startup fetch, no watcher). It returns counts of new jobs and is the call the Phase 2 watcher will reuse.
- **D-14:** Remotive is searched once per career field, merged and deduplicated by URL.
- **D-15:** With no career fields set, `POST /api/fetch` returns 400 `{"error": "Choose at least one career field in settings"}`.

### Settings
- **D-16:** `GET /api/settings` always returns the full shape with defaults: career_fields [], excluded_words [], min_salary 0, location "", API keys "", Gmail poll 5 min, API poll 60 min.
- **D-17:** API keys are returned in full (local single-user app).
- **D-18:** `PUT` rejects wrong types and unknown keys with 400, and merges only the keys sent.

### Job status, Undo, stats
- **D-19:** `undo` resets the job to `new` and updates `status_changed_at`.
- **D-20:** `GET /api/jobs` returns only `new` jobs by default; a `?status=` param fetches others.
- **D-21:** Stats use a rolling last 7 days: found by creation time; queued/dismissed/applied by `status_changed_at`; each split by source.
- **D-22:** Unknown job id → 404; invalid transition (e.g. dismissing an `applied` job) → 409. Both with `{"error": ...}`.

### Database and tests
- **D-23:** DB at `api/data/jobhelper.db`, gitignored, path overridable via `JOBHELPER_DB` env var.
- **D-24:** Schema via `CREATE TABLE IF NOT EXISTS` on startup; no migrations.
- **D-25:** Tests use a temp DB file via the env var and plain asserts; `python test_core.py` needs no pytest. API tests use Flask's test client.

### Claude's Discretion
- Exact point values and base score, salary-penalty curve, and the hourly/daily conversion constants, as long as `test_core.py` pins the ordering and behaviours above.
- Module layout (`core.py`, `sources.py`, DB helper) following PLAN.md.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project definition
- `.planning/ROADMAP.md` — Phase 1 goal and success criteria
- `.planning/REQUIREMENTS.md` — DATA-01..06, SCORE-01..04, SRC-01, SRC-02
- `.planning/PROJECT.md` — constraints (Python 3.9/3.12, stdlib sqlite3, no AI in v1)
- `PLAN.md` — original design: data model, scoring rules, module layout

### Codebase maps
- `.planning/codebase/ARCHITECTURE.md` — layers, error handling rules
- `.planning/codebase/STACK.md` — installed deps and gaps (`requests` not yet installed)
- `.planning/codebase/CONVENTIONS.md` — naming and style

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `api/app.py`: Flask app with `/api/health` and static/SPA fallback; the `/api/` 404 JSON handler already follows the error-shape rule.

### Established Patterns
- Error responses use `jsonify(error=...)` with a 4xx/5xx status.
- Python snake_case; must run on 3.9 and 3.12.

### Integration Points
- New API routes register on the existing `app` in `api/app.py`.
- `api/requirements.txt` needs `requests` for Remotive.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

- Experience-gap and CV-skill scoring rules switch on in Phase 3 when a profile exists.
- Fetch-on-startup and background polling belong to Phase 2 (watcher).

</deferred>

---

*Phase: 1-Data, Scoring and First Source*
*Context gathered: 2026-10-15*
