import base64
import json
import threading
import time
import urllib.request
from typing import Dict, List, Optional
from urllib.parse import urlencode, urlsplit

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
REED_URL = "https://www.reed.co.uk/api/1.0/search"
ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/gb/search/1"
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
    # ponytail: the same ad on Reed and Adzuna is not merged; dedupe is by URL only
    return list(found.values())


def _canonical(url: str) -> str:
    # Adzuna redirect_url query (se, v, utm_*) changes per call; keep scheme://host/path as the dedupe key
    u = urlsplit(url)
    return "%s://%s%s" % (u.scheme, u.netloc, u.path)


def _adzuna_type(item: dict) -> Optional[str]:
    if item.get("contract_type") == "contract":
        return "Contract"
    return {"full_time": "Full-time", "part_time": "Part-time"}.get(item.get("contract_time"))


def fetch_adzuna(fields: List[str], app_id: str, app_key: str, location: str = "", min_salary: int = 0) -> List[dict]:
    # ponytail: ~1 call per career field per poll vs a free tier reported near 250/day; no back-off
    found = {}  # type: Dict[str, dict]
    try:
        for field in fields:
            params = {"app_id": app_id, "app_key": app_key, "what": field, "results_per_page": PAGE_SIZE,
                      "sort_by": "date", "content-type": "application/json"}
            if location:
                params["where"] = location
            if min_salary > 0:
                params["salary_min"] = min_salary
            for item in get_json(ADZUNA_URL, params)["results"]:
                url = _canonical(item["redirect_url"])
                found.setdefault(url, {
                    "url": url,
                    "source": "adzuna",
                    "title": item.get("title") or "",
                    "company": ((item.get("company") or {}).get("display_name") or "").strip(),
                    "location": (item.get("location") or {}).get("display_name") or "",
                    # a predicted salary is a guess: never let it score as a real one
                    "salary": "" if str(item.get("salary_is_predicted")) == "1" else _salary_text(item.get("salary_min"), item.get("salary_max")),
                    "description": item.get("description") or "",
                    "job_type": _adzuna_type(item),
                    "remote": None,
                })
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        # message from the exception only: never params/url (they carry app_id and app_key)
        raise SourceError("Adzuna fetch failed: %s" % e)
    return list(found.values())
