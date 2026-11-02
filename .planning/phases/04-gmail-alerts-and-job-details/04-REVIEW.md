---
phase: 04-gmail-alerts-and-job-details
reviewed: 2026-11-02T23:31:50Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - api/alerts.py
  - api/app.py
  - api/browser.py
  - api/core.py
  - api/db.py
  - api/sources.py
  - api/watcher.py
  - api/requirements.txt
  - api/test_details.py
  - api/test_gmail.py
  - api/test_watcher.py
findings:
  critical: 2
  warning: 8
  info: 7
  total: 17
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-11-02T23:31:50Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Narrative Findings (AI reviewer)

## Summary

I reviewed the Phase 4 diff (`1175ad6..HEAD`) in context. That covers the Gmail IMAP source, the six alert parsers, the details worker, the urllib details fetcher and the single Playwright thread.

Some things are handled correctly:
- **App Password:** it goes only to keyring. It is never written to SQLite, never returned by the API and never logged. Login failures return a fixed hint and do not echo the server reply.
- **Read-only IMAP:** the mailbox is opened with `select(readonly=True)` and mail is read with `BODY.PEEK[]`. No STORE, COPY or EXPUNGE is sent.
- **SQLite:** every thread opens its own connection.
- **Python 3.9:** the code runs on 3.9. It uses `IMAP4_SSL(timeout=)`, `date.fromisoformat` and `str.isascii`, which all exist in 3.9.

The serious problems are in the SSRF guard on the details fetcher:
- The per-hop redirect check is undone by the Playwright retry. A redirect that urllib refuses is retried in headless Chrome, which follows it.
- `core.http_url` accepts loopback and LAN hosts written in forms other than plain dotted IPv4. I confirmed this against the system resolver.

Other problems found:
- One case of alert-data loss: the last-poll date is saved before the jobs are inserted.
- 404 or expired pages loaded in the browser are stored as job descriptions.
- The Totaljobs invite parser drops common job titles.
- Browser timeouts pile up, and one launch failure turns the browser off until restart.
- Several smaller issues with error paths and races.

## Critical Issues

### CR-01: The Playwright retry undoes the redirect guard. Refused redirects are opened in headless Chrome

**File:** `api/sources.py:126-131, 225-230`, `api/browser.py:80-97`
**Issue:** `_SafeRedirect` refuses any redirect hop that fails `core.http_url`, such as a LAN or loopback host or a non-http scheme. It does this by raising `HTTPError`, so `get_page` returns `(302, "")`. Two other cases end the same way:
- a final URL that fails the check returns `(0, "")`;
- a fetch error leaves `code, doc = 0, ""`.

In all three cases `judge_page` returns `None`. `fetch_details` then calls `browser.fetch_page(url)` with the **same URL**. Chrome follows the same redirect chain with no per-hop check. It loads the refused target, including subresources and running its JavaScript. `_load_page` checks `page.url` only after `goto` and `wait_for_load_state("networkidle")` have finished, so that check only stops the content being stored. The request has already been made.

So the check added for T-04-10 never stops a request in production. `test_redirect_to_file_blocked` passes only because `fresh()` installs `no_browser`. No test covers a redirect to a private host followed by the browser retry.
**Fix:** Do not retry in the browser when urllib refused the URL or a redirect. Also guard the browser's own navigation and requests:
```python
# sources.py
class RedirectRefused(Exception):
    pass

class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not core.http_url(newurl) or core.never_fetch(newurl):
            raise RedirectRefused(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

# fetch_details
    try:
        code, doc = get_page(url)
    except RedirectRefused:
        return "", "blocked"          # never hand a refused target to the browser

# browser._load_page, before goto
page.route("**/*", lambda route: route.continue_() if core.http_url(route.request.url)
           and not core.never_fetch(route.request.url) else route.abort())
```

### CR-02: `core.http_url` lets loopback and LAN addresses through when they are not written as plain dotted IPv4

**File:** `api/core.py:48-68`
**Issue:** The private-host check only runs when `ipaddress.ip_address(host)` parses the host. Any other string counts as a "public name", but the OS resolver (`inet_aton` rules) still maps many such strings to private addresses. I checked each of these with `socket.gethostbyname` on this machine:

