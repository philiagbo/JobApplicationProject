---
status: testing
phase: 04-gmail-alerts-and-job-details
source: [04-VERIFICATION.md]
started: 2026-11-02T00:00:00Z
updated: 2026-11-02T00:00:00Z
---

## Current Test

number: 1
name: Live Gmail poll brings real alert jobs into the app
expected: |
  With the alert emails in INBOX and a Google App Password: PUT /api/gmail returns connected: true;
  POST /api/fetch returns a gmail count with no gmail error in GET /api/watcher; GET /api/jobs shows jobs
  from linkedin, indeed, cv-library and totaljobs; LinkedIn and Indeed jobs have details_status "skipped",
  CV-Library and Totaljobs jobs move from "pending" to "ok" or "blocked"; unread alerts stay unread;
  a wrong password gives 400 with the App Password hint.
awaiting: user response

## Tests

### 1. Live Gmail poll brings real alert jobs into the app
expected: PUT /api/gmail connected: true; fetch has no gmail error; jobs from all four sites appear; LinkedIn/Indeed details_status skipped; CV-Library/Totaljobs reach ok or blocked; unread alerts stay unread; wrong password gives 400 with the App Password hint
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
