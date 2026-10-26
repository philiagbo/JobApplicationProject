import contextlib
import datetime
import email
import email.policy
import imaplib
import logging
import ssl
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import keyring
import keyring.errors

import core
import sources

KEYRING_SERVICE = "JobHelper"
IMAP_HOST = "imap.gmail.com"
IMAP_TIMEOUT = 30
MAX_EMAIL_BYTES = 5 * 1024 * 1024
APP_PASSWORD_HINT = ("Gmail rejected the login. Use a Google App Password "
                     "(2-Step Verification must be on), not your normal Gmail password.")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
log = logging.getLogger("jobhelper.alerts")

imap_factory = imaplib.IMAP4_SSL  # looked up at call time: tests swap it, like sources.get_json


class GmailAuthError(sources.SourceError):
    pass


# --- credential store -------------------------------------------------------

def gmail_password(address: str) -> Optional[str]:
    return keyring.get_password(KEYRING_SERVICE, address)


def store_password(address: str, password: str) -> None:
    keyring.set_password(KEYRING_SERVICE, address, password)


def forget_password(address: str) -> None:
    try:
        keyring.delete_password(KEYRING_SERVICE, address)
    except keyring.errors.PasswordDeleteError:
        pass  # already gone


# --- IMAP -------------------------------------------------------------------

def imap_date(d: datetime.date) -> str:
    # built by hand, not with a date-format call: month names follow the OS locale, and Gmail only accepts English month names
    return "%02d-%s-%d" % (d.day, _MONTHS[d.month - 1], d.year)


def gmail_login(address: str, password: str):
    try:
        client = imap_factory(IMAP_HOST, ssl_context=ssl.create_default_context(), timeout=IMAP_TIMEOUT)
    except OSError as e:
        raise sources.SourceError("Could not reach Gmail: %s" % e)
    try:
        client.login(address, password)
    except imaplib.IMAP4.error:
        with contextlib.suppress(Exception):
            client.logout()
        raise GmailAuthError(APP_PASSWORD_HINT)  # fixed text: the server reply is never echoed
    except OSError as e:
        raise sources.SourceError("Could not reach Gmail: %s" % e)
    return client


# --- alert emails -----------------------------------------------------------

# site -> (label, sender addresses, parser(html) -> jobs)
# 04-05 adds linkedin, indeed, cv-library and totaljobs from the person's real samples (D-06); tests register a test site.
ALERTS = {}  # type: Dict[str, Tuple[str, Tuple[str, ...], Callable[[str], List[dict]]]]


def email_body(msg) -> str:
    part = msg.get_body(preferencelist=("html", "plain"))
    return part.get_content() if part is not None else ""


def canonical_url(href: str, keep: Tuple[str, ...] = ()) -> str:
    """The one URL a job is stored under, so UNIQUE(url) dedupes the same job across emails."""
    href = href.strip()
    if not core.http_url(href):
        return ""
    p = urlsplit(href)
    query = urlencode([(k, v) for k, v in parse_qsl(p.query) if k in keep])
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path, query, ""))


def alert_job(site: str, url: str, title: str, company: str = "", location: str = "",
              salary: str = "", snippet: str = "") -> Optional[dict]:
    title = (title or "").strip()
    if not core.http_url(url) or not title:
        return None
    return {
        "url": url, "source": site, "title": title, "company": (company or "").strip(),
        "location": (location or "").strip(), "salary": (salary or "").strip(),
        "description": core.plain_text(snippet),  # plain text only, never HTML
        "job_type": None, "remote": None,
    }


def fetch_gmail_alerts(address: str, since: datetime.date, warn: Callable[[str], None]) -> List[dict]:
    if not ALERTS:
        return []
    password = gmail_password(address)
    if password is None:
        raise sources.SourceError("Gmail is not connected")
    client = gmail_login(address, password)
    found = {}  # type: Dict[str, dict]
    empty = set()  # sites with an alert that gave no jobs
    try:
        # ponytail: INBOX only, [Gmail]/All Mail is locale-named. Alerts archived out of INBOX (e.g. by a Gmail
        # filter) are missed; upgrade: find All Mail by its IMAP \All special-use flag and select that instead.
        typ, _ = client.select("INBOX", readonly=True)
        if typ != "OK":
            raise sources.SourceError("Gmail fetch failed: could not open INBOX")
        # ponytail: SINCE is date-granular, so each poll re-reads the day's alerts and URL dedupe absorbs the overlap;
        # every mail from an alert sender counts as an alert (add a subject check if a sender also sends other mail).
        for site, (label, senders, parse) in ALERTS.items():
            for sender in senders:
                typ, data = client.uid("SEARCH", None, "FROM", '"%s"' % sender, "SINCE", imap_date(since))
                if typ != "OK" or not data or not data[0]:
                    continue
                for uid in data[0].split():
                    typ, reply = client.uid("FETCH", uid.decode(), "(BODY.PEEK[])")
                    raw = next((x[1] for x in reply or [] if isinstance(x, tuple)), None)
                    if typ != "OK" or not raw or len(raw) > MAX_EMAIL_BYTES:  # ponytail: size checked after download
                        continue
                    try:
                        msg = email.message_from_bytes(raw, policy=email.policy.default)
                        jobs = parse(email_body(msg))
                    except Exception:
                        log.exception("%s alert parser failed", site)
                        jobs = []
                    if not jobs:
                        empty.add(site)
                    for job in jobs:
                        found.setdefault(job["url"], job)
    except (OSError, imaplib.IMAP4.error) as e:
        raise sources.SourceError("Gmail fetch failed: %s" % e)
    finally:
        with contextlib.suppress(Exception):
            client.logout()
    for site in sorted(empty):
        warn("%s alert parsed 0 jobs — format may have changed" % ALERTS[site][0])
    return list(found.values())
