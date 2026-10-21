---
phase: quick-261021-wez
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - api/sources.py
  - api/watcher.py
  - api/test_watcher.py
  - api/db.py
  - api/app.py
  - api/test_api.py
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
  - .planning/PROJECT.md
  - .planning/phases/02-watcher-and-more-sources/COVERAGE.md
autonomous: true
requirements: [SRC-03]

estimate:
  tokens: 40000
  raw_tokens: 40000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "A watcher poll with a saved Reed key and career fields calls Reed, then Remotive, and no other source"
    - "GET /api/settings returns no Adzuna keys, and a PUT that sends the old Adzuna keys gets 400 (save_settings rejects unknown keys)"
    - "Saving reed_api_key or career_fields still wakes the watcher; other settings still do not"
    - "api/ has no Adzuna code, settings or tests, and all three test files pass"
    - "SRC-03, the ROADMAP Phase 2 entry and the PROJECT sources line name Reed only; the 02-02 ROADMAP line says Adzuna was added then removed by this quick task"
    - "COVERAGE.md records Adzuna as removed and passes the api-coverage verify gate"
  artifacts:
    - path: "api/sources.py"
      provides: "Remotive and Reed adapters only"
    - path: "api/watcher.py"
      provides: "_sources yields reed (when keyed) then remotive"
    - path: ".planning/phases/02-watcher-and-more-sources/COVERAGE.md"
      provides: "Valid Reed coverage matrix with one Adzuna OPT-OUT row marking the removal"
  key_links:
    - from: "api/watcher.py _sources"
      to: "api/sources.py fetch_reed / fetch_remotive"
      via: "the only two yielded sources"
      pattern: "yield \"reed\"|yield \"remotive\""
    - from: "api/app.py WAKE_KEYS"
      to: "api/db.py DEFAULTS"
      via: "every wake key is a saveable setting"
      pattern: "WAKE_KEYS = frozenset"
---

<objective>
Remove Adzuna as a job source. The person will not use Adzuna yet; git history keeps the adapter and its tests for later.

Purpose: Phase 2 ships with Remotive and Reed only. Reed is already verified live against the real API (plan 02-04 is paused at its human-verify checkpoint). No dead source code, settings or Adzuna docs claims should be left behind.
Output: Adzuna code, settings keys and tests deleted from api/. REQUIREMENTS, ROADMAP, PROJECT and COVERAGE.md updated to Reed only.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.claude/CLAUDE.md
@api/sources.py
@api/watcher.py
@api/db.py

Facts the planner checked (2026-10-21):
- Baseline: test_core "ok: 30 tests", test_api "ok: 31 tests", test_watcher "ok: 21 tests". After this plan test_watcher drops 6 Adzuna tests, so it prints "ok: 15 tests". The other two counts do not change.
- `_canonical` (and the `urlsplit` import in sources.py) is only used by the Adzuna adapter. app.py has its own `urlsplit` import, which stays.
- `db.get_settings` copies only keys that are in DEFAULTS. `db.save_settings` raises "Unknown setting: <key>", which becomes HTTP 400.
- The working copy of api/app.py differs from HEAD only by CRLF line endings: `git diff --ignore-cr-at-eol` is empty. The repo stores LF.
- COVERAGE.md already fails the api-coverage gate: 5 rows have a capability cell over 80 characters. Task 3 rewrites it, which fixes that.
- Other dirty files in the tree (.gitignore, .planning/config.json, .planning/milestone.lock, .planning/state.json) are not part of this task. Stage files by explicit path and never use `git add -A`.
</context>

<tasks>

<!-- planner-discipline-allow: adzuna -->
<!-- planner-discipline-allow: Adzuna -->

<task type="tracer">
  <name>Task 1: Remove Adzuna from the fetch path end to end (sources, watcher, watcher tests)</name>
  <files>api/sources.py, api/watcher.py, api/test_watcher.py</files>
  <action>
