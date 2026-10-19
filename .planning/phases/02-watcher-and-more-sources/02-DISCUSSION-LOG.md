# Phase 2: Watcher and More Sources - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-19
**Phase:** 2-Watcher and More Sources
**Areas discussed:** Watcher start & timing, Reed & Adzuna queries, Failure & visibility, Fetch/watcher interplay

---

## Watcher start & timing

| Option | Selected |
|--------|----------|
| First poll at startup | ✓ |
| First poll after one interval | |
| No career fields: skip quietly | ✓ |
| No career fields: log warning each poll | |
| Reloader: start only in real process | ✓ |
| Reloader: disable | |

## Reed & Adzuna queries

| Option | Selected |
|--------|----------|
| One search per career field, merged | ✓ |
| One combined query | |
| Two Adzuna settings keys (app_id, app_key) | ✓ |
| One 'id:key' string | |
| First page only | ✓ |
| A few pages | |

## Failure & visibility

| Option | Selected |
|--------|----------|
| Missing key: skip silently | ✓ |
| Missing key: log once per poll | |
| Console log + last-poll status in API | ✓ |
| Console only | |
| Retry next poll | ✓ |
| Back off after N failures | |

## Fetch/watcher interplay

| Option | Selected |
|--------|----------|
| Manual fetch: all sources, shared lock | ✓ |
| Manual stays Remotive-only | |
| Overlap: 409 | ✓ |
| Overlap: wait | |
| Wake watcher on key/field save | ✓ |
| No immediate poll on save | |

## Claude's Discretion

Reed/Adzuna request details, wake mechanism, status endpoint shape.

## Deferred Ideas

Gmail polling (Phase 4); back-off; persisted watcher history.
