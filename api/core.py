import html
import re
from typing import Dict, List, Optional, Tuple

BASE_SCORE = 50
TITLE_POINTS = 15


def normalise(text: str) -> str:
    return re.sub(r"[\W_]+", " ", (text or "").lower()).strip()


# --- text helpers -----------------------------------------------------------
# Every tag regex is bounded ([^<>]{0,1000}) so untrusted 200 KB descriptions stay linear (T-01-07).

_LI = re.compile(r"<li(?![A-Za-z])[^<>]{0,1000}>", re.I)
_BLOCK = re.compile(r"</?(?:p|div|br|h[1-6]|ul|ol|tr|section)(?![A-Za-z0-9])[^<>]{0,1000}>", re.I)
_TAG = re.compile(r"<[^<>]{0,1000}>")


def _text_lines(html_or_text: str) -> List[str]:
    t = _LI.sub("\n• ", html_or_text or "")
    t = _BLOCK.sub("\n", t)
    t = html.unescape(_TAG.sub("", t))
    lines = []
    for ln in t.split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        if ln[0] in "-*·•":
            ln = "• " + ln[1:].strip()
        lines.append(ln)
    return lines


# --- salary -----------------------------------------------------------------

_SYMBOLS = {"£": "GBP", "$": "USD", "€": "EUR", "GBP": "GBP", "USD": "USD", "EUR": "EUR"}
_MARK = r"(?:£|\$|€|GBP|USD|EUR)"
_NUM = r"\d(?:[\d.,]{0,11}\d)?"
_SALARY_RE = re.compile(
    r"(?P<m1>%s)?\s?(?P<n1>%s)(?P<k1>[kK](?![A-Za-z]))?"
    r"(?:\s{0,3}(?:[-–—]|to)\s{0,3}(?P<m2>%s)?\s?(?P<n2>%s)(?P<k2>[kK](?![A-Za-z]))?)?" % (_MARK, _NUM, _MARK, _NUM)
)
_ANY_MARK_RE = re.compile(r"£|\$|€|\b(?:GBP|USD|EUR)\b")
_PERIOD_RE = re.compile(r"\b(hour|hourly|hr|ph|day|daily|pd|month|monthly|pcm)\b", re.I)
_PERIOD_X = {"hour": 2000, "hourly": 2000, "hr": 2000, "ph": 2000,
             "day": 230, "daily": 230, "pd": 230, "month": 12, "monthly": 12, "pcm": 12}


def _num(s: str) -> float:
    # "," or "." followed by exactly three digits is a thousands mark; any other is a decimal mark.
    s = re.sub(r"[.,](?=\d{3}(?!\d))", "", s)
    return float(s.replace(",", "."))


def _parse_salary(text: str, require_symbol: bool) -> Optional[Tuple[str, int, Optional[str]]]:
    # ponytail: 1,000..1,000,000 annual window is how "$20 million" and "5 years" are skipped; widen if needed.
    for m in _SALARY_RE.finditer(text):
        if require_symbol and not m.group("m1"):
            continue
        try:
            a = _num(m.group("n1"))
            b = _num(m.group("n2")) if m.group("n2") else a
        except ValueError:
            continue
        if m.group("k2") and not m.group("k1") and m.group("n2"):
            a *= 1000  # "35-45k": the k carries to the first number
        if m.group("k1"):
            a *= 1000
        if m.group("k2"):
            b *= 1000
        window = text if not require_symbol else text[m.end():m.end() + 40]
        pm = _PERIOD_RE.search(window)
        annual = int(round((a + b) / 2 * (_PERIOD_X[pm.group(1).lower()] if pm else 1)))
        if not 1000 <= annual <= 1000000:
            continue
        mark = m.group("m1") or m.group("m2")
        if not mark and not require_symbol:
            am = _ANY_MARK_RE.search(text)
            mark = am.group(0) if am else None
        return m.group(0).strip(), annual, _SYMBOLS[mark] if mark else None
    return None