In api/sources.py, delete ADZUNA_URL, `_canonical`, `_adzuna_type` and `fetch_adzuna`, together with their comments. `_canonical` has no other caller (`git grep -n _canonical` shows only sources.py), so it goes too. Change the `urllib.parse` import to import only `urlencode`. Keep `Optional` and `Dict`, because get_json and the other adapters still use them. Near the end of fetch_reed there is a ponytail comment that names Adzuna. Reword it to "# ponytail: the same ad on two sources is not merged; dedupe is by URL only". That limit still applies to Reed and Remotive, so the marker stays and only the removed source name goes. Do not change Remotive, Reed, get_json or _salary_text.

In api/watcher.py, delete the two-line Adzuna branch in `_sources`. It should now yield "reed" (only when reed_api_key is set) and then "remotive". Nothing else in the watcher changes.

In api/test_watcher.py, delete the following:
- ADZ, ADZUNA_BASE and the ADZUNA dict
- the Adzuna branch in fake_get_json, with its comment about the query string
- the adzuna_calls helper
- the six tests test_adzuna_request_params, test_adzuna_mapping, test_adzuna_canonical_url_dedupe, test_adzuna_failures_hide_keys, test_adzuna_needs_both_keys and test_adzuna_settings_keys

Rename test_three_sources_one_poll to test_two_sources_one_poll and change it as follows:
- save only career_fields ["python"] and reed_api_key "key"
- run one watcher._tick(None)
- collect the hosts from `calls` for ("reed.co.uk", "remotive.com") and assert they equal ["reed.co.uk", "remotive.com"]
- assert that watcher.STATUS shows ok True for "reed" and "remotive"
- assert that the set of sources in db.list_jobs is {"reed", "remotive"}

Keep it before test_watcher_thread_end_to_end. That test must stay last because its daemon thread runs until exit.

Add no new tests. The existing Reed tests already cover what the remaining sources need: key hiding, skip without a key, and failure isolation.
  </action>
  <verify>
    <automated>.venv/bin/python api/test_watcher.py | grep -x "ok: 15 tests" && .venv/bin/python api/test_api.py | grep -x "ok: 31 tests" && ! grep -ni adzuna api/sources.py api/watcher.py api/test_watcher.py</automated>
    <fails_when>non-zero exit, a traceback, the line "ok: 15 tests" or "ok: 31 tests" missing from output, or grep printing any matching line</fails_when>
  </verify>
  <done>sources.py holds only the Remotive and Reed adapters. A watcher poll calls Reed and then Remotive. test_watcher prints "ok: 15 tests", test_api still prints "ok: 31 tests", and the three files contain no Adzuna text.</done>
</task>

<task type="auto">
  <name>Task 2: Drop the Adzuna settings keys and wake keys</name>
  <files>api/db.py, api/app.py, api/test_api.py</files>
  <precondition>`git diff --ignore-cr-at-eol --quiet -- api/app.py` exits 0, so the uncommitted change to api/app.py is line endings only.</precondition>
  <action>
Start with api/app.py. Its working copy differs from HEAD only by CRLF line endings. Run `git checkout -- api/app.py` to restore the repo's LF endings, so the commit for this task is a one-line diff. Python reads either ending. If the precondition fails because the file has real content edits, stop and report instead of checking out. Record the line-ending restore in the SUMMARY.

In api/db.py, delete the two Adzuna keys from DEFAULTS. No migration is needed. get_settings copies only keys that are in DEFAULTS, so any Adzuna rows already stored in the person's settings table are ignored and never returned by GET /api/settings or GET /api/watcher.

In api/app.py, change WAKE_KEYS to frozenset({"reed_api_key", "career_fields"}). Leave the comment above it as it is.

In api/test_api.py, edit test_settings_save_wakes_watcher. Remove the two Adzuna bodies from the second (waking) tuple. Keep {"reed_api_key": "x"}, {"career_fields": ["python"]} and {"min_salary": 2, "career_fields": ["sql"]}. Leave the non-waking tuple unchanged.

