---
phase: "02"
slug: watcher-and-more-sources
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-19"
---

# Phase 02 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | plain-assert scripts with `__main__` runner (no pytest) |
| **Config file** | none |
| **Quick run command** | `.venv/bin/python api/test_watcher.py` |
| **Full suite command** | `.venv/bin/python api/test_core.py && .venv/bin/python api/test_api.py && .venv/bin/python api/test_watcher.py` |
| **Estimated runtime** | ~10 seconds |

## Sampling Rate

- **After every task commit:** quick run command
- **After every plan wave:** full suite command
- **Before `/gsd-verify-work`:** full suite green
- **Max feedback latency:** 15 seconds

## Per-Task Verification Map

| Req | Behavior | Test Type | Automated Command | File Exists |
|-----|----------|-----------|-------------------|-------------|
| SRC-03 | `fetch_reed` Basic auth, field mapping, `SourceError` on failure | unit | `.venv/bin/python api/test_watcher.py` | ❌ W0 |
| SRC-03 | `fetch_adzuna` gb endpoint, URL canonicalisation, predicted salary dropped | unit | same | ❌ W0 |
| SRC-03 | Keys saved -> `POST /api/fetch` returns scored, deduped jobs from reed + adzuna; missing keys skip silently | integration | `.venv/bin/python api/test_api.py` | edit existing |
| WATCH-01 | Watcher polls on its own; one source failing does not stop others; thread survives exceptions | unit | `test_watcher.py` | ❌ W0 |
| WATCH-02 | Defaults 5/60 min; changing `api_poll_minutes` changes cadence without restart | unit | `test_watcher.py`, `test_api.py` | ❌ W0 |
| D-12/D-13/D-14/D-10/D-03 | 409 when busy, `errors` map, WAKE on settings change, `GET /api/watcher`, no thread on import | integration | `test_api.py`, `test_watcher.py` | ❌ W0 |

## Wave 0 Requirements

- [ ] `api/test_watcher.py` — SRC-03 adapters, WATCH-01, WATCH-02, D-03, D-10
- [ ] `api/test_api.py` — generalise `fake_get_json` to `(url, params, headers=None)`; update `test_fetch_dedupes` exact-body assertion; reset `watcher.STATUS` in `fresh_client()`

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Reed/Adzuna responses map correctly; second fetch adds 0 new Adzuna jobs | SRC-03 | Needs real API keys | Save both keys, `POST /api/fetch`, confirm jobs from both, repeat and confirm 0 new Adzuna |

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] No 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
