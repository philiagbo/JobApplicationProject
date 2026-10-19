---
phase: "3"
slug: "profile-and-answers"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-19"
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Plain-assert scripts, no pytest (project convention) |
| **Config file** | none |
| **Quick run command** | `.venv/bin/python api/test_core.py` |
| **Full suite command** | `.venv/bin/python api/test_core.py && .venv/bin/python api/test_api.py` (+ `&& .venv/bin/python api/test_watcher.py` once Phase 2 has created it) |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python api/test_core.py` (plus `api/test_api.py` when the task touches `db.py`/`app.py`/`cv.py`)
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

Filled in by the planner/executor per task. Requirement → test mapping (from RESEARCH.md):

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| PROF-01 | `extract_profile` pulls name/email/phone/LinkedIn/skills from text | unit | `.venv/bin/python api/test_core.py` | ✅ edit | ⬜ pending |
| PROF-01 | PDF/DOCX upload pre-fills profile; bad file → 400; hand edits kept | API | `.venv/bin/python api/test_api.py` | ✅ edit | ⬜ pending |
| PROF-02 | `/api/answers` list/create/upsert/edit/delete, 404/409/400 paths | API | `.venv/bin/python api/test_api.py` | ✅ edit | ⬜ pending |
| PROF-03 | `find_answer` exact → fuzzy ≥ 0.85 → option mapping, `None` on miss | unit | `.venv/bin/python api/test_core.py` | ✅ edit | ⬜ pending |
| PROF-04 | company-name / >300-char answers blocked, no row written | unit + API | full suite | ✅ edit | ⬜ pending |
| PROF-05 | `cover_letter` fills placeholders via `re.sub`; route 200/404 | unit + API | full suite | ✅ edit | ⬜ pending |
| D-07/D-09 | skills scoring rule; profile change re-scores `new` jobs only | unit + API | full suite | ✅ edit | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Task-level map (from the plans)

| Task | Plan | Wave | Requirement / Decision | Automated Command | Status |
|------|------|------|------------------------|-------------------|--------|
| 03-01 T1 | 01 | 1 | package gate (T-03-SC) | blocking-human checkpoint, no command | ⬜ pending |
| 03-01 T2 | 01 | 1 | PROF-01 deps | `.venv/bin/python -c "import pypdf, docx"` + test_core + test_api | ⬜ pending |
| 03-02 T1 (tracer) | 02 | 1 | PROF-02/03/04 | `.venv/bin/python api/test_core.py && .venv/bin/python api/test_api.py` | ⬜ pending |
| 03-02 T2 | 02 | 1 | PROF-03, PROF-04, D-10..D-12 | `.venv/bin/python api/test_core.py` | ⬜ pending |
| 03-02 T3 | 02 | 1 | PROF-02, D-05, D-13, D-14 | `.venv/bin/python api/test_core.py && .venv/bin/python api/test_api.py` | ⬜ pending |
| 03-03 T1 (tracer) | 03 | 2 | PROF-01, D-01, D-03 | `.venv/bin/python api/test_core.py && .venv/bin/python api/test_api.py` | ⬜ pending |
| 03-03 T2 | 03 | 2 | PROF-01, D-02, D-04 | `.venv/bin/python api/test_core.py` | ⬜ pending |
| 03-03 T3 | 03 | 2 | PROF-01, D-01..D-03, D-06 | `.venv/bin/python api/test_core.py && .venv/bin/python api/test_api.py` | ⬜ pending |
| 03-04 T1 (tracer) | 04 | 3 | PROF-05, D-15..D-17 | `.venv/bin/python api/test_core.py && .venv/bin/python api/test_api.py` | ⬜ pending |
| 03-04 T2 | 04 | 3 | D-07, D-08, D-09 | `.venv/bin/python api/test_core.py && .venv/bin/python api/test_api.py` | ⬜ pending |
| 03-04 T3 | 04 | 3 | PROF-05, D-15..D-17 | `.venv/bin/python api/test_core.py && .venv/bin/python api/test_api.py` | ⬜ pending |

Every implementation task has an automated verify, so no 3 consecutive tasks lack one. Wave 0 items are covered: requirements and install (03-01 T2), `api/data/` gitignore (03-03 T3), `api/cover_letter.txt` (03-04 T1), PDF and DOCX builders (03-03 T1 and T3), and the rewrite of `test_score_profile_ignored` (03-04 T2).

---

## Wave 0 Requirements

- [ ] `api/requirements.txt` adds `pypdf`, `python-docx`; `.venv/bin/pip install -r api/requirements.txt` (behind human-verify checkpoint)
- [ ] `.gitignore` adds `api/data/`
- [ ] `api/cover_letter.txt` default template
- [ ] PDF/DOCX builder helpers in `api/test_api.py`
- [ ] Rewrite obsolete `test_score_profile_ignored` in `api/test_core.py`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real-world CV parses sensibly | PROF-01 | Real CV layouts vary; tests use synthetic files | Upload a real PDF and DOCX CV via `POST /api/profile/cv`, check `GET /api/profile` fields |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
