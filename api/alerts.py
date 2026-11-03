import contextlib
import datetime
import email
import email.policy
import imaplib
import logging
import re
import ssl
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import keyring
import keyring.errors
from bs4 import BeautifulSoup, NavigableString, Tag

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
              salary: str = "", snippet: str = "", job_type: Optional[str] = None,
              remote: Optional[str] = None) -> Optional[dict]:
    title = (title or "").strip()
    if not core.http_url(url) or not title:
        return None
    return {
        "url": url, "source": site, "title": title, "company": (company or "").strip(),
        "location": (location or "").strip(), "salary": (salary or "").strip(),
        "description": core.plain_text(snippet),  # plain text only, never HTML
        "job_type": job_type, "remote": remote,
    }


# --- site parsers (D-06): HTML in, job dicts out; no network, no assumption about wrapper markup ---------------------

_REMOTE = core._REMOTES + [("On-site", ["in person"])]
_SALARY = re.compile(r"[£$€]|\bper (?:annum|hour|day|year)\b", re.I)


def _on(host: Optional[str], domain: str) -> bool:
    return bool(host) and (host == domain or host.endswith("." + domain))


def _text(node) -> str:
    return " ".join(node.get_text().split())


def _strings(soup) -> List[str]:
    return [" ".join(n.split()) for n in soup.find_all(string=True) if type(n) is NavigableString and n.strip()]


def _label(text: str, table: list) -> Optional[str]:
    return core._first_label(core.normalise(text), table)


def _groups(html: str, canon: Callable[[str], str]) -> List[Tuple[str, List[str]]]:
    """[(url, lines)] in document order: a job link's own text plus the text after it, up to the next link.
    A repeated link ("View more", "Apply") or any other link with text ends the card; the first sighting of a job wins."""
    out, cur, seen = [], None, set()
    for n in BeautifulSoup(html or "", "html.parser").descendants:
        if isinstance(n, Tag):
            if n.name == "a" and n.get_text(strip=True):
                try:
                    url = canon(n.get("href") or "")
                except ValueError:
                    url = ""
                if url and url not in seen:
                    seen.add(url)
                    cur = []
                    out.append((url, cur))
                else:
                    cur = None
        elif type(n) is NavigableString and cur is not None and n.strip():
            cur.append(" ".join(n.split()))
    return out


def _extras(lines: List[str]) -> Tuple[str, Optional[str], Optional[str], str]:
    """salary, job type, work mode, snippet from the loose lines of a card.
    ponytail: heuristic, short lines are tags (salary has a currency sign), 60+ characters is description text."""
    salary, job_type, remote, snippet = "", None, None, []
    for t in lines:
        if len(t) >= 60:
            snippet.append(t)
        elif not salary and _SALARY.search(t):
            salary = t
        else:
            job_type = job_type or _label(t, core._TYPES)
            remote = remote or _label(t, _REMOTE)
    return salary, job_type, remote, "\n".join(snippet)


def _keep_all(href: str) -> str:
    # a link with no job ID in it: keep everything but utm_ so the same email re-read gives the same URL
    return canonical_url(href, tuple(k for k, _ in parse_qsl(urlsplit(href).query) if not k.startswith("utm_")))


def _clean(jobs: List[Optional[dict]]) -> List[dict]:
    return [j for j in jobs if j is not None]


def _linkedin_url(href: str) -> str:
    p = urlsplit(href.strip())
    m = re.search(r"/jobs/view/(?:[^/?]*-)?(\d+)", p.path)
    return canonical_url("https://www.linkedin.com/jobs/view/" + m.group(1)) if m and _on(p.hostname, "linkedin.com") else ""


