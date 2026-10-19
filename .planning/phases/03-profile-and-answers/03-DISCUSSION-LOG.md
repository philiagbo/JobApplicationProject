# Phase 3: Profile and Answers - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-19
**Phase:** 03-profile-and-answers
**Areas discussed:** Profile & CV upload, Turn on skills scoring, Answer matching & saving, Cover letter template

---

## Profile & CV upload

| Question | Options | Selected |
|----------|---------|----------|
| Profile storage | Single profile row/JSON · As answers (source=profile) · You decide | Single profile row/JSON |
| Re-upload behaviour | Fill empty only · Overwrite · Preview then confirm | Fill empty only |
| Keep CV file | Yes, under api/data/ · No | Yes |
| Skills extraction | Section + known list · Section only · List only | Section + known list |
| Common application facts | Seed as saved answers · Fixed profile fields · Neither | Seed as saved answers |
| Upload limits | PDF/DOCX, 10 MB, 400 · You decide | PDF/DOCX, 10 MB, 400 |

---

## Turn on skills scoring

| Question | Options | Selected |
|----------|---------|----------|
| Skills-matched rule | Pro + small boost · Pro only · Leave off | Pro + small boost |
| Experience-gap rule | Leave off · Profile years field · Estimate from CV dates | Leave off |
| Re-score on profile change | Re-score new jobs · Future jobs only | Re-score new jobs |
| Missing-requirements con | Leave off · From known-skills list | Leave off |

---

## Answer matching & saving

| Question | Options | Selected |
|----------|---------|----------|
| Option mapping | Exact → Yes/No prefix → fuzzy ≥0.85 → none · Always closest | Exact → prefix → fuzzy → none |
| Fuzzy tie | Highest ratio, then most recent · No match when ambiguous | Highest ratio, then most recent |
| Company rule | Question or answer · Answer only · Question only | Question or answer |
| Blocked save response | 400 with reason · 200 silently skipped | 400 with reason |

---

## Cover letter template

| Question | Options | Selected |
|----------|---------|----------|
| Template location | Default file + edits in settings · Setting only | Default file + edits in settings |
| Placeholders | Core set · Core + summary bits | Core set |
| Output | Plain text + GET /api/jobs/<id>/cover-letter · Function only | Plain text + endpoint |

---

## Claude's Discretion

- Profile storage shape, extra profile fields, known-skills list, seeded question wording, skills-boost values, CV parsing regexes, clearing `unanswered` on save.

## Deferred Ideas

- Experience-gap scoring rule.
- "Requirements the CV doesn't mention" con.
