import collections
import contextlib
import html
import http.client
import http.server
import json
import logging
import os
import queue
import sqlite3
import sys
import tempfile
import threading
import concurrent.futures
import subprocess

os.environ["JOBHELPER_DB"] = os.path.join(tempfile.mkdtemp(), "boot.db")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app  # noqa: E402
import browser  # noqa: E402
import core  # noqa: E402
import db  # noqa: E402
import sources  # noqa: E402
import watcher  # noqa: E402

REAL_GET_PAGE = sources.get_page
REAL_FETCH_PAGE = browser.fetch_page
REAL_START = browser._start_playwright


def no_browser(url):
    raise browser.BrowserUnavailable("no browser in tests")  # only the live and fake-based tests may reach a browser


browser.fetch_page = no_browser
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
JS_TEXT = "Analyst role. " + "You will build weekly reports and help the team choose what to measure next. " * 5
serve("/js", '<html><body><main id="m"></main><script>document.getElementById("m").innerHTML = "<p>%s</p>";</script></body></html>' % JS_TEXT)
serve("/403", "<html><body><p>%s</p></body></html>" % ("Access to this page is forbidden for your client. " * 8), status=403)


def fresh():
    os.environ["JOBHELPER_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
    db.init_db()
    sources.get_page = REAL_GET_PAGE
    browser.fetch_page = no_browser
    COUNTS.clear()
    core.ALLOW_PRIVATE_HOSTS = True


def reset_browser(start):
    browser._thread = None  # an old thread keeps waiting on its old queue and is harmless
    browser._q = queue.Queue()
    browser._unavailable = None
    browser._start_playwright = start


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
    calls = []
    browser.fetch_page = lambda url: calls.append(url) or (200, POSTING_PAGE)
    for target in ("file:///etc/passwd", "ftp://127.0.0.1/secret", "https://uk.indeed.com/viewjob?jk=1"):
        url = serve("/redir", "", status=302, headers={"Location": target})
        raises(sources.RedirectRefused, sources.get_page, url)
        assert sources.fetch_details(url) == ("", "blocked")
    assert calls == []  # a refused redirect is never handed to the browser, which would follow it (CR-01, D-18)
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


def test_browser_retry_live():
    fresh()
    reset_browser(REAL_START)
    browser.fetch_page = REAL_FETCH_PAGE
    try:
        try:
            browser.fetch_page(BASE + "/posting")
        except browser.BrowserUnavailable as e:
            print("live browser: skipped (%s)" % e)
            return
        COUNTS.clear()
        js_id, forbidden_id = job(BASE + "/js", description="short"), job(BASE + "/403", description="short")
        watcher._details_step()
        watcher._details_step()
        got_js, got_403 = get(js_id), get(forbidden_id)
        assert got_js["details_status"] == "ok" and "Analyst role." in got_js["description"], got_js
        assert got_403["details_status"] == "blocked" and got_403["description"] == "short"
        assert COUNTS["/js"] == 2 and COUNTS["/403"] == 2  # one urllib request plus one browser request each
        print("live browser: ok")
    finally:
        reset_browser(REAL_START)


class FakeResponse:
    def __init__(self, status):
        self.status = status


class FakeRequest:
    def __init__(self, url, navigation):
        self.url, self.navigation = url, navigation

    def is_navigation_request(self):
        return self.navigation


class FakeRoute:
    def __init__(self, page, request):
        self.page, self.request = page, request

    def continue_(self):
        self.page.routed.append(("continue", self.request.url))

    def abort(self):
        self.page.routed.append(("abort", self.request.url))


class FakePage:
    def __init__(self, status=200, content="<html>page</html>", url=None, goto_error=None, hops=(), subresources=()):
        self.calls, self.status, self.html, self.after, self.goto_error, self.url = [], status, content, url, goto_error, ""
        self.handlers, self.routed, self.hops, self.subresources = {}, [], hops, subresources

    def route(self, pattern, handler):
        self.handlers["route"] = handler

    def on(self, event, handler):
        self.handlers[event] = handler

    def _request(self, url, navigation, routed=True):
        request = FakeRequest(url, navigation)
        if "request" in self.handlers:
            self.handlers["request"](request)
        if routed and "route" in self.handlers:
            self.handlers["route"](FakeRoute(self, request))

    def goto(self, url, **kw):
        self.calls.append(("goto", (url,), kw))
        if self.goto_error:
            raise self.goto_error
        self._request(url, True)
        if ("abort", url) in self.routed:
            raise browser.Error("net::ERR_FAILED")
        for hop in self.hops:
            self._request(hop, True, routed=False)  # like Playwright: a server redirect hop is never routed
        for sub in self.subresources:
            self._request(sub, False)
        self.url = self.after or (self.hops[-1] if self.hops else url)
        return FakeResponse(self.status)

    def wait_for_load_state(self, *a, **kw):
        self.calls.append(("wait_for_load_state", a, kw))

    def content(self):
        self.calls.append(("content", (), {}))
        return self.html

    def close(self):
        self.calls.append(("close", (), {}))


class FakeBrowser:
    def __init__(self, page):
        self.page, self.new_page_args, self.closed = page, None, False

    def new_page(self, *a, **kw):
        self.new_page_args = (a, kw)
        return self.page

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, page=None, missing=(), broken=()):
        self.page, self.missing, self.broken, self.launches, self.browsers = page or FakePage(), missing, broken, [], []

    def launch(self, **kw):
        self.launches.append(kw)
        if kw.get("channel") in self.missing:
            raise browser.Error("Chromium distribution '%s' is not found" % kw.get("channel"))
        if kw.get("channel") in self.broken:
            raise browser.Error("Timeout 20000ms exceeded")
        self.browsers.append(FakeBrowser(self.page))
        return self.browsers[-1]


