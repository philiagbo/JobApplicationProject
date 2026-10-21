---
phase: "02"
slug: "watcher-and-more-sources"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-10-22"
---

# Phase 02 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| app to Reed API | Outbound HTTPS with the Reed key in a Basic auth header; JSON reply is third-party input | API key (secret), job listings |
| watcher thread to SQLite | Second thread writes the same database as request threads | Job rows |
| app to console / API responses | Source error text is logged and returned in `errors` and `STATUS` | Error strings |
| browser/client to Flask /api | PUT /api/settings, GET /api/watcher, POST /api/fetch | Settings incl. masked key |
| person's terminal to local app | Real key typed during manual verification (02-04) | API key (secret) |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-02-01 | Information Disclosure | sources.fetch_reed, watcher logging/STATUS | high | mitigate | `api/sources.py:104` error text is "Reed fetch failed: " + exception only; `test_failure_text_never_contains_key` (`api/test_watcher.py:255`) | closed |
| T-02-02 | Denial of Service | watcher thread | medium | mitigate | Per-source and tick-level `except Exception` (`api/watcher.py:45,90`); WR-03 sleeps after a failed tick | closed |
| T-02-03 | Tampering | concurrent fetches / SQLite | medium | mitigate | `FETCH_LOCK.acquire(blocking=False)` in `api/watcher.py:70` and `api/app.py:107` (409); own connection closed in `finally` | closed |
| T-02-04 | Denial of Service | Reed quota / site terms | low | mitigate | `PAGE_SIZE = 50` first page only (`api/sources.py:11`); poll floor 1 min in `db._clean` (`api/db.py:94`) | closed |
| T-02-05 | Tampering | outbound query values | low | mitigate | `urlencode(params)` with constant `REED_URL` (`api/sources.py:10,34`) | closed |
| T-02-06 | Denial of Service | duplicate watcher under reloader | low | mitigate | `WERKZEUG_RUN_MAIN` guard (`api/app.py:158`); `test_import_does_not_start_watcher` | closed |
| T-02-07 | Information Disclosure | sources.fetch_adzuna | high | mitigate | N/A — Adzuna removed (quick 261021-wez); no Adzuna code in `api/` | closed |
| T-02-08 | Tampering | malformed Adzuna JSON | low | mitigate | N/A — Adzuna removed | closed |
| T-02-09 | Tampering | Adzuna predicted salary | low | mitigate | N/A — Adzuna removed | closed |
| T-02-10 | Denial of Service | Adzuna free quota | low | accept | N/A — Adzuna removed | closed |
| T-02-11 | Information Disclosure | GET /api/watcher, POST /api/fetch | high | mitigate | `watcher_status` returns `watcher.status()` only (`api/app.py:121`); WR-05 also masks `reed_api_key` in GET/PUT /api/settings | closed |
| T-02-12 | Spoofing / CSRF | new /api routes | medium | mitigate | `local_only` before_request guard (`api/app.py:20-21`); foreign-Origin 403 asserted (`api/test_api.py:395`) | closed |
| T-02-13 | Denial of Service | repeated saves / fetches | low | mitigate | Single `WAKE` Event coalesces saves (`api/watcher.py:14`); FETCH_LOCK 409 | closed |
| T-02-14 | Information Disclosure | keys during manual verification | medium | mitigate | Key read with `read -s`, PUT response sent to `/dev/null`, variable unset after; done in the 02-04 live check | closed |
| T-02-SC | Tampering | package installs | high | mitigate | `api/requirements.txt` is still only `flask>=3.0` | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

No accepted risks.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-22 | 15 | 15 | 0 | Claude (secure-phase, L1 grep check) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-22
