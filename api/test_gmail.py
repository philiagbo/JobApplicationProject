import contextlib
import email
import email.message
import email.utils
import imaplib
import logging
import os
import re
import socket
import ssl
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import date, timedelta

os.environ["JOBHELPER_DB"] = os.path.join(tempfile.mkdtemp(), "boot.db")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import keyring  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
import keyring.backends.fail  # noqa: E402
import keyring.errors  # noqa: E402
from keyring.backend import KeyringBackend  # noqa: E402


class MemKeyring(KeyringBackend):
    """In-memory credential store: the real keychain must never be used by tests."""
    priority = 1

    def __init__(self):
        self.d = {}
        self.calls = []

    def get_password(self, service, user):
        self.calls.append(("get", service, user))
        return self.d.get((service, user))

    def set_password(self, service, user, password):
        self.calls.append(("set", service, user))
        self.d[(service, user)] = password

    def delete_password(self, service, user):
        self.calls.append(("delete", service, user))
        if (service, user) not in self.d:
            raise keyring.errors.PasswordDeleteError("not found")
        del self.d[(service, user)]


MEM = MemKeyring()
keyring.set_keyring(MEM)

import alerts  # noqa: E402
import app  # noqa: E402
import core  # noqa: E402
import db  # noqa: E402
import sources  # noqa: E402
import watcher  # noqa: E402

sources.REMOTIVE_GAP_SECONDS = 0
REAL_ALERTS = dict(alerts.ALERTS)  # the registry as shipped; fresh() empties it so the older tests see only their test site

SENDER = "alerts@board.example"
PW = "abcdefghijklmnop"
ADDRESS = "me@gmail.com"
calls = []  # (url, params, headers) seen by fake_get_json


def fake_get_json(url, params, headers=None):
    calls.append((url, params, headers))
    if "reed.co.uk" in url:
        return {"results": []}
    if "remotive.com" in url:
        slug = params["search"].replace(" ", "-")
        return {"jobs": [{"url": "https://remotive.com/remote-jobs/" + slug, "title": "Remote " + params["search"],
                          "company_name": "Rem", "job_type": "full_time", "description": "x"}]}
    raise AssertionError(url)


class FakeIMAP:
    MAILBOX = []  # raw message bytes, uid = position + 1
    instances = []
    CONNECT_FAILS = LOGIN_FAILS = FETCH_FAILS = False

    def __init__(self, host, ssl_context=None, timeout=None):
        if FakeIMAP.CONNECT_FAILS:
            raise OSError("network down")
        self.host, self.ssl_context, self.timeout = host, ssl_context, timeout
        self.calls = []
        FakeIMAP.instances.append(self)

    def login(self, user, password):
        self.calls.append(("login", (user, password), {}))
        if FakeIMAP.LOGIN_FAILS:
            raise imaplib.IMAP4.error(b"[AUTHENTICATIONFAILED] Invalid credentials (Failure)")
        return "OK", [b"logged in"]

    def select(self, mailbox="INBOX", readonly=False):
        self.calls.append(("select", (mailbox,), {"readonly": readonly}))
        return "OK", [b"N"]

    def uid(self, command, *args):
        self.calls.append(("uid", (command,) + args, {}))
        if command == "SEARCH":
            sender = args[2].strip('"')
            uids = [str(i + 1).encode() for i, raw in enumerate(FakeIMAP.MAILBOX)
                    if sender in str(email.message_from_bytes(raw)["From"])]
            return "OK", [b" ".join(uids)]
        if FakeIMAP.FETCH_FAILS:
            raise OSError("connection reset")
        raw = FakeIMAP.MAILBOX[int(args[0]) - 1]
        return "OK", [(b"%s (UID %s BODY[] {%d}" % (args[0].encode(), args[0].encode(), len(raw)), raw), b")"]

    def logout(self):
        self.calls.append(("logout", (), {}))
        return "BYE", []


def make_alert(sender, links, subject="New jobs"):
    m = email.message.EmailMessage()
    m["From"] = email.utils.formataddr(("Board Alerts", sender))
    m["To"] = ADDRESS
    m["Subject"] = subject
    m.set_content("<html><body>%s</body></html>" % "".join('<p><a href="%s">%s</a></p>' % l for l in links),
                  subtype="html")
    return m.as_bytes()


def one_job(path="1", title="Data Analyst", extra=""):
    return make_alert(SENDER, [("https://jobs.board.example/job/%s%s" % (path, extra), title)])


def parse_board(html):
    jobs, seen = [], set()
    for href, text in re.findall(r'<a href="([^"]+)">([^<]+)</a>', html):
        job = alerts.alert_job("testboard", alerts.canonical_url(href), text)
        if job is not None and job["url"] not in seen:
            seen.add(job["url"])
            jobs.append(job)
    return jobs