class FakePW:
    def __init__(self, page=None, missing=(), broken=()):
        self.chromium = FakeChromium(page, missing, broken)


def test_browser_single_thread():
    fresh()
    starts = []
    reset_browser(lambda: starts.append(1) or FakePW())
    try:
        who = lambda pw: (threading.current_thread().name, threading.get_ident())
        got = [browser.submit(who).result(5)]
        other = []
        t = threading.Thread(target=lambda: other.append(browser.submit(who).result(5)))
        t.start()
        t.join(5)
        got += other + [browser.submit(who).result(5)]
        assert len(got) == 3 and {g[0] for g in got} == {"browser"} and len({g[1] for g in got}) == 1
        assert got[0][1] != threading.get_ident() and starts == [1]
    finally:
        reset_browser(REAL_START)


def test_browser_exception_through_future():
    fresh()
    reset_browser(lambda: FakePW())
    try:
        def boom(pw):
            raise ValueError("boom")

        raises(ValueError, browser.submit(boom).result, 5)
        assert browser.submit(lambda pw: "still serving").result(5) == "still serving"
    finally:
        reset_browser(REAL_START)


def test_browser_not_started_on_import():
    code = ("import sys; sys.path.insert(0, %r)\nimport app, watcher, sources, browser, threading\n"
            "print(browser._thread, sorted(t.name for t in threading.enumerate() if t.name in ('browser', 'details')))"
            % os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, JOBHELPER_DB=os.path.join(tempfile.mkdtemp(), "i.db"))
    out = subprocess.run([sys.executable, "-I", "-c", code], env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0 and out.stdout.strip() == "None []", out.stdout + out.stderr


def test_playwright_start_failure():
    fresh()

    def no_driver():
        raise RuntimeError("no driver")

    reset_browser(no_driver)
    browser.fetch_page = REAL_FETCH_PAGE
    browser.log.disabled = True  # the expected failure is logged with a traceback
    try:
        raises(browser.BrowserUnavailable, browser.fetch_page, BASE + "/posting")
        assert sources.fetch_details(BASE + "/403") == ("", "blocked")
    finally:
        browser.log.disabled = False
        reset_browser(REAL_START)


def test_channel_order_and_memo():
    fresh()
    reset_browser(REAL_START)
    pw = FakePW(missing=("msedge",))
    assert isinstance(browser.launch_headless(pw), FakeBrowser)
    assert pw.chromium.launches == [{"channel": "msedge", "headless": True, "timeout": 20000},
                                    {"channel": "chrome", "headless": True, "timeout": 20000}]
    both = FakePW(missing=("msedge", "chrome"))
    try:
        browser.launch_headless(both)
        raise AssertionError("BrowserUnavailable not raised")
    except browser.BrowserUnavailable as e:
        assert str(e) == "Edge or Chrome is not installed"
    assert len(both.chromium.launches) == 2
    raises(browser.BrowserUnavailable, browser.launch_headless, both)
    assert len(both.chromium.launches) == 2  # remembered: no second probe
    reset_browser(REAL_START)


def test_page_task_only_reads():
    fresh()
    reset_browser(REAL_START)
    page = FakePage(status=200, content="<html>hello</html>")
    pw = FakePW(page)
    assert browser._load_page(pw, BASE + "/x") == (200, "<html>hello</html>")
    assert page.calls == [("goto", (BASE + "/x",), {"wait_until": "domcontentloaded", "timeout": 20000}),
                          ("wait_for_load_state", ("networkidle",), {"timeout": 5000}),
                          ("content", (), {}), ("close", (), {})]
    assert pw.chromium.browsers[0].new_page_args == ((), {}) and pw.chromium.browsers[0].closed


def test_page_closed_on_error():
    fresh()
    reset_browser(REAL_START)
    page = FakePage(goto_error=browser.Error("timeout"))
    pw = FakePW(page)
    raises(browser.Error, browser._load_page, pw, BASE + "/x")
    assert page.calls[-1][0] == "close" and pw.chromium.browsers[0].closed


def test_post_navigation_url_checked():
    fresh()
    reset_browser(REAL_START)
    page = FakePage(url="file:///etc/passwd", content="secret")
    pw = FakePW(page)
    assert browser._load_page(pw, BASE + "/x") == (0, "")
    assert "content" not in [c[0] for c in page.calls] and pw.chromium.browsers[0].closed


def test_fetch_details_retries_once():
    fresh()
    calls = []

    def answer(result):
        def fake(url):
            calls.append(url)
            if isinstance(result, BaseException):
                raise result
            return result
        return fake

    sources.get_page = lambda url: (403, "")
    posting = REAL_GET_PAGE(BASE + "/posting")[1]
    browser.fetch_page = answer((200, posting))
    text, status = sources.fetch_details("https://a.example/p")
    assert status == "ok" and "Build dashboards" in text and calls == ["https://a.example/p"]
    for result in ((403, ""), browser.BrowserUnavailable("x"), browser.Error("x"), concurrent.futures.TimeoutError(), OSError("x")):
        del calls[:]
        browser.fetch_page = answer(result)
        assert sources.fetch_details("https://a.example/p") == ("", "blocked"), result
        assert len(calls) == 1
    del calls[:]
    sources.get_page = REAL_GET_PAGE
    browser.fetch_page = answer((200, ""))
    assert sources.fetch_details(BASE + "/posting")[1] == "ok" and calls == []  # readable by urllib: no browser


def test_browser_challenge_blocked():
    fresh()
    calls = []
    page = "<html><body><p>%s Verify you are human</p></body></html>" % ("Please wait while we check your browser. " * 10)
    sources.get_page = lambda url: (403, "")
    browser.fetch_page = lambda url: calls.append(url) or (200, page)
    assert sources.fetch_details("https://a.example/c") == ("", "blocked") and len(calls) == 1


def test_never_fetch_and_unsafe_skip_browser():
    fresh()
    calls = []
    browser.fetch_page = lambda url: calls.append(url) or (200, "")
    sources.get_page = lambda url: (403, "")
    job("https://www.linkedin.com/jobs/view/1", source="linkedin", description="seen in alert")
    job("https://uk.indeed.com/viewjob?jk=1", source="indeed", description="seen in alert")
    watcher._details_step()
    watcher._details_step()
    assert sources.fetch_details("file:///etc/passwd") == ("", "blocked")
    assert calls == []


def test_browser_guard_aborts_refused_requests():
    fresh()
    reset_browser(REAL_START)
    core.ALLOW_PRIVATE_HOSTS = False
    try:
        page = FakePage(subresources=("https://www.linkedin.com/li.js", "http://192.168.1.1/admin", "http://127.1/",
                                      "https://93.184.216.34/ok.js"))
        assert browser._load_page(FakePW(page), "https://93.184.216.34/job") == (200, "<html>page</html>")
        assert page.routed == [("continue", "https://93.184.216.34/job"), ("abort", "https://www.linkedin.com/li.js"),
                               ("abort", "http://192.168.1.1/admin"), ("abort", "http://127.1/"),
                               ("continue", "https://93.184.216.34/ok.js")]
        for hop in ("http://10.0.0.1/", "https://uk.indeed.com/viewjob?jk=1"):  # a hop through a refused host, back out
            page = FakePage(hops=(hop, "https://93.184.216.34/back"))
            assert browser._load_page(FakePW(page), "https://93.184.216.34/job") == (0, ""), hop
            assert "content" not in [c[0] for c in page.calls]
        page = FakePage()
        raises(browser.Error, browser._load_page, FakePW(page), "https://www.linkedin.com/jobs/view/1")
        assert page.routed == [("abort", "https://www.linkedin.com/jobs/view/1")]
    finally:
        core.ALLOW_PRIVATE_HOSTS = True


def test_gone_page_never_stored():
    fresh()
    calls = []
    browser.fetch_page = lambda url: calls.append(url) or (404, POSTING_PAGE)
    for code in (404, 410):
        assert sources.fetch_details(serve("/gone%d" % code, POSTING_PAGE, status=code)) == ("", "blocked")
    assert calls == []  # the browser cannot bring an expired listing back
    sources.get_page = lambda url: (0, "")
    assert sources.fetch_details("https://a.example/g") == ("", "blocked") and len(calls) == 1
    assert sources.judge_page(500, POSTING_PAGE) is None and sources.judge_page(200, POSTING_PAGE) is not None


def test_http_client_errors_retry_in_browser():
    fresh()

    def truncated(url):
        raise http.client.IncompleteRead(b"partial")

    sources.get_page = truncated
    browser.fetch_page = lambda url: (200, POSTING_PAGE)
    assert sources.fetch_details("https://a.example/t")[1] == "ok"
    deep = '<script type="application/ld+json">%s</script>' % ("[" * 100000)
    assert sources.extract_description(deep) == ("", False, False)


def test_timed_out_task_cancelled():
    fresh()
    page = FakePage()
    reset_browser(lambda: FakePW(page))
    hold = threading.Event()
    try:
        browser.submit(lambda pw: hold.wait(5))  # keeps the browser thread busy
        with patched(browser, "RESULT_TIMEOUT_SECONDS", 0.1):
            raises(concurrent.futures.TimeoutError, REAL_FETCH_PAGE, BASE + "/x")
        hold.set()
        assert browser.submit(lambda pw: "after").result(5) == "after"
        assert page.calls == []  # dropped while queued, not run late
    finally:
        hold.set()
        reset_browser(REAL_START)


def test_transient_browser_failure_not_remembered():
    fresh()
    reset_browser(REAL_START)
    flaky = FakePW(missing=("msedge",), broken=("chrome",))
    raises(browser.BrowserUnavailable, browser.launch_headless, flaky)
    raises(browser.BrowserUnavailable, browser.launch_headless, flaky)
    assert len(flaky.chromium.launches) == 4 and browser._unavailable is None  # probed again next time
    starts = []

    def start_once_busy():
        starts.append(1)
        if len(starts) == 1:
            raise RuntimeError("busy")
        return FakePW()

    reset_browser(start_once_busy)
    browser.log.disabled = True
    try:
        with patched(browser, "START_RETRY_SECONDS", 0):
            raises(browser.BrowserUnavailable, browser.submit(lambda pw: 1).result, 5)
            assert browser.submit(lambda pw: "up").result(5) == "up" and len(starts) == 2
    finally:
        browser.log.disabled = False
        reset_browser(REAL_START)


if __name__ == "__main__":
    tests = [f for n, f in list(globals().items()) if n.startswith("test_") and callable(f)]
    for t in tests:
        t()
    print("ok: %d tests" % len(tests))
