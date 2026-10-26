import contextlib
import email
import email.message
import email.utils
import imaplib
import logging
import os
import re
import ssl
import sys
import tempfile
import threading
import time
from datetime import date, timedelta

os.environ["JOBHELPER_DB"] = os.path.join(tempfile.mkdtemp(), "boot.db")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import keyring  # noqa: E402
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
    register_board()


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


if __name__ == "__main__":
    tests = [f for n, f in list(globals().items()) if n.startswith("test_") and callable(f)]
    for t in tests:
        t()
    print("ok: %d tests" % len(tests))
