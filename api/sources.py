import base64
import html
import json
import threading
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode

from bs4 import BeautifulSoup, NavigableString

import core

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
REED_URL = "https://www.reed.co.uk/api/1.0/search"
PAGE_SIZE = 50  # first page only
USER_AGENT = "JobHelper/1.0 (local job search app)"
REMOTIVE_GAP_SECONDS = 31
REMOTIVE_JOB_TYPES = {
    "full_time": "Full-time",
    "part_time": "Part-time",
    "contract": "Contract",
    "freelance": "Freelance",
    "internship": "Internship",
}

# ponytail: process-wide throttle, fine for one process
_remotive_lock = threading.Lock()
_remotive_last = None  # monotonic time of the previous Remotive request


class SourceError(Exception):
    pass


def get_json(url: str, params: dict, headers: Optional[dict] = None):
    all_headers = {"User-Agent": USER_AGENT}
    all_headers.update(headers or {})
    req = urllib.request.Request(url + "?" + urlencode(params), headers=all_headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def fetch_remotive(fields: List[str]) -> List[dict]:
    global _remotive_last
    found = {}  # type: Dict[str, dict]
    try:
        for field in fields:
            with _remotive_lock:
                if _remotive_last is not None:
                    wait = REMOTIVE_GAP_SECONDS - (time.monotonic() - _remotive_last)
                    if wait > 0:
                        time.sleep(wait)
                try:
                    data = get_json(REMOTIVE_URL, {"search": field})
                finally:
                    _remotive_last = time.monotonic()
            for item in data["jobs"]:
                found.setdefault(item["url"], {
                    "url": item["url"],
                    "source": "remotive",
                    "title": item.get("title") or "",
                    "company": (item.get("company_name") or "").strip(),
                    "location": item.get("candidate_required_location") or "",
                    "salary": item.get("salary") or "",
                    "description": item.get("description") or "",
                    "job_type": REMOTIVE_JOB_TYPES.get(item.get("job_type")),
                    "remote": "Remote",
                })
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise SourceError("Remotive fetch failed: %s" % e)
    return list(found.values())


def _salary_text(lo, hi) -> str:
    lo, hi = lo or 0, hi or 0
    if not lo and not hi:
        return ""
    if lo and hi and round(lo) != round(hi):
        return "£{:,.0f} - £{:,.0f}".format(lo, hi)
    return "£{:,.0f}".format(lo or hi)


def fetch_reed(fields: List[str], api_key: str, location: str = "", min_salary: int = 0) -> List[dict]:
    # Basic auth: key as username, EMPTY password (the colon is required)
    auth = {"Authorization": "Basic " + base64.b64encode((api_key + ":").encode()).decode()}
    found = {}  # type: Dict[str, dict]
    try:
        for field in fields:
            params = {"keywords": field, "resultsToTake": PAGE_SIZE}
            if location:
                params["locationName"] = location
            if min_salary > 0:
                params["minimumSalary"] = min_salary
            for item in get_json(REED_URL, params, headers=auth)["results"]:
                found.setdefault(item["jobUrl"], {
                    "url": item["jobUrl"],
                    "source": "reed",
                    "title": item.get("jobTitle") or "",
                    "company": (item.get("employerName") or "").strip(),
                    "location": item.get("locationName") or "",
                    "salary": _salary_text(item.get("minimumSalary"), item.get("maximumSalary")),
                    "description": item.get("jobDescription") or "",
                    "job_type": None,
                    "remote": None,
                })
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        # message from the exception only: never params/headers/url (they carry the key)
        raise SourceError("Reed fetch failed: %s" % e)
    # ponytail: the same ad on two sources is not merged; dedupe is by URL only
    return list(found.values())


# --- full job description from the posting page (DETAIL-01, D-16) -------------

MAX_PAGE_BYTES = 2 * 1024 * 1024
BLOCKED_TEXT_CHARS = 200
BLOCKED_STATUSES = (403, 429, 503)
CHALLENGE_PHRASES = ("captcha", "verify you are human", "are you a robot", "just a moment",
                     "checking your browser", "unusual traffic", "access denied")


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    # urllib would follow a redirect to ftp:// (or a LAN host) on its own; refuse anything http_url refuses
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not core.http_url(newurl):
            raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def get_page(url: str) -> Tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # no Accept-Encoding: urllib cannot gunzip
    try:
        with urllib.request.build_opener(_SafeRedirect).open(req, timeout=20) as resp:
            if not core.http_url(resp.geturl()):
                return 0, ""
            raw = resp.read(MAX_PAGE_BYTES)
            try:
                return resp.status, raw.decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
            except LookupError:  # unknown charset name
                return resp.status, raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""


def _jobpostings(data, found: list) -> None:
    """Collect each JobPosting's description ("" when it has none) from a parsed JSON-LD value."""
    if isinstance(data, list):
        for x in data:
            _jobpostings(x, found)
    elif isinstance(data, dict):
        t = data.get("@type")
        if "JobPosting" in (t if isinstance(t, list) else [t]):
            d = data.get("description")
            found.append(d if isinstance(d, str) else "")
        for key in ("@graph", "mainEntity"):
            if key in data:
                _jobpostings(data[key], found)


def _block_text(el) -> str:
    parts = []
    for c in el.children:
        if type(c) is NavigableString:
            if c.strip():
                parts.append(c.strip())
        elif c.name == "p":
            parts.append(c.get_text(" ", strip=True))
        elif c.name == "li":
            parts.append("• " + c.get_text(" ", strip=True))
        elif c.name in ("ul", "ol"):
            parts += ["• " + li.get_text(" ", strip=True) for li in c.find_all("li", recursive=False)]
    return "\n".join(p for p in parts if p)


def extract_description(doc: str) -> Tuple[str, bool, bool]:
    """(plain text, came from a JobPosting description, a JobPosting block exists)."""
    soup = BeautifulSoup(doc or "", "html.parser")
    found = []  # type: list
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            _jobpostings(json.loads(tag.get_text(), strict=False), found)  # strict=False: raw newlines are common
        except ValueError:
            continue
    for raw in found:
        text = core.plain_text(html.unescape(raw))  # unescape first to expose the tags, then strip them
        if text:
            return text, True, True
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg"]):
        tag.decompose()
    # direct children only: scoring recursive text would always pick <body>
    best = max((_block_text(el) for el in soup.find_all(["div", "section", "article", "main", "ul", "body"])),
               key=len, default="")
    return best, False, bool(found)


def judge_page(code: int, doc: str) -> Optional[str]:
    """The readable description, or None when the page is blocked (D-16)."""
    if code in BLOCKED_STATUSES:
        return None
    text, _, has_jobposting = extract_description(doc)
    if not has_jobposting:  # a real posting page often mentions reCAPTCHA in a footer: only judge pages with no JobPosting
        soup = BeautifulSoup(doc or "", "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        visible = soup.get_text(" ").lower()  # includes the <title>
        if any(p in visible for p in CHALLENGE_PHRASES):
            return None
    return text if len(text) >= BLOCKED_TEXT_CHARS else None


def fetch_details(url: str) -> Tuple[str, str]:
    """("text", "ok") or ("", "blocked"); never raises on network trouble."""
    if not core.http_url(url):
        return "", "blocked"
    try:
        code, doc = get_page(url)
    except (OSError, ValueError):
        # ponytail: a fetch that fails while offline is final (blocked); set details_status back to 'pending' to retry
        code, doc = 0, ""
    text = judge_page(code, doc)
    return (text, "ok") if text is not None else ("", "blocked")  # 04-06: one Playwright retry goes here
