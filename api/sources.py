import json
import threading
import time
import urllib.request
from typing import Dict, List
from urllib.parse import urlencode

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
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


def get_json(url: str, params: dict):
    req = urllib.request.Request(url + "?" + urlencode(params), headers={"User-Agent": USER_AGENT})
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
