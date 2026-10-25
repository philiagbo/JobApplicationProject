# Phase 4: Gmail Alerts and Job Details - Context

**Gathered:** 2026-10-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Jobs from LinkedIn, Indeed, CV-Library and Totaljobs arrive through the person's Gmail job-alert emails (read over IMAP with credentials kept in `keyring`). Each site has its own parser, and the jobs are scored and deduplicated like the other sources. Any job can get its full description through `fetch_details`. That function reads the page's JSON-LD `JobPosting`, falls back to the largest text block, and retries once in Playwright. A page that is still blocked is marked "open listing to read". CAPTCHAs are never attempted.

Out of this phase: the autofill and Apply queue (Phase 5), and the UI pages (Phase 6).

</domain>

<decisions>
## Implementation Decisions

### Gmail credentials and mail rules (GMAIL-01)
- **D-01:** Credentials are entered through the API. `PUT /api/gmail` with `{address, app_password}` stores them in `keyring`. `GET /api/gmail` returns only `{address, connected}`. The app password never goes into SQLite or any response. Gmail IMAP needs a Google App Password, and the error text should say so. Disconnecting (e.g. `DELETE /api/gmail`) is at Claude's discretion. — **Reversibility:** costly — the Phase 6 Settings page builds on this endpoint shape.
- **D-02:** Each poll searches IMAP `FROM` each known alert sender, `SINCE` a stored last-poll date. The mailbox is opened read-only, so the person's mail is never marked read. Dedupe by job URL handles the overlap between polls.
- **D-03:** The first poll looks back 7 days.
- **D-04:** Alert jobs are **not** filtered by career field. The person already chose what the alerts send. Scoring (including excluded words) ranks them.
- **D-05:** Gmail is its own source, `gmail`, in the watcher status and in `POST /api/fetch` counts. It is polled every `gmail_poll_minutes` (already a setting, default 5), separately from the 60-minute API tick. When Gmail isn't connected it is skipped quietly (Phase 2 D-09).