save_settings rejects unknown keys ("Unknown setting: <key>" becomes 400), so a PUT that sends the old Adzuna keys now returns 400. That is accepted per the request. test_settings_rejects_bad_input already covers unknown keys with {"nope": 1}, so add no new test.
  </action>
  <verify>
    <automated>.venv/bin/python api/test_core.py | grep -x "ok: 30 tests" && .venv/bin/python api/test_api.py | grep -x "ok: 31 tests" && .venv/bin/python api/test_watcher.py | grep -x "ok: 15 tests" && ! grep -rni adzuna api/ && ! grep -q "$(printf '\r')" api/app.py</automated>
    <fails_when>non-zero exit, a traceback, any "ok: N tests" line missing or showing a different count, grep printing any match under api/, or api/app.py still containing CR characters</fails_when>
  </verify>
  <done>DEFAULTS and WAKE_KEYS contain no Adzuna keys. api/app.py has LF line endings, and its committed diff is the one WAKE_KEYS line. `grep -rni adzuna api/` prints nothing. The three suites print "ok: 30 tests", "ok: 31 tests" and "ok: 15 tests".</done>
</task>

<task type="auto">
  <name>Task 3: Update REQUIREMENTS, ROADMAP, PROJECT and COVERAGE.md to Reed only</name>
  <files>.planning/REQUIREMENTS.md, .planning/ROADMAP.md, .planning/PROJECT.md, .planning/phases/02-watcher-and-more-sources/COVERAGE.md</files>
  <action>
Use Edit with scoped replacements in the first three files. Never rewrite them whole.

.planning/REQUIREMENTS.md: change the SRC-03 line to "- [ ] **SRC-03**: `fetch_reed` returns jobs using the key saved in settings". Keep it unticked, and leave the traceability row "| SRC-03 | Phase 2 | Pending |" as it is.

.planning/ROADMAP.md: make these five line edits.
1. In the phase list, the Phase 2 summary becomes "Background watcher thread polling Remotive and Reed on configurable intervals".
2. The Phase 2 Goal becomes "The job feed refreshes itself in the background from Remotive and Reed".
3. Success criterion 1 becomes "After saving a Reed key in settings, Reed jobs appear in `GET /api/jobs`, scored and deduplicated".
4. The 02-02 plan line stays ticked and becomes "- [x] 02-02-PLAN.md — Adzuna (gb) adapter wired into the watcher, plus COVERAGE.md; Adzuna was later removed by quick task 261021-wez and the code stays in git history (wave 2)".
5. The 02-04 plan line stays unticked and becomes "- [ ] 02-04-PLAN.md — Real-process check plus human verification with a real Reed key (wave 3, checkpoint)".

Change nothing else in ROADMAP.md.

.planning/PROJECT.md: the Active line becomes "- [ ] Job sources (Remotive, Reed, Gmail alerts) fed by a watcher thread".

.planning/phases/02-watcher-and-more-sources/COVERAGE.md: rewrite the whole file. Write is fine here because the file is small and replaced in full. The current file fails the gate because some capability cells are over 80 characters. Every cell must stay pipe-free and on one line. The only allowed decisions are INTEGRATE and OPT-OUT, so "removed" goes in an OPT-OUT reason. Write these lines in order:
- the title "# API Coverage — Reed (Adzuna removed)"
- a blank line
- "> Full coverage by default. Opt-outs are explicit, reasoned decisions."
- "> Surface checked 2026-10-19 against https://www.reed.co.uk/developers/jobseeker. Adzuna was integrated in plan 02-02 and removed on 2026-10-21 by quick task 261021-wez; its code and tests are in git history."
- a blank line
- the header row "| capability | decision | reason |"
- the separator "|---|---|---|"

Then write these nine rows, one per line:
`| Reed job search (GET /api/1.0/search) | INTEGRATE | |`
`| Reed params: keywords, locationName, minimumSalary, resultsToTake=50 | INTEGRATE | |`
`| Reed HTTP Basic auth (key as username, empty password) | INTEGRATE | |`
`| Reed fields used by the job dict | INTEGRATE | jobUrl, jobTitle, employerName, locationName, minimumSalary, maximumSalary, jobDescription |`
`| Reed job details (GET /api/1.0/jobs/{id}) | OPT-OUT | one extra call per job; Phase 4 fetch_details reads the full listing page |`
`| Reed resultsToSkip paging | OPT-OUT | first page only per field each poll (D-06) |`
`| Reed filters other than keywords, location and minimum salary | OPT-OUT | the app ranks jobs by score instead of hiding them (distanceFromLocation, employerId, employerProfileId, permanent, contract, temp, partTime, fullTime, maximumSalary, postedBy*, graduate) |`
`| Reed fields: jobId, currency, date, expirationDate, applications | OPT-OUT | not used by scoring or the job dict |`
`| Adzuna (all endpoints, params and fields) | OPT-OUT | removed 2026-10-21 by quick task 261021-wez: not used yet; the adapter and its tests stay in git history |`

