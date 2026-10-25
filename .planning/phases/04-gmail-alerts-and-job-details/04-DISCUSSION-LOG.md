# Phase 4: Gmail Alerts and Job Details - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md. This log keeps the alternatives that were considered.

**Date:** 2026-10-25
**Phase:** 4-Gmail Alerts and Job Details
**Areas discussed:** Gmail sign-in & mail rules, Sample alert emails, When details are fetched, Blocked pages & Playwright, Dependencies & polling

---

## Gmail sign-in & mail rules

| Question | Options | Selected |
|----------|---------|----------|
| Credentials entry | API endpoint into keyring / One-off command / You decide | API endpoint |
| Mail filter | By sender since last poll, read-only / Unread only, mark read / Dedicated label | By sender since last poll |
| First run lookback | 7 days / 2 days / 30 days | 7 days |
| Career-field filter | Keep all alert jobs / Drop non-matching titles | Keep all |

## Sample alert emails

| Question | Options | Selected |
|----------|---------|----------|
| Samples | User exports real ones / Best-guess from public examples / Mix | User exports real ones |
| Privacy | Redact then commit / Keep local, gitignored | Redact then commit |
| Zero-job parse | Record in watcher status / Silently skip | Record in watcher status |
| Totaljobs | Email parser only / Try RSS, fall back | Email parser only |

## When details are fetched

| Question | Options | Selected |
|----------|---------|----------|
| Trigger | Background after insert / On demand only / Both | Background after insert |
| Which jobs | Short/empty description only / Every new job | Short/empty only |
| Re-score | Yes if still new / No | Yes if still new |
| Throttle | 5 s fixed / Setting | 5 s fixed |

## Blocked pages & Playwright

| Question | Options | Selected |
|----------|---------|----------|
| Retry mechanism | Single browser thread now / Short-lived per retry / Defer to Phase 5 | Single browser thread now |
| Blocked definition | Status + content signals / HTTP status only | Status + content signals |
| Marker | details_status column / Text in description | details_status column |
| LinkedIn/Indeed pages | Skip, mark open listing / Fetch like others | Skip |

## Dependencies & polling

| Question | Options | Selected |
|----------|---------|----------|
| HTML parsing | beautifulsoup4 / stdlib html.parser | beautifulsoup4 |
| HTTP | Keep urllib / Add requests | Keep urllib |
| Gmail cadence | Own source + own interval / Same tick as APIs | Own source + interval |
| Browser | Installed Edge/Chrome / playwright install chromium | Installed Edge/Chrome |

## Claude's Discretion

- Sender addresses and selectors, the storage for the Gmail last-poll date, the details worker mechanics, the text thresholds, and whether there is a disconnect endpoint.

## Deferred Ideas

None.
