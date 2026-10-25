---
phase: "4"
slug: "gmail-alerts-and-job-details"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-25"
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | plain-assert scripts (`test_*` functions + `__main__` runner), as in `api/test_core.py` |
| **Config file** | none — each script sets `JOBHELPER_DB` to a temp path before importing |
| **Quick run command** | `.venv/bin/python api/test_details.py` / `.venv/bin/python api/test_gmail.py` |
| **Full suite command** | `for f in api/test_*.py; do .venv/bin/python "$f" \|\| exit 1; done` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run the new/extended test script for that task
- **After every plan wave:** Run the full suite loop
- **Before `/gsd-verify-work`:** Full suite must be green, plus the human-verify live Gmail poll
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01 T1 | 01 | 1 | all four (deps) | T-04-SC | bs4, keyring, playwright verified on pypi.org before install; never auto-approved | checkpoint:human-action (gate blocking-human, never auto-approved) | `.venv/bin/pip show beautifulsoup4 keyring playwright` still exits 1 until approval | n/a | ⬜ pending |
| 04-01 T2 | 01 | 1 | all four (deps) | T-04-01 | upper-bounded pins; playwright <1.61; no browser download | smoke | `.venv/bin/python -c "import bs4, keyring, playwright.sync_api ..."` then test_core, test_api, test_watcher | ✅ existing | ⬜ pending |
| 04-02 T1 (tracer) | 02 | 2 | GMAIL-01 | T-04-02 | password only in keyring; login tested before store | integration | `.venv/bin/python api/test_gmail.py && .venv/bin/python api/test_api.py && .venv/bin/python api/test_watcher.py` | ❌ W0 (this task creates test_gmail.py) | ⬜ pending |
| 04-02 T2 | 02 | 2 | GMAIL-01 (D-01) | T-04-02, T-04-05, T-04-09 | password never in responses, DB file, STATUS or logs; 400/502/503 paths store nothing | integration | `.venv/bin/python api/test_gmail.py && .venv/bin/python api/test_api.py` | ✅ after T1 | ⬜ pending |
| 04-02 T3 | 02 | 2 | GMAIL-01 (D-02..D-05, D-08) | T-04-03, T-04-04, T-04-06, T-04-07 | verified TLS; EXAMINE + BODY.PEEK only; http(s) public-host allowlist; size cap | unit | `.venv/bin/python api/test_gmail.py && .venv/bin/python api/test_api.py && .venv/bin/python api/test_watcher.py` | ✅ after T1 | ⬜ pending |
| 04-03 T1 | 03 | 3 | DETAIL-01 (D-17) | T-04-14 | one-way column add confirmed (go or hold; D-17 itself not reopened) before the live DB changes | checkpoint:decision (gate blocking, no auto-select: waits for the person's "add-column" or "hold") | none | n/a | ⬜ pending |
| 04-03 T2 (tracer) | 03 | 3 | DETAIL-01 | T-04-10, T-04-12 | http(s) gate before urllib; plain text only stored | integration (local http.server) | `.venv/bin/python api/test_details.py && .venv/bin/python api/test_watcher.py && .venv/bin/python api/test_api.py && .venv/bin/python api/test_gmail.py` | ❌ W0 (this task creates test_details.py) | ⬜ pending |
| 04-03 T3 | 03 | 3 | DETAIL-01, DETAIL-02 (D-12, D-13, D-16..D-18) | T-04-10, T-04-11, T-04-13, T-04-15 | file:// and redirect-to-file blocked; LinkedIn/Indeed never fetched; blocked pages store nothing | unit | `.venv/bin/python api/test_details.py && .venv/bin/python api/test_watcher.py && .venv/bin/python api/test_api.py` | ✅ after T2 | ⬜ pending |
| 04-04 T1 | 04 | 3 | GMAIL-02 (D-06) | T-04-16 | raw exports only under gitignored api/data/ | checkpoint:human-action | `test -s api/data/alert-samples/linkedin.eml && ... && git check-ignore -q api/data/alert-samples/linkedin.eml` | n/a | ⬜ pending |
| 04-04 T2 | 04 | 3 | GMAIL-02 (D-07) | T-04-16, T-04-17 | no recipient address, name or delivery headers in samples | scan | python one-liner (headers, body) + `! grep -qiwFf api/data/alert-samples/scrub-terms.txt api/samples/*.eml` | ❌ W0 (this task creates api/samples/) | ⬜ pending |
| 04-04 T3 | 04 | 3 | GMAIL-02 (D-07) | T-04-17 | hand redaction of names, tokens, account links | checkpoint:human-action | re-run the 04-04 T2 scan | ✅ after T2 | ⬜ pending |
| 04-05 T1 (tracer) | 05 | 4 | GMAIL-02 | T-04-19 | canonical http(s) URLs only | integration (fake IMAP + real sample) | `.venv/bin/python api/test_gmail.py` | ✅ | ⬜ pending |
| 04-05 T2 | 05 | 4 | GMAIL-02 (D-06, D-08, D-09) | T-04-19, T-04-20, T-04-21 | parsers make no network call; exact senders, never bare domains | unit + human-check (live Gmail; blocking human gate, plan autonomous: false) | `.venv/bin/python api/test_gmail.py && .venv/bin/python api/test_api.py && .venv/bin/python api/test_watcher.py` | ✅ | ⬜ pending |
| 04-06 T1 (tracer) | 06 | 4 | DETAIL-02 | T-04-22, T-04-26 | single browser thread; post-navigation URL check | live smoke (real Chrome, local page) | `.venv/bin/python api/test_details.py` must print `live browser: ok`, then test_watcher, test_api | ✅ | ⬜ pending |
| 04-06 T2 | 06 | 4 | DETAIL-02 (D-14..D-16, D-18) | T-04-22..T-04-25 | no page interaction, no agent override or evasion flags, challenge pages blocked | unit (fake Playwright) | `.venv/bin/python api/test_details.py && .venv/bin/python api/test_watcher.py && .venv/bin/python api/test_api.py && .venv/bin/python api/test_gmail.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `api/test_gmail.py` — fake IMAP, in-memory keyring, endpoint tests (created by 04-02 T1); parser tests added by 04-05 once the samples exist
- [ ] `api/test_details.py` — extraction, blocked rules, local HTTP server, migration, `save_details` (created by 04-03 T2); fake and live browser tests added by 04-06
- [ ] `api/samples/` — four redacted `.eml` files (04-04: human export, decode and scrub, human redaction)
- [ ] Pins in `api/requirements.txt` + `.venv/bin/pip install -r api/requirements.txt` (04-01, after the blocking-human package check)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Gmail poll with real App Password | GMAIL-01, GMAIL-02 | needs the person's Google account | 04-05 T2 `<human-check>`: first confirm the alert emails are in INBOX, not archived by a Gmail filter (INBOX-only is an accepted limit); then `PUT /api/gmail`, `POST /api/fetch`, check the `gmail` count, `GET /api/watcher` and `GET /api/jobs`; alerts stay unread. 04-05 is `autonomous: false`; the phase stays human_needed until this is confirmed |
| Hand redaction of the four samples | GMAIL-02 (D-07) | only the person can judge what is personal | 04-04 T3 checkpoint, then the staged diff before commit |
| Windows keyring + Edge channel | GMAIL-01, DETAIL-02 | dev is macOS (RESEARCH A4, A5, A6) | run the app on the Windows PC (Python 3.12): connect Gmail, watch a blocked job get one Edge retry |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
