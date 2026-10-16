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

sources.REMOTIVE_GAP_SECONDS = 0

SUMMARY_KEYS = {"salary_text", "salary_annual", "currency", "job_type", "remote",
                "years_experience", "what_youd_do", "what_they_want"}


def item(slug, title, description="", job_type="full_time", salary=""):
    return {"id": slug, "url": "https://remotive.com/remote-jobs/" + slug, "title": title,
            "company_name": "Acme ", "category": "x", "tags": [], "job_type": job_type,
            "publication_date": "2026-10-15", "candidate_required_location": "Worldwide",
            "salary": salary, "description": description}


SHARED = item("shared-1", "Python Developer")
CANNED = {
    "data analyst": [item("da-1", "Data Analyst"), item("om-1", "Office Manager", "we use python daily"), SHARED],
    "python": [SHARED, item("py-2", "Backend Engineer", job_type="contract")],
}

calls = []


def fake_get_json(url, params):
    calls.append(params["search"])
    return {"jobs": CANNED[params["search"]]}


sources.get_json = fake_get_json


def fresh_client():
    os.environ["JOBHELPER_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
    db.init_db()
    del calls[:]
    return app.app.test_client()


def count_jobs():
    with db.connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]


def test_schema_created():
    fresh_client()
    with db.connect() as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"jobs", "answers", "unanswered", "settings"} <= names


def test_settings_defaults():
    c = fresh_client()
    assert c.get("/api/settings").get_json() == db.DEFAULTS
    assert c.get("/api/settings").get_json()["reed_api_key"] == ""


def test_settings_merge():
    c = fresh_client()
    assert c.put("/api/settings", json={"career_fields": [" data analyst ", ""]}).status_code == 200
    r = c.put("/api/settings", json={"min_salary": 40000})
    want = dict(db.DEFAULTS, career_fields=["data analyst"], min_salary=40000)
    assert r.get_json() == want
    assert c.get("/api/settings").get_json() == want


def test_settings_keys_returned_in_full():
    c = fresh_client()
    c.put("/api/settings", json={"reed_api_key": "abc123"})
    assert c.get("/api/settings").get_json()["reed_api_key"] == "abc123"


def test_settings_rejects_bad_input():
    c = fresh_client()
    bad = [{"nope": 1}, {"min_salary": "40k"}, {"min_salary": True}, {"career_fields": "data"},
           {"career_fields": [1]}, {"api_poll_minutes": 0}, {"min_salary": -1}, {"location": 5},
           [1, 2], {"career_fields": ["ok"], "nope": 1}]
    for body in bad:
        r = c.put("/api/settings", json=body)
        assert r.status_code == 400 and "error" in r.get_json(), body
    assert c.get("/api/settings").get_json() == db.DEFAULTS


def test_fetch_requires_fields():
    c = fresh_client()
    r = c.post("/api/fetch")
    assert r.status_code == 400
    assert r.get_json() == {"error": "Choose at least one career field in settings"}
    assert calls == []


def test_fetch_dedupes():
    c = fresh_client()
    c.put("/api/settings", json={"career_fields": ["data analyst", "python"]})
    r = c.post("/api/fetch")
    assert r.status_code == 200
    assert len(calls) == 2
    assert r.get_json() == {"new": 4, "by_source": {"remotive": 4}}
    r = c.post("/api/fetch")
    assert r.get_json()["new"] == 0
    assert count_jobs() == 4


def test_jobs_listing():
    c = fresh_client()
    c.put("/api/settings", json={"career_fields": ["data analyst", "python"]})
    c.post("/api/fetch")
    jobs = c.get("/api/jobs").get_json()
    scores = [j["score"] for j in jobs]
    assert scores == sorted(scores, reverse=True)
    for j in jobs:
        assert isinstance(j["pros"], list) and isinstance(j["cons"], list)
        assert isinstance(j["summary"], dict) and set(j["summary"]) == SUMMARY_KEYS
    titles = [j["title"] for j in jobs]
    assert titles.index("Data Analyst") < titles.index("Office Manager")


def test_fetch_source_failure_is_502():
    c = fresh_client()
    c.put("/api/settings", json={"career_fields": ["python"]})
    real = sources.get_json

    def boom(url, params):
        raise OSError("down")

    try:
        sources.get_json = boom
        r = c.post("/api/fetch")
        assert r.status_code == 502 and "Remotive" in r.get_json()["error"]
        sources.get_json = lambda url, params: {"oops": []}
        r = c.post("/api/fetch")
        assert r.status_code == 502 and "Remotive" in r.get_json()["error"]
    finally:
        sources.get_json = real
    assert count_jobs() == 0


def test_remotive_spacing():
    sources.REMOTIVE_GAP_SECONDS = 0.2
    try:
        start = time.monotonic()
        sources.fetch_remotive(["data analyst", "python"])
        assert time.monotonic() - start >= 0.2
    finally:
        sources.REMOTIVE_GAP_SECONDS = 0


if __name__ == "__main__":
    tests = [f for n, f in list(globals().items()) if n.startswith("test_") and callable(f)]
    for t in tests:
        t()
    print("ok: %d tests" % len(tests))