# --- type / remote / years / bullets ---------------------------------------

# ponytail: keyword guesses, first hit wins; "not a remote job" still reads as Remote. Source fields beat these.
_TYPES = [
    ("Full-time", ["full time", "permanent"]),
    ("Part-time", ["part time"]),
    ("Contract", ["contract", "contractor", "fixed term"]),
    ("Freelance", ["freelance"]),
    ("Internship", ["internship", "intern"]),
    ("Temporary", ["temporary", "temp"]),
]
_REMOTES = [
    ("Hybrid", ["hybrid"]),
    ("Remote", ["remote", "work from home", "wfh"]),
    ("On-site", ["on site", "onsite", "in office", "office based"]),
]
_YEARS_RE = re.compile(r"\b\d{1,2}\+?(?:\s?(?:-|–|to)\s?\d{1,2})?\s?(?:years?|yrs?)\b.{0,40}?experience", re.I)
_DUTY_HEAD = ["responsibilities", "what you ll do", "what you will do", "the role", "your role", "duties", "day to day"]
_WANT_HEAD = ["requirements", "qualifications", "what we re looking for", "what we are looking for", "about you",
              "who you are", "you have", "skills", "must have", "what you ll bring"]
_DUTY_KW = ["you will", "you ll"]
_WANT_KW = ["experience with", "experience in", "you have", "knowledge of", "degree", "proficien"]


def _first_label(norm: str, table: list) -> Optional[str]:
    padded = " %s " % norm
    for label, words in table:
        if any(" %s " % w in padded for w in words):
            return label
    return None


def _heading_kind(line: str) -> Optional[str]:
    if line.startswith("• ") or len(line) > 60:
        return None
    padded = " %s " % normalise(line)
    if any(" %s " % p in padded for p in _DUTY_HEAD):
        return "duty"
    if any(" %s " % p in padded for p in _WANT_HEAD):
        return "want"
    return None


def _bullets(lines: List[str]) -> Tuple[List[str], List[str]]:
    out = {"duty": [], "want": []}  # type: Dict[str, List[str]]
    for i, ln in enumerate(lines):
        kind = _heading_kind(ln)
        if not kind or out[kind]:
            continue
        for nxt in lines[i + 1:]:
            if nxt.startswith("• "):
                out[kind].append(nxt[2:])
                if len(out[kind]) == 3:
                    break
            elif out[kind] or _heading_kind(nxt):
                break
    # keyword fallback over sentences, kept with their end punctuation
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", "\n".join(lines)) if s.strip()]
    for kind, kws in (("duty", _DUTY_KW), ("want", _WANT_KW)):
        if not out[kind]:
            out[kind] = [s.lstrip("• ") for s in sentences if any(k in normalise(s) for k in kws)][:3]
    return out["duty"], out["want"]


def summarize(job: dict) -> dict:
    field = (job.get("salary") or "").strip()
    lines = _text_lines(job.get("description") or "")
    desc = " ".join(lines)
    parsed = _parse_salary(field, False) if field else _parse_salary(desc, True)
    title = normalise(job.get("title") or "")
    desc_norm = normalise(desc)
    duties, wants = _bullets(lines)
    ym = _YEARS_RE.search(desc)
    where = normalise("%s %s" % (job.get("title") or "", job.get("location") or ""))
    return {
        "salary_text": field or (parsed[0] if parsed else ""),
        "salary_annual": parsed[1] if parsed else None,
        "currency": parsed[2] if parsed else None,
        "job_type": job.get("job_type") or _first_label(title, _TYPES) or _first_label(desc_norm, _TYPES),
        "remote": job.get("remote") or _first_label(where, _REMOTES) or _first_label(desc_norm, _REMOTES),
        "years_experience": int(re.match(r"\d+", ym.group(0)).group(0)) if ym else None,
        "what_youd_do": duties,
        "what_they_want": wants,
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