| URL | `http_url` | Resolves to |
| --- | --- | --- |
| `http://127.1/` | True | 127.0.0.1 |
| `http://2130706433/` | True | 127.0.0.1 |
| `http://0x7f000001/` | True | 127.0.0.1 |
| `http://017700000001/` | True | 127.0.0.1 |
| `http://localhost./` | True | 127.0.0.1 |
| `http://0/` | True | 0.0.0.0 |
| `http://10.1/` | True | 10.0.0.1 |

The details fetcher and `_SafeRedirect` rely on this check. Any job page, or a redirect from any public host, can therefore point urllib at the user's router or other local services. The response text is then saved as the job description. The Flask API is still protected by `local_only`, because the Host header would be `127.1`. Everything else on loopback or the LAN is reachable.
**Fix:** Resolve the name and check every address it resolves to. That also covers the DNS-name gap noted in the ponytail comment, and it is a few stdlib lines:
```python
import socket
    if ALLOW_PRIVATE_HOSTS:
        return True
    try:
        infos = socket.getaddrinfo(host.rstrip("."), None)
    except (socket.gaierror, UnicodeError):
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True
```
`canonical_url` and `alert_job` also call `http_url`, and parsing should not touch the network. If that matters, keep a no-DNS version for those calls and use the resolving version only in `get_page`, `_SafeRedirect` and the browser route guard. At the very least, reject any host that is entirely digits, hex or dots, and strip a trailing `.` before the `localhost` comparison.

## Warnings

### WR-01: The Gmail last-poll date is saved before the jobs are inserted, so a failed insert loses alerts

**File:** `api/watcher.py:57-62, 84-85`
**Issue:** `_fetch_gmail` writes `gmail_last_poll = yesterday` (line 61) and then returns the jobs. `run_fetch` calls `db.insert_jobs` afterwards (line 85). If that insert raises, for example `sqlite3.OperationalError: database is locked` while the details worker or a request is writing, the jobs are thrown away but the poll window has already moved forward. Two cases lose mail for good:
- the first poll after connecting (7-day lookback);
- the first poll after the app was off for several days.

Any alert older than yesterday is never searched again. The comment on line 61 says "only after a good poll", but the date is saved before the insert has happened.
**Fix:** Save the date in `run_fetch` after `insert_jobs` succeeds. One way is to have `_fetch_gmail` return a commit callback. A simpler way is to compute the date in `_fetch_gmail` and write it after the insert:
```python
jobs = call(warnings.append)
counts[name] = db.insert_jobs(conn, jobs, db.get_settings(conn))
if name == "gmail":
    db.set_raw(conn, "gmail_last_poll", (date.today() - timedelta(days=1)).isoformat())
```

### WR-02: A 404, 410 or 5xx page loaded in the browser is saved as the job description and re-scored

**File:** `api/sources.py:200-212, 225-231`, `api/browser.py:93`
**Issue:** For an expired listing, urllib gets `HTTPError 404`, so `get_page` returns `(404, "")` and `judge_page` returns `None`. That triggers the browser retry. `_load_page` returns `(404, page.content())` with the full "job no longer available" page. `judge_page` blocks only 403, 429 and 503, so the largest text block on that page is accepted if it has 200 or more characters. That block may be "similar jobs", a cookie banner or footer text. The job is marked `ok`, its description is replaced and it is re-scored using that text. Expired listings are common in alert emails, so this will happen often.
**Fix:** Only accept 2xx responses, and do not retry in the browser for 404 or 410, because a browser will not change a definite "gone":
```python
def judge_page(code, doc):
    if not 200 <= code < 300:
        return None
```
Then in `fetch_details`, return `("", "blocked")` straight away when `code in (404, 410)`.

### WR-03: The Totaljobs invite parser drops jobs whose title contains "contact", "privacy", "terms" or "browser"

**File:** `api/alerts.py:279, 288`
**Issue:** `_CHROME = re.compile(r"browser|unsubscribe|privacy|terms|contact", re.I)` is matched against the job link's text, which is the job title. I swapped "Support Coordinator" in `samples/totaljobs-invite.eml` for each of two other titles:
- "Contact Centre Advisor", one of the most common UK Totaljobs titles: `parse_totaljobs_invite` returns `[]`.
- "Data Privacy Officer": also `[]`.

Each such email logs a "Totaljobs alert parsed 0 jobs — format may have changed" warning, and the job is lost.
**Fix:** Match whole chrome labels instead of substrings, for example `re.compile(r"^(show in the browser|view in browser|unsubscribe|privacy policy|terms and conditions|contact us)$", re.I)`. Also require the job link to be on `web.totaljobsmail.co.uk` or `totaljobs.com` using `_on(...)` (see IN-01).

