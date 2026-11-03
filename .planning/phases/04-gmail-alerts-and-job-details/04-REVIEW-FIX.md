---
phase: 04-gmail-alerts-and-job-details
fixed_at: 2026-11-02T00:00:00Z
review_path: .planning/phases/04-gmail-alerts-and-job-details/04-REVIEW.md
iteration: 1
findings_in_scope: 10
fixed: 10
skipped: 0
status: all_fixed
---

# Phase 4: Code Review Fix Report

**Fixed at:** 2026-11-02
**Source review:** .planning/phases/04-gmail-alerts-and-job-details/04-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 10 (CR-01, CR-02, WR-01..WR-08; IN-07's test is included under CR-01)
- Fixed: 10
- Skipped: 0

**Nothing is committed.** The user approves every commit, so all changes are left in the working tree. The commit split per finding is listed under each item.

**Where verification ran:** in the main checkout (no worktree, because nothing is committed). Command used:
`.venv/bin/python api/test_core.py && .venv/bin/python api/test_api.py && .venv/bin/python api/test_watcher.py && .venv/bin/python api/test_gmail.py && .venv/bin/python api/test_details.py`
Result: 77 / 60 / 18 / 47 / 43 passed (baseline 75 / 60 / 18 / 45 / 38). The live-browser test ran against real Chrome and passed, so the new `page.route` guard works with real Playwright. `test_core.py` also passes on Python 3.12. The other suites need Flask, which is not installed for 3.12 on this machine.

**Proof that each new test catches its bug:** each fix was removed on its own in a temporary copy of `api/` (the working tree was not touched), and the matching test was run. Every one of the 16 checks failed with its fix removed, which is the expected result.

## Fixed Issues

### CR-01: The Playwright retry undid the redirect guard

**Files modified:** `api/sources.py`, `api/browser.py`, `api/test_details.py`
**Status:** fixed: requires human verification (the browser's redirect-hop limit is described below)
**Applied fix:**
- New `sources.RedirectRefused`. urllib raises it in these cases:
  - `_SafeRedirect` refuses a hop;
  - urllib refuses a hop itself (a `file://` target or a redirect loop surfaces as a 3xx `HTTPError`);
  - the final URL fails the check.
- `fetch_details` returns `blocked` on `RedirectRefused` and never calls the browser.
- `browser._load_page` sets `page.route("**/*", _guard)`. It aborts any routed request that fails `core.fetchable`: the first URL, frames, subresources and script navigations.
- Playwright routes only the first URL of a server redirect. To cover the hops, a `request` listener records any refused navigation hop, and that page is discarded, returning `(0, "")`. A `ponytail:` comment names this limit: the hop request has already been sent by then, and a filtering proxy is the upgrade.
- Tests:
  - `test_redirect_to_file_blocked` now records `browser.fetch_page` calls and asserts the browser is never called (IN-07). It now expects `RedirectRefused` rather than `(302, "")`.
  - New `test_browser_guard_aborts_refused_requests` uses the Playwright fakes. `FakePage` gained `route`/`on`, `hops` and `subresources`.

### CR-02: `http_url` let loopback and LAN shorthand forms through

**Files modified:** `api/core.py`, `api/test_core.py`
**Applied fix:**
- `http_url` stays DNS-free, because alert parsing calls it and the gmail tests run offline. It now:
  - strips a trailing `.`;
  - rejects any host whose last label is a decimal or `0x` number (the inet_aton shorthands).
- New `core.fetchable(url)`: `http_url`, plus not LinkedIn/Indeed, plus `socket.getaddrinfo` with every resolved address checked by `ipaddress`. It is used before every request: `fetch_details`, each urllib redirect hop, the final URL, the browser route guard and `page.url`.
- `ALLOW_PRIVATE_HOSTS` is kept as the test escape hatch.
- A `ponytail:` comment notes the DNS-rebinding window between the check and the fetch.
- Tests:
  - `test_private_host_shorthands_refused` covers 127.1, 2130706433, 0x7f000001, 017700000001, `localhost.`, 0, 10.1, [::1], [::ffff:127.0.0.1], `127.0.0.1.` and `.`.
  - `test_fetchable_resolves_every_address` uses a faked `getaddrinfo`.

### WR-01: The Gmail last-poll date was saved before the insert

**Files modified:** `api/watcher.py`, `api/test_gmail.py`
**Applied fix:**
- `_sources` now yields `(name, call, stored)`. For Gmail, `stored` writes `gmail_last_poll`, and `run_fetch` calls it only after `db.insert_jobs` succeeds.
- `_fetch_gmail` is replaced by `_gmail_polled`.
- Test: `test_failed_insert_keeps_poll_window`.

### WR-02: 404/410/5xx pages were stored as job descriptions

**Files modified:** `api/sources.py`, `api/test_details.py`
**Applied fix:**
- `judge_page` accepts only 2xx responses.
- `fetch_details` returns `blocked` straight away for 404 and 410, with no browser retry.
- The unused `BLOCKED_STATUSES` is replaced by `GONE_STATUSES`.
- Test: `test_gone_page_never_stored`.

### WR-03: The Totaljobs invite parser dropped titles containing contact/privacy/terms/browser

**Files modified:** `api/alerts.py`, `api/test_gmail.py`
**Applied fix:**
- `_CHROME` now matches whole chrome labels (`fullmatch`): show/view in (the) browser, unsubscribe, privacy policy, terms and conditions, contact us. These are taken from the real sample's links.
- The invite sample test now also parses the email with the title swapped to "Contact Centre Advisor", "Data Privacy Officer", "Terms Manager" and "Browser Engineer".
- Not done: the `_on(...)` host check. It is IN-01, which is out of scope.

### WR-04: Browser timeouts counted queue time, and timed-out tasks were never cancelled

**Files modified:** `api/browser.py`, `api/test_details.py`
**Applied fix:**
- `fetch_page` cancels the Future on `TimeoutError`, so a still-queued task is dropped.
- `launch` gets `timeout=LAUNCH_TIMEOUT_MS` (20 s). Launch, goto and idle now add up to 45 s, which is under the 60 s result timeout.
- Test: `test_timed_out_task_cancelled`. `test_channel_order_and_memo` was updated to expect the new `timeout` argument.

### WR-05: One launch failure turned the browser off until restart

**Files modified:** `api/browser.py`, `api/test_details.py`
**Status:** fixed: requires human verification (it depends on Playwright's error wording)
**Applied fix:**
- `launch_headless` remembers `_unavailable` only when both channels fail with a "not installed" message (`is not found` / `Executable doesn't exist`). Any other launch error raises `BrowserUnavailable` without being remembered.
- `_run` now starts Playwright on demand and tries again after `START_RETRY_SECONDS` (60 s), instead of storing the failure for the life of the thread.
- Test: `test_transient_browser_failure_not_remembered`.

### WR-06: Changing or disconnecting Gmail during a poll lost the new account's 7-day lookback

**Files modified:** `api/watcher.py`, `api/test_gmail.py`
**Status:** fixed: requires human verification (the race fix is check-then-write)
**Applied fix:**
- `_gmail_polled` writes `gmail_last_poll` only if `gmail_address` still equals the polled address.
- A `ponytail:` comment names the remaining very small check-then-write window.
- Not changed: the old account's jobs are still inserted if the person disconnects mid-poll. The review's fix covers only the poll date.
- Test: `test_account_change_during_poll_keeps_lookback`.

### WR-07: `http.client` errors escaped `fetch_details`

**Files modified:** `api/sources.py`, `api/test_details.py`
**Applied fix:**
- `fetch_details` also catches `http.client.HTTPException`, so these errors go to the browser retry.
- `extract_description` also catches `RecursionError` from deeply nested JSON-LD.
- Test: `test_http_client_errors_retry_in_browser`.

### WR-08: LinkedIn and Indeed were blocked only on the first URL

**Files modified:** `api/core.py`, `api/sources.py`, `api/browser.py`, `api/test_details.py`
**Applied fix:**
- New `core.never_fetch(url)`, used by `details_plan` and inside `core.fetchable`.
- That puts the check on every urllib redirect hop, on the final URL, on every routed browser request and on `page.url`.
- Tests: an Indeed redirect target in `test_redirect_to_file_blocked`, and LinkedIn/Indeed requests and hops in `test_browser_guard_aborts_refused_requests`.

## Suggested commit split (files per finding)

Several findings touch the same file, so per-finding commits need `git add -p`. The other option is one commit per file group:
- core.py + test_core.py: CR-02 and WR-08 (`never_fetch`)
- sources.py: CR-01, WR-02, WR-07 and WR-08
- browser.py: CR-01/WR-08 (guard), WR-04 and WR-05
- watcher.py: WR-01 and WR-06
- alerts.py: WR-03
- test_details.py / test_gmail.py: the tests for the matching findings

---

_Fixed: 2026-11-02_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
