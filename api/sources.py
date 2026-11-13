import base64
import concurrent.futures
import html
import http.client
import json
import threading
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode

from bs4 import BeautifulSoup, NavigableString

import browser
import core

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
REED_URL = "https://www.reed.co.uk/api/1.0/search"
REED_JOB_URL = "https://www.reed.co.uk/api/1.0/jobs/%d"
REED_LOOKUP_RESULTS = 100  # Reed's resultsToTake maximum
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


def _reed_auth(api_key: str) -> dict:
    # Basic auth: key as username, EMPTY password (the colon is required)
    return {"Authorization": "Basic " + base64.b64encode((api_key + ":").encode()).decode()}


def fetch_reed(fields: List[str], api_key: str, location: str = "", min_salary: int = 0) -> List[dict]:
    auth = _reed_auth(api_key)
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


def reed_lookup(job: dict, api_key: str) -> Optional[dict]:
    """The Reed ad that is this LinkedIn/Indeed alert job: {"text", "salary", "job_type"} or None (D-01, D-04).
    At most two searches and one details request; only ever the Reed API, never the alert site (D-18)."""
    if not core.company_key(job.get("company")) or not core.normalise(job.get("title") or ""):
        return None
    auth = _reed_auth(api_key)
    title, company = job["title"], job["company"]
    try:
        best = None
        for keywords in ("%s %s" % (title, company), title):
            results = get_json(REED_URL, {"keywords": keywords, "resultsToTake": REED_LOOKUP_RESULTS}, headers=auth)["results"]
            best = core.reed_match(job, results)
            if best:
                break
        if not best:
            return None
        d = get_json(REED_JOB_URL % int(best["jobId"]), {}, headers=auth)  # int(): an API value never enters the path as text
        text = core.plain_text(html.unescape(d.get("jobDescription") or ""))
        if not text:
            return None
        if d.get("partTime") is True and d.get("fullTime") is not True:
            job_type = "Part-time"
        else:
            job_type = core._first_label(core.normalise("%s %s" % (d.get("jobType") or "", d.get("contractType") or "")), core._TYPES)
        return {"text": text, "salary": _salary_text(d.get("minimumSalary"), d.get("maximumSalary")), "job_type": job_type}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        # message from the exception only: never params/headers/url (they carry the key)
        raise SourceError("Reed lookup failed: %s" % e)


# --- full job description from the posting page (DETAIL-01, D-16) -------------

MAX_PAGE_BYTES = 2 * 1024 * 1024
BLOCKED_TEXT_CHARS = 200
GONE_STATUSES = (404, 410)
CHALLENGE_PHRASES = ("captcha", "verify you are human", "are you a robot", "just a moment",
                     "checking your browser", "unusual traffic", "access denied")


class RedirectRefused(Exception):
    """A hop pointed somewhere fetchable() refuses; the browser must never be handed this URL."""


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    # urllib would follow a redirect to ftp://, a LAN host or LinkedIn/Indeed on its own; refuse every such hop
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not core.fetchable(newurl):
            raise RedirectRefused(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def get_page(url: str) -> Tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # no Accept-Encoding: urllib cannot gunzip
    try:
        with urllib.request.build_opener(_SafeRedirect).open(req, timeout=20) as resp:
            if not core.fetchable(resp.geturl()):
                raise RedirectRefused(resp.geturl())
            raw = resp.read(MAX_PAGE_BYTES)
            try:
                return resp.status, raw.decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
            except LookupError:  # unknown charset name
                return resp.status, raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if 300 <= e.code < 400:  # urllib refused the hop itself (file:// target, redirect loop): the browser must not try
            raise RedirectRefused(e.filename)
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
        except (ValueError, RecursionError):
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
    if not 200 <= code < 300:  # 404 / 410 / 5xx pages are never a job description
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
    if not core.fetchable(url):
        return "", "blocked"
    try:
        code, doc = get_page(url)
    except RedirectRefused:
        return "", "blocked"  # never hand a refused target to the browser
    except (OSError, ValueError, http.client.HTTPException):
        # ponytail: a fetch that fails while offline is final (blocked); set details_status back to 'pending' to retry
        code, doc = 0, ""
    if code in GONE_STATUSES:
        return "", "blocked"  # a browser will not bring an expired listing back
    text = judge_page(code, doc)
    if text is None:  # DETAIL-02: one retry in the real browser, then blocked
        try:
            code, doc = browser.fetch_page(url)
        except (browser.BrowserUnavailable, browser.Error, concurrent.futures.TimeoutError, OSError):
            return "", "blocked"
        text = judge_page(code, doc)
    return (text, "ok") if text is not None else ("", "blocked")
