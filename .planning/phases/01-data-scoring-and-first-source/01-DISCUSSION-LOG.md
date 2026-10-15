# Phase 1: Data, Scoring and First Source - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-15
**Phase:** 1-Data, Scoring and First Source
**Areas discussed:** Score scale and weights, Fetching, Settings defaults and API keys, Job status/Undo/stats, Database and tests, Re-scoring, Pros/cons wording, Summary extraction

---

## Score scale and weights
**Choices:** 0–100 integer; skip skills rule with no penalty before a CV; salary vs minimum weighs most; excluded words = big penalty, job stays visible; no-salary neutral + con; scaled penalty below minimum; experience rule skipped until profile has years.

## How jobs get fetched
**Choices:** `POST /api/fetch` only; one Remotive search per career field; 400 when no fields set.

## Settings defaults and API keys
**Choices:** full default shape; keys returned in full; strict validation (400); merge on PUT.

## Job status, Undo, stats
**Choices:** undo resets to `new`; list returns `new` only by default; rolling 7 days; 404/409 for unknown id/invalid transition.

## Database and tests
**Choices:** `api/data/jobhelper.db` gitignored + env override; temp DB + plain asserts; `CREATE TABLE IF NOT EXISTS`.

## Re-scoring
**Choices:** re-score `new` jobs on settings PUT; store score/pros/cons/summary as columns.

## Pros/cons wording
**Choices:** fixed sentences with values; keep all that apply (user chose over the recommended cap of 3); JSON arrays in SQLite.

## Summary extraction
**Choices:** annual-normalised salary + original text; tag currency, compare only £; heading-based bullets with keyword fallback; source fields first for remote/type.

## Claude's Discretion
Exact point values, penalty curve, conversion constants, module layout.

## Deferred Ideas
Experience/skills rules (Phase 3); startup fetch and polling (Phase 2).