def parse_linkedin(html: str) -> List[dict]:
    jobs = []
    for url, s in _groups(html, _linkedin_url):
        company, _, where = (s[1] if len(s) > 1 else "").partition(" · ")  # "bet365 · Manchester (Hybrid)"
        m = re.search(r"\s*\(([^()]*)\)\s*$", where)
        mode = _label(m.group(1), _REMOTE) if m else None
        salary, job_type, remote, snippet = _extras(s[2:])
        jobs.append(alert_job("linkedin", url, s[0], company, where[:m.start()] if mode else where, salary, snippet,
                              job_type, mode or remote))
    return _clean(jobs)


def _indeed_url(href: str) -> str:
    p = urlsplit(href.strip())
    if not _on(p.hostname, "indeed.com") or not p.path.startswith(("/rc/clk", "/pagead/clk", "/viewjob")):
        return ""
    jk = dict(parse_qsl(p.query)).get("jk", "")
    if re.fullmatch(r"[A-Za-z0-9]+", jk):
        return canonical_url("https://%s/viewjob?jk=%s" % (p.hostname, jk), ("jk",))
    # ponytail: sponsored links carry no job ID, so the same ad in two emails is two rows; upgrade: dedupe on title+company
    return _keep_all(href) if p.path.startswith("/pagead/clk") else ""


def parse_indeed(html: str) -> List[dict]:
    jobs = []
    for url, s in _groups(html, _indeed_url):
        title, company, location = (s + ["", ""])[:3]
        salary, job_type, remote, snippet = _extras(s[3:])
        jobs.append(alert_job("indeed", url, title, company, location, salary, snippet, job_type, remote))
    return _clean(jobs)


_MATCH_LABELS = ("Salary", "Job types", "Work settings", "Job description preview")


def parse_indeed_match(html: str) -> List[dict]:
    """One job per "job match" email: title, company, location, then labelled Salary / Job types / Work settings / preview."""
    soup = BeautifulSoup(html or "", "html.parser")
    s = _strings(soup)
    links = {}
    for a in soup.find_all("a", href=True):
        links.setdefault(_text(a), a["href"])
    first = next((i for i, t in enumerate(s) if t in _MATCH_LABELS), None)
    if first is None:
        return []
    t = next((i for i in range(first - 1, max(first - 5, -1), -1) if s[i] in links), None)
    if t is None:
        return []
    company, location = (s[t + 1:first] + ["", ""])[:2]
    sections, cur = {}, None
    for x in s[first:]:
        if x == "Learn more":
            break
        cur = sections.setdefault(x, []) if x in _MATCH_LABELS else cur
        if cur is not None and x not in _MATCH_LABELS:
            cur.append(x)
    intro = []
    if "Introduction" in s and "View job" in s:
        intro = [x for x in s[s.index("Introduction") + 1:s.index("View job")] if not re.match(r"(hi|hello|dear)\b", x, re.I)]
    # ponytail: no job ID in these links (opaque tracker path); the same job in two emails is two rows
    url = canonical_url(links.get(s[t]) or links.get("View job") or "")
    chips = lambda key, table: next((l for l in (_label(c, table) for c in sections.get(key, [])) if l), None)  # noqa: E731
    job = alert_job("indeed", url, s[t], company, location, (sections.get("Salary") or [""])[0],
                    "\n".join(intro + sections.get("Job description preview", [])),
                    chips("Job types", core._TYPES), chips("Work settings", _REMOTE))
    return [job] if job else []


def _cv_url(href: str) -> str:
    p = urlsplit(href.strip())
    if not _on(p.hostname, "cv-library.co.uk"):
        return ""
    # alert links are click wrappers: /refer/<id>?url=%2Fjob%2F<id>%2F<slug>%3Futm_...  (read from the text, never followed)
    m = re.match(r"/job/\d+(?:/[^/]+)?", urlsplit(dict(parse_qsl(p.query)).get("url", p.path)).path)
    return canonical_url("https://www.cv-library.co.uk" + m.group(0)) if m else ""


def parse_cv_library(html: str) -> List[dict]:
    jobs = []
    for url, s in _groups(html, _cv_url):  # title, location, snippet; the alert carries no company or salary
        jobs.append(alert_job("cv-library", url, s[0], "", s[1] if len(s) > 1 else "", "", "\n".join(s[2:])))
    return _clean(jobs)