### WR-04: Browser timeouts include time spent queued, and timed-out tasks are never cancelled

**File:** `api/browser.py:100-102`
**Issue:** `fetch_page` waits up to `RESULT_TIMEOUT_SECONDS = 60` for the result, and that wait includes time spent queued behind earlier tasks. The work itself can take longer than 60 seconds: launch (Playwright default 30 s), `goto` 20 s, `networkidle` 5 s, plus close. When a call times out, the Future is abandoned but not cancelled, so the task still runs later. The details worker sends the next blocked job 5 seconds later. That job's 60-second budget is partly used up by the previous job still running, so it can time out too. On a slow Windows PC this can turn into a run of `blocked` results, and browser launches whose results nobody reads. Phase 5 autofill tasks on the same queue will make this worse. `_run` already checks `set_running_or_notify_cancel()`, but nothing calls `cancel()`.
**Fix:**
```python
def fetch_page(url):
    fut = submit(lambda pw: _load_page(pw, url))
    try:
        return fut.result(timeout=RESULT_TIMEOUT_SECONDS)
    except concurrent.futures.TimeoutError:
        fut.cancel()  # drops it if still queued; a running task finishes and is ignored
        raise
```
Also pass `timeout=` to `pw.chromium.launch` so the worst-case time for one task stays under `RESULT_TIMEOUT_SECONDS`.

### WR-05: One launch failure turns the browser off until the app restarts, and the affected jobs stay blocked

**File:** `api/browser.py:36-40, 66-77`
**Issue:** `launch_headless` sets `_unavailable` after any `Error` from both channels, and that includes temporary errors: a launch timeout, Edge updating in the background, or the antivirus holding the exe. If `_start_playwright()` fails once, `_run` stores `failure` for the life of the thread. In both cases every later browser retry fails at once, and every job that would have needed the browser is saved as `blocked`. That status is final; the ponytail comment at `sources.py:222` names manually resetting it to `pending` as the upgrade. The ponytail comment only explains that installing a browser needs a restart. It does not say that one brief failure has the same effect.
**Fix:** Only remember the failure when the Playwright error says the executable is missing (the message contains "Executable doesn't exist" or "is not found"). For any other launch error, raise `BrowserUnavailable` without storing it. Let `_run` retry `_start_playwright()` on the next task once a backoff has passed, rather than storing `failure` permanently.

### WR-06: Changing or disconnecting the Gmail account during a poll loses the 7-day lookback for the new account

**File:** `api/app.py:164-172, 176-184`, `api/watcher.py:57-62, 71-74`
**Issue:** `gmail_put` and `gmail_delete` do not take `FETCH_LOCK`. Suppose a poll for account A is running when the person connects account B:
1. `gmail_put` clears `gmail_last_poll` (line 171).
2. The poll for A, which still holds the old `address`, finishes and saves `gmail_last_poll = yesterday`.
3. B's first poll searches from yesterday instead of 7 days back, so D-03 is broken for B.

After a DELETE, the running poll also writes `gmail_last_poll` back and inserts A's jobs after the person has disconnected.
**Fix:** In `_fetch_gmail`, write `gmail_last_poll` only if `db.get_raw(conn, "gmail_address") == address` is still true after the poll. Alternatively, store the date per account, for example under the key `gmail_last_poll:<address>`, so a reset for one account cannot be overwritten by a poll of another.

### WR-07: `fetch_details` says it "never raises on network trouble", but `http.client` errors escape

**File:** `api/sources.py:215-223`
**Issue:** `get_page` only catches `HTTPError`, and `fetch_details` only catches `(OSError, ValueError)`. Some network errors are neither:
- `http.client.IncompleteRead` (a truncated body), `BadStatusLine` and `LineTooLong` (oversized headers) all subclass `http.client.HTTPException`, not `OSError`.
- A `RecursionError` from deeply nested JSON-LD in `json.loads` or `_jobpostings` is not caught either.

These errors go up to `_details_step`, which logs a full traceback and marks the job `blocked`. That skips the browser retry that DETAIL-02 requires, and it breaks the docstring's promise.
**Fix:** Catch `http.client.HTTPException` together with `OSError` and `ValueError` in `fetch_details`. Also add `RecursionError` to the `except ValueError` around `json.loads` in `extract_description`.

