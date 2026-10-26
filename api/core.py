import datetime
import difflib
import html
import ipaddress
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlsplit

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


def plain_text(html_or_text: str) -> str:
    return "\n".join(_text_lines(html_or_text))


# ponytail: tests flip this to reach a loopback fixture server
ALLOW_PRIVATE_HOSTS = False


def http_url(url) -> bool:
    """True for an http(s) link to a public host; mail links must never point the app at local files or the LAN."""
    if not isinstance(url, str):
        return False
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        return False
    if parts.scheme.lower() not in ("http", "https") or not host:
        return False
    if ALLOW_PRIVATE_HOSTS:
        return True
    if host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # ponytail: no DNS resolution, so a public name pointing at a private address is not caught; local single-user app
        return True
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified)


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


SALARY_ABOVE_POINTS = 30
REMOTE_POINTS = 10
HYBRID_POINTS = 5
EXCLUDED_POINTS = 25
SKILL_POINTS_EACH = 2
SKILL_POINTS_CAP = 10  # below TITLE_POINTS, so salary stays the heaviest rule


def k(n: float) -> str:
    return "£" + format(n / 1000, ".3g") + "k"


def score(job: dict, settings: dict, profile: Optional[dict] = None) -> Tuple[int, List[str], List[str]]:
    # D-08: no experience-gap or missing-requirements rules; only the skills rule below reads the profile.
    pros = []  # type: List[str]
    cons = []  # type: List[str]
    total = BASE_SCORE
    summary = job.get("summary") or summarize(job)

    # Salary is the heaviest rule (D-02); only GBP is comparable (D-10).
    annual, floor = summary.get("salary_annual"), settings.get("min_salary") or 0
    if annual is None:
        cons.append("Salary not listed")
    elif floor > 0:
        if summary.get("currency") != "GBP":
            cons.append("Pays %s, can't compare with your %s minimum (not in £)" % (summary.get("salary_text"), k(floor)))
        elif annual >= floor:
            total += SALARY_ABOVE_POINTS
            pros.append("Pays %s, %s your %s minimum" % (k(annual), "meets" if annual == floor else "above", k(floor)))
        else:
            total -= 15 + round(30 * min((floor - annual) / floor / 0.5, 1))
            cons.append("Pays %s, below your %s minimum" % (k(annual), k(floor)))

    title_tokens = set(normalise(job.get("title", "")).split())
    for field in settings.get("career_fields", []):
        tokens = normalise(field).split()
        if tokens and all(t in title_tokens for t in tokens):
            total += TITLE_POINTS
            pros.append("Title matches your field '%s'" % field)
            break

    if summary.get("remote") == "Remote":
        total += REMOTE_POINTS
        pros.append("Fully remote")
    elif summary.get("remote") == "Hybrid":
        total += HYBRID_POINTS
        pros.append("Hybrid working")

    hits = matched_skills((profile or {}).get("skills") or [], job)
    if hits:
        total += min(SKILL_POINTS_EACH * len(hits), SKILL_POINTS_CAP)
        pros.append("Matches %d of your skills: %s%s" % (len(hits), ", ".join(hits[:3]), "…" if len(hits) > 3 else ""))

    # Excluded words cost points but never hide the job (D-04); one penalty however many hit.
    haystack = " %s %s " % (normalise(job.get("title", "")), normalise(" ".join(_text_lines(job.get("description") or ""))))
    hits = [w for w in settings.get("excluded_words", []) if normalise(w) and " %s " % normalise(w) in haystack]
    for w in hits:
        cons.append("Mentions excluded word '%s'" % w)
    if hits:
        total -= EXCLUDED_POINTS

    return max(0, min(100, int(total))), pros, cons


# --- saved answers ----------------------------------------------------------

FUZZY_MIN = 0.85
MAX_ANSWER_CHARS = 300
MAX_QUESTION_CHARS = 500
_LEGAL = {"ltd", "limited", "plc", "inc", "llc", "llp", "corp", "corporation", "co", "uk"}


