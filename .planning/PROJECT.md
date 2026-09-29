# Job Helper

## What This Is

A local web app, built for someone else to run on their Windows PC, that finds and applies to jobs. The person picks career fields. The app watches job sources, ranks and summarises listings, and shows them as swipe cards or a list. Ticked jobs go into an Apply queue, which the app fills from the CV and saved answers. The person reviews each one and clicks Submit.

## Core Value

Surface well-ranked jobs and pre-fill applications so the person only reviews and submits. The app never clicks Submit.

## Requirements

### Validated

- ✓ Flask app serving `GET /api/health` and the built UI from `api/static/` — existing
- ✓ Vite + React + TypeScript shell that calls `/api/health`, with dev proxy and build output to `api/static/` — existing

### Active

- [ ] SQLite schema and jobs/settings/stats API (current milestone: API first)
- [ ] Rule-based scoring, pros/cons and summaries in `core.py`
- [ ] Job sources (Remotive, Reed, Adzuna, Gmail alerts) fed by a watcher thread
- [ ] Profile, CV extraction, saved answers and answer matching
- [ ] Full job descriptions via `fetch_details`
- [ ] Playwright autofill worker and Apply queue API
- [ ] UI pages (Jobs, Queue, Dashboard, Profile, Settings) — after the API

### Out of Scope

- AI for scoring, summaries or cover letters in v1 — rules and templates only; each lives in one function so a model call can replace it later
- Clicking Submit — the person always submits
- Automating LinkedIn/Indeed forms — breaks their terms; open page and show copy-paste answers only
- Getting past CAPTCHAs — never attempted
- Greenhouse/Lever feeds, desktop notifications, outcome tracker — deferred
- Hosted multi-user deployment — local, single user; the watcher is the first piece to split if this changes

## Context

- Brownfield: only the scaffold exists (see `.planning/codebase/`). `PLAN.md` holds the original full design.
- Dev machine is macOS (Python 3.9.6 in `.venv`); target is Windows with Python 3.12. The UI ships pre-built so the target needs no Node.
- LinkedIn/Indeed/CV-Library/Totaljobs have no public APIs, so their job-alert emails are read from Gmail. Alert parsers need real sample emails and will break when formats change.
- Playwright's sync API isn't thread-safe: all browser work runs on one thread fed by a `queue.Queue`.

## Constraints

- **Tech stack**: Flask + stdlib `sqlite3`, one Python process — simple to run on someone else's PC
- **Distribution**: Double-click `Start.bat`, app at `http://localhost:8765`, all data local
- **Compatibility**: Code must run on Python 3.9 (dev) and 3.12 (target)
- **Compliance**: Respect site terms; no CAPTCHA bypass, no auto-submit

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Build the API first, bottom-up (pure logic before threads/Playwright) | Testable slices; UI needs only the response shapes | — Pending |
| No AI in v1 | Keeps it free and predictable; swap point per function | — Pending |
| Gmail job-alert parsing instead of scraping | No public job APIs on the big boards | — Pending |
| Single Playwright thread + queue | Sync API isn't thread-safe | — Pending |
| Monolith: Flask serves API, UI, watcher and autofill | One process for a non-technical user | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-09-29 after initialization*
