# Job Helper — local web app for finding + applying to jobs

## Context
Built for someone else to run on their **Windows** PC. They pick career fields. The app watches job sources, ranks and summarises listings, and shows them as swipe cards or a list. Ticked jobs go into an **Apply queue**, which the app works through itself: it pre-fills each application from the CV and saved answers. The person reviews each one and clicks Submit. Every answer they give is remembered, so later applications need less typing.

Decisions made:
- **Job sources.** LinkedIn/Indeed/CV-Library/Totaljobs have no public job APIs, so the app reads their job-alert emails from the person's **Gmail**. It also uses the official free **Reed** API, plus Adzuna and Remotive.
- **No AI for v1.** Scoring, pros/cons, summaries and cover letters use rules and templates. Each lives in one function, so a Claude or ChatGPT call can replace it later.
- **The app fills, the person submits.** The app never clicks Submit.
- **Local web app, one Python process (monolith) + React/TypeScript UI.** The person double-clicks `Start.bat` and the app opens at `http://localhost:8765`. All data stays on the PC.
- **The UI ships pre-built.** The developer builds it with Node; the person using the app never needs Node.

## Architecture
One Flask process serves the built React app (`api/static/`), the JSON API, the watcher thread and the autofill worker thread. Data lives in one SQLite file.
- Playwright's sync API isn't thread-safe, so all browser work runs on one dedicated thread fed by a `queue.Queue`.
- If this ever becomes a hosted multi-user app, the watcher is the piece to split off first.

## Stack
- **Backend:** Python 3.12 + Flask, stdlib `sqlite3` / `imaplib` / `email` / `difflib`, `pypdf` + `python-docx`, `beautifulsoup4`, `requests`, `playwright`, `keyring`.
- **Frontend:** React + TypeScript, built with Vite.
  - `react-router-dom`: pages with working back/forward.
  - `motion` (Framer Motion): drag-to-swipe with spring physics, and cards/rows animating in and out, for the smooth feel.
  - Plain CSS with variables, no UI kit.
  - Data via typed `fetch` helpers plus a small `usePoll` hook (30 s), no state library.
  - In development, Vite's dev server proxies `/api` to Flask. `npm run build` outputs to `api/static/`, and those built files ship with the app.

## Data (SQLite)
- `jobs`: url (unique), source, title, company, location, salary, description, summary, score, pros, cons, status (`new → dismissed | queued → filling → ready | needs_input → applied | skipped`), status_changed_at
- `answers`: question (normalised), answer, field_type, source (profile/learned), updated_at. **The memory bank.**
- `unanswered`: question, times_seen, last_seen. Feeds "Profile gaps" and is cleared when the question is answered.
- `settings`: career fields, excluded words, min salary, location, API keys, poll intervals, view preference

## Step 1: initialise the project (the next thing to do, then stop for review)
1. Check which tools this Mac has: `python3 --version`, `node --version`, `npm --version`.
2. **`api/`**: `app.py` with a minimal Flask app: `GET /api/health → {"ok": true}` and serving `api/static/index.html` for non-API paths. Plus `requirements.txt` (flask only for now) and a `.venv` created with `pip install -r requirements.txt`.
3. **`ui/`**: `npm create vite@latest ui -- --template react-ts`, then `npm install`. In `vite.config.ts`, proxy `/api` to `http://localhost:8765` and set `build.outDir: "../api/static"`. Replace the Vite demo `App.tsx` with an empty shell that calls `/api/health` and shows "API connected".
4. **Root:** `.gitignore` (`.venv/`, `node_modules/`, `api/static/`, `*.db`, `__pycache__/`), and **`PLAN.md`, a copy of this plan**, so it's readable from the Claude Code extension in VS Code.
5. **Verify:** run Flask and `npm run dev`; the page shows "API connected". `npm run build` succeeds.
6. **Stop.** Every later section is built only when asked.