def answer_block_reason(question: str, answer: str, company: Optional[str] = "") -> Optional[str]:
    """Why an answer must not be saved for reuse (D-12), or None. Whole-word match, like excluded words in score."""
    if not (answer or "").strip():
        return None
    if len(answer.strip()) > MAX_ANSWER_CHARS:
        return "longer than %d characters" % MAX_ANSWER_CHARS
    words = normalise(company or "").split()
    name = " ".join([w for w in words if w not in _LEGAL] or words)
    if len(name) >= 2 and any(" %s " % name in " %s " % normalise(t) for t in (question, answer)):
        return "mentions the company"
    return None


def _ratio(a: str, b: str) -> float:
    # autojunk=False: the default junk heuristic distorts ratios on strings of 200+ characters
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def _polarity(norm_text: str) -> Optional[str]:
    first = norm_text.split(" ")[0]
    return first if first in ("yes", "no") else None


def map_option(answer: str, options: List[str]) -> Optional[str]:
    """Pick the option a saved answer means (D-11); None when unclear, never a guess."""
    na = normalise(answer)
    if not na:
        return None
    norm = [(o, normalise(o)) for o in options]
    exact = next((o for o, n in norm if n == na), None)
    if exact:
        return exact
    pol = _polarity(na)
    same = [o for o, n in norm if pol and _polarity(n) == pol]
    if len(same) == 1:
        return same[0]
    best = max(norm, key=lambda p: _ratio(na, p[1]), default=None)
    return best[0] if best and _ratio(na, best[1]) >= FUZZY_MIN else None


def find_answer(label: str, answers: List[dict], options: Optional[List[str]] = None) -> Optional[dict]:
    """Best saved answer for a form label: exact first, then fuzzy >= FUZZY_MIN (D-10). answers hold normalised questions."""
    q = normalise(label)[:MAX_QUESTION_CHARS]
    rows = [a for a in answers if (a["answer"] or "").strip()]
    if not q or not rows:
        return None
    # an exact match scores 1.0, so one max covers exact-then-fuzzy; ties go to newest updated_at, then highest id
    hit = max(rows, key=lambda a: (_ratio(q, a["question"]), a["updated_at"], a["id"]))
    ratio = _ratio(q, hit["question"])
    if ratio < FUZZY_MIN:
        return None
    option = map_option(hit["answer"], options) if options else None
    if options and option is None:
        return None
    return {"id": hit["id"], "question": hit["question"], "answer": hit["answer"],
            "ratio": round(ratio, 3), "option": option}


