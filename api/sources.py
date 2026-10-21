import base64
import json
import threading
import time
import urllib.request
from typing import Dict, List, Optional
from urllib.parse import urlencode

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
