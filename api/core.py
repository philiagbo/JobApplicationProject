import re
from typing import Dict, List, Optional, Tuple

BASE_SCORE = 50
TITLE_POINTS = 15


def normalise(text: str) -> str:
    return re.sub(r"[\W_]+", " ", (text or "").lower()).strip()


def summarize(job: dict) -> dict:
    # Plan 01-02 completes salary parsing, keyword fallbacks, years and bullets here.
    return {
        "salary_text": (job.get("salary") or "").strip(),
        "salary_annual": None,
        "currency": None,
        "job_type": job.get("job_type") or None,
        "remote": job.get("remote") or None,
        "years_experience": None,
        "what_youd_do": [],
        "what_they_want": [],
    }


def score(job: dict, settings: dict, profile: Optional[dict] = None) -> Tuple[int, List[str], List[str]]:
    # profile is accepted and ignored (D-05).
    pros = []  # type: List[str]
    cons = []  # type: List[str]
    total = BASE_SCORE
    title_tokens = set(normalise(job.get("title", "")).split())
    for field in settings.get("career_fields", []):
        tokens = normalise(field).split()
        if tokens and all(t in title_tokens for t in tokens):
            total += TITLE_POINTS
            pros.append("Title matches your field '%s'" % field)
            break
    return max(0, min(100, total)), pros, cons