The planner measured every capability at 80 characters or fewer and every reason at 200 or fewer.

Do not touch 02-04-PLAN.md, any other PLAN, SUMMARY, RESEARCH or CONTEXT file, or the STATE.md decision log. They are history.
  </action>
  <verify>
    <automated>node "$HOME/.claude/gsd-core/bin/gsd-tools.cjs" check api-coverage.verify-pre .planning/phases/02-watcher-and-more-sources | grep -q '"passed": true' && ! grep -ni adzuna .planning/REQUIREMENTS.md .planning/PROJECT.md && test "$(grep -ci adzuna .planning/ROADMAP.md)" = 1 && grep -i adzuna .planning/ROADMAP.md | grep -q "02-02-PLAN.md" && git diff --quiet -- .planning/phases/02-watcher-and-more-sources/02-04-PLAN.md</automated>
    <fails_when>non-zero exit; the gate output shows "passed": false or lists errors; grep prints an Adzuna line from REQUIREMENTS.md or PROJECT.md; ROADMAP.md has an Adzuna line other than the single 02-02 line; or 02-04-PLAN.md shows a diff</fails_when>
  </verify>
  <done>SRC-03, the ROADMAP Phase 2 summary, goal, criterion 1 and the 02-04 line, and the PROJECT sources line all name Reed only, with no Adzuna. The 02-02 line records the add-then-remove. The api-coverage gate reports "passed": true for phase 02. 02-04-PLAN.md is unchanged.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser to PUT /api/settings | untrusted JSON body is validated by db.save_settings |
| settings table to GET /api/settings | stored values, including API keys, returned to the local UI |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-wez-01 | Information disclosure | settings table: stale Adzuna key rows left by an earlier save | low | accept | get_settings copies only DEFAULTS keys, so stale rows are never returned by GET /api/settings or GET /api/watcher. The DB is local and single-user, and the rows hold the person's own key. No migration code is added. |
| T-wez-02 | Tampering | PUT /api/settings with the removed keys | low | mitigate | The existing save_settings unknown-key check turns these into 400 before anything is written. test_settings_rejects_bad_input ({"nope": 1}) already locks this. |
| T-wez-03 | Information disclosure | removal of the Adzuna key-hiding tests | low | accept | No Adzuna code remains to leak a key. Reed key hiding stays covered by test_failure_text_never_contains_key. |
| T-wez-SC | Tampering | npm/pip/cargo installs | low | accept | This plan installs no packages. It only deletes code and edits docs. |
</threat_model>

<verification>
- `.venv/bin/python api/test_core.py && .venv/bin/python api/test_api.py && .venv/bin/python api/test_watcher.py` prints "ok: 30 tests", "ok: 31 tests" and "ok: 15 tests"
- `grep -rni adzuna api/` prints nothing
- the api-coverage gate passes for .planning/phases/02-watcher-and-more-sources
- `git status` shows only this plan's files staged in the task commits. .gitignore, .planning/config.json, .planning/milestone.lock and .planning/state.json stay as they were.
</verification>

<success_criteria>
- Adzuna is gone from api/, and Remotive plus Reed still fetch, score, dedupe and wake as before
- REQUIREMENTS, ROADMAP, PROJECT and COVERAGE.md describe Phase 2 as Remotive and Reed, and the 02-02 ROADMAP line records the removal
- Historical phase artifacts, 02-04-PLAN.md and the STATE.md decision log are untouched
</success_criteria>

<output>
Create `.planning/quick/261021-wez-remove-adzuna-job-source/261021-wez-SUMMARY.md` when done
</output>
