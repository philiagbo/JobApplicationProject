import concurrent.futures
import logging
import queue
import threading
import time
from concurrent.futures import Future
from typing import Callable, Tuple

from playwright.sync_api import Error, sync_playwright

import core

log = logging.getLogger("jobhelper.browser")

CHANNELS = ("msedge", "chrome")  # the installed browsers, never a download (D-15)
LAUNCH_TIMEOUT_MS = 20000
GOTO_TIMEOUT_MS = 20000
IDLE_TIMEOUT_MS = 5000
RESULT_TIMEOUT_SECONDS = 60  # above launch + goto + idle, so one task fits its own budget
START_RETRY_SECONDS = 60  # a failed Playwright start is tried again after this, not remembered for the process
MISSING_MARKS = ("is not found", "Executable doesn't exist")  # Playwright's words for a channel that is not installed


class BrowserUnavailable(Exception):
    pass


_q = queue.Queue()
_thread = None
_lock = threading.Lock()
_unavailable = None  # set only when neither browser is installed; remembered for the process


def _start_playwright():
    return sync_playwright().start()


def _run(q):
    # Playwright's sync API is not thread-safe: this one thread owns it and every task runs here (D-14)
    pw, failure, retry_at = None, "", 0.0
    while True:
        fn, fut = q.get()
        if not fut.set_running_or_notify_cancel():
            continue
        if pw is None and time.monotonic() >= retry_at:
            try:
                pw = _start_playwright()
            except Exception as e:
                log.exception("Playwright could not start")
                failure, retry_at = str(e), time.monotonic() + START_RETRY_SECONDS
        if pw is None:
            fut.set_exception(BrowserUnavailable("Playwright could not start: " + failure))
            continue
        try:
            fut.set_result(fn(pw))
        except BaseException as e:  # one task must never kill the thread
            fut.set_exception(e)


def submit(fn: Callable) -> Future:
    """Run fn(playwright) on the single browser thread; its result or exception lands in the Future."""
    global _thread
    with _lock:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_run, args=(_q,), name="browser", daemon=True)
            _thread.start()
    fut = Future()
    _q.put((fn, fut))
    return fut


def launch_headless(pw):
    global _unavailable
    if _unavailable:
        raise BrowserUnavailable(_unavailable)
    missing = 0
    for channel in CHANNELS:
        try:
            return pw.chromium.launch(channel=channel, headless=True, timeout=LAUNCH_TIMEOUT_MS)
        except Error as e:  # Playwright's "install" hint is never shown or followed
            missing += any(m in str(e) for m in MISSING_MARKS)
    if missing < len(CHANNELS):
        raise BrowserUnavailable("Edge or Chrome could not start")  # timeout, updating, antivirus: tried again next time
    # ponytail: remembered for the process, so installing Edge or Chrome needs an app restart
    _unavailable = "Edge or Chrome is not installed"
    raise BrowserUnavailable(_unavailable)


def _guard(route):
    # every routed request (the first URL, frames, subresources, script navigations) is checked before it is sent
    if core.fetchable(route.request.url):
        route.continue_()
    else:
        route.abort()


def _load_page(pw, url: str) -> Tuple[int, str]:
    """Open, wait, read, close. Never clicks, types or waits out a challenge page (D-16)."""
    browser = launch_headless(pw)
    try:
        page = browser.new_page()
        refused = []
        try:
            page.route("**/*", _guard)
            # ponytail: Playwright routes only the first URL of a server redirect, so a refused navigation hop is seen
            # here after it was sent and the page is thrown away; urllib refused chains never reach the browser. A
            # filtering proxy would stop the hop itself.
            page.on("request", lambda r: r.is_navigation_request() and not core.fetchable(r.url) and refused.append(r.url))
            response = page.goto(url, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT_MS)
            try:
                page.wait_for_load_state("networkidle", timeout=IDLE_TIMEOUT_MS)
            except Error:
                pass  # best effort for script-rendered pages
            if refused or not core.fetchable(page.url):
                return 0, ""
            return (response.status if response is not None else 0), page.content()
        finally:
            page.close()
    finally:
        browser.close()


def fetch_page(url: str) -> Tuple[int, str]:
    """(status, html) read in the real browser; raises BrowserUnavailable, Error or concurrent.futures.TimeoutError."""
    fut = submit(lambda pw: _load_page(pw, url))
    try:
        return fut.result(timeout=RESULT_TIMEOUT_SECONDS)
    except concurrent.futures.TimeoutError:
        fut.cancel()  # dropped if still queued; a running task finishes and its result is ignored
        raise