## Files (project root: `~/Desktop/JobApplicationProject/`, open it in VS Code)
Backend in `api/`, frontend in `ui/`.
| File | Purpose |
|---|---|
| `api/app.py` | Serves `static/index.html` for every non-API path (so client-side routes work), JSON API (`/api/jobs`, `/api/jobs/<id>/dismiss|queue|undo`, `/api/queue`, `/api/answers`, `/api/stats`), DB setup, watcher thread, autofill thread |
| `api/sources.py` | `fetch_reed`, `fetch_adzuna(country="gb")`, `fetch_remotive`, `fetch_gmail_alerts()` (a parser each for LinkedIn/Indeed/CV-Library/Totaljobs alerts; use the Totaljobs RSS feed instead if it still works), `fetch_details(url)` |
| `api/core.py` | `score(job, settings, profile) → (score, pros, cons)`, `summarize`, `cover_letter`, `extract_profile`, `normalise`, `find_answer` |
| `api/autofill.py` | Playwright fill logic plus the submit listener |
| `ui/` (Vite React TS source) | `src/api.ts`: `Job`/`QueueItem`/`Answer`/`Stats` types and fetch helpers · `src/usePoll.ts` · `src/App.tsx`: top nav (Jobs · Apply queue · Dashboard · Profile · Settings, with badge counts) and routes · `src/pages/` `Jobs.tsx`, `Queue.tsx`, `Dashboard.tsx`, `Profile.tsx`, `Settings.tsx` · `src/components/` `JobCard.tsx` (shared by both views), `SwipeDeck.tsx`, `JobList.tsx`, `FilterBar.tsx`, `UndoToast.tsx` · `src/app.css` |
| `api/static/` | Vite build output, served by Flask |
| `api/cover_letter.txt`, `api/test_core.py`, `api/tests/form_a.html`, `api/tests/form_b.html`, root `Start.bat`, `README.txt`, `PLAN.md` | as described below |

## Jobs page (the main screen)
- **Two views**, switched by a toggle that's remembered in `localStorage`:
  - **Swipe:** one card at a time.
  - **List:** a vertical stack of the same cards in compact form.
- **Order and filters.** Both views are sorted by score, highest first. Filter chips come from the person's career fields (e.g. *Data Analyst*, *Marketing*), next to a title search box. Filtering happens instantly in the browser with no server round-trip.
- **Card contents:**
  - title, company, location, salary
  - match score badge
  - **Pros** (green) and **Cons** (red)
  - "More" expands the key points: what you'd do, what they want, type, remote status, experience required
  - a link to the original listing
- **Pros and cons come from `score`, not AI.**
  - Pros: salary at or above the minimum, remote/hybrid, *N* CV skills matched, title matches a chosen field.
  - Cons: salary below the minimum or not listed, asks for more years of experience than the CV shows, requirements the CV doesn't mention, onsite when remote is preferred, excluded words.
- **Actions:** **✕** dismisses, **✓** adds to the Apply queue.
  - Swipe view: drag left or right with Motion `drag="x"` (the card tilts with drag distance, shows a ✕ or ✓ stamp, and flies off past a distance or speed threshold, otherwise springs back), click the buttons, or press ← / →.
  - List view: buttons on each row, and the row collapses out.
  - Every action shows an **Undo** toast for 5 seconds.
  - Buttons have `aria-label`s, and keyboard focus is visible.
- **Live updates.** New jobs arrive every 30 seconds and are slotted in by score. A "3 new jobs" pill appears instead of the list jumping around. The tab title shows the unread count.

## Apply queue (the app works through it)
1. Ticked jobs have status `queued`. The autofill thread **starts on its own** and fills **up to 5 applications at a time, each in its own browser tab**. It starts the next as soon as one is submitted or skipped. The queue survives app restarts.
2. For each form, it matches every field against:
   - **the profile keyword map**, e.g. first name, email, CV upload
   - **saved answers:** `find_answer` normalises the label, tries an exact match then a fuzzy `difflib` match (≥ 0.85), and maps the answer onto dropdown or radio options
   - **a cover letter, only if the form has a cover-letter field**
3. Each job ends up **Ready to submit** or **Needs your input** (unknown fields are outlined red in the tab).
4. `queue.html` shows each job as a row with its status. **Review & submit** brings that tab to the front.
5. **"Questions the app needs answered"** panel: unique unanswered questions across the whole queue. Answering one in the app **fills it in every open form that asks it** and saves it to `answers`. Answers typed directly into a form are also captured when Submit is clicked (via a `page.expose_binding` listener), with a **Save my answers** button as backup.
6. Answers are **not** saved when the question mentions the company's name or the answer is longer than 300 characters.
7. When the submit is detected the job becomes `applied`. The person can also **Skip** a job to drop it from the queue.
8. On linkedin.com / indeed.com the app only opens the page and shows a copy-paste panel of answers, because automating those sites breaks their terms.