def _totaljobs_url(href: str) -> str:
    p = urlsplit(href.strip())
    jid = dict(parse_qsl(p.query)).get("JobID", "")
    return canonical_url("https://www.totaljobs.com/JobSearch/EmailLink.aspx?JobID=" + jid, ("JobID",)) \
        if jid.isdigit() and _on(p.hostname, "totaljobs.com") else ""


def parse_totaljobs(html: str) -> List[dict]:
    jobs = []
    for url, s in _groups(html, _totaljobs_url):  # title, then "• location", "• salary", "• company"
        location, salary, company = ([x[1:].strip() for x in s[1:] if x.startswith("•")] + ["", "", ""])[:3]
        jobs.append(alert_job("totaljobs", url, s[0], company, location, "" if "unspecified" in salary.lower() else salary))
    return _clean(jobs)


# whole labels only: "Contact Centre Advisor" or "Data Privacy Officer" is a job title, not page chrome
_CHROME = re.compile(r"(show|view) in (the )?browser|unsubscribe|privacy policy|terms and conditions|contact us", re.I)


def parse_totaljobs_invite(html: str) -> List[dict]:
    """One job per recruiter "invited you to apply" email: the first link with text that is not page chrome is the job."""
    soup = BeautifulSoup(html or "", "html.parser")
    s = _strings(soup)
    for a in soup.find_all("a", href=True):
        title = _text(a)
        if title and title in s and not _CHROME.fullmatch(title) and "totaljobs" in (urlsplit(a["href"]).hostname or ""):
            rest = s[s.index(title) + 1:]
            company, location = ((rest[:rest.index(title)] if title in rest else rest[:2]) + ["", ""])[:2]
            # ponytail: no job ID in these links (opaque tracker path); the same job in two emails is two rows
            job = alert_job("totaljobs", canonical_url(a["href"]), title, company, location)
            return [job] if job else []
    return []


# site -> (label, sender addresses, parser(html) -> jobs); exact sender addresses from the person's real samples (never a
# bare domain: FROM is a substring search). Two senders of one site share the job source and the label, so D-08 warns once.
# Tests register a test site on top of these.
ALERTS = {
    "linkedin": ("LinkedIn", ("jobs-noreply@linkedin.com",), parse_linkedin),
    "indeed": ("Indeed", ("donotreply@jobalert.indeed.com",), parse_indeed),
    "indeed-match": ("Indeed", ("donotreply@match.indeed.com",), parse_indeed_match),
    "cv-library": ("CV-Library", ("admin@cv-library.co.uk",), parse_cv_library),
    "totaljobs": ("Totaljobs", ("totaljobs@totaljobsmail.com",), parse_totaljobs),
    "totaljobs-invite": ("Totaljobs", ("totaljobs@recruit.totaljobsmail.co.uk",), parse_totaljobs_invite),
}  # type: Dict[str, Tuple[str, Tuple[str, ...], Callable[[str], List[dict]]]]


def fetch_gmail_alerts(address: str, since: datetime.date, warn: Callable[[str], None]) -> List[dict]:
    if not ALERTS:
        return []
    password = gmail_password(address)
    if password is None:
        raise sources.SourceError("Gmail is not connected")
    client = gmail_login(address, password)
    found = {}  # type: Dict[str, dict]
    empty = set()  # labels of sites with an alert that gave no jobs
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
                        empty.add(label)
                    for job in jobs:
                        found.setdefault(job["url"], job)
    except (OSError, imaplib.IMAP4.error) as e:
        raise sources.SourceError("Gmail fetch failed: %s" % e)
    finally:
        with contextlib.suppress(Exception):
            client.logout()
    for label in sorted(empty):
        warn("%s alert parsed 0 jobs — format may have changed" % label)
    return list(found.values())