# --- CV extraction ----------------------------------------------------------

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){1,5}")
_LINKEDIN = re.compile(r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/[\w%-]+", re.I)
_PHONE = re.compile(r"(?<![\w+])\+?\(?\d[\d \t().-]{7,18}\d(?!\w)")  # no \s: a number must not span lines
_NOT_NAME = {"cv", "resume", "curriculum vitae", "profile", "personal details", "contact"}
_YEAR = re.compile(r"^(?:19|20)\d\d$")
_NAME_WORD = re.compile(r"^[^\W\d_](?:[^\W\d_]|['.\-])*$")
_SKILL_HEADS = {"skills", "key skills", "core skills", "technical skills", "skills and tools", "skills summary"}
_SKILL_STOPS = {"experience", "work experience", "employment", "work history", "education", "projects",
                "certifications", "references", "interests", "summary", "profile", "languages"}
_SKILL_SPLIT = re.compile(r"[,;•·|]")
_PAREN_TAIL = re.compile(r"\s*\([^()]{0,60}\)\s*$")


def has_term(text: str, term: str) -> bool:
    # not padded-normalise matching: that turns C++ and C# into the same token
    return re.search(r"(?<![A-Za-z0-9+#])%s(?![A-Za-z0-9+#])" % re.escape(term), text or "", re.I) is not None


def dedupe_skills(skills: List[str]) -> List[str]:
    seen, out = set(), []
    for s in skills:
        s = s.strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


def merge_profile(current: dict, extracted: dict) -> dict:
    """Fill only empty fields; skills are merged with the existing spelling first (D-02)."""
    out = {}
    for key in ("name", "email", "phone", "linkedin"):
        out[key] = current.get(key, "") if (current.get(key) or "").strip() else extracted.get(key, "")
    out["skills"] = dedupe_skills(list(current.get("skills") or []) + list(extracted.get("skills") or []))
    return out


def _extract_name(lines: List[str]) -> str:
    # ponytail: a one-word name followed by a job-title line yields the job title; the profile is editable
    # and an upload never overwrites a filled field.
    for line in lines[:8]:
        words = line.split()
        if (2 <= len(words) <= 4 and len(line) <= 40 and normalise(line) not in _NOT_NAME
                and all(_NAME_WORD.match(w) for w in words)):
            return line.title() if line.isupper() else line
    return ""


def _extract_phone(text: str) -> str:
    for m in _PHONE.finditer(text):
        s = m.group().strip()
        digits = re.findall(r"\d+", s)
        if 10 <= sum(len(d) for d in digits) <= 13 and not all(_YEAR.match(d) for d in digits):
            return s
    return ""


def _extract_skills(text: str, lines: List[str], known_skills: List[str]) -> List[str]:
    found = [s for s in known_skills if has_term(text, s)]
    section = []  # type: List[str]
    for i, line in enumerate(lines):
        if len(line) <= 40 and line[0] not in "-*·•" and normalise(line) in _SKILL_HEADS:
            for ln in lines[i + 1:i + 13]:
                if normalise(ln) in _SKILL_STOPS:
                    break
                for item in _SKILL_SPLIT.split(ln):
                    item = _PAREN_TAIL.sub("", item.strip(" \t-*"))
                    if item and len(item) <= 40 and len(item.split()) <= 4:
                        section.append(item)
            break
    return dedupe_skills(found + section)


def extract_profile(text: str, known_skills: Optional[List[str]] = None) -> dict:
    # known_skills is the user's known_skills setting, matched across the whole CV (empty by default)
    # ponytail: a LinkedIn URL behind link text (PDF annotations, DOCX relationships) is not seen;
    # scan the PDF /Annots URIs for linkedin.com/in if that matters.
    text = text or ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    email = _EMAIL.search(text)
    li = _LINKEDIN.search(text)
    linkedin = li.group() if li else ""
    if linkedin and not linkedin.lower().startswith("http"):
        linkedin = "https://" + linkedin
    return {"name": _extract_name(lines), "email": email.group() if email else "",
            "phone": _extract_phone(text), "linkedin": linkedin, "skills": _extract_skills(text, lines, known_skills or [])}


# --- skills match and cover letter ------------------------------------------

def matched_skills(profile_skills: List[str], job: dict) -> List[str]:
    text = "%s %s" % (job.get("title") or "", " ".join(_text_lines(job.get("description") or "")))
    return [s for s in profile_skills if has_term(text, s)]


_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
# not strftime("%B"): month names follow the Windows locale
_MONTHS = ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"]


def _join_and(items: List[str]) -> str:
    return ", ".join(items[:-1]) + " and " + items[-1] if len(items) > 1 else "".join(items)


def cover_letter(profile, job, template, today=None):
    """Fill the template from the profile and job (D-16). Only {known} names change; one regex pass, never str.format."""
    d = today or datetime.date.today()
    skills = profile.get("skills") or []
    values = {"name": profile.get("name") or "", "email": profile.get("email") or "",
              "phone": profile.get("phone") or "",
              "company": (job.get("company") or "").strip(), "job_title": (job.get("title") or "").strip(),
              "top_skills": _join_and((matched_skills(skills, job) or skills)[:3]),
              "date": "%d %s %d" % (d.day, _MONTHS[d.month - 1], d.year)}
    return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), template)
