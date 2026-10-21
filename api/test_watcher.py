import contextlib
import logging
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


class Records(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.records = []

    def emit(self, record):
        self.records.append(record)


@contextlib.contextmanager
def captured():
    h = Records()
    watcher.log.addHandler(h)
    try:
        yield h.records
    finally:
        watcher.log.removeHandler(h)


def reed_calls():
    return [c for c in calls if "reed.co.uk" in c[0]]


def test_poll_interval_defaults():
    fresh()
    assert db.DEFAULTS["gmail_poll_minutes"] == 5 and db.DEFAULTS["api_poll_minutes"] == 60
    with contextlib.closing(db.connect()) as conn:
        s = db.get_settings(conn)
    assert s["gmail_poll_minutes"] == 5 and s["api_poll_minutes"] == 60


def test_reed_request_params():
    fresh()
    sources.fetch_reed(["data analyst", "python"], "key", "London", 40000)
    got = reed_calls()
    assert len(got) == 2
    for (url, params, headers), field in zip(got, ["data analyst", "python"]):
        assert url == sources.REED_URL
        assert params == {"keywords": field, "resultsToTake": 50, "locationName": "London", "minimumSalary": 40000}
        assert headers["Authorization"] == "Basic a2V5Og=="
    del calls[:]
    sources.fetch_reed(["python"], "key")
    assert set(reed_calls()[0][1]) == {"keywords", "resultsToTake"}


def test_reed_mapping_and_salary():
    fresh()
    jobs = sources.fetch_reed(["a", "b"], "key")
    assert len(jobs) == 2  # same jobUrls returned for both fields
    keys = {"url", "source", "title", "company", "location", "salary", "description", "job_type", "remote"}
    assert all(set(j) == keys and j["source"] == "reed" for j in jobs)
    assert jobs[0]["company"] == "Acme" and jobs[0]["salary"] == "\u00a350,000 - \u00a360,000"
    assert jobs[1]["salary"] == ""
    assert sources._salary_text(45000, None) == "\u00a345,000"
    assert sources._salary_text(None, None) == ""


def test_reed_failures_raise_source_error():
    fresh()
    FAIL.add("reed.co.uk")
    for _ in range(2):
        try:
            sources.fetch_reed(["python"], "key")
            assert False, "expected SourceError"
        except sources.SourceError as e:
            assert str(e).startswith("Reed fetch failed")
        FAIL.clear()
        sources.get_json = lambda url, params, headers=None: {"oops": []}
    sources.get_json = fake_get_json


def test_tick_polls_immediately():
    fresh()
    save(career_fields=["data analyst"], reed_api_key="key")
    assert isinstance(watcher._tick(None), float)
    assert len(reed_calls()) == 1 and len(calls) == 2


def test_tick_quiet_without_fields():
    fresh()
    with captured() as records:
        assert watcher._tick(None) is None
    assert calls == [] and records == []


def test_interval_change_applies_without_restart():
    fresh()
    save(career_fields=["python"], api_poll_minutes=60)
    watcher.SECONDS_PER_MINUTE = 0.01
    try:
        last = watcher._tick(None)
        n = len(calls)
        assert watcher._tick(last) == last and len(calls) == n
        save(api_poll_minutes=1)
        time.sleep(0.02)
        assert watcher._tick(last) != last and len(calls) > n
    finally:
        watcher.SECONDS_PER_MINUTE = 60


def test_failing_source_isolated_and_retried():
    fresh()
    save(career_fields=["python"], reed_api_key="key")
    FAIL.add("reed.co.uk")
    with captured() as records:
        watcher._tick(None)
    st = watcher.STATUS
    assert st["reed"]["ok"] is False and st["reed"]["error"].startswith("Reed fetch failed")
    assert st["remotive"]["ok"] is True and st["remotive"]["new"] == 1
    assert [r.levelno for r in records] == [logging.WARNING]
    n = len(reed_calls())
    watcher.WAKE.set()
    watcher._tick(time.monotonic())
    assert len(reed_calls()) == n + 1


def test_unexpected_source_error_isolated():
    fresh()
    save(career_fields=["python"], reed_api_key="key")

    def boom(url, params, headers=None):
        if "reed.co.uk" in url:
            raise RuntimeError("secret detail")
        return fake_get_json(url, params, headers)

    sources.get_json = boom
    watcher.log.disabled = True
    try:
        with contextlib.closing(db.connect()) as conn:
            result = watcher.run_fetch(conn, db.get_settings(conn))
    finally:
        sources.get_json = fake_get_json
        watcher.log.disabled = False
    assert result["errors"] == {"reed": "reed fetch failed unexpectedly (see console)"}
    assert result["by_source"]["remotive"] == 1


def test_tick_skips_when_fetch_running():
    fresh()
    save(career_fields=["python"])
    assert watcher.FETCH_LOCK.acquire(blocking=False)
    try:
        assert watcher._tick(None) is None and calls == []
    finally:
        watcher.FETCH_LOCK.release()


def test_reed_skipped_without_key():
    fresh()
    save(career_fields=["python"])
    with contextlib.closing(db.connect()) as conn:
        result = watcher.run_fetch(conn, db.get_settings(conn))
    assert result["by_source"] == {"remotive": 1} and result["errors"] == {}
    assert "reed" not in watcher.STATUS and reed_calls() == []


def test_failure_text_never_contains_key():
    fresh()
    key = "SECRET-REED-KEY"
    save(career_fields=["python"], reed_api_key=key)
    FAIL.add("reed.co.uk")
    with captured() as records:
        with contextlib.closing(db.connect()) as conn:
            result = watcher.run_fetch(conn, db.get_settings(conn))
    texts = [str(v) for s in watcher.STATUS.values() for v in s.values()]
    texts += list(result["errors"].values()) + [r.getMessage() for r in records]
    assert texts and not any(key in t for t in texts)


def test_two_sources_one_poll():
    fresh()
    save(career_fields=["python"], reed_api_key="key")
    watcher._tick(None)
    hosts = [h for u, _, _ in calls for h in ("reed.co.uk", "remotive.com") if h in u]
    assert hosts == ["reed.co.uk", "remotive.com"]
    assert all(watcher.STATUS[n]["ok"] is True for n in ("reed", "remotive"))
    with contextlib.closing(db.connect()) as conn:
        assert {j["source"] for j in db.list_jobs(conn)} == {"reed", "remotive"}


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
