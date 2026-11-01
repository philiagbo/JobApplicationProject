import collections
import contextlib
import html
import http.server
import json
import logging
import os
import sqlite3
import sys
import tempfile
import threading

os.environ["JOBHELPER_DB"] = os.path.join(tempfile.mkdtemp(), "boot.db")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app  # noqa: E402
import core  # noqa: E402
import db  # noqa: E402
import sources  # noqa: E402
import watcher  # noqa: E402

REAL_GET_PAGE = sources.get_page
core.ALLOW_PRIVATE_HOSTS = True  # the fixture server is on loopback
watcher.DETAILS_GAP_SECONDS = 0
watcher.DETAILS_IDLE_SECONDS = 0.05

PAGES = {}  # path -> (status, content type, body bytes[, extra headers])
COUNTS = collections.Counter()  # path -> requests seen


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        COUNTS[self.path] += 1
        status, ctype, body, *rest = PAGES.get(self.path, (404, "text/plain", b"not here"))
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (rest[0] if rest else {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=_server.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d" % _server.server_address[1]


def serve(path, body, status=200, ctype="text/html; charset=utf-8", headers=None):
    PAGES[path] = (status, ctype, body.encode("utf-8") if isinstance(body, str) else body, headers or {})
    return BASE + path


def ldpage(obj, body="", head=""):
    return '<html><head>%s<script type="application/ld+json">%s</script></head><body>%s</body></html>' % (
        head, obj if isinstance(obj, str) else json.dumps(obj), body)


def jobposting(description):
    return {"@context": "https://schema.org", "@type": "JobPosting", "title": "Data Analyst", "description": description}


POSTING_HTML = (
    "<p>We are a fully remote team of analysts building reporting for clients across the UK and beyond, working closely"
    " with product and finance.</p>\n<h3>Responsibilities</h3><ul><li>Build dashboards</li><li>Own the weekly report</li>"
    "<li>Mentor analysts</li></ul><p>Requirements: three years of experience with SQL and a love of clear, honest charts."
    " You will join a friendly group that values documentation and calm delivery. We offer flexible hours, a learning"
    " budget and regular team meetups throughout the year.</p>")
# the raw newline inside the JSON string is deliberate: real JSON-LD often has one (strict=False)
POSTING_PAGE = ldpage(json.dumps(jobposting(html.escape(POSTING_HTML))).replace("\\n", "\n"))
assert len(POSTING_HTML) > 500 and "\n" in POSTING_PAGE.split('">', 1)[1]
serve("/posting", POSTING_PAGE)


def fresh():
    os.environ["JOBHELPER_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
    db.init_db()
    sources.get_page = REAL_GET_PAGE
    COUNTS.clear()
    core.ALLOW_PRIVATE_HOSTS = True


def job(url, source="reed", title="Data Analyst", description="analyse data", **extra):
    j = {"url": url, "source": source, "title": title, "company": "Acme", "location": "London", "salary": "",
         "description": description, "job_type": None, "remote": None}
    j.update(extra)
    with contextlib.closing(db.connect()) as conn:
        db.insert_jobs(conn, [j], db.get_settings(conn))
        return conn.execute("SELECT id FROM jobs WHERE url = ?", (url,)).fetchone()["id"]


def get(job_id):
    with contextlib.closing(db.connect()) as conn:
        return db.get_job(conn, job_id)


def save(job_id, text, status):
    with contextlib.closing(db.connect()) as conn:
        db.save_details(conn, job_id, text, status)


def raises(exc, fn, *args):
    try:
        fn(*args)
    except exc:
        return
    raise AssertionError("%s not raised" % exc.__name__)


def test_details_end_to_end():
    fresh()
    job_id = job(BASE + "/posting")
    before = get(job_id)["score"]
    assert watcher._details_step() is True
    c = app.app.test_client()
    got = [j for j in c.get("/api/jobs").get_json() if j["id"] == job_id][0]
    assert got["details_status"] == "ok"
    assert "Build dashboards" in got["description"] and "<" not in got["description"] and "&lt;" not in got["description"]
    assert got["summary"]["what_youd_do"] == ["Build dashboards", "Own the weekly report", "Mentor analysts"]
    assert got["summary"]["remote"] == "Remote" and "Fully remote" in got["pros"]
    assert got["score"] > before
    assert watcher._details_step() is None
    assert COUNTS["/posting"] == 1


def test_migration_adds_column_once():
    path = os.path.join(tempfile.mkdtemp(), "legacy.db")
    os.environ["JOBHELPER_DB"] = path
    old = sqlite3.connect(path)  # the jobs table as Phase 1 to 3 shipped it, without details_status
    old.executescript("""
        CREATE TABLE jobs (id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE, source TEXT NOT NULL,
          title TEXT NOT NULL DEFAULT '', company TEXT NOT NULL DEFAULT '', location TEXT NOT NULL DEFAULT '',
          salary TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', summary TEXT NOT NULL DEFAULT '{}',
          score INTEGER NOT NULL DEFAULT 0, pros TEXT NOT NULL DEFAULT '[]', cons TEXT NOT NULL DEFAULT '[]',
          status TEXT NOT NULL DEFAULT 'new', created_at TEXT NOT NULL DEFAULT (datetime('now')),
          status_changed_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO jobs (url, source, title) VALUES ('https://a.example/1', 'reed', 'A'), ('https://a.example/2', 'reed', 'B');
    """)
    old.commit()
    old.close()
    db.init_db()
    db.init_db()
    with contextlib.closing(db.connect()) as conn:
        assert [r[1] for r in conn.execute("PRAGMA table_info(jobs)")].count("details_status") == 1
        assert [r[0] for r in conn.execute("SELECT details_status FROM jobs")] == ["pending", "pending"]
        db.insert_jobs(conn, [{"url": "https://a.example/3", "source": "reed", "title": "C"}], db.get_settings(conn))
        assert conn.execute("SELECT details_status FROM jobs WHERE url = 'https://a.example/3'").fetchone()[0] == "pending"


def test_jobs_api_returns_details_status():
    fresh()
    job_id = job("https://a.example/9")
    c = app.app.test_client()
    assert [j["details_status"] for j in c.get("/api/jobs").get_json()] == ["pending"]
    assert c.post("/api/jobs/%d/queue" % job_id).status_code == 200
    assert [j["details_status"] for j in c.get("/api/jobs?status=queued").get_json()] == ["pending"]


JD = "<p>Intro paragraph.</p><ul><li>One</li><li>Two</li></ul>"
JD_TEXT = "Intro paragraph.\n• One\n• Two"


def test_extract_jsonld_shapes():
    jp = jobposting(html.escape(JD))
    other = {"@type": "Organization", "name": "Acme", "description": "not a posting"}
    shapes = [
        jp,
        [other, jp],
        {"@graph": [other, jp]},
        {"@type": "WebPage", "mainEntity": jp},
        dict(jp, **{"@type": ["JobPosting"]}),
    ]
    for shape in shapes:
        assert sources.extract_description(ldpage(shape)) == (JD_TEXT, True, True), shape
    two = '<script type="application/ld+json">{not json</script>'
    assert sources.extract_description(ldpage(json.dumps(jp), head=two)) == (JD_TEXT, True, True)
    assert sources.extract_description(two + ldpage(json.dumps(jp))) == (JD_TEXT, True, True)
    assert sources.extract_description(ldpage(other)) == ("", False, False)
    raw = '{"@type": "JobPosting", "description": "Line one\n\tTabbed line"}'  # raw newline and tab inside the string
    assert sources.extract_description(ldpage(raw)) == ("Line one\nTabbed line", True, True)


def test_extract_largest_block():
    items = "".join("<li>item %d</li>" % i for i in range(5))
    doc = ("<html><head><title>t</title></head><body><header><p>HEADERTEXT</p></header>"
           "<nav><ul>%s</ul><p>NAVTEXT</p></nav><aside><p>short aside</p></aside>"
           "<article><p>First paragraph of the posting.</p><p>Second paragraph.</p><p>Third paragraph.</p><ul>%s</ul></article>"
           "<footer><p>FOOTERTEXT</p></footer></body></html>") % ("<li>navlink</li>" * 30, items)
    text, from_jsonld, has_jp = sources.extract_description(doc)
    assert (from_jsonld, has_jp) == (False, False)
    assert text == ("First paragraph of the posting.\nSecond paragraph.\nThird paragraph.\n"
                    + "\n".join("• item %d" % i for i in range(5)))
    for junk in ("HEADERTEXT", "NAVTEXT", "navlink", "FOOTERTEXT", "short aside"):
        assert junk not in text


def test_extract_empty():
    for doc in ("", None, "<html><body></body></html>", "<html><head><title>t</title></head></html>"):
        assert sources.extract_description(doc) == ("", False, False)
    article = "<article><p>%s</p></article>" % ("Posting words here. " * 20).strip()
    for jp in (jobposting(""), {"@type": "JobPosting"}):
        text, from_jsonld, has_jp = sources.extract_description(ldpage(jp, body=article))
        assert text == ("Posting words here. " * 20).strip() and (from_jsonld, has_jp) == (False, True)


def test_blocked_statuses():
    fresh()
    long_page = ldpage(jobposting("Readable text. " * 30))
    for code in (403, 429, 503):
        assert sources.fetch_details(serve("/s%d" % code, long_page, status=code)) == ("", "blocked")
        assert sources.judge_page(code, long_page) is None
    assert sources.judge_page(200, long_page) is not None


def test_blocked_short_text():
    fresh()
    assert sources.fetch_details(serve("/x150", ldpage(jobposting("x" * 150)))) == ("", "blocked")
    assert sources.fetch_details(serve("/e199", ldpage(jobposting("é" * 199)))) == ("", "blocked")
    assert sources.fetch_details(serve("/e200", ldpage(jobposting("é" * 200)))) == ("é" * 200, "ok")  # code points, not bytes


def test_page_charset_decoding():
    fresh()
    serve("/latin1", b"<html><body>caf\xa3</body></html>", ctype="text/html; charset=iso-8859-1")
    code, doc = sources.get_page(BASE + "/latin1")
    assert code == 200 and "£" in doc
    serve("/badutf", b"<html>\xff\xfe bad</html>", ctype="text/html")
    code, doc = sources.get_page(BASE + "/badutf")
    assert code == 200 and "�" in doc
    serve("/oddcharset", b"<html>plain</html>", ctype="text/html; charset=nonsense-9")
    assert sources.get_page(BASE + "/oddcharset") == (200, "<html>plain</html>")


def test_challenge_without_jsonld_blocked():
    fresh()
    article = "<article><p>%s</p></article>" % ("Plenty of ordinary words here. " * 40)
    assert sources.fetch_details(serve("/human", "<html><body><h1>Verify you are human</h1>%s</body></html>" % article)) == ("", "blocked")
    assert sources.fetch_details(serve("/moment", "<html><head><title>Just a moment...</title></head><body>%s</body></html>" % article)) == ("", "blocked")
    assert sources.fetch_details(serve("/plain", "<html><body>%s</body></html>" % article))[1] == "ok"


def test_challenge_phrase_with_jsonld_ok():
    fresh()
    desc = "Real posting text. " * 20
    page = ldpage(jobposting(desc), body="<footer>This site is protected by reCAPTCHA</footer>")
    assert sources.fetch_details(serve("/recaptcha", page)) == (desc.strip(), "ok")


def test_challenge_phrase_with_empty_jobposting():
    fresh()
    footer = "<footer>This site is protected by reCAPTCHA</footer>"
    long_text = ("posting text " * 25).strip()
    page = ldpage(jobposting(""), body="<article><p>%s</p></article>%s" % (long_text, footer))
    assert sources.fetch_details(serve("/emptyjp", page)) == (long_text, "ok")
    short_text = ("posting text " * 12).strip()[:150]
    page = ldpage(jobposting(""), body="<article><p>%s</p></article>%s" % (short_text, footer))
    assert sources.extract_description(page) == (short_text, False, True)  # a JobPosting was found, so no phrase check
    assert sources.fetch_details(serve("/emptyjp_short", page)) == ("", "blocked")  # the 200-character rule


def test_fetch_details_rejects_unsafe_urls():
    fresh()
    seen = []
    sources.get_page = lambda url: seen.append(url) or (200, "x")
    try:
        for url in ("file:///etc/passwd", "ftp://example.com/x", "javascript:alert(1)", ""):
            assert sources.fetch_details(url) == ("", "blocked"), url
        assert seen == []
    finally:
        sources.get_page = REAL_GET_PAGE
    core.ALLOW_PRIVATE_HOSTS = False
    try:
        assert sources.fetch_details(BASE + "/posting") == ("", "blocked")
        assert sources.fetch_details("http://localhost/x") == ("", "blocked")
    finally:
        core.ALLOW_PRIVATE_HOSTS = True
    assert COUNTS["/posting"] == 0


def test_redirect_to_file_blocked():
    fresh()
    for target in ("file:///etc/passwd", "ftp://127.0.0.1/secret"):
        url = serve("/redir", "", status=302, headers={"Location": target})
        assert sources.get_page(url) == (302, "")
        assert sources.fetch_details(url) == ("", "blocked")
    core.ALLOW_PRIVATE_HOSTS = True
    serve("/hop", "", status=302, headers={"Location": BASE + "/posting"})
    assert sources.fetch_details(BASE + "/hop")[1] == "ok"  # a redirect to a safe page still works


def test_details_plan_rules():
    s = dict(db.DEFAULTS, excluded_words=["senior"])

    def plan(**kw):
        return core.details_plan(dict({"url": "https://www.reed.co.uk/jobs/1", "source": "reed", "title": "Nurse",
                                       "description": "analyse data"}, **kw), s)

    assert plan(source="linkedin") == "skipped" and plan(source="indeed") == "skipped"
    assert plan(url="https://uk.indeed.com/viewjob?jk=1") == "skipped"
    assert plan(url="https://www.linkedin.com/jobs/view/1") == "skipped"
    assert plan(url="https://notindeed.com/x") == "fetch"
    assert plan(title="Senior Nurse") == "skipped"
    assert plan(source="remotive", description="r" * 600) == "ok"
    assert plan() == "fetch"
    assert plan(description="a" * 499) == "fetch" and plan(description="a" * 500) == "ok"


def test_linkedin_indeed_never_fetched():
    fresh()
    seen = []
    sources.get_page = lambda url: seen.append(url) or (200, "x")
    try:
        ids = [job("https://www.linkedin.com/jobs/view/1", source="linkedin", description="seen in alert"),
               job("https://uk.indeed.com/viewjob?jk=1", source="indeed", description="seen in alert")]
        assert watcher._details_step() is False and watcher._details_step() is False
        assert watcher._details_step() is None
    finally:
        sources.get_page = REAL_GET_PAGE
    assert seen == []
    for i in ids:
        got = get(i)
        assert got["details_status"] == "skipped" and got["description"] == "seen in alert"


LONG_TEXT = ("Responsibilities\n• Write weekly reports\n• Plan the team tasks\n• Review incoming data\n"
             + "You will work with a small friendly group on useful tools every day. " * 5)


def test_save_details_new_rescored_hints_kept():
    fresh()
    job_id = job("https://remotive.com/remote-jobs/1", source="remotive", description="x", job_type="Full-time", remote="Remote")
    assert "Fully remote" in get(job_id)["pros"] and "remote" not in LONG_TEXT.lower()
    save(job_id, LONG_TEXT, "ok")
    got = get(job_id)
    assert got["description"] == LONG_TEXT and got["details_status"] == "ok"
    assert "Fully remote" in got["pros"] and got["summary"]["remote"] == "Remote" and got["summary"]["job_type"] == "Full-time"
    assert got["summary"]["what_youd_do"] == ["Write weekly reports", "Plan the team tasks", "Review incoming data"]


def test_save_details_queued_keeps_score():
    fresh()
    job_id = job("https://a.example/q", description="short")
    with contextlib.closing(db.connect()) as conn:
        db.set_status(conn, job_id, "queue")
    before = get(job_id)
    save(job_id, LONG_TEXT + " Fully remote role paying £90,000 a year.", "ok")
    after = get(job_id)
    assert after["description"] != before["description"] and after["details_status"] == "ok"
    for key in ("score", "pros", "cons", "summary"):
        assert after[key] == before[key], key


def test_dismissed_not_picked():
    fresh()
    job_id = job("https://a.example/d")
    c = app.app.test_client()
    assert c.post("/api/jobs/%d/dismiss" % job_id).status_code == 200
    with contextlib.closing(db.connect()) as conn:
        assert db.next_pending(conn) is None
    assert c.post("/api/jobs/%d/undo" % job_id).status_code == 200
    with contextlib.closing(db.connect()) as conn:
        assert db.next_pending(conn)["id"] == job_id


def test_shorter_text_never_overwrites():
    fresh()
    job_id = job("https://a.example/s", description="d" * 800)
    save(job_id, "t" * 300, "ok")
    got = get(job_id)
    assert got["description"] == "d" * 800 and got["details_status"] == "ok"


def test_blocked_keeps_snippet():
    fresh()
    job_id = job("https://a.example/b", description="the alert snippet")
    before = get(job_id)
    save(job_id, "Verify you are human " * 20, "blocked")  # even if challenge text is passed, nothing is stored
    after = get(job_id)
    assert after["details_status"] == "blocked"
    assert dict(after, details_status=None) == dict(before, details_status=None)


def test_save_details_rejects_unknown_status():
    fresh()
    job_id = job("https://a.example/u")
    for status in ("pending", "nope"):
        raises(ValueError, save, job_id, "", status)
    assert get(job_id)["details_status"] == "pending"


def test_only_pending_picked():
    fresh()
    job_id = job(BASE + "/posting")
    assert watcher._details_step() is True and get(job_id)["details_status"] == "ok"
    assert watcher._details_step() is None
    assert COUNTS["/posting"] == 1


@contextlib.contextmanager
def patched(obj, name, value):
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


def test_worker_marks_blocked_on_error():
    fresh()
    job_id = job("https://a.example/err")

    def boom(url):
        raise RuntimeError("boom")

    records = []
    handler = logging.Handler()
    handler.emit = records.append
    watcher.log.addHandler(handler)
    try:
        with patched(sources, "fetch_details", boom):
            assert watcher._details_step() is True
    finally:
        watcher.log.removeHandler(handler)
    assert get(job_id)["details_status"] == "blocked"
    assert len(records) == 1 and "boom" in repr(records[0].exc_info[1])
    assert watcher._details_step() is None


def test_interrupted_fetch_stays_pending():
    fresh()
    job_id = job("https://a.example/int")

    def interrupted(url):
        raise SystemExit

    with patched(sources, "fetch_details", interrupted):
        raises(SystemExit, watcher._details_step)
    assert get(job_id)["details_status"] == "pending"  # retried on the next start


def test_details_start_once():
    release = threading.Event()
    with patched(watcher, "_details_loop", release.wait), patched(watcher, "_loop", release.wait):
        try:
            watcher.start()
            first, watcher_thread = watcher._details_thread, watcher._thread
            watcher.start()
            assert watcher._details_thread is first and watcher._thread is watcher_thread
            assert first.is_alive() and first.name == "details"
        finally:
            release.set()
            first.join(2)
            watcher_thread.join(2)
            watcher._details_thread = watcher._thread = None


if __name__ == "__main__":
    tests = [f for n, f in list(globals().items()) if n.startswith("test_") and callable(f)]
    for t in tests:
        t()
    print("ok: %d tests" % len(tests))