def register_board():
    alerts.ALERTS["testboard"] = ("Test Board", (SENDER,), parse_board)


def fresh():
    os.environ["JOBHELPER_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
    db.init_db()
    sources.get_json = fake_get_json
    del calls[:]
    FakeIMAP.MAILBOX = []
    del FakeIMAP.instances[:]
    FakeIMAP.CONNECT_FAILS = FakeIMAP.LOGIN_FAILS = FakeIMAP.FETCH_FAILS = False
    alerts.imap_factory = FakeIMAP
    alerts.MAX_EMAIL_BYTES = 5 * 1024 * 1024
    core.ALLOW_PRIVATE_HOSTS = False
    MEM.d.clear()
    del MEM.calls[:]
    keyring.set_keyring(MEM)
    watcher.STATUS.clear()
    watcher.WAKE.clear()
    watcher.GMAIL_WAKE.clear()
    alerts.ALERTS.clear()
    register_board()


def real_sites():
    alerts.ALERTS.clear()
    alerts.ALERTS.update(REAL_ALERTS)


def save(**changes):
    with contextlib.closing(db.connect()) as conn:
        db.save_settings(conn, changes)


def stored(key):
    with contextlib.closing(db.connect()) as conn:
        return db.get_raw(conn, key)


def connect_gmail(c, address=ADDRESS, password="abcd efgh ijkl mnop"):
    r = c.put("/api/gmail", json={"address": address, "app_password": password})
    assert r.status_code == 200, r.get_json()
    return r


def jobs(c):
    return c.get("/api/jobs").get_json()


class Records(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.records = []

    def emit(self, record):
        self.records.append(record)


@contextlib.contextmanager
def captured():
    h = Records()
    loggers = (alerts.log, watcher.log)
    for lg in loggers:
        lg.addHandler(h)
    try:
        yield h.records
    finally:
        for lg in loggers:
            lg.removeHandler(h)


def names(inst):
    return [c[0] for c in inst.calls]


def searches(inst):
    return [c[1] for c in inst.calls if c[0] == "uid" and c[1][0] == "SEARCH"]


# --- Task 1: tracer ---------------------------------------------------------

def test_gmail_alert_job_end_to_end():
    fresh()
    c = app.app.test_client()
    FakeIMAP.MAILBOX.append(one_job(extra="?utm_source=alert&tk=abc"))
    r = connect_gmail(c)
    assert r.get_json() == {"address": ADDRESS, "connected": True}
    assert FakeIMAP.instances[0].calls[0] == ("login", (ADDRESS, PW), {})
    assert watcher.GMAIL_WAKE.is_set() and not watcher.WAKE.is_set()
    assert isinstance(watcher._tick_gmail(None), float)
    got = jobs(c)
    assert len(got) == 1
    job = got[0]
    assert job["source"] == "testboard" and job["url"] == "https://jobs.board.example/job/1"
    assert job["title"] == "Data Analyst"
    assert isinstance(job["score"], int) and isinstance(job["pros"], list) and isinstance(job["cons"], list)
    gm = c.get("/api/watcher").get_json()["sources"]["gmail"]
    assert gm["ok"] is True and gm["new"] == 1
    assert c.get("/api/gmail").get_json() == {"address": ADDRESS, "connected": True}
    for body in (c.get("/api/watcher"), c.get("/api/gmail"), c.get("/api/jobs"), c.get("/api/settings")):
        assert PW not in body.get_data(as_text=True)


# --- Task 2: /api/gmail contract -------------------------------------------

def test_gmail_get_not_connected():
    fresh()
    r = app.app.test_client().get("/api/gmail")
    assert r.status_code == 200 and r.get_json() == {"address": "", "connected": False}
    assert MEM.calls == []


def test_gmail_put_bad_body():
    fresh()
    c = app.app.test_client()
    bad = [{"address": ADDRESS}, {}, [], {"address": ADDRESS, "app_password": "x", "extra": 1},
           {"address": 5, "app_password": "x"}, {"address": "not-an-address", "app_password": "abcd"},
           {"address": ADDRESS, "app_password": "pässwörd"}, {"address": ADDRESS, "app_password": "   "}]
    responses = [c.put("/api/gmail", data="not json", content_type="text/plain")]
    responses += [c.put("/api/gmail", json=b) for b in bad]
    for r in responses:
        assert r.status_code == 400 and "error" in r.get_json()
    assert FakeIMAP.instances == [] and not [x for x in MEM.calls if x[0] == "set"]
    assert stored("gmail_address") is None


def test_gmail_put_login_rejected():
    fresh()
    c = app.app.test_client()
    FakeIMAP.LOGIN_FAILS = True
    r = c.put("/api/gmail", json={"address": ADDRESS, "app_password": PW})
    text = r.get_data(as_text=True)
    assert r.status_code == 400 and r.get_json() == {"error": alerts.APP_PASSWORD_HINT}
    assert "App Password" in text and "AUTHENTICATIONFAILED" not in text and PW not in text
    assert MEM.d == {} and stored("gmail_address") is None


def test_gmail_put_unreachable():
    fresh()
    FakeIMAP.CONNECT_FAILS = True
    r = app.app.test_client().put("/api/gmail", json={"address": ADDRESS, "app_password": PW})
    assert r.status_code == 502 and r.get_json()["error"].startswith("Could not reach Gmail")
    assert MEM.d == {} and stored("gmail_address") is None


def test_gmail_credential_store_unavailable():
    fresh()
    c = app.app.test_client()
    keyring.set_keyring(keyring.backends.fail.Keyring())
    try:
        r = c.put("/api/gmail", json={"address": ADDRESS, "app_password": PW})
        assert r.status_code == 503 and r.get_json()["error"].startswith("Could not use the system credential store")
        assert stored("gmail_address") is None
        with contextlib.closing(db.connect()) as conn:
            db.set_raw(conn, "gmail_address", ADDRESS)
        for r in (c.get("/api/gmail"), c.delete("/api/gmail")):
            assert r.status_code == 503 and r.get_json()["error"].startswith("Could not use the system credential store")
    finally:
        keyring.set_keyring(MEM)


def test_gmail_delete_idempotent():
    fresh()
    c = app.app.test_client()
    connect_gmail(c)
    watcher._tick_gmail(None)
    assert stored("gmail_last_poll") is not None
    for _ in range(2):
        r = c.delete("/api/gmail")
        assert r.status_code == 200 and r.get_json() == {"address": "", "connected": False}
        assert MEM.d == {} and stored("gmail_address") is None and stored("gmail_last_poll") is None


def test_gmail_address_change_forgets_old():
    fresh()
    c = app.app.test_client()
    connect_gmail(c, "a@gmail.com")
    watcher._tick_gmail(None)
    assert stored("gmail_last_poll") is not None
    connect_gmail(c, "b@gmail.com")
    assert list(MEM.d) == [(alerts.KEYRING_SERVICE, "b@gmail.com")]
    assert stored("gmail_address") == "b@gmail.com" and stored("gmail_last_poll") is None
    watcher._tick_gmail(None)
    last = stored("gmail_last_poll")
    assert last is not None
    connect_gmail(c, "b@gmail.com")
    assert stored("gmail_last_poll") == last


def test_gmail_password_never_leaks():
    fresh()
    pw = "qwertyuiopasdfgh"
    c = app.app.test_client()
    FakeIMAP.MAILBOX.append(one_job())
    bodies = []
    with captured() as records:
        bodies.append(c.put("/api/gmail", json={"address": ADDRESS, "app_password": pw}))
        bodies.append(c.get("/api/gmail"))
        bodies.append(c.get("/api/settings"))
        bodies.append(c.put("/api/settings", json={"career_fields": ["python"]}))
        bodies.append(c.post("/api/fetch"))
        watcher._tick_gmail(None)
        bodies.append(c.get("/api/watcher"))
        FakeIMAP.LOGIN_FAILS = True
        bodies.append(c.put("/api/gmail", json={"address": ADDRESS, "app_password": pw}))
        FakeIMAP.LOGIN_FAILS = False
        FakeIMAP.FETCH_FAILS = True
        watcher._tick_gmail(None)
        bodies.append(c.get("/api/watcher"))
    assert pw not in "".join(b.get_data(as_text=True) for b in bodies)
    with open(db.db_path(), "rb") as f:
        assert pw.encode() not in f.read()
    assert pw not in repr(watcher.STATUS)
    assert records and not any(pw in r.getMessage() for r in records)


def test_gmail_keys_hidden_from_settings():
    fresh()
    c = app.app.test_client()
    connect_gmail(c)
    assert set(c.get("/api/settings").get_json()) == set(db.DEFAULTS)
    for key, value in (("gmail_address", "x@y.z"), ("gmail_last_poll", "2020-01-01")):
        r = c.put("/api/settings", json={key: value})
        assert r.status_code == 400 and r.get_json() == {"error": "Unknown setting: " + key}


def test_gmail_put_wakes_gmail_only():
    fresh()
    c = app.app.test_client()
    connect_gmail(c)
    assert watcher.GMAIL_WAKE.is_set() and not watcher.WAKE.is_set()
    watcher.GMAIL_WAKE.clear()
    FakeIMAP.LOGIN_FAILS = True
    assert c.put("/api/gmail", json={"address": ADDRESS, "app_password": PW}).status_code == 400
    assert not watcher.GMAIL_WAKE.is_set() and not watcher.WAKE.is_set()


# --- Task 3: IMAP and cadence rules ----------------------------------------

def test_imap_connects_with_verified_tls():
    fresh()
    connect_gmail(app.app.test_client())
    inst = FakeIMAP.instances[0]
    assert inst.host == "imap.gmail.com" and inst.timeout == 30
    assert isinstance(inst.ssl_context, ssl.SSLContext)
    assert inst.ssl_context.verify_mode == ssl.CERT_REQUIRED and inst.ssl_context.check_hostname is True


def test_imap_read_only():
    fresh()
    FakeIMAP.MAILBOX += [one_job("1"), one_job("2", "Other")]
    connect_gmail(app.app.test_client())
    watcher._tick_gmail(None)
    polled = 0
    for inst in FakeIMAP.instances:
        assert set(names(inst)) <= {"login", "select", "uid", "logout"}
        assert names(inst).count("logout") == 1
        for name, args, kwargs in inst.calls:
            if name == "select":
                polled += 1
                assert args == ("INBOX",) and kwargs == {"readonly": True}
            if name == "uid":
                assert args[0] in ("SEARCH", "FETCH")
                if args[0] == "FETCH":
                    assert args[2] == "(BODY.PEEK[])"
    assert polled == 1


def test_imap_logout_on_failure():
    fresh()
    FakeIMAP.MAILBOX.append(one_job())
    connect_gmail(app.app.test_client())
    FakeIMAP.FETCH_FAILS = True
    with captured():
        watcher._tick_gmail(None)
    st = watcher.STATUS["gmail"]
    assert st["ok"] is False and st["error"].startswith("Gmail fetch failed")
    assert names(FakeIMAP.instances[-1]).count("logout") == 1
    assert stored("gmail_last_poll") is None


def test_imap_search_from_and_since():
    fresh()
    FakeIMAP.MAILBOX.append(one_job())
    connect_gmail(app.app.test_client())
    watcher._tick_gmail(None)
    found = searches(FakeIMAP.instances[-1])
    assert found
    for args in found:
        assert args[2] == "FROM" and args[4] == "SINCE"  # never a search without FROM
    mine = [a for a in found if a[3] == '"%s"' % SENDER]
    assert len(mine) == 1 and re.fullmatch(r"\d\d-[A-Z][a-z]{2}-\d{4}", mine[0][5])


def test_imap_date_english_months():
    abbrs = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    for m, abbr in enumerate(abbrs, 1):
        assert alerts.imap_date(date(2026, m, 5)) == "05-%s-2026" % abbr
    assert alerts.imap_date(date(2026, 10, 25)) == "25-Oct-2026"


def test_first_poll_7_days_then_last_poll():
    fresh()
    connect_gmail(app.app.test_client())
    today = date.today()
    watcher._tick_gmail(None)
    assert [a[5] for a in searches(FakeIMAP.instances[-1])] == [alerts.imap_date(today - timedelta(days=7))]
    assert stored("gmail_last_poll") == (today - timedelta(days=1)).isoformat()
    watcher._tick_gmail(None)
    assert [a[5] for a in searches(FakeIMAP.instances[-1])] == [alerts.imap_date(today - timedelta(days=1))]


def test_failed_insert_keeps_poll_window():
    fresh()
    FakeIMAP.MAILBOX.append(one_job())
    connect_gmail(app.app.test_client())
    real = db.insert_jobs

    def locked(*a):
        raise db.sqlite3.OperationalError("database is locked")

    db.insert_jobs = locked
    try:
        with captured():
            watcher._tick_gmail(None)
    finally:
        db.insert_jobs = real
    assert watcher.STATUS["gmail"]["ok"] is False and stored("gmail_last_poll") is None
    watcher._tick_gmail(None)  # the next poll still looks back the full 7 days
    assert [a[5] for a in searches(FakeIMAP.instances[-1])] == [alerts.imap_date(date.today() - timedelta(days=7))]


def test_account_change_during_poll_keeps_lookback():
    fresh()
    c = app.app.test_client()
    connect_gmail(c, "a@gmail.com")
    real = alerts.fetch_gmail_alerts

    def reconnect_meanwhile(*a):
        found = real(*a)
        connect_gmail(c, "b@gmail.com")
        return found

    alerts.fetch_gmail_alerts = reconnect_meanwhile
    try:
        watcher._tick_gmail(None)
    finally:
        alerts.fetch_gmail_alerts = real
    assert stored("gmail_address") == "b@gmail.com" and stored("gmail_last_poll") is None


def test_zero_job_alert_warns_once():
    fresh()
    c = app.app.test_client()
    FakeIMAP.MAILBOX += [make_alert(SENDER, []), make_alert(SENDER, []), one_job()]
    connect_gmail(c)
    watcher._tick_gmail(None)
    st = watcher.STATUS["gmail"]
    assert st["ok"] is True and st["new"] == 1
    assert st["error"] == "Test Board alert parsed 0 jobs — format may have changed"
    r = c.post("/api/fetch")
    assert r.status_code == 200 and r.get_json()["errors"] == {}


def test_parser_exception_isolated():
    fresh()

    def picky(html):
        if "explode" in html:
            raise RuntimeError("bad markup")
        return parse_board(html)

    alerts.ALERTS["testboard"] = ("Test Board", (SENDER,), picky)
    c = app.app.test_client()
    FakeIMAP.MAILBOX += [one_job("1", "explode"), one_job("2", "Fine")]
    connect_gmail(c)
    with captured() as records:
        watcher._tick_gmail(None)
    assert [j["title"] for j in jobs(c)] == ["Fine"]
    assert "parsed 0 jobs" in watcher.STATUS["gmail"]["error"] and watcher.STATUS["gmail"]["ok"] is True
    assert [r for r in records if r.name == "jobhelper.alerts" and r.exc_info]


def test_oversized_email_skipped():
    fresh()
    c = app.app.test_client()
    small, big = one_job("1", "Small"), one_job("2", "Big " + "x" * 5000)
    FakeIMAP.MAILBOX += [big, small]
    connect_gmail(c)
    alerts.MAX_EMAIL_BYTES = len(small) + 100
    watcher._tick_gmail(None)
    assert [j["title"] for j in jobs(c)] == ["Small"]


def test_alert_jobs_not_filtered_by_fields():
    fresh()
    c = app.app.test_client()
    save(career_fields=["nurse"], excluded_words=["analyst"])
    FakeIMAP.MAILBOX.append(one_job())
    connect_gmail(c)
    watcher._tick_gmail(None)
    got = jobs(c)
    assert len(got) == 1 and "Mentions excluded word 'analyst'" in got[0]["cons"]


def test_alert_dedupe_across_polls():
    fresh()
    c = app.app.test_client()
    FakeIMAP.MAILBOX += [one_job(extra="?tk=1"), one_job(extra="?tk=2&utm_source=x#top")]
    connect_gmail(c)
    watcher._tick_gmail(None)
    assert len(jobs(c)) == 1 and watcher.STATUS["gmail"]["new"] == 1
    watcher._tick_gmail(None)
    assert len(jobs(c)) == 1 and watcher.STATUS["gmail"]["new"] == 0


def test_canonical_url_rules():
    cu = alerts.canonical_url
    assert cu("https://Jobs.Board.Example/Job/1?utm=1&jk=ab&x=2#frag") == "https://jobs.board.example/Job/1"
    assert cu("https://Jobs.Board.Example/job?x=2&jk=ab&utm=1#frag", keep=("jk",)) == "https://jobs.board.example/job?jk=ab"
    assert cu("  HTTP://a.example/p  ") == "http://a.example/p"
    for bad in ("file:///etc/passwd", "javascript:alert(1)", "mailto:a@b.c", "ftp://x.example/a", "/job/1", "",
                "http://localhost/x", "http://127.0.0.1/x", "http://10.0.0.5/x", "http://[::1]/x"):
        assert cu(bad) == "", bad
    core.ALLOW_PRIVATE_HOSTS = True
    try:
        assert cu("http://127.0.0.1:8000/x") == "http://127.0.0.1:8000/x"
    finally:
        core.ALLOW_PRIVATE_HOSTS = False


def test_alert_job_shape():
    job = alerts.alert_job("site", "https://x.example/a", "  Title ", " Co ", " Leeds ", " 50k ", "<p>Hello <b>w</b></p><ul><li>one</li></ul>")
    assert set(job) == {"url", "source", "title", "company", "location", "salary", "description", "job_type", "remote"}
    assert job["source"] == "site" and job["title"] == "Title" and job["company"] == "Co"
    assert job["location"] == "Leeds" and job["salary"] == "50k"
    assert "<" not in job["description"] and job["description"].startswith("Hello w")
    assert job["job_type"] is None and job["remote"] is None
    assert alerts.alert_job("site", "https://x.example/a", "   ") is None
    assert alerts.alert_job("site", "javascript:alert(1)", "Title") is None


def test_gmail_tick_cadence():
    fresh()
    connect_gmail(app.app.test_client())
    save(gmail_poll_minutes=60)
    watcher.SECONDS_PER_MINUTE = 0.01
    try:
        last = watcher._tick_gmail(None)
        n = len(FakeIMAP.instances)
        assert watcher._tick_gmail(last) == last and len(FakeIMAP.instances) == n
        watcher.GMAIL_WAKE.set()
        last = watcher._tick_gmail(last)
        assert len(FakeIMAP.instances) == n + 1
        save(gmail_poll_minutes=1)
        time.sleep(0.1)
        assert watcher._tick_gmail(last) != last and len(FakeIMAP.instances) == n + 2
    finally:
        watcher.SECONDS_PER_MINUTE = 60


def test_gmail_tick_without_career_fields():
    fresh()
    c = app.app.test_client()
    FakeIMAP.MAILBOX.append(one_job())
    connect_gmail(c)
    watcher._tick_gmail(None)
    assert len(jobs(c)) == 1
    watcher._tick(None)
    assert calls == []


def test_gmail_tick_not_connected_is_quiet():
    fresh()
    with captured() as records:
        assert isinstance(watcher._tick_gmail(None), float)
    assert FakeIMAP.instances == [] and MEM.calls == [] and "gmail" not in watcher.STATUS and records == []


def test_gmail_tick_skips_when_fetch_running():
    fresh()
    connect_gmail(app.app.test_client())
    del FakeIMAP.instances[:]
    assert watcher.FETCH_LOCK.acquire(blocking=False)
    try:
        assert watcher._tick_gmail(None) is None and FakeIMAP.instances == []
    finally:
        watcher.FETCH_LOCK.release()


def test_api_tick_never_polls_gmail():
    fresh()
    connect_gmail(app.app.test_client())
    save(career_fields=["python"])
    del FakeIMAP.instances[:]
    watcher._tick(None)
    assert FakeIMAP.instances == [] and "gmail" not in watcher.STATUS and calls


def test_manual_fetch_includes_gmail():
    fresh()
    c = app.app.test_client()
    FakeIMAP.MAILBOX.append(one_job())
    connect_gmail(c)
    save(career_fields=["python"])
    r = c.post("/api/fetch")
    assert r.status_code == 200 and set(r.get_json()["by_source"]) == {"remotive", "gmail"}
    fresh()
    c = app.app.test_client()
    FakeIMAP.MAILBOX.append(one_job())
    connect_gmail(c)
    r = c.post("/api/fetch")
    assert r.status_code == 200 and r.get_json() == {"new": 1, "by_source": {"gmail": 1}, "errors": {}}
    fresh()
    r = app.app.test_client().post("/api/fetch")
    assert r.status_code == 400 and r.get_json() == {"error": "Choose at least one career field in settings"}


def test_loop_keeps_gmail_alive():
    fresh()
    count, real_tick, real_gmail, real_ticks = [0], watcher._tick, watcher._tick_gmail, watcher.TICK_SECONDS

    def broken(last):
        raise RuntimeError("db locked")

    def counting(last):
        count[0] += 1
        if count[0] == 3:
            raise SystemExit  # ends the thread quietly
        return last

    watcher._tick, watcher._tick_gmail, watcher.TICK_SECONDS = broken, counting, 0.05
    watcher.log.disabled = True
    try:
        t = threading.Thread(target=watcher._loop, daemon=True)
        t.start()
        t.join(2)
        assert not t.is_alive() and count[0] == 3
    finally:
        watcher._tick, watcher._tick_gmail, watcher.TICK_SECONDS = real_tick, real_gmail, real_ticks
        watcher.log.disabled = False


# --- 04-05: the person's real sample alerts ---------------------------------

SAMPLES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
JOB_KEYS = {"url", "source", "title", "company", "location", "salary", "description", "job_type", "remote"}
SITES = {"linkedin", "indeed", "cv-library", "totaljobs"}  # job sources; Indeed and Totaljobs each have two senders


def sample(name):
    with open(os.path.join(SAMPLES, name + ".eml"), "rb") as f:
        return f.read()


def sample_body(name):
    return alerts.email_body(email.message_from_bytes(sample(name), policy=email.policy.default))


def sample_without_links(name):
    soup = BeautifulSoup(sample_body(name), "html.parser")
    for a in soup.find_all("a"):
        a.decompose()
    return str(soup)


def check_sample(key, name, source, count, first, query=(), extra=None):
    """The parser registered as `key` on sample `name`: the job count, the first job's fields, and the rules every job follows."""
    jobs = REAL_ALERTS[key][2](sample_body(name))
    assert len(jobs) == count, len(jobs)
    for i, want in [(0, first)] + sorted((extra or {}).items()):
        for field, value in want.items():
            if field == "url_prefix":
                assert jobs[i]["url"].startswith(value), jobs[i]["url"]
            elif field == "description_has":
                assert value in jobs[i]["description"], jobs[i]["description"]
            else:
                assert jobs[i][field] == value, (i, field, jobs[i][field])
    urls = [j["url"] for j in jobs]
    assert len(set(urls)) == len(urls)
    for j in jobs:
        assert set(j) == JOB_KEYS and j["source"] == source and j["title"]
        assert "<" not in j["description"] and core.http_url(j["url"])
        assert "utm_" not in j["url"] and "#" not in j["url"]
        keys = {k for k, _ in urllib_parse_qsl(j["url"])}
        assert keys <= set(query) or "/pagead/clk" in j["url"], keys  # sponsored Indeed links have no job ID to keep
    return jobs


def urllib_parse_qsl(url):
    return alerts.parse_qsl(alerts.urlsplit(url).query)


# Each site's expected first job comes from the sample's first card. Place names such as Sampletown and the REDACTED
# tokens are redaction placeholders, so they are never asserted.

def test_parse_linkedin_sample():
    check_sample("linkedin", "linkedin", "linkedin", 6, dict(
        url="https://www.linkedin.com/jobs/view/4479505277", title="Software Developer, Cerberus", company="bet365",
        location="Manchester", salary="", remote="Hybrid", job_type=None),
        extra={3: dict(url="https://www.linkedin.com/jobs/view/4477704384", title="Full Stack Engineer",
                       company="Corecom Consulting", location="Manchester Area, United Kingdom",
                       salary="£80K-£90K / year", remote="Remote")})


def test_parse_indeed_sample():
    jobs = check_sample("indeed", "indeed", "indeed", 29, dict(
        url="https://uk.indeed.com/viewjob?jk=1e7d0d5a0b4b0a64", title="Inclusion Co-ordinator and Designated Safeguarding Lead (DSL) (7817)",
        company="Hanson Academy", location="Bradford", salary="£46,579 - £50,908 a year"), query=("jk",),
        extra={3: dict(title="Domestic Abuse Case Worker (Refuge based)", company="Staying Put", location="Bradford",
                       salary="£27,554 - £28,735 a year", url_prefix="https://uk.indeed.com/pagead/clk/")})
    # 30 cards in the sample: two sponsored links are identical once redacted, so they are one job here
    assert sum("viewjob?jk=" in j["url"] for j in jobs) == 6


def test_parse_indeed_match_sample():
    check_sample("indeed-match", "indeed-match", "indeed", 1, dict(
        url_prefix="https://cts.indeed.com/v3/", title="Employee Relations Specialist", company="BDS Northern",
        location="Bradford", salary="£19.48 - £25.27 an hour", job_type="Temporary", remote="Hybrid",
        description_has="strong understanding of UK employment law"))
    job = alerts.parse_indeed_match(sample_body("indeed-match"))[0]
    assert "Hi " not in job["description"] and "*About the role*" in job["description"]  # greeting dropped, preview kept


def test_parse_cv_library_sample():
    check_sample("cv-library", "cv-library", "cv-library", 10, dict(
        url="https://www.cv-library.co.uk/job/212349846/Trainee-Mortgage-Advisor", title="Trainee Mortgage Advisor",
        company="", location="Nationwide", salary="", description_has="passing CeMAP and becoming a mortgage adviser"))


def test_parse_totaljobs_sample():
    check_sample("totaljobs", "totaljobs", "totaljobs", 19, dict(
        url="https://www.totaljobs.com/JobSearch/EmailLink.aspx?JobID=82529937", title="Associate IS Specialist/Information Services",
        company="First Choice Corporate Ltd", location="Trafford Park, Manchester (M17)", salary="Negotiable"), query=("JobID",),
        extra={10: dict(title="Design Specialist, Manchester", company="Bureau Veritas", salary="")})  # "Salary unspecified" is no salary


def test_parse_totaljobs_invite_sample():
    check_sample("totaljobs-invite", "totaljobs-invite", "totaljobs", 1, dict(
        url_prefix="https://web.totaljobsmail.co.uk/", title="Support Coordinator", company="NFP People"))
    assert alerts.parse_totaljobs_invite(sample_body("totaljobs-invite"))[0]["location"]
    for title in ("Contact Centre Advisor", "Data Privacy Officer", "Terms Manager", "Browser Engineer"):
        jobs = alerts.parse_totaljobs_invite(sample_body("totaljobs-invite").replace("Support Coordinator", title))
        assert [j["title"] for j in jobs] == [title], title


# key -> (sample, URL rule): the four sites whose links carry a job ID
MULTI = {"linkedin": ("linkedin", alerts._linkedin_url), "indeed": ("indeed", alerts._indeed_url),
         "cv-library": ("cv-library", alerts._cv_url), "totaljobs": ("totaljobs", alerts._totaljobs_url)}
ALL = [("linkedin", "linkedin"), ("indeed", "indeed"), ("indeed-match", "indeed-match"), ("cv-library", "cv-library"),
       ("totaljobs", "totaljobs"), ("totaljobs-invite", "totaljobs-invite")]


def test_parsers_collapse_duplicate_links():
    for key, name in ALL:
        parse = REAL_ALERTS[key][2]
        before = parse(sample_body(name))
        soup = BeautifulSoup(sample_body(name), "html.parser")
        first = before[0]["title"]
        a = next(a for a in soup.find_all("a", href=True) if first in " ".join(a.get_text().split()))
        dup = soup.new_tag("a", href=a["href"] + ("&" if "?" in a["href"] else "?") + "utm_source=x&trk=y")
        dup.string = "again"
        a.insert_after(dup)
        after = parse(str(soup))
        assert [j["url"] for j in after] == [j["url"] for j in before], key


def test_parsers_keep_document_order():
    for key, (name, canon) in MULTI.items():
        order = []
        for a in BeautifulSoup(sample_body(name), "html.parser").find_all("a", href=True):
            url = canon(a["href"]) if a.get_text(strip=True) else ""
            if url and url not in order:
                order.append(url)
        got = [j["url"] for j in REAL_ALERTS[key][2](sample_body(name))]
        assert got == order and len(got) > 1, key


def test_parsers_empty_input():
    for key, name in ALL:
        parse = REAL_ALERTS[key][2]
        assert parse("") == [], key
        assert parse("<html><body><p>No jobs today</p></body></html>") == [], key
        assert parse(sample_without_links(name)) == [], key


def test_parsers_make_no_network_calls():
    def boom(*a, **k):
        raise AssertionError("network call")

    real = urllib.request.urlopen, socket.create_connection
    urllib.request.urlopen, socket.create_connection = boom, boom
    try:
        for key, name in ALL:
            assert REAL_ALERTS[key][2](sample_body(name))
    finally:
        urllib.request.urlopen, socket.create_connection = real


def test_alert_registry_matches_samples():
    assert set(REAL_ALERTS) == {k for k, _ in ALL}
    labels = {"linkedin": "LinkedIn", "indeed": "Indeed", "indeed-match": "Indeed", "cv-library": "CV-Library",
              "totaljobs": "Totaljobs", "totaljobs-invite": "Totaljobs"}
    for key, name in ALL:
        label, senders, parse = REAL_ALERTS[key]
        sent_from = email.utils.parseaddr(str(email.message_from_bytes(sample(name))["From"]))[1]
        assert label == labels[key] and sent_from in senders and all("@" in x for x in senders), key
        assert {j["source"] for j in parse(sample_body(name))} <= SITES


def test_linkedin_sample_end_to_end():
    fresh()
    real_sites()
    c = app.app.test_client()
    connect_gmail(c)
    FakeIMAP.MAILBOX = [sample("linkedin")]
    assert isinstance(watcher._tick_gmail(None), float)
    got = [j for j in jobs(c) if j["source"] == "linkedin"]
    assert len(got) == 6
    first = next(j for j in got if j["title"] == "Software Developer, Cerberus")
    assert first["company"] == "bet365" and first["url"] == "https://www.linkedin.com/jobs/view/4479505277"
    assert all(j["url"].startswith("https://www.linkedin.com/jobs/view/") and "?" not in j["url"] for j in got)
    st = watcher.STATUS["gmail"]
    assert st["ok"] is True and st["error"] is None


def test_six_sample_poll_end_to_end():
    fresh()
    real_sites()
    c = app.app.test_client()
    connect_gmail(c)
    FakeIMAP.MAILBOX = [sample(name) for _, name in ALL]
    watcher._tick_gmail(None)
    got = jobs(c)
    assert {j["source"] for j in got} == SITES and len(got) == 6 + 29 + 1 + 10 + 19 + 1
    st = watcher.STATUS["gmail"]
    assert st["ok"] is True and st["error"] is None and st["new"] == len(got)
    watcher._tick_gmail(None)  # same mailbox again: same URLs, no new rows
    assert watcher.STATUS["gmail"]["new"] == 0 and len(jobs(c)) == len(got)


def test_format_change_warns():
    fresh()
    real_sites()

    def stripped(name):
        m = email.message_from_bytes(sample(name), policy=email.policy.default)
        m.set_content(sample_without_links(name), subtype="html")  # same From, no job links
        return m.as_bytes()

    c = app.app.test_client()
    connect_gmail(c)
    FakeIMAP.MAILBOX = [stripped("indeed"), sample("linkedin"), sample("cv-library"), sample("totaljobs")]
    watcher._tick_gmail(None)
    st = watcher.STATUS["gmail"]
    assert st["error"] == "Indeed alert parsed 0 jobs — format may have changed"
    assert {j["source"] for j in jobs(c)} == {"linkedin", "cv-library", "totaljobs"}
    FakeIMAP.MAILBOX = [stripped("indeed"), stripped("indeed-match")]  # both Indeed senders: still one warning
    watcher._tick_gmail(None)
    assert watcher.STATUS["gmail"]["error"] == "Indeed alert parsed 0 jobs — format may have changed"


if __name__ == "__main__":
    tests = [f for n, f in list(globals().items()) if n.startswith("test_") and callable(f)]
    for t in tests:
        t()
    print("ok: %d tests" % len(tests))
