# Phase 4: Gmail Alerts and Job Details - Research

**Researched:** 2026-10-25
**Domain:** stdlib IMAP + email parsing, `keyring` credential storage, bs4 alert parsers, JSON-LD page extraction, single-thread Playwright worker, SQLite column migration, watcher wiring
**Confidence:** HIGH for mechanics (all probed this session on the project's Python 3.9.6), MEDIUM for Gmail account behaviour, LOW for alert sender addresses and per-site HTML (cannot be known until the user supplies samples)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Credentials are entered through the API. `PUT /api/gmail` with `{address, app_password}` stores them in `keyring`. `GET /api/gmail` returns only `{address, connected}`. The app password never goes into SQLite or any response. Gmail IMAP needs a Google App Password, and the error text should say so. Disconnecting (e.g. `DELETE /api/gmail`) is at Claude's discretion. (Reversibility: costly, Phase 6 Settings page builds on this endpoint shape.)
- **D-02:** Each poll searches IMAP `FROM` each known alert sender, `SINCE` a stored last-poll date. The mailbox is opened read-only, so the person's mail is never marked read. Dedupe by job URL handles the overlap between polls.
- **D-03:** The first poll looks back 7 days.
- **D-04:** Alert jobs are **not** filtered by career field. The person already chose what the alerts send. Scoring (including excluded words) ranks them.
- **D-05:** Gmail is its own source, `gmail`, in the watcher status and in `POST /api/fetch` counts. It is polled every `gmail_poll_minutes` (already a setting, default 5), separately from the 60-minute API tick. When Gmail isn't connected it is skipped quietly (Phase 2 D-09).
- **D-06:** Each of LinkedIn, Indeed, CV-Library and Totaljobs gets its own parser function. Each is tested against a **real** alert email that the user exports. The plan must include a checkpoint where the user supplies one sample per site (`.eml` or HTML from Gmail's "Show original") before or while the parsers are built.
- **D-07:** The samples are redacted by hand (names, email addresses, tracking tokens) and committed under `api/samples/`, so the tests run anywhere.
- **D-08:** If an email from a known sender parses to 0 jobs, that is recorded in the `gmail` source's `last_error` (e.g. "LinkedIn alert parsed 0 jobs — format may have changed"). The other emails are still processed.
- **D-09:** Totaljobs uses the email parser only. No RSS path.
- **D-10:** HTML parsing uses `beautifulsoup4` (a new pinned dep in `api/requirements.txt`). HTTP stays on stdlib `urllib`, with no `requests`. `keyring` is a new dep.
- **D-11:** `fetch_details` runs in the background after insert, for new jobs, one fetch every 5 seconds. The gap is a fixed constant, not a setting. The descriptions are ready by the time the person opens a job.
- **D-12:** Only jobs with an empty or short description are fetched: Gmail alert jobs, and any job whose description is under ~500 characters. Reed and Remotive full text is kept as it is. Jobs whose title hits an excluded word are skipped.
- **D-13:** When the full description arrives it is stored, and score, pros, cons and summary are recomputed **only if the job is still `new`**. Queued and dismissed jobs keep their score (same rule as Phase 1 D-08 and Phase 3 D-09).
- **D-14:** The **single Playwright browser thread fed by `queue.Queue`** is introduced now. It is the same thread Phase 5 autofill will extend. For details it loads the page headless, reads JSON-LD or the text, and closes the page. (Reversibility: costly, Phase 5 builds autofill on this thread and queue.)
- **D-15:** The browser is the installed Edge or Chrome (`channel="msedge"` / `"chrome"`), so no Playwright browser download is needed. If neither is available, the job is marked blocked.
- **D-16:** A page counts as "blocked" on HTTP 403/429/503, or when the page text shows a CAPTCHA or human-check signal (captcha, "verify you are human", Cloudflare challenge), or when the extracted text is under ~200 characters. The app never interacts with a CAPTCHA.
- **D-17:** A new `details_status` column on `jobs` takes the values `pending` / `ok` / `blocked` / `skipped`, and `GET /api/jobs` returns it. `blocked` means "Open listing to read full description". (Reversibility: one-way, adds a column to the live SQLite `jobs` table on existing user DBs. Phase 1 says there are no migrations, so this needs an idempotent `ALTER TABLE ... ADD COLUMN` guarded on `init_db`.)
- **D-18:** LinkedIn and Indeed job pages are **never fetched**. They are marked `skipped` / open-listing, and the alert snippet is kept. This follows the project rule against automating LinkedIn and Indeed.

### Claude's Discretion
- The exact alert sender addresses and per-site HTML selectors (from the real samples).
- Where the last-poll date for Gmail is stored (settings key vs in-memory plus the 7-day fallback).
- The details worker mechanics: a separate thread or part of the watcher loop, and how it hands blocked jobs to the Playwright thread.
- How the JSON-LD `description` HTML is turned into text (reuse `core._text_lines`).
- The exact short-description threshold and blocked-text threshold (about 500 and 200 characters).

### Deferred Ideas (OUT OF SCOPE)
None. The discussion stayed within the phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GMAIL-01 | `fetch_gmail_alerts` reads job-alert emails over IMAP using credentials from `keyring` | Pattern 1 (IMAP read-only), Pattern 2 (keyring), `/api/gmail` design, watcher Gmail tick (Pattern 6) |
| GMAIL-02 | Separate parsers for LinkedIn, Indeed, CV-Library, Totaljobs, each tested against a saved sample | Pattern 3 (parser registry + sample-gated plan), URL canonicalisation pitfall, Validation Architecture |
| DETAIL-01 | `fetch_details` reads JSON-LD `JobPosting`, else largest text block | Pattern 4 (verified extraction prototype), Pattern 5 (worker + `details_status`) |
| DETAIL-02 | Blocked page: retry once in Playwright, then "open listing to read"; never CAPTCHA | Pattern 7 (Playwright thread), blocked-detection rules, Security Domain |
</phase_requirements>

## Summary

Everything this phase needs exists in stdlib (`imaplib`, `email`, `urllib`, `queue`, `concurrent.futures.Future`, `sqlite3`) plus three pinned packages the user already chose: `beautifulsoup4`, `keyring`, `playwright`. All three install and work on the project's Python 3.9.6 venv; the only version trap is Playwright: releases from 1.61 (2026-06-29) require Python >=3.10, so the single shared pin must be `playwright>=1.49,<1.61` (resolved to 1.60.0 here). I prototyped every mechanism (read-only IMAP flow semantics from stdlib source, keyring round-trip and no-backend error, JSON-LD and largest-block extraction, blocked detection against a local HTTP server, a queue-fed Playwright thread driving real Chrome headless) so the planner can prescribe code, not hope.

The biggest structural insight is that **only the four parsers depend on the user's samples**. IMAP I/O, keyring, `/api/gmail`, the `details_status` migration, the details worker, `fetch_details`, the Playwright thread and the watcher Gmail cadence can all be built and tested now with a fake IMAP class and a synthetic email, so the sample checkpoint should sit in front of only the parser plan. The second insight is that the details pipeline gets much smaller if `details_status` defaults to `pending` for **every** row (new and legacy) and the worker is the single place that decides skipped/ok/fetch: `insert_jobs` then needs no change at all.

Two things in the existing code will bite if missed: (1) `db.rescore_new` re-scores from the stored `summary` and never recomputes it, and `core.summarize` on a DB row loses the source-provided `remote`/`job_type` hints, so D-13's re-score needs a purpose-built `save_details` that recomputes the summary and keeps old hints; (2) `watcher._tick` returns early with no career fields and `/api/fetch` 400s without career fields, but D-04 says Gmail is not tied to career fields, so Gmail needs its own tick and must not sit behind that gate.

**Primary recommendation:** Build in this order: (a) deps + `details_status` migration + `browser.py` thread + `extract_description`/`fetch_details` + details worker; (b) keyring + `/api/gmail` + IMAP fetch with a fake IMAP in tests + watcher `_tick_gmail`; (c) user-sample checkpoint, then the four parsers last, each test-first against its committed sample.

## Project Constraints (from ./.claude/CLAUDE.md)

- Flask + stdlib `sqlite3`, one Python process; stdlib before deps, no unrequested abstractions, shortest working diff; mark deliberate shortcuts with `# ponytail:` comments.
- Code must run on Python 3.9 (dev) and 3.12 (target): typing stays 3.9-compatible (existing code uses `# type:` comments and `typing.List/Optional`, no `X | Y`).
- Compliance: respect site terms, no CAPTCHA bypass, no auto-submit; never automate LinkedIn/Indeed.
- Flask `/api/` routes return `{"error": "message"}` with 4xx/5xx, never 200 with an error key; routes stay thin.
- Playwright sync API on **one** thread fed by `queue.Queue`.
- Tests are plain-assert scripts using a temp DB through `JOBHELPER_DB`.
- GSD workflow: edits happen through GSD commands. Memory note: ask the user before any git commit (including subagent commits).
- Windows target: no Node required, UI is pre-built; `Start.bat` installs from `api/requirements.txt`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Gmail credentials (store/clear/status) | API / Backend (`app.py` + `keyring`) | Database (address only, not secret) | Secret lives in OS credential store; UI only calls `/api/gmail` |
| IMAP read + alert-email parsing | API / Backend (watcher thread) | none | Pure parsing in a module, I/O in `sources.py` |
| Alert dedupe, scoring | Database / Storage (`insert_jobs`, UNIQUE url) | API / Backend (`core.score`) | Existing path, reused unchanged |
| Full-description fetch (HTTP) | API / Backend (details worker thread) | none | stdlib urllib, background, throttled |
| JS-rendered / blocked retry | Browser thread (Playwright, `browser.py`) | none | Sync API is not thread-safe: single dedicated thread |
| `details_status` state | Database / Storage | API / Backend | Persisted so pending work survives restarts |
| "Open listing to read" presentation | Browser / Client (Phase 6) | API exposes `details_status` | Phase 4 only exposes the field |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `imaplib`, `email`, `ssl` | stdlib | Read-only IMAP over TLS, MIME parsing | D-02, D-10 stdlib first |
| `urllib.request` | stdlib | Page fetch for details | D-10: no `requests` |
| `beautifulsoup4` | 4.15.0 (pin `>=4.13,<5`) | Alert HTML parsers, JSON-LD `<script>` lookup, largest block | D-10. Installed on py3.9.6 in this session; `requires_python >=3.7` [VERIFIED: pypi.org/pypi/beautifulsoup4/json + local pip install] |
| `keyring` | 25.7.0 (pin `>=25.6,<26`) | App password in macOS Keychain / Windows Credential Manager | D-01. `requires_python >=3.9` (25.6.0+), uploaded 2025-11-16 [VERIFIED: pypi.org/pypi/keyring/json + local pip install]. On Windows it pulls `pywin32-ctypes>=0.2.0` automatically [VERIFIED: installed METADATA `Requires-Dist: pywin32-ctypes>=0.2.0; sys_platform == "win32"`] |
| `playwright` | 1.60.0 (pin `>=1.49,<1.61`) | Retry for blocked/JS pages; Phase 5 autofill thread | D-14/D-15. **1.61.0 onward requires Python >=3.10** [VERIFIED: pypi.org release metadata: 1.49.0 `>=3.9`, 1.61.0 `>=3.10`]; 1.60.0 installed and ran against real Chrome 156 on py3.9.6. Wheels are `py3-none-win_amd64` etc. (Python-version independent), deps `pyee<14,>=13`, `greenlet>=3.1.1` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `concurrent.futures.Future` | stdlib | Hand a result from the browser thread back to the caller | Instead of inventing a result-queue protocol |
| `http.server` | stdlib | Local fixture server in tests (403 page, JSON-LD page) | `test_details.py` |
| `soupsieve` | auto (2.8.4 on py3.9) | bs4 transitive | Do not pin; pip resolves per interpreter (3.0.x needs py>=3.11.5) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `html.parser` bs4 backend | `lxml` | lxml is already installed as a python-docx dependency but adds nothing needed; `html.parser` is deterministic and stdlib |
| Gmail OAuth | App Password | OAuth needs a Google Cloud client + consent flow: out of scope; D-01 locks App Password |
| `X-GM-RAW` Gmail search | `FROM`/`SINCE` | D-02 locks standard IMAP criteria; also portable |
| New abstraction layers | none | Ponytail |

**Installation (add to `api/requirements.txt`, matching its `>=,<` style):**
```
beautifulsoup4>=4.13,<5
keyring>=25.6,<26
playwright>=1.49,<1.61
```
Do **not** run `playwright install`: D-15 uses the installed Edge/Chrome via `channel=`. Note for the future: the `<1.61` cap is only forced by the Python 3.9 dev interpreter; lift it when dev moves to >=3.10.

**Version verification:** versions and `requires_python` read from the PyPI JSON API on 2026-10-25 and confirmed by `pip install` into a throwaway venv built from the project `.venv` (Python 3.9.6): `keyring 25.7.0, beautifulsoup4 4.15.0, soupsieve 2.8.4, playwright 1.60.0, greenlet 3.2.5, pyee 13.0.1`.

## Package Legitimacy Audit

Seam result: `gsd-tools query package-legitimacy check --ecosystem pypi keyring beautifulsoup4 playwright` returned **SUS** for all three. The reasons are `unknown-downloads` (the PyPI API exposes no download counts, so every PyPI package gets this flag) and, for `playwright`, `too-new` + `no-repository` because the check looks at the latest release (1.64.1, published 2026-10-22), not the 1.60.x line we pin. All three are named by the user in CONTEXT.md D-10/D-14, in `PLAN.md`, and in this project's CLAUDE.md, and are the canonical, long-established packages (`jaraco/keyring`, Crummy's bs4, `microsoft/playwright-python`). The flag is a data limitation, not a slopsquat signal, but the seam rule is applied literally.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| keyring | PyPI | many yrs (10.5.0 in 2017) | unknown (PyPI gives none) | github.com/jaraco/keyring | SUS | `keyring` [WARNING: flagged as suspicious by seam — verify before using.] Planner adds one `checkpoint:human-verify` before the first `pip install` |
| beautifulsoup4 | PyPI | many yrs (4.10.0 in 2021) | unknown | crummy.com/software/BeautifulSoup | SUS | `beautifulsoup4` [WARNING: flagged as suspicious by seam — verify before using.] Same checkpoint |
| playwright | PyPI | many yrs (1.9.0 in 2021); pin 1.60.0 is from 2026-05-18 | unknown | github.com/microsoft/playwright-python (project_urls homepage) | SUS | `playwright` [WARNING: flagged as suspicious by seam — verify before using.] Same checkpoint; the `too-new` signal applies to 1.64.1, which we do not install |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** keyring, beautifulsoup4, playwright (planner inserts a single `checkpoint:human-verify` covering the three-line `requirements.txt` change before install). Postinstall scripts: not applicable on PyPI wheels.

## Architecture Patterns

### System Architecture Diagram

```
                 PUT/GET/DELETE /api/gmail
 Browser/UI ───────────────┐
                           v
                 ┌───────────────────┐   address (not secret)   ┌──────────────────┐
                 │ app.py (thin)     │ ───────────────────────> │ SQLite settings  │
                 │ test login first  │                          │ row gmail_address│
                 └─────────┬─────────┘                          │ row gmail_last_poll
                           │ password                           └────────┬─────────┘
                           v                                             │
                  ┌─────────────────┐                                    │
                  │ keyring (OS     │                                    │
                  │ credential store)│                                    │
                  └────────┬────────┘                                    │
                           │ password                                    │
 watcher thread            v                                             v
 _loop ── _tick (API 60m, needs career_fields)         ┌──────────────────────────────┐
      └── _tick_gmail (gmail_poll_minutes, no fields) ─>│ fetch_gmail_alerts           │
                                                        │ IMAP4_SSL(ctx,timeout)       │
 Gmail imap.gmail.com:993 <────────────────────────────│ EXAMINE INBOX (readonly)     │
   UID SEARCH FROM <sender> SINCE <date>                │ UID FETCH BODY.PEEK[]        │
                                                        │ email.parse -> pick parser   │
                                                        │ by sender -> jobs[] / warn   │
                                                        └──────────────┬───────────────┘
                                                                       v
                                       db.insert_jobs (INSERT OR IGNORE by url, score)
                                           jobs.details_status DEFAULT 'pending'
                                                                       │
 details worker thread ◄── DETAILS_WAKE / 30s poll ────────────────────┘
   SELECT next pending ─> classify (no network):
        linkedin/indeed source ─────────> 'skipped'
        title hits excluded word ───────> 'skipped'
        description >= 500 chars ───────> 'ok'
        else fetch_details(url):
              urllib GET ─ ok & >=200 chars ───────────────────> save, 'ok'
                  │ 403/429/503, captcha text, <200 chars, error
                  v
              browser.submit(task).result(timeout)  ──> Playwright thread (queue.Queue)
                  │ still blocked / browser missing        headless Edge/Chrome, goto,
                  v                                        read content, close
              'blocked' = "Open listing to read"           (never interacts)
   sleep 5 s after every real network fetch
```

### Recommended Project Structure
```
api/
├── alerts.py        # NEW: SENDERS table, 4 pure parsers (html -> jobs), parse_email(); needs bs4
├── browser.py       # NEW: Playwright thread + queue + submit(); Phase 5 extends
├── sources.py       # + gmail_login(), fetch_gmail_alerts(), extract_description(), fetch_details()
├── watcher.py       # + _tick_gmail, gmail in _sources/run_fetch, details worker thread
├── db.py            # + guarded ALTER in init_db, gmail raw-settings helpers, next_pending/save_details
├── app.py           # + /api/gmail routes
├── samples/         # NEW: redacted .eml per site (committed, D-07)
├── test_gmail.py    # NEW
├── test_details.py  # NEW
└── test_watcher.py  # extend: gmail cadence + status
```
`core.py` is touched only if `needs_details`/blocked-text helpers are placed there (pure functions; fine either place).

### Pattern 1: Read-only IMAP with search by sender and date
**What:** `imaplib.IMAP4_SSL` with a verifying context and a timeout; `select(..., readonly=True)` sends `EXAMINE` (confirmed from stdlib source: `if readonly: name = 'EXAMINE'`); `UID SEARCH`; `UID FETCH ... (BODY.PEEK[])`.
**Facts:**
- `timeout=` exists since Python 3.9 [CITED: docs.python.org/3/library/imaplib.html]. On 3.12 `keyfile`/`certfile` are gone, so pass only keyword `ssl_context=` and `timeout=`.
- The default context does **not** verify the certificate/hostname [CITED: docs.python.org imaplib]: always pass `ssl.create_default_context()` (uses the Windows cert store).
- IMAP is always on for Gmail since Jan 2025: "IMAP access is always turned on in Gmail" [CITED: support.google.com/mail/answer/7126229]. Do not tell the person to "enable IMAP".
- `SINCE` takes `DD-Mon-YYYY` with English month names. **Do not use `strftime("%b")`**: it is locale-dependent (a non-English Windows locale yields an invalid date and a `BAD`). Use a fixed month tuple.
- `SINCE` is date-granular (no time), so each 5-minute poll re-reads all of today's matching mail. Dedupe by URL absorbs the overlap (D-02). Ceiling: re-download of a day's alerts every poll; mitigation if it ever matters is an in-memory set of seen `(UIDVALIDITY, uid)`.
- `FROM` is a **substring** match on the header, so a domain works as well as a full address.
- Failed login: `imaplib` raises `imaplib.IMAP4.error` whose `args[0]` is **bytes** (e.g. `b'[AUTHENTICATIONFAILED] Invalid credentials (Failure)'`), so `str(e)` gives `"b'[AUTH...'"`. Decode it before showing it [VERIFIED: stdlib source `raise self.error(dat[-1])` + local probe of `str()`]. The Gmail wording for a normal password is "Application-specific password required" [CITED: web search summary of Google/forum reports; MEDIUM]. Map any `IMAP4.error` at login to the fixed D-01 hint text, not the raw server text.
- Non-ASCII in a password makes `login()` raise `UnicodeEncodeError` (imaplib encodes ASCII). Validate in `PUT /api/gmail`: strip spaces (Google shows the 16-char app password in 4 groups), require ASCII.
- `fetch` response is `[(b'1 (UID 5 BODY[] {n}', raw_bytes), b')']`; docs warn about unsolicited extras, so take the first `tuple` element [CITED: docs.python.org imaplib].

**Example (shape; the real code is the planner's):**
```python
# Source: docs.python.org/3/library/imaplib.html; stdlib source checked locally
import email, email.policy, imaplib, ssl
_MONTHS = ("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec")

def _imap_date(d):  # not strftime: %b is locale-dependent on Windows
    return "%02d-%s-%d" % (d.day, _MONTHS[d.month - 1], d.year)

def gmail_login(address, password, factory=imaplib.IMAP4_SSL):
    imap = factory("imap.gmail.com", ssl_context=ssl.create_default_context(), timeout=30)
    try:
        imap.login(address, password)
    except imaplib.IMAP4.error:   # args[0] is bytes; never echo it, use the fixed hint
        raise SourceError("Gmail rejected the login. Use a Google App Password ...")
    return imap

# per sender:
imap.select("INBOX", readonly=True)                       # EXAMINE
typ, data = imap.uid("SEARCH", None, "FROM", '"%s"' % sender, "SINCE", _imap_date(since))
for uid in data[0].split():
    typ, parts = imap.uid("FETCH", uid, "(BODY.PEEK[])")
    raw = next(p[1] for p in parts if isinstance(p, tuple))
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    html_part = msg.get_body(preferencelist=("html",))    # None if no HTML part
    body = html_part.get_content() if html_part else ""
```
(Always `imap.logout()` in a `finally`; the stub above only illustrates login mapping.)

**Mailbox choice:** use `INBOX`. `[Gmail]/All Mail` is locale-named and would surface archived mail; if the person has a Gmail filter that skips the inbox for alerts, they will not appear: document in the Settings text, do not engineer around it [ASSUMED: alerts stay in INBOX].

### Pattern 2: `keyring` storage, with the address kept outside the secret store
**What:** `keyring.set_password("JobHelper", address, app_password)`. `keyring` cannot enumerate usernames for a service, so `GET /api/gmail` needs the address from SQLite: store it as a raw row in `settings` under key `gmail_address`. This follows the precedent in `db.py` where the profile is a raw `settings` row (`INSERT OR REPLACE INTO settings (key, value) VALUES ('profile', ?)`). Keys that are not in `DEFAULTS` are not returned by `get_settings` and are rejected by `PUT /api/settings` ("Unknown setting"), so neither the address nor `gmail_last_poll` can leak through or be overwritten via the settings API.
**Verified behaviours (local probe, keyring 25.7.0 on macOS Keychain):**
- round trip works; `get_password` of a missing entry returns `None`; `delete_password` of a missing entry raises `keyring.errors.PasswordDeleteError` (so `DELETE /api/gmail` must catch it and stay idempotent).
- No usable backend raises `keyring.errors.NoKeyringError`, a subclass of `keyring.errors.KeyringError` (and `RuntimeError`), with text "No recommended backend was available...". Catch `KeyringError` once in the Gmail helpers and return 503 `{"error": "Could not use the system credential store: ..."}`.
- Windows uses Credential Manager via `pywin32-ctypes`, installed automatically by pip [VERIFIED: METADATA]. Runtime on Windows is untested here [ASSUMED].
- `connected` should be: `gmail_address` row exists **and** `keyring.get_password(...)` is not `None`. When there is no address row, **do not call keyring at all**: this keeps every existing test and every non-Gmail user away from the OS keychain (and from macOS keychain prompts).
**Recommended endpoint behaviour (D-01 + discretion):** `PUT` validates body keys exactly `{address, app_password}` (400 otherwise), strips spaces from the password, requires ASCII and an `@`, then **tests the login** (`gmail_login`) before storing: auth failure -> 400 with the App Password hint, network failure -> 502, success -> store + wake the Gmail tick, return `{address, connected: true}`. `DELETE` -> remove keyring entry (swallow `PasswordDeleteError`), delete the two raw settings rows, return `{address: "", connected: false}`. Never include the password in a log, an exception message, or a response.

### Pattern 3: Parser registry, gated by the user's samples
**What:** `alerts.py` holds a `SENDERS` table (site -> list of sender substrings) and one pure function per site `parse_<site>(html: str) -> List[dict]`; `parse_email(msg) -> (site, jobs)` picks the parser by the `From` address. Parsers return the exact job dict that `fetch_reed` returns. Verified shape [VERIFIED: api/sources.py:91-101]:
```
found.setdefault(item["jobUrl"], {
    "url": item["jobUrl"],
    "source": "reed",
    "title": item.get("jobTitle") or "",
    "company": (item.get("employerName") or "").strip(),
    "location": item.get("locationName") or "",
    "salary": _salary_text(item.get("minimumSalary"), item.get("maximumSalary")),
    "description": item.get("jobDescription") or "",
    "job_type": None,
    "remote": None,
})
```
Set `source` to the site name (`"linkedin"`, `"indeed"`, `"cv-library"`, `"totaljobs"`) per CONTEXT code_context. Two namespaces coexist: the **watcher/fetch source** is `gmail` (status, `by_source` counts from `/api/fetch`); the **job's `source` column** is the site (so `/api/stats` `by_source` breaks down by site). `description` = alert snippet text (may be empty); use bs4 `get_text` then `core._text_lines`-style cleanup, store plain text, never HTML.
**Sender addresses are `[ASSUMED]`.** Starting guesses to be corrected from the samples: LinkedIn `jobalerts-noreply@linkedin.com`; Indeed domains `indeed.com` / `indeedemail.com` / `indeedmail.com` [CITED: Indeed Help Center "How to verify emails from Indeed" says its mail always comes from @indeed.com, @indeedemail.com or @indeedmail.com]; CV-Library and Totaljobs: nothing authoritative found, read the actual `From` header off each sample. Because `FROM` is a substring match, searching on the domain is fine, but see the pitfall about non-alert mail from the same domain.
**URL canonicalisation is mandatory per parser:** alert links carry per-email tracking parameters; if they are stored raw, `UNIQUE(url)` dedupe never matches across emails and the same job floods the feed. Reduce each link to a stable form (e.g. LinkedIn `https://www.linkedin.com/jobs/view/<id>`, Indeed `https://<host>/viewjob?jk=<jk>`; the exact forms come from the samples). If a site wraps links in a click-tracker redirect that hides the job ID, that is a design problem to raise at the checkpoint: the app must not follow the redirect (that would hit the site, and LinkedIn/Indeed are never fetched, D-18) [ASSUMED: alert hrefs are direct enough to canonicalise].
**Plan shape:** the checkpoint (`checkpoint:human-action`: user exports one `.eml` per site via Gmail "Download message", or "Show original" then "Download Original", and redacts names, emails, tracking tokens, IP/`Received` headers) comes immediately before the parser tasks only. Everything else in the phase is independent of it. Each parser task is test-first against its committed sample.

### Pattern 4: JSON-LD extraction then largest-block fallback (prototype verified)
Verified against a synthetic page in the project's Python 3.9 + bs4 4.15.0:
- Use `soup.find_all("script", type="application/ld+json")`; parse with `json.loads(text, strict=False)` (plain `json.loads` raises "Invalid control character" on the raw newlines that real JSON-LD often contains) and skip blocks that fail to parse.
- Walk the structure: top level may be a dict, a list, or a dict with `@graph` (and sometimes `mainEntity`). `@type` may be a string or a list (`["JobPosting"]`).
- `description` is usually **entity-escaped HTML** (`&lt;p&gt;...`). Order matters: `html.unescape(desc)` first (to expose the tags), **then** `core._text_lines` (which strips tags and unescapes the remaining text entities). `_text_lines` alone would leave literal `<p>` text in place.
- Largest-block fallback: remove `script, style, noscript, nav, header, footer, aside, form, svg`; then for each `div/section/article/main/ul/body` score the text that is **directly** in its `p`/`li` children plus its own text nodes (non-recursive), and take the best. Choosing the container with the largest *recursive* text always returns `<body>`. The prototype picked the right container (540 chars) over a short sibling and over a nav block.
```python
# Source: prototype verified in this session (bs4 4.15.0, Python 3.9.6)
def _jobposting_descriptions(data):
    if isinstance(data, list):
        for x in data: yield from _jobposting_descriptions(x)
    elif isinstance(data, dict):
        t = data.get("@type")
        if "JobPosting" in (t if isinstance(t, list) else [t]) and data.get("description"):
            yield data["description"]
        for k in ("@graph", "mainEntity"):
            if k in data: yield from _jobposting_descriptions(data[k])

def extract_description(doc):   # -> (text, found_jsonld)
    soup = BeautifulSoup(doc, "html.parser")
    for s in soup.find_all("script", type="application/ld+json"):
        try: data = json.loads(s.string or s.get_text(), strict=False)
        except ValueError: continue
        for raw in _jobposting_descriptions(data):
            return "\n".join(core._text_lines(html.unescape(raw))), True
    ...  # largest block, returns (text, False)
```
**Blocked rule (D-16), refined:** status in `{403, 429, 503}`, or extracted text `< 200` chars, or a challenge phrase in the **visible text** (`title` + body text, not raw HTML). Challenge phrases: `captcha`, `verify you are human`, `are you a robot`, `just a moment`, `checking your browser`, `unusual traffic`, `access denied`. Apply the phrase check only when **no JSON-LD description was found**: a real posting page often mentions reCAPTCHA in a script or footer and must not be marked blocked (raw-HTML grep would false-positive on it).
**Fetch details (urllib):** `HTTPError` (403/429/503) is an `OSError` subclass and carries `.code` [VERIFIED: local probe: `isinstance(HTTPError, OSError)` is True]; read at most ~2 MB; decode with `resp.headers.get_content_charset() or "utf-8"` and `errors="replace"`; do **not** send `Accept-Encoding` (urllib does not gunzip). Use the existing `USER_AGENT` constant: it is honest, so more sites 403 and fall to the Playwright retry, which is acceptable and consistent with the compliance posture. Treat timeouts/connection errors like a blocked attempt (they go to the Playwright retry, then `blocked`).

### Pattern 5: `details_status` column and the details worker
**Migration (D-17).** SQLite 3.51.0 here; `ALTER TABLE ADD COLUMN ... NOT NULL DEFAULT '<const>'` back-fills existing rows and a second run raises `OperationalError: duplicate column name: details_status` [VERIFIED: local probe]. Guard with `PRAGMA table_info(jobs)` rather than catching the error text:
```python
# in init_db(), after executescript(SCHEMA):
cols = [r[1] for r in conn.execute("PRAGMA table_info(jobs)")]
if "details_status" not in cols:
    conn.execute("ALTER TABLE jobs ADD COLUMN details_status TEXT NOT NULL DEFAULT 'pending'")
```
Keep this as the only definition of the column (leave `SCHEMA` alone) so the one code path runs on fresh and legacy DBs and is therefore always tested; test it with a hand-built legacy `jobs` table (old schema, a few rows), `init_db()` twice, assert the column exists once and legacy rows are `pending`.
**Why `pending` is the right default for every row.** The worker classifies each pending row with **no network** where it can: source `linkedin`/`indeed` -> `skipped` (D-18); title hits an excluded word -> `skipped` (D-12); description >= 500 chars after `_text_lines` -> `ok` (Remotive full text kept); else fetch. Consequences: `insert_jobs` stays unchanged, legacy Reed rows (short previews, see Phase 2 research: "`jobDescription` in the search response is a short preview") get their full text on the first run, and there is one decision point. Do not sleep the 5 s gap after a no-network classification, only after a real fetch.
**`GET /api/jobs` needs no code change:** `job_dict(row)` does `d = dict(row)` over `SELECT *`, so the new column is returned automatically [VERIFIED: db.py:118-122, `d = dict(row)`; `list_jobs` uses `SELECT * FROM jobs`].
**Worker mechanics (Claude's discretion, recommended):** a second daemon thread started next to the watcher thread (not inside the 30 s watcher tick, which cannot honour a 5 s cadence). Loop: own `db.connect()` per iteration, `SELECT * FROM jobs WHERE details_status = 'pending' ORDER BY score DESC, id DESC LIMIT 1`; none -> `DETAILS_WAKE.wait(30)`; set `DETAILS_WAKE` after a successful `insert_jobs` that added rows. `DETAILS_GAP_SECONDS = 5` is a module constant (D-11), tests set it to 0. State lives in the DB so a restart resumes. Any unexpected exception for a job marks that job `blocked` (log it) so the loop can never spin on one bad row.
**Saving the result (D-13) needs a dedicated `db.save_details(conn, job_id, text, status)`:**
- always write `details_status`; replace `description` only if the new text is longer than the old (an extraction that is shorter than the alert snippet must not erase it);
- only if the row's `status` is `new`, recompute `summary`, `score`, `pros`, `cons`. Do **not** call `rescore_new`: it iterates all `new` rows and reuses the **stored** summary (`core.score(job_dict(row), ...)` reads `job.get("summary")`), so the summary would never reflect the new text;
- when recomputing the summary from a DB row, keep the old `remote` and `job_type` if the new value is `None`: `summarize` reads them from the job dict (`job.get("job_type") or _first_label(...)`), and the source-provided hints (e.g. Remotive `"remote": "Remote"`, `job_type`) are not stored as columns, so a naive re-summary silently loses "Fully remote" +10 points. Pass the row's `salary`, `title`, `location`, `description` and merge `old_summary["remote"]`/`["job_type"]` into the new summary before scoring.
- use `with conn:`; score through `core.score(dict(job, summary=summary), settings, profile)` exactly as `insert_jobs` does. Read fresh settings/profile at save time (settings can change during a slow fetch, same lesson as Phase 2).

### Pattern 6: Watcher integration
Read the current structure [VERIFIED: watcher.py:26-31, 33-57, 60-94]. Required changes:
- `_sources(settings)` currently yields only reed/remotive from settings. Gmail needs the connection (address row) and keyring, so extend `run_fetch(conn, settings, ...)` with a way to select sources (e.g. a `names` filter) and yield `"gmail"` only when connected. When not connected nothing is yielded, so the existing exact-equality assertions (`by_source == {"reed": 0, "remotive": 0}`) in `test_watcher.py` keep passing and keyring is never touched.
- The API tick must **not** run Gmail (different cadence); the manual `POST /api/fetch` runs everything (D-05) and so counts `gmail`.
- Add `_tick_gmail(last)` modelled on `_tick`: due when `last is None or GMAIL_WAKE.is_set() or elapsed >= settings["gmail_poll_minutes"] * SECONDS_PER_MINUTE`; if not connected return `last` quietly; acquire `FETCH_LOCK` non-blocking and return `None` (stay due) when busy; on errors return an early-retry time like `_tick`. **Do not** put it behind the `if not settings["career_fields"]: return last` gate (D-04, Gmail is independent of fields). Call both ticks from `_loop`, each wrapped so one failing cannot stop the other. A separate `GMAIL_WAKE` event (set by `PUT /api/gmail`) avoids triggering an unwanted API poll via `WAKE`; worst-case latency is the 30 s `TICK_SECONDS`.
- Keep `_tick(last)` signature and behaviour so the ~15 existing `_tick` tests are untouched.
- `STATUS["gmail"]` uses the existing keys `last_poll, ok, last_ok_at, error, new`. D-08 per-email "parsed 0 jobs" warnings are partial failures: keep `ok` true, set `error` to the joined warning text, and do **not** add them to the returned `errors` dict (that dict drives the 502 and the retry-soon logic). Pass a `warn` callback into `fetch_gmail_alerts` rather than changing the return type.
- Where to store the last-poll date (discretion): raw `settings` row `gmail_last_poll` (ISO date), written only after a fully successful poll, value = poll-start date minus 1 day (SINCE is date-granular and server-timezone-dependent; the overlap is deduped). If absent, `since = today - 7 days` (D-03). In-memory-only would re-scan 7 days of mail on every restart; the row costs ~6 lines.
- `POST /api/fetch` currently returns 400 "Choose at least one career field in settings" before doing anything. That gate also blocks a manual Gmail-only fetch. Leave it unless the planner wants Gmail-only manual polls; flag it in the plan.

### Pattern 7: Single Playwright thread fed by `queue.Queue`
**Prototype verified** on py3.9.6 / playwright 1.60.0 / real Chrome 156: a daemon thread owns `sync_playwright().start()`; callers `submit(fn)` which puts `(fn, Future)` on a `queue.Queue` and returns the `Future`; the worker calls `fn(pw)` and sets the result or exception; two sequential tasks ran on the same thread.
Design points:
- Hand the task the **Playwright object** (`fn(pw)`), not a long-lived browser. The details task launches headless, opens a page, closes both. Phase 5 needs a *headed* browser for the person to review forms, which cannot be the same browser as a headless one; handing out `pw` leaves that open and avoids a lingering headless Chrome process. Per-task launch cost (~1 s) is irrelevant for a rare retry.
- Lazy start: the thread and `sync_playwright().start()` happen on the first `submit`, never at import. Tests must never start it: inject a fake `submit`.
- `sync_playwright` must not run on a thread that has a running asyncio loop; a plain `threading.Thread` is fine (Flask handlers and the watcher have none) [CITED: playwright python docs; ASSUMED for Windows threads, mac verified].
- Channel selection: try `"msedge"` then `"chrome"`. Missing channel raises `playwright.sync_api.Error` with text `BrowserType.launch: Chromium distribution 'msedge' is not found at ...` followed by `Run "playwright install msedge"` [VERIFIED: local probe]. Catch `Error`, try the next, and if both fail raise a project `BrowserUnavailable`; the details worker maps it to `blocked` (D-15). **Never surface or follow the "playwright install" hint.** Remember the unavailability for the session so every blocked job does not re-probe.
- Page logic per D-14/D-16: `page.goto(url, wait_until="domcontentloaded", timeout=20000)`; read `response.status` (verified 403 surfaces); optionally one best-effort `wait_for_load_state("networkidle", timeout=5000)` in a try/except for JS-rendered pages; `page.content()` -> the same `extract_description` + blocked rules; `page.close()` in `finally`. No clicks, no typing, no waiting for a challenge to be solved. `Error` (including `TimeoutError`) -> blocked.
- Result wait: `future.result(timeout=60)`; on timeout treat as blocked.
- Default headless UA contains `HeadlessChrome` [VERIFIED: probe: `.../HeadlessChrome/156.0.0.0 Safari/537.36`]. Some sites will refuse it. Do not spoof or add stealth tricks: that drifts toward evasion and the project's compliance rule. The consequence is more `blocked` jobs, which is the designed outcome.
- Thread safety of the bridge: only the details worker calls `submit` in Phase 4; Phase 5 adds more task kinds on the same queue. Keep module-level `_q`, a start lock, and nothing else.

### Anti-Patterns to Avoid
- **Marking mail read:** never `select(readonly=False)`, never `RFC822`/`BODY[]` without `.PEEK` (belt and braces with EXAMINE), never `STORE`/`COPY`/`EXPUNGE`.
- **`datetime.utcnow()`/`strftime("%b")`:** the former is deprecated on 3.12 (existing code uses timezone-aware `datetime.now(timezone.utc)`), the latter is locale-dependent.
- **Putting the app password anywhere but keyring:** not in SQLite, not in `STATUS`, not in exception text, not in `GET /api/watcher`.
- **Raw HTML grep for "captcha":** false positives on real postings.
- **Fetching the page for LinkedIn/Indeed jobs:** D-18; mark `skipped` before any network.
- **Following alert redirect links** to discover the real URL.
- **Gmail inside the `career_fields` gate** of `_tick` / `/api/fetch`.
- **Re-using `rescore_new` for D-13.**
- **Starting any browser or touching the real keychain in automated tests.**

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MIME decoding, charset, `Subject`/`From` header decoding | Custom header/quoted-printable decode | `email.message_from_bytes(raw, policy=email.policy.default)` + `msg.get_body(preferencelist=("html","plain"))` + `get_content()` | Handles multipart, base64/QP, charsets; verified to return the HTML part |
| Secret storage | Encrypted file / SQLite column | `keyring` | OS credential store; D-01 |
| HTML parsing of emails and pages | Regex over HTML | `beautifulsoup4` with `html.parser` | D-10; real alert HTML is table soup |
| JSON-LD tolerance | `json.loads` + string fixes | `json.loads(..., strict=False)` + structure walker | Control characters and `@graph`/list shapes are the norm |
| HTML to text | New converter | `core._text_lines` (after `html.unescape`) | Already handles `<li>`, block tags, entities; D-Discretion says reuse |
| Cross-thread result handoff to Playwright | Result queues / events | `queue.Queue` + `concurrent.futures.Future` | Exceptions propagate through `Future` for free |
| Throttle between fetches | Rate-limiter class | `time.sleep(DETAILS_GAP_SECONDS)` in the single worker | One worker means one gap; ponytail |
| Dedup of alert jobs | Custom matching | `UNIQUE(url)` + `INSERT OR IGNORE` after URL canonicalisation | Existing; only the canonical URL form is new work |
| Schema migration framework | Versioned migrations | One guarded `ALTER TABLE` | Phase 1: no migration framework |

**Key insight:** the genuinely custom code is small: four site parsers (inherently site-specific), the blocked-page rule, and the one-row `save_details`. Everything else is a stdlib call.

## Common Pitfalls

### Pitfall 1: Non-alert mail from the same sender domain looks like a parser failure
**What goes wrong:** searching `FROM linkedin.com` returns invitations, digests and security notices; they parse to 0 jobs and D-08 fires a false "format may have changed" every poll.
**Why:** `FROM` is a substring match and these companies send many mail types.
**How to avoid:** search on the specific alert sender (from the sample's `From` header) and/or gate the D-08 warning on a subject or structural marker taken from the sample; unknown mails from the sender are ignored silently, only a mail that matches the alert shape and yields 0 jobs warns. Warn at most once per poll per site, not once per email.
**Warning signs:** permanent `error` text on the `gmail` status in a healthy account.

### Pitfall 2: Tracking parameters defeat URL dedupe
**What goes wrong:** the same job inserted again from every email, floods the feed, re-fetches details repeatedly.
**How to avoid:** canonicalise in each parser; a unit test asserts two sample links to the same job collapse to one URL and that no `utm_`/token params survive.

### Pitfall 3: Summary/score regression on details save
**What goes wrong:** (a) `rescore_new` reuses the stored summary; (b) re-summarising a row drops the source's `remote`/`job_type` hints, so a Remotive job loses "Fully remote".
**How to avoid:** dedicated `save_details` per Pattern 5; a test saves details for a `remote="Remote"` job and asserts the pro "Fully remote" and the score survive, and that a `queued` job's score is untouched (D-13).

### Pitfall 4: App Password failure modes
**What goes wrong:** the person pastes their normal password, or has Advanced Protection / a Workspace account where app passwords are unavailable.
**How to avoid:** fixed error text: "Gmail rejected the login. Use a Google App Password (2-Step Verification must be on), not your normal password." Test the login on `PUT`. Note Google's own page calls app passwords "not recommended and unnecessary in most cases" [CITED: support.google.com/mail/answer/7126229] and secondary sources say Advanced Protection and Workspace accounts cannot use them [CITED: web search summary, MEDIUM]. Validate against the person's real account during the sample checkpoint; OAuth is out of scope.

### Pitfall 5: Offline or flaky network marks everything `blocked`
**What goes wrong:** connection errors fall through to Playwright and then `blocked`; no automatic retry later.
**How to avoid / accept:** ponytail ceiling, documented in a `# ponytail:` comment: a failed fetch is final until the person opens the listing. A cheap mitigation if wanted: if the failure is a DNS/connection error (not an HTTP status), leave the row `pending` and sleep 60 s once. Do not add an attempt counter column.

### Pitfall 6: SSRF and local file read through email-derived URLs
**What goes wrong:** `urllib.request.urlopen` accepts `file://` and `ftp://`; Playwright `goto` accepts `file://` and `chrome://`. A hostile or spoofed alert could put such a URL in an href and the app would read a local file into `description`.
**How to avoid:** a single `_http_url(url)` gate used by both parsers and `fetch_details`: scheme must be `http`/`https` and the host non-empty; reject `localhost` and IP-literal private/loopback hosts. Parsers drop non-http(s) hrefs.

### Pitfall 7: Worker spins on one bad row
**How to avoid:** every iteration must change the row out of `pending` (or sleep). Wrap the per-row body in `try/except Exception` -> `blocked` + `log.exception`.

### Pitfall 8: Tests hitting the real world
**What goes wrong:** a test imports the watcher and the Gmail tick calls keyring or IMAP; or starts Chrome.
**How to avoid:** connected-check short-circuits on the missing address row; tests install an in-memory keyring backend and a fake IMAP class; tests replace `browser.submit` with a fake. Existing `test_watcher.py` stops threads explicitly by replacing `watcher._tick`; the new tick and the details worker thread must be stoppable the same way (module-level function the test can monkeypatch to `sys.exit`).

### Pitfall 9: Debug reloader double-starting threads
`app.py` starts the watcher only in the `WERKZEUG_RUN_MAIN` child. Start the details worker from the same place (`watcher.start()` can start both) and never at import time (`test_import_does_not_start_watcher` asserts `watcher._thread is None`).

## Code Examples

### In-memory keyring backend for tests (verified)
```python
# Source: verified in this session with keyring 25.7.0
import keyring
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError

class Mem(KeyringBackend):
    priority = 1
    def __init__(self): self.d = {}
    def get_password(self, service, user): return self.d.get((service, user))
    def set_password(self, service, user, password): self.d[(service, user)] = password
    def delete_password(self, service, user):
        if (service, user) not in self.d: raise PasswordDeleteError("not found")
        del self.d[(service, user)]

keyring.set_keyring(Mem())
```
For the no-backend path: `keyring.set_keyring(keyring.backends.fail.Keyring())` makes `get_password` raise `NoKeyringError`.

### Queue-fed Playwright thread (verified)
```python
# Source: prototype run in this session (playwright 1.60.0, Chrome 156, py3.9.6)
import queue, threading
from concurrent.futures import Future
from playwright.sync_api import sync_playwright

_q = queue.Queue(); _t = None; _lock = threading.Lock()

def _run():
    pw = sync_playwright().start()
    try:
        while True:
            fn, fut = _q.get()
            if not fut.set_running_or_notify_cancel():
                continue
            try:
                fut.set_result(fn(pw))
            except BaseException as e:   # includes BrowserUnavailable
                fut.set_exception(e)
    finally:
        pw.stop()

def submit(fn):
    global _t
    with _lock:
        if _t is None or not _t.is_alive():
            _t = threading.Thread(target=_run, name="browser", daemon=True)
            _t.start()
    fut = Future(); _q.put((fn, fut)); return fut

def launch_headless(pw):                  # used by the details task
    for channel in ("msedge", "chrome"):
        try:
            return pw.chromium.launch(channel=channel, headless=True)
        except Error:                      # playwright.sync_api.Error
            pass
    raise BrowserUnavailable("Edge or Chrome is not installed")
```

### Local fixture server for `fetch_details` tests (verified)
```python
# 403 page, JSON-LD page, challenge page served by stdlib; urllib raised HTTPError(403) (an OSError)
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        code = 403 if self.path == "/403" else 200
        body = CHALLENGE if self.path == "/chal" else PAGE
        self.send_response(code); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
```
Note: the `_http_url` gate must allow the loopback fixture host in tests (inject the allowed-host check, or let tests monkeypatch it).

### Fake IMAP for `fetch_gmail_alerts` tests
A ~25-line class with `login`, `select(mailbox, readonly)`, `uid(cmd, ...)`, `logout`, constructed via the `factory=` parameter. Assert: `select` was called with `readonly=True`; no `store`/`expunge` ever called; `uid("SEARCH")` args contain the sender and the formatted `SINCE`; a login failure raises `SourceError` containing "App Password"; per-email 0-job result calls `warn` and does not stop other emails.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| "Enable IMAP in Gmail settings" | IMAP always on, toggle removed | January 2025 | Don't tell the person to enable IMAP [CITED: support.google.com/mail/answer/7126229] |
| Gmail "less secure apps" password | App Password (needs 2-Step Verification), discouraged by Google in favour of OAuth | ongoing | Works for personal accounts today; keep error text and a live check at the checkpoint (MEDIUM) |
| `playwright install` browser download | `channel="msedge"/"chrome"` uses the installed browser | long-standing | No download; fails cleanly when absent |
| Playwright py3.9 support | dropped from 1.61.0 (2026-06-29) | 2026-06 | Pin `<1.61` while dev is 3.9.6 |
| `IMAP4_SSL(keyfile, certfile)` | `ssl_context=` only (params removed in 3.12) | 3.12 | Use keywords `ssl_context` and `timeout` |

**Deprecated/outdated:** `datetime.utcnow()` (3.12 warning); default unverified `IMAP4_SSL` context.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Alert sender addresses/domains (LinkedIn `jobalerts-noreply@linkedin.com`; CV-Library and Totaljobs unknown; Indeed domains are CITED but the exact alert address is not) | Pattern 3 | Searches return nothing or too much; fixed by reading `From` off the user's samples. Needs the checkpoint |
| A2 | Alert hrefs are direct or canonicalisable (not opaque click-tracker redirects) | Pattern 3 | Dedupe fails or job ID unrecoverable; discover at the checkpoint, may need a design decision |
| A3 | Alerts arrive in `INBOX` (not skipped by filters) | Pattern 1 | Poll finds nothing; document in Settings text |
| A4 | The target Windows PC has Edge or Chrome installed (Edge ships with Windows 10/11) | Pattern 7, Env | Every blocked retry becomes `blocked`; harmless by design (D-15) |
| A5 | Playwright sync API runs correctly on a non-main thread on Windows/3.12 | Pattern 7 | Retry path fails on target; verify during a Windows run. Verified only on macOS/3.9 |
| A6 | `keyring` Windows Credential Manager backend works as on macOS | Pattern 2 | Connect fails on target with a clear 503; verify on the Windows PC |
| A7 | The user's Google account can create an App Password (2SV on, not Advanced Protection, not Workspace-restricted) | Pitfall 4 | Gmail source unusable; OAuth out of scope. Verify at the checkpoint with a live login |
| A8 | `https://myaccount.google.com/apppasswords` is the App Password page named in the error text | Pitfall 4 | Cosmetic; drop the URL if unsure |
| A9 | Headless UA `HeadlessChrome` leads more sites to block (not measured against any job site) | Pattern 7 | Behavioural only; designed outcome is `blocked` |

## Open Questions (RESOLVED)

1. **Does the first real poll hit Gmail's actual wording and filters?**
   - What we know: stdlib behaviour and the error path are verified; Google behaviour is from docs/secondary sources.
   - What's unclear: whether this person's account accepts an App Password and keeps alerts in INBOX.
   - Recommendation: add a short live `human-verify` step after the Gmail plan (store creds, `POST /api/fetch`, see `gmail` in status), coupled with the sample checkpoint.
   - RESOLVED: 04-05 Task 2 `<human-check>` (blocking human gate, end-of-phase UAT) runs the live poll with a real App Password and first confirms the alerts sit in INBOX; INBOX-only is an accepted limit (04-02 Assumptions, CONTEXT.md D-02).

2. **Gmail-only manual fetch with no career fields.**
   - What we know: `/api/fetch` 400s without fields today; D-04 says Gmail is independent.
   - Recommendation: leave as is for now (Phase 6 UI decides); the watcher's Gmail tick is independent regardless. Raise it in the plan as a one-line decision.
   - RESOLVED: 04-02 decides it from D-04 and D-05: with no career fields but Gmail connected, `POST /api/fetch` runs Gmail alone (200, `by_source: {gmail: N}`); with neither, the existing 400 stays word for word (Task 3, `test_manual_fetch_includes_gmail`).

3. **Offline marks jobs `blocked` permanently** (Pitfall 5). Recommendation: accept with a `# ponytail:` comment.
   - RESOLVED: 04-03 Assumptions "Offline fetches are final": a fetch that fails offline marks the job `blocked`, with a `# ponytail:` comment in `fetch_details` naming the upgrade (set `details_status` back to `pending`).

4. **Does the `needs_details` classification (skipped/ok) belong in `core.py`?** Recommendation: yes, as a pure function `details_plan(job, settings) -> "skipped" | "ok" | "fetch"`, unit-tested in `test_details.py` (no I/O).
   - RESOLVED: 04-03 Interfaces define `core.details_plan(job, settings) -> "skipped" | "ok" | "fetch"` as a pure function, pinned by `test_details_plan_rules` in `api/test_details.py`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (project `.venv`) | everything | yes | 3.9.6 | none needed |
| `keyring`, `beautifulsoup4`, `playwright` in `.venv` | all new code | no (not installed yet) | verified installable: 25.7.0 / 4.15.0 / 1.60.0 in a throwaway venv | install from updated `requirements.txt` |
| Google Chrome (dev, macOS) | Playwright retry smoke test | yes | 156.0.8078.47 (launched headless OK) | tests use a fake `submit` |
| Microsoft Edge (dev, macOS) | `msedge` channel | no (`Chromium distribution 'msedge' is not found`) | n/a | `chrome` channel, then `BrowserUnavailable` -> `blocked` |
| macOS Keychain backend | keyring dev use | yes (`keyring.backends.macOS.Keyring`) | n/a | in-memory test backend |
| Network + `imap.gmail.com:993` | live Gmail check | not exercised here | n/a | fake IMAP in tests |
| Google App Password for the user's account | live Gmail check | user-supplied | n/a | live check deferred to a human-verify step |
| Real alert emails (4 sites) | parsers (GMAIL-02) | no (user must export) | n/a | blocks parser tasks only |
| Windows 3.12 target | final check | not available here | n/a | A4/A5/A6 verified later on the PC |

**Missing dependencies with no fallback:** the four sample emails (blocks GMAIL-02 parser tasks only).
**Missing dependencies with fallback:** Edge on dev Mac (Chrome works); packages (install step).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | plain-assert scripts with `test_*` functions and an `if __name__ == "__main__"` runner (existing `api/test_core.py`, `test_api.py`, `test_watcher.py`); `pytest 8.4.2` is also installed in `.venv` and collects the same functions |
| Config file | none; each script sets `JOBHELPER_DB` to a temp path before importing `db`/`app`, and inserts `api/` on `sys.path` |
| Quick run command | `.venv/bin/python api/test_details.py` / `.venv/bin/python api/test_gmail.py` |
| Full suite command | `for f in api/test_*.py; do .venv/bin/python "$f" || exit 1; done` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GMAIL-01 | IMAP flow uses `readonly=True`, `FROM`/`SINCE` (English month), no mutating command; first poll = today-7d; bad login -> `SourceError` mentioning App Password; non-ASCII password rejected; 0-job email warns, others still processed | unit (fake IMAP) | `.venv/bin/python api/test_gmail.py` | no, Wave 0 |
| GMAIL-01 | `PUT/GET/DELETE /api/gmail`: password never in any response/`GET /api/settings`/`GET /api/watcher`; DELETE idempotent; `NoKeyringError` -> 503; login tested before store | integration (Flask test client, in-memory keyring) | `.venv/bin/python api/test_gmail.py` | no, Wave 0 |
| GMAIL-01 | Gmail tick: due logic, skipped quietly when not connected, independent of `career_fields`, `STATUS["gmail"]` shape, `/api/fetch` includes `gmail` only when connected, existing `by_source` assertions unchanged | unit | `.venv/bin/python api/test_watcher.py` | extend existing |
| GMAIL-02 | Each of 4 parsers against its committed `api/samples/<site>.eml`: >=1 job, first job's title/company/url match, urls are http(s), canonical, unique, `source` is the site name; same job twice collapses to one URL | unit | `.venv/bin/python api/test_gmail.py` | no, blocked on samples |
| GMAIL-02 | Parsed jobs insert, score and dedupe via `insert_jobs` (second insert returns 0 new) | unit | same | no, Wave 0 |
| DETAIL-01 | `extract_description`: `@graph`, list, `@type` list, escaped-HTML description, invalid control chars, no JSON-LD -> largest block picks the right container, empty page | unit | `.venv/bin/python api/test_details.py` | no, Wave 0 |
| DETAIL-01 | `details_plan` classification; migration adds `details_status` once, legacy rows `pending`; `/api/jobs` returns the field | unit/integration | same | no, Wave 0 |
| DETAIL-01 | `save_details`: `new` job recomputes summary+score, keeps Remotive "Remote" pro; `queued`/`dismissed` score untouched; shorter text never overwrites a longer description | unit | same | no, Wave 0 |
| DETAIL-02 | Blocked rules: 403/429/503, `<200` chars, challenge text without JSON-LD, challenge phrase on a page that does have JSON-LD stays `ok`; urllib failure -> retried once via fake `browser.submit` -> `blocked`; `BrowserUnavailable` -> `blocked`; LinkedIn/Indeed never call urllib or browser | unit (local `http.server` + fake submit) | same | no, Wave 0 |
| DETAIL-02 | `file://`, `ftp://`, empty host rejected before any fetch | unit | same | no, Wave 0 |
| FILL-01 groundwork | `browser.submit` runs two tasks on the same single thread, propagates exceptions through the `Future` | optional live smoke, auto-skipped when no Edge/Chrome | `.venv/bin/python api/test_details.py` | no, Wave 0 |

### Sampling Rate
- **Per task commit:** the single new/extended test script for that task (< 5 s each; local HTTP server and fakes only).
- **Per wave merge:** full suite loop above.
- **Phase gate:** full suite green, plus the human-verify live Gmail poll, before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `api/test_gmail.py`: fake IMAP, in-memory keyring backend, endpoint tests, parser tests (parser part gated on samples)
- [ ] `api/test_details.py`: extraction, blocked rules, local HTTP server, fake browser submit, migration, `save_details`, optional live browser smoke
- [ ] `api/samples/` with four redacted `.eml` files (user checkpoint)
- [ ] Framework/deps install: add the three pins to `api/requirements.txt`, then `.venv/bin/pip install -r api/requirements.txt` (after the SUS human-verify checkpoint)

## Security Domain

`security_enforcement` is enabled (ASVS level 1, block on high).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (credential for a third party) | App Password stored only in `keyring`; never SQLite/response/log |
| V3 Session Management | no (local, no login) | existing `local_only` Host/Origin guard still covers `/api/gmail` |
| V4 Access Control | yes, minimal | `local_only` before-request already blocks non-local Host/Origin for `/api/*` [VERIFIED: app.py:26-35] |
| V5 Input Validation | yes | strict key whitelist on `PUT /api/gmail`; ASCII/`@` checks; URL scheme allowlist; response and email size caps |
| V6 Cryptography | yes (transport) | `ssl.create_default_context()` for IMAP TLS; do not hand-roll storage crypto |
| V7 Error handling/logging | yes | error texts built from fixed strings, never from the password or raw server text with credentials |
| V12 SSRF/files | yes | `_http_url` allowlist (http/https, non-private host) before urllib or Playwright |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| App password leaks via API, status, log or traceback | Information disclosure | keyring only; `GET /api/gmail` returns `{address, connected}`; catch exceptions around login and re-raise fixed text; a test asserts the password string appears in no response body |
| `file://` / internal-host URL planted in a spoofed alert | Tampering / Information disclosure | scheme + host allowlist in parsers and in `fetch_details`; Gmail DMARC makes spoofing hard but parsers must still not trust hrefs |
| Malicious HTML in email or page reaches the UI | Tampering (XSS) | store plain text only (`get_text`, `_text_lines`); UI must render as text (Phase 6) |
| Oversized email or page exhausts memory | Denial of service | cap page read (~2 MB) and skip emails above a size cap (ponytail) |
| MITM on IMAP | Information disclosure | verifying SSL context (the stdlib default does not verify) |
| Marking/altering the person's mail | Tampering | `EXAMINE` + `BODY.PEEK`, no store/expunge |
| CAPTCHA/automation abuse | Compliance | no interaction in the browser task; LinkedIn/Indeed never fetched; no UA spoofing |
| Cross-site request to `/api/gmail` | Spoofing / CSRF | existing Host + Origin allowlist; `PUT/DELETE` require JSON body |

## Sources

### Primary (HIGH confidence)
- Local probes on Python 3.9.6 `.venv`-derived venv (keyring 25.7.0, bs4 4.15.0, playwright 1.60.0, Chrome 156): keyring round trip / missing entry / `NoKeyringError`; JSON-LD extraction; `http.server` 403 + `HTTPError`; queue-fed Playwright thread; msedge-missing error text; SQLite `ALTER TABLE` idempotence; stdlib `imaplib` source (`select` -> `EXAMINE`, `login` raising `error(dat[-1])`, `IMAP4_SSL` signature)
- `/Users/philipagbo/Desktop/JobApplicationProject/api/{watcher,sources,db,app,core}.py` read this session
- PyPI JSON API for `keyring`, `playwright`, `beautifulsoup4`, `soupsieve` (versions, `requires_python`, wheel names, `requires_dist`)
- https://docs.python.org/3/library/imaplib.html (`IMAP4_SSL` timeout/ssl_context, `select(readonly)`, search/fetch notes)
- https://support.google.com/mail/answer/7126229 (IMAP always on from Jan 2025; app passwords not recommended)

### Secondary (MEDIUM confidence)
- Web search summaries on Gmail "Application-specific password required", Advanced Protection disabling app passwords, Workspace restrictions (third-party/forum; not Google-official)
- Indeed Help Center "How to verify emails from Indeed" (official sender domains)

### Tertiary (LOW confidence)
- Alert sender addresses for LinkedIn, CV-Library, Totaljobs (not found in any source; assumed pending samples)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, installed and exercised on the target Python line
- Architecture / integration with existing code: HIGH, all four integration files read in full
- IMAP/Gmail account behaviour: MEDIUM, stdlib verified, Google specifics from docs and summaries
- Parsers/senders: LOW until the user's samples exist
- Windows runtime behaviour (keyring, Playwright thread): MEDIUM-LOW, mac-only probe

**Research date:** 2026-10-25
**Valid until:** 2026-11-25 for stack facts (Playwright releases fast); Gmail account behaviour should be re-checked at the live step
