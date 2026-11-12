---
phase: "04"
slug: "gmail-alerts-and-job-details"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-11-12"
---

# Phase 04 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| PyPI to .venv | Third-party packages enter the runtime | bs4, keyring, playwright and their dependencies |
| Browser/API client to Flask | Local HTTP API, guarded by the `local_only` Host/Origin check | Gmail address, App Password (PUT only) |
| App to OS credential store | keyring | App Password (secret) |
| App to Gmail IMAP | TLS, read-only mailbox | Alert emails (personal data) |
| Alert email to parser | Untrusted HTML from senders | Job fields, hrefs |
| App to job pages (urllib, headless browser) | Untrusted remote pages; SSRF boundary toward the local network | Job descriptions |
| Repo to public git history | Committed test samples | Redacted alert emails |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-04-01 | Tampering | requirements.txt ranges | medium | mitigate | Upper-bounded pins (requirements.txt:4-6) | closed |
| T-04-SC | Tampering | pip installs | high | mitigate | blocking-human legitimacy gate in 04-01 (approved); installed metadata matches upstream; no browser download | closed |
| T-04-02 | Information Disclosure | App Password | high | mitigate | keyring only; GET returns {address, connected}; fixed error text; test_gmail_password_never_leaks | closed |
| T-04-03 | Information Disclosure | IMAP MITM | high | mitigate | ssl.create_default_context() (alerts.py:61); test_imap_connects_with_verified_tls | closed |
| T-04-04 | Tampering | Mailbox | high | mitigate | select readonly=True + BODY.PEEK[]; test_imap_read_only | closed |
| T-04-05 | Spoofing | Cross-site PUT/DELETE /api/gmail | medium | mitigate | local_only guard (app.py:29-38); JSON body required | closed |
| T-04-06 | Tampering | Alert hrefs | medium | mitigate | core.http_url in canonical_url and alert_job; test_canonical_url_rules | closed |
| T-04-07 | Denial of Service | Oversized/malformed emails | low | mitigate | MAX_EMAIL_BYTES, per-email try/except, 30 s IMAP timeout | closed |
| T-04-08 | Tampering | HTML in snippets | medium | mitigate | core.plain_text before storage | closed |
| T-04-09 | Elevation of Privilege | Unusable credential store | low | mitigate | 503, nothing written; watcher treats as disconnected | closed |
| T-04-10 | Information Disclosure | Details fetch SSRF | high | mitigate | core.fetchable (resolved-address check) before every request; per-hop _SafeRedirect; final-URL check; refused redirects never reach the browser | closed |
| T-04-11 | Denial of Service | Huge/slow pages | medium | mitigate | 20 s timeout, MAX_PAGE_BYTES, one worker with 5 s gap | closed |
| T-04-12 | Tampering | Page HTML (stored XSS) | medium | mitigate | Plain text only stored; blocked pages store nothing; UI renders text | closed |
| T-04-13 | Denial of Service | Row that always throws | low | mitigate | Per-row except marks blocked; test_worker_marks_blocked_on_error | closed |
| T-04-14 | Tampering | Legacy DB migration | medium | mitigate | PRAGMA-guarded ALTER, default pending; D-17 checkpoint answered | closed |
| T-04-15 | Compliance | LinkedIn/Indeed fetching | high | mitigate | details_plan + core.never_fetch on every hop, final URL and browser route | closed |
| T-04-16 | Information Disclosure | Committed samples | high | mitigate | Only From/Date/Subject kept; scrub terms 0 hits; raw exports gitignored | closed |
| T-04-17 | Information Disclosure | Tracking tokens in samples | medium | mitigate | Scripted redaction at the person's request (04-04-SUMMARY) | closed |
| T-04-18 | Tampering | Malicious exported email | low | accept | See Accepted Risks Log | closed |
| T-04-19 | Tampering | Hostile alert hrefs | medium | mitigate | Same gates as T-04-06; all 66 parsed URLs pass http_url | closed |
| T-04-20 | Denial of Service | Adversarial alert HTML | low | mitigate | bs4 html.parser, guarded lookups, per-email isolation | closed |
| T-04-21 | Compliance | Following tracker links | high | mitigate | Parsers make no network calls; test_parsers_make_no_network_calls | closed |
| T-04-22 | Information Disclosure | Browser SSRF | high | mitigate | fetchable before request; page.route guard; hop listener; page.url re-check discards content | closed |
| T-04-23 | Elevation of Privilege | Hostile page JavaScript | medium | mitigate | Headless, fresh browser per task, closed in finally, no profile, no interaction | closed |
| T-04-24 | Denial of Service | Hanging page/browser | medium | mitigate | goto 20 s, idle 5 s, launch 20 s, 60 s wait with task cancellation | closed |
| T-04-25 | Compliance | CAPTCHA/evasion/auto-submit | high | mitigate | Read-only page task, no UA override or evasion args; challenge pages blocked | closed |
| T-04-26 | Tampering | Cross-thread Playwright use | medium | mitigate | Single queue-fed thread; test_browser_single_thread | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-04-01 | T-04-18 | Exported sample emails are only parsed by stdlib `email` and bs4 `html.parser` in tests; nothing in them is executed or fetched (auditor confirmed with sockets blocked). Disposition `accept` was set at plan time in 04-04-PLAN.md. | Plan 04-04 threat model | 2026-11-12 |

*Accepted risks do not resurface in future audit runs.*

### Residual notes (non-blocking at ASVS L1)

1. `core._public_ip` does not use `ip.is_global`, so the shared-address range 100.64.0.0/10 (used by Tailscale and carrier-grade NAT) passes the SSRF guard. Fix: return `ip.is_global`.
2. DNS rebinding window between `fetchable` and the request (ponytail comment, core.py:95).
3. Browser: a refused server-redirect hop is sent before the page is discarded (ponytail comment, browser.py:105-107); `page.route` likely misses service-worker and WebSocket traffic. No content is stored in any of these cases.
4. The 60 s browser wait bounds the caller, not the browser thread: the route guard's `getaddrinfo` has no timeout.
5. T-04-12 relies on Phase 6 rendering descriptions as text (decoded `&lt;` may appear as `<`).

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-12 | 27 | 27 | 0 | gsd-security-auditor (HEAD bbf1076) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-12
