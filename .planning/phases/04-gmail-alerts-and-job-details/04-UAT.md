---
status: partial
phase: 04-gmail-alerts-and-job-details
source: [04-VERIFICATION.md]
started: 2026-11-02T00:00:00Z
updated: 2026-11-12T00:00:00Z
---

## Current Test

[testing paused — 1 item outstanding]

## Tests

### 1. Live Gmail poll brings real alert jobs into the app
expected: PUT /api/gmail connected: true; fetch has no gmail error; jobs from all four sites appear; LinkedIn/Indeed details_status skipped; CV-Library/Totaljobs reach ok or blocked; unread alerts stay unread; wrong password gives 400 with the App Password hint
result: skipped
reason: Deferred by the person on 2026-11-12 — not yet run live; to be tested later with a real App Password

## Summary

total: 1
passed: 0
issues: 0
pending: 0
skipped: 1
blocked: 0

## Gaps
