import contextlib
import os
import sqlite3
import sys
import tempfile
import time

os.environ["JOBHELPER_DB"] = os.path.join(tempfile.mkdtemp(), "boot.db")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app  # noqa: E402
import db  # noqa: E402
import sources  # noqa: E402
import watcher  # noqa: E402

sources.REMOTIVE_GAP_SECONDS = 0
watcher.TICK_SECONDS = 0.05

calls = []  # (url, params, headers)
FAIL = set()  # URL substrings that raise OSError

REED_ITEMS = [
    {"jobId": 1, "jobUrl": "https://www.reed.co.uk/jobs/a/1", "jobTitle": "Data Analyst", "employerName": " Acme ",
     "locationName": "London", "minimumSalary": 50000, "maximumSalary": 60000, "jobDescription": "analyse data"},
    {"jobId": 2, "jobUrl": "https://www.reed.co.uk/jobs/b/2", "jobTitle": "Analyst", "employerName": "Beta",
     "locationName": "Leeds", "jobDescription": "no salary shown"},
]


def fake_get_json(url, params, headers=None):
    calls.append((url, params, headers))
    if any(f in url for f in FAIL):
        raise OSError("down")
    if "reed.co.uk" in url:
        return {"results": REED_ITEMS}
    if "remotive.com" in url:
        slug = params["search"].replace(" ", "-")
        return {"jobs": [{"url": "https://remotive.com/remote-jobs/" + slug, "title": "Remote " + params["search"],
                          "company_name": "Rem", "job_type": "full_time", "description": "x"}]}
    raise AssertionError(url)


sources.get_json = fake_get_json


def fresh():
    os.environ["JOBHELPER_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
    db.init_db()
    del calls[:]
    FAIL.clear()
    watcher.STATUS.clear()
    watcher.WAKE.clear()


def save(**changes):
    with contextlib.closing(db.connect()) as conn:
        db.save_settings(conn, changes)


def test_import_does_not_start_watcher():
    assert watcher._thread is None


def test_watcher_thread_end_to_end():
    # keep this the last test: the daemon thread runs until the process exits
    fresh()
    c = app.app.test_client()
    assert c.put("/api/settings", json={"career_fields": ["data analyst"], "reed_api_key": "key"}).status_code == 200
    real, failures = db.get_settings, []

    def flaky(conn):
        if not failures:
            failures.append(1)
            raise sqlite3.OperationalError("database is locked")
        return real(conn)

    db.get_settings = flaky
    watcher.log.disabled = True  # keep the expected traceback out of test output
    try:
        watcher.start()
        deadline, reed = time.monotonic() + 5, []
        while not reed and time.monotonic() < deadline:
            reed = [j for j in c.get("/api/jobs").get_json() if j["source"] == "reed"]
            time.sleep(0.05)
        assert reed, "no reed job appeared"
        assert len(failures) == 1
        assert watcher._thread.is_alive()
        st = watcher.status()
        assert st["running"] is True and st["sources"]["reed"]["ok"] is True
        first = [x for x in calls if "reed.co.uk" in x[0]][0]
        assert first[2]["Authorization"] == "Basic a2V5Og=="
        assert [j for j in reed if j["title"] == "Data Analyst"][0]["summary"]["salary_annual"] == 55000
        deadline = time.monotonic() + 5
        while watcher.FETCH_LOCK.locked() and time.monotonic() < deadline:
            time.sleep(0.02)
        r = c.post("/api/fetch")
        assert r.status_code == 200
        assert r.get_json() == {"new": 0, "by_source": {"reed": 0, "remotive": 0}, "errors": {}}
        thread = watcher._thread
        watcher.start()
        assert watcher._thread is thread
    finally:
        db.get_settings = real
        watcher.log.disabled = False


if __name__ == "__main__":
    tests = [f for n, f in list(globals().items()) if n.startswith("test_") and callable(f)]
    for t in tests:
        t()
    print("ok: %d tests" % len(tests))