### Alert parsers and samples (GMAIL-02)
- **D-06:** Each of LinkedIn, Indeed, CV-Library and Totaljobs gets its own parser function. Each is tested against a **real** alert email that the user exports. The plan must include a checkpoint where the user supplies one sample per site (`.eml` or HTML from Gmail's "Show original") before or while the parsers are built.
- **D-07:** The samples are redacted by hand (names, email addresses, tracking tokens) and committed under `api/samples/`, so the tests run anywhere.
- **D-08:** If an email from a known sender parses to 0 jobs, that is recorded in the `gmail` source's `last_error` (e.g. "LinkedIn alert parsed 0 jobs — format may have changed"). The other emails are still processed.
- **D-09:** Totaljobs uses the email parser only. No RSS path.
- **D-10:** HTML parsing uses `beautifulsoup4` (a new pinned dep in `api/requirements.txt`). HTTP stays on stdlib `urllib`, with no `requests`. `keyring` is a new dep.

### Fetching details (DETAIL-01)
- **D-11:** `fetch_details` runs in the background after insert, for new jobs, one fetch every 5 seconds. The gap is a fixed constant, not a setting. The descriptions are ready by the time the person opens a job.
- **D-12:** Only jobs with an empty or short description are fetched: Gmail alert jobs, and any job whose description is under ~500 characters. Reed and Remotive full text is kept as it is. Jobs whose title hits an excluded word are skipped.
- **D-13:** When the full description arrives it is stored, and score, pros, cons and summary are recomputed **only if the job is still `new`**. Queued and dismissed jobs keep their score (same rule as Phase 1 D-08 and Phase 3 D-09).

### Blocked pages and Playwright (DETAIL-02)
- **D-14:** The **single Playwright browser thread fed by `queue.Queue`** is introduced now. It is the same thread Phase 5 autofill will extend. For details it loads the page headless, reads JSON-LD or the text, and closes the page. — **Reversibility:** costly — Phase 5 builds autofill on this thread and queue.
- **D-15:** The browser is the installed Edge or Chrome (`channel="msedge"` / `"chrome"`), so no Playwright browser download is needed. If neither is available, the job is marked blocked.
- **D-16:** A page counts as "blocked" on HTTP 403/429/503, or when the page text shows a CAPTCHA or human-check signal (captcha, "verify you are human", Cloudflare challenge), or when the extracted text is under ~200 characters. The app never interacts with a CAPTCHA.
- **D-17:** A new `details_status` column on `jobs` takes the values `pending` / `ok` / `blocked` / `skipped`, and `GET /api/jobs` returns it. `blocked` means "Open listing to read full description". — **Reversibility:** one-way — this adds a column to the live SQLite `jobs` table on existing user DBs. Phase 1 says there are no migrations, so this needs an idempotent `ALTER TABLE ... ADD COLUMN` guarded on `init_db`.
- **D-18:** LinkedIn and Indeed job pages are **never fetched**. They are marked `skipped` / open-listing, and the alert snippet is kept. This follows the project rule against automating LinkedIn and Indeed.

### Claude's Discretion
- The exact alert sender addresses and per-site HTML selectors (from the real samples).
- Where the last-poll date for Gmail is stored (settings key vs in-memory plus the 7-day fallback).
- The details worker mechanics: a separate thread or part of the watcher loop, and how it hands blocked jobs to the Playwright thread.
- How the JSON-LD `description` HTML is turned into text (reuse `core._text_lines`).
- The exact short-description threshold and blocked-text threshold (about 500 and 200 characters).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Original design
- `PLAN.md` — the sources table (`fetch_gmail_alerts`, `fetch_details`), the "Reading the full job description" section, the Watcher section, Known limits (alert parsers break when formats change), Verification (alert parsing against saved sample HTML)

### Requirements and roadmap
- `.planning/REQUIREMENTS.md` — GMAIL-01, GMAIL-02, DETAIL-01, DETAIL-02
- `.planning/ROADMAP.md` — Phase 4 success criteria
- `.planning/PROJECT.md` — Out of Scope (no LinkedIn/Indeed automation, no CAPTCHA bypass)

### Prior phase decisions
- `.planning/phases/01-data-scoring-and-first-source/01-CONTEXT.md` — scoring and re-score rule (D-08), settings shape, no-migrations stance
- `.planning/phases/02-watcher-and-more-sources/02-CONTEXT.md` — watcher status, failure handling, fetch lock (D-04, D-09..D-14)
- `.planning/phases/03-profile-and-answers/03-CONTEXT.md` — skills scoring with the profile (D-07, D-09)

### Codebase maps
- `.planning/codebase/CONVENTIONS.md`, `.planning/codebase/TESTING.md`, `.planning/codebase/ARCHITECTURE.md` (the Playwright single-thread rule)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `api/sources.py`: `SourceError`, `USER_AGENT`, the `get_json` urllib helper, and the job dict shape returned by `fetch_remotive` / `fetch_reed`. The Gmail parsers return that same shape with `source` set to the site name.
- `api/watcher.py`: `_sources`, `run_fetch` (per-source counts and errors), `_tick` / `WAKE` / `status()` with per-source last_ok and last_error. Extend it for the `gmail` source and its own interval.
- `api/db.py`: `insert_jobs(conn, jobs, settings, profile)` (dedupe by URL plus scoring), `rescore_new`, the `DEFAULTS` holding `gmail_poll_minutes`, and `init_db`, where the `details_status` column is added.
- `api/core.py`: `_text_lines` (HTML to lines), `summarize`, `score`.

### Established Patterns
- Pure parsing goes in `core.py` or `sources.py` and can be tested without the network. DB helpers go in `db.py`, and Flask routes in `app.py` stay thin and return `{"error"}` with 400/404/409.
- Tests are plain-assert scripts (`api/test_core.py`, `api/test_api.py`, `api/test_watcher.py`) using a temp DB through `JOBHELPER_DB`.
- Typing stays Python 3.9-compatible. Deliberate shortcuts are marked with `# ponytail:` comments.

### Integration Points
- `api/requirements.txt` gains `beautifulsoup4`, `keyring` and `playwright` (pinned).
- The watcher loop gains the Gmail cadence and the details worker. `POST /api/fetch` includes `gmail`.
- The `jobs` table gains `details_status`, and `job_dict` exposes it.
- The Playwright thread and queue are reused by Phase 5 autofill.

</code_context>

<specifics>
## Specific Ideas

- Error text when Gmail login fails should tell the person to use a Google App Password (2-step verification must be on).
- The user will export real alert emails, one per site, for the fixtures.

</specifics>

<deferred>
## Deferred Ideas

None. The discussion stayed within the phase scope.

</deferred>

---

*Phase: 04-gmail-alerts-and-job-details*
*Context gathered: 2026-10-25*