### WR-08: LinkedIn and Indeed are only blocked on the first URL, not on redirects (D-18 and the project constraint)

**File:** `api/core.py:126-139`, `api/sources.py:126-131`, `api/browser.py:86`
**Issue:** `details_plan` checks `NEVER_FETCH_DOMAINS` against the job's own URL only. A Reed, CV-Library or Totaljobs tracker URL that redirects to `linkedin.com` or `uk.indeed.com` is followed by urllib and then loaded in headless Chrome. Totaljobs invite links are opaque `web.totaljobsmail.co.uk/o-…` trackers, so the app cannot know where they lead. The project rule is "never fetch LinkedIn or Indeed", and that rule has to hold on every hop.
**Fix:** Turn the host test in `details_plan` into `core.never_fetch(url)`. Call it in `_SafeRedirect.redirect_request`, in the browser route guard from CR-01, and on `page.url` / `resp.geturl()`.

## Info

### IN-01: The Totaljobs invite parser's host check is a substring match

**File:** `api/alerts.py:288`
**Issue:** `"totaljobs" in hostname` accepts hosts like `totaljobs.evil.example`. All the other parsers use `_on(host, domain)`.
**Fix:** `_on(h, "totaljobsmail.co.uk") or _on(h, "totaljobs.com")`.

### IN-02: Alert emails that fail FETCH or are too large are skipped without a warning, and the poll window still moves on

**File:** `api/alerts.py:333-336`
**Issue:** If `typ != "OK"`, `raw` is empty or the email is larger than `MAX_EMAIL_BYTES`, the loop moves on without adding to `empty` or calling `warn`. The poll still counts as good, so the email is never read again.
**Fix:** Call `warn("%s alert could not be read" % label)`, or add the label to `empty`, in that branch.

### IN-03: `gmail_login` reports dropped connections as a wrong password and leaves the socket open

**File:** `api/alerts.py:64-71`
**Issue:** `imaplib.IMAP4.abort` is a subclass of `IMAP4.error`. A connection reset during LOGIN therefore returns the App Password hint, and `PUT /api/gmail` answers 400 instead of 502. The `except OSError` branch after `login` raises without calling `client.logout()`, so the socket is left open.
**Fix:** Add `except imaplib.IMAP4.abort` before the `IMAP4.error` branch and treat it as "Could not reach Gmail". Call `logout()` under `contextlib.suppress` in the OSError branch.

### IN-04: An error from `logout()` in `gmail_put` becomes a generic 500 after the login check passed

**File:** `api/app.py:159`
**Issue:** `alerts.gmail_login(...).logout()` can raise `IMAP4.abort` or `OSError` after a successful login. That error falls through to `api_unhandled_error`, so the response is 500 and nothing is stored.
**Fix:** `with contextlib.suppress(Exception): client.logout()`.

### IN-05: The person cannot disconnect Gmail while the credential store is failing

**File:** `api/app.py:176-184`
**Issue:** `forget_password` runs before the database row is cleared. Any `KeyringError` other than `PasswordDeleteError` returns 503 and leaves `gmail_address` in place, so polling carries on.
**Fix:** Clear `gmail_address` and `gmail_last_poll` first. Then call `forget_password` and log any error, rather than failing the request.

### IN-06: The app will not start without Playwright, even though the browser is only a fallback

**File:** `api/browser.py:7`, `api/sources.py:14`
**Issue:** `from playwright.sync_api import ...` runs when the module is imported, via `app → alerts/watcher → sources → browser`. If the Playwright package is missing or broken on the target PC, the whole app fails to start. Under D-15, a missing browser should only mean the job is marked blocked.
**Fix:** Import Playwright inside `_start_playwright` and `launch_headless`, and turn `ImportError` into `BrowserUnavailable`.

### IN-07: A revoked App Password is retried every 5 minutes with no limit

**File:** `api/watcher.py:125-126`, `api/alerts.py:69`
**Issue:** A `GmailAuthError` counts as a normal error, so the Gmail tick logs in again every `RETRY_SECONDS`. Google may rate-limit or flag an account that keeps failing IMAP logins. The test suite also never checks the refused-redirect path with a browser present (see CR-01), because `fresh()` installs `no_browser`.
**Fix:** After a `GmailAuthError`, stop polling Gmail until the person reconnects through `PUT /api/gmail`. Add a test that checks a refused redirect is not passed to `browser.fetch_page`.

---

_Reviewed: 2026-11-02T23:31:50Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
