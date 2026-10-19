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
