# UI Map: Job Helper frontend

Mapped 2026-11-13 against the backend as of Phase 4.1 (plans 01-02 committed, 03 in progress). Source of truth for the UI's structure and slice order; PLAN.md sections (Jobs page, Apply queue, Dashboard, Profile page) remain the source of truth for page behaviour.

## Current state

- `ui/src/` is a placeholder: `App.tsx` (health check), `main.tsx`, `index.css` (5 tokens: `--bg --text --muted --ok --bad`, dark mode via `prefers-color-scheme`).
- Plumbing works: Vite builds to `api/static/`, dev proxy `/api` → `:8765`, Flask falls back to `index.html` for non-API paths (history routes like `/queue` load directly).
- Requirements UI-01..UI-05 are v2 in REQUIREMENTS.md.

## API readiness per page

| Page | Endpoints | Ready |
|---|---|---|
| Settings | `GET/PUT /api/settings`, `GET /api/watcher`, `POST /api/fetch`, `GET/PUT/DELETE /api/gmail` | Now |
| Jobs (list + swipe) | `GET /api/jobs?status=`, `POST /api/jobs/<id>/dismiss\|queue\|undo`, `PUT /api/jobs/<id>/description` | Now |
| Dashboard stats | `GET /api/stats` | Partial (see gaps) |
| Profile | `GET/PUT /api/profile`, `POST /api/profile/cv`, `/api/answers` CRUD, `GET /api/jobs/<id>/cover-letter` | Now |
| Dashboard profile gaps | unanswered-questions list | Phase 6 (QUEUE-02) |
| Apply queue | `GET /api/queue`, skip, Review & submit | Phases 5-6 |

### API contracts the UI consumes today

- `GET /api/jobs?status=new` → `Job[]` sorted score desc. Job: `id, url, source, title, company, location, salary, description, summary, score, pros[], cons[], status, created_at, status_changed_at`. `summary`: `salary_text, salary_annual, currency, job_type, remote, years_experience, what_youd_do[], what_they_want[]`.
- Status actions return the updated job; 404 unknown id; 409 invalid transition (`undo` only from `dismissed`/`queued`).
- `GET /api/settings` → `career_fields[], known_skills[], excluded_words[], min_salary, location, reed_api_key, gmail_poll_minutes, api_poll_minutes, cover_letter_template`. (No Adzuna settings: the backend dropped Adzuna; sources are reed, remotive, gmail.) `PUT` merges; 400 `{"error"}` on bad type/unknown key.
- `POST /api/fetch` → 400 when no career fields, 409 if already fetching, 502 if every source failed, else 200 `{by_source, errors}`.
- `GET /api/watcher` → `{running, fetching, sources: {name: {last_poll, ok, last_ok_at, error}}}`.
- `GET /api/stats` → `{days: 7, found|queued|dismissed|applied: {total, by_source}}`.
- `GET /api/gmail` → `{address, connected}`; `PUT {address, app_password}` tests the login first (400 bad creds/format, 502 network); `DELETE` disconnects.
- `PUT /api/jobs/<id>/description {description}` → updated job, re-scored; 400 empty/too long, 404 gone.
- `GET/PUT /api/profile`, `POST /api/profile/cv` (multipart field `cv`, PDF/DOCX ≤ 10 MB) → profile; CV only fills empty fields.
- `GET /api/jobs/<id>/cover-letter` → `{text}`.
- All errors: `{"error": "..."}` with 4xx/5xx; error strings are user-facing — show them as-is.

### Binding contracts from earlier phases

- `.planning/phases/04.1-better-linkedin-and-indeed-ranking/04.1-UI-SPEC.md` — forward contract for `PartialInfoBadge` (on `summary.partial_info`) and `PasteDescription` (collapsed control + textarea → paste endpoint), with exact strings, spacing scale and typography. The Jobs slice must follow it, not re-decide it.

### Gaps

1. Stats lacks "this week vs last week" and avg score of applied (PLAN.md Dashboard) — small `db.stats` change, do with the Dashboard slice.
2. No badge-count endpoint: Jobs badge from the polled `new` list length; queue badge waits for `/api/queue` (queue spans queued/filling/ready/needs_input).
3. "N new jobs" pill: no API change — `usePoll` diffs job ids between polls.
4. First run: fetch 400s until career fields are saved → Jobs empty state links to Settings; Settings is built first.

## Structure (from PLAN.md Files table)

```
ui/src/
  api.ts         types (Job, Summary, Settings, Stats, WatcherStatus) + typed fetch helpers; throw Error(body.error) on non-2xx
  usePoll.ts     30 s poll, pauses when document.hidden; returns {data, error, loading, refresh}
  App.tsx        top nav (Jobs · Apply queue · Dashboard · Profile · Settings, badges) + routes
  index.css      design tokens
  pages/         Jobs.tsx, Settings.tsx, Dashboard.tsx, Profile.tsx, Queue.tsx
  components/    JobCard.tsx (shared by both views), JobList.tsx, SwipeDeck.tsx, FilterBar.tsx, UndoToast.tsx, NewJobsPill.tsx
```

## Decisions

- **State:** `useState` + `usePoll`, no state library (PLAN.md). View toggle (swipe/list) in `localStorage`. Filters in component state — client-side only.
- **Actions are optimistic:** card leaves, request fires; Undo toast (5 s) calls `/undo`; on 409/error the card returns with a message.
- **Tokens:** extend `index.css` with surface, border, accent, focus ring, pros/cons colours (always paired with an icon or text, never colour alone), 4px spacing scale, two radii, system font stack. Plain CSS, no UI kit, no inline styles.
- **Accessibility:** `aria-label` on every action button, ← / → in swipe view, toast `role="status"`, visible focus, list view as the screen-reader fallback for swipe.
- **Dependencies:** `motion` (drag + spring physics, PLAN.md). `react-router-dom` per PLAN.md for back/forward; 5 flat routes could instead be ~15 lines over `history.pushState` — decide at plan time.
- **Components ≤ 200 lines; no business logic in the UI** (scores, pros/cons come from the API).

## Slice order

| # | Slice | Depends on | Where |
|---|---|---|---|
| 1 | Shell + Settings: tokens, nav, `api.ts`, `usePoll`, Settings form, Gmail connect, per-source watcher status, Check now | 4.1 | Phase 4.2 |
| 2 | Jobs list view: JobCard (score, pros/cons, "More"), PartialInfoBadge + PasteDescription (04.1 UI-SPEC), filter chips + title search, dismiss/queue, Undo toast, new-jobs pill, tab-title unread count | 4.1 | Phase 4.2 |
| 3 | Swipe view: motion drag deck (tilt, ✕/✓ stamp, fly-off threshold, spring back), keyboard, view toggle | 4.2 | Phase 4.3 |
| 4 | Dashboard stats (CSS bars) + stats gap fix | Phase 2 | v2 milestone |
| 5 | Profile page: CV upload, common questions, cover letter template, saved answers (API ready now — candidate to pull forward) | Phase 3 | v2 milestone |
| 6 | Apply queue page + Dashboard profile gaps | Phases 5-6 | v2 milestone |
| 7 | UI-05: `Start.bat`, `README.txt`, pre-built bundle | all | v2 milestone |

## Verification (every slice)

- `npx tsc --noEmit`, `npm run lint`, `npm run build` pass; Flask serves the build and a refresh on a sub-route loads.
- Checked in a browser at 320 / 768 / 1024 / 1440 px, light and dark, keyboard-only pass.
- Loading, empty, error states present for every data view.