## Dashboard
- **Weekly stats** (plain SQL counts, bars drawn with CSS, no chart library):
  - jobs found, queued, applied and dismissed this week vs last week
  - jobs found and applied per source
  - average match score of applied jobs
- **Profile gaps:** questions from `unanswered` sorted by how often they came up, e.g. "Asked in 4 applications: *Do you have a full UK driving licence?*". Each has an inline answer box that saves straight to `answers`.

## Profile page (first-run onboarding)
1. Upload a CV, and the regex pre-fills name/email/phone/LinkedIn/skills.
2. Common application questions: address, right to work, visa sponsorship, notice period/start date, salary expectation, relocation, driving licence, highest qualification, portfolio, how did you hear, and equal-opportunities questions (default "Prefer not to say").
3. Editable cover letter template.
4. **Saved answers** list, where every learned answer can be edited or deleted.

## Reading the full job description (no AI needed)
`fetch_details(url)` runs for every new job that passes a quick title check, one fetch every few seconds:
1. **JSON-LD** `JobPosting` block first.
2. Otherwise the largest text block on the page.
3. If blocked, retry once in Playwright; after that, "Open listing to read full description". The app never tries to get past a CAPTCHA.

`summarize` pulls salary, type, remote status, years of experience, 3 "What you'd do" bullets and 3 "What they want" bullets.

## Watcher
The watcher checks Gmail every 5 minutes and the APIs every 60 minutes (both configurable). It dedupes by URL, then fetches details and scores each job. Optional "open when Windows starts" setting, so the watcher is always running.

## Known limits (`ponytail:` comments in code)
- Alert-email parsers depend on each site's email HTML. They need real samples and will break when the format changes.
- Label matching and fuzzy matching are heuristics, so reused answers are listed for review. Multi-page Workday forms leave more fields to fill by hand.
- A cap of 5 tabs at once, because login sessions on the form sites can time out. It's a setting.
- Skipped for now: Greenhouse/Lever per-company feeds, desktop notifications, AI, and an application-outcome tracker (interview/offer).

## Verification
1. `python test_core.py` covers:
   - salary regex
   - score order, pros/cons and excluded words
   - alert parsing against saved sample HTML
   - `find_answer` (differently worded visa questions match, and the answer maps onto a Yes/No dropdown)
   - cover-letter placeholders
   - the rule that skips saving company-specific answers
1b. In `ui/`, `npx tsc --noEmit` and `npm run build` pass. Flask then serves the built UI, and refreshing on `/queue` loads correctly.
2. Run the app and check each piece:
   - **Profile:** upload a sample CV and check the pre-fill.
   - **Check now:** with the "data analyst" field it pulls Remotive/Reed jobs.
   - **Swipe view:** cards are in score order and drag, buttons and arrow keys all work. Undo restores a job. The filter chips narrow the stack.
   - **List view:** same order and actions.
   These are checked in the built-in browser at desktop and narrow widths.
3. Queue ✓ on the two local fixture forms, `tests/form_a.html` and `tests/form_b.html`, and check:
   - **Autofill starts on its own.** Form A (no cover-letter field) → no cover letter is generated, and it's marked *Needs your input: visa sponsorship*.
   - **Answering in the app** fills that field in the open tab and saves it.
   - **Form B** (a differently worded visa question plus a cover-letter box) → *Ready to submit*.
   - **Submitting a fixture** marks the job applied.
   - **Nothing is ever auto-submitted.**
4. The dashboard shows this week's counts, and an unanswered question appears under Profile gaps.
5. Gmail parsing against a real alert email from each site.
6. `Start.bat` has to be tested on the Windows PC (this machine is a Mac).

## Running in development (done in Step 1)
Two terminals from the project root:
1. `.venv/bin/python api/app.py` starts the API on http://localhost:8765 (Windows: `.venv\Scripts\python api\app.py`).
2. `cd ui && npm run dev` starts the UI on http://localhost:5173 with hot reload. `/api` is proxied to 8765.

`cd ui && npm run build` writes the UI into `api/static/`, and Flask then serves it all at http://localhost:8765.

Notes:
- The port is **8765, not 5000**, because macOS's AirPlay Receiver takes port 5000.
- This Mac only has Python 3.9. Keep the backend code 3.9-compatible, e.g. use `Optional[str]` rather than `str | None` in runtime code. The Windows PC will get 3.12.
