import logging
import queue
import threading
from concurrent.futures import Future
from typing import Callable, Tuple

from playwright.sync_api import Error, sync_playwright

import core

log = logging.getLogger("jobhelper.browser")

CHANNELS = ("msedge", "chrome")  # the installed browsers, never a download (D-15)
GOTO_TIMEOUT_MS = 20000
IDLE_TIMEOUT_MS = 5000
RESULT_TIMEOUT_SECONDS = 60


class BrowserUnavailable(Exception):
    pass


_q = queue.Queue()
_thread = None
_lock = threading.Lock()
_unavailable = None  # why no browser could be launched; remembered for the process


def _start_playwright():
    return sync_playwright().start()


def _run(q):
    # Playwright's sync API is not thread-safe: this one thread owns it and every task runs here (D-14)
    pw, failure = None, None
    try:
        pw = _start_playwright()
    except Exception as e:
        log.exception("Playwright could not start")
        failure = str(e)
    while True:
        fn, fut = q.get()
        if not fut.set_running_or_notify_cancel():
            continue
        if failure is not None:
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
    for channel in CHANNELS:
        try:
            return pw.chromium.launch(channel=channel, headless=True)
        except Error:
            continue  # not installed; Playwright's "install" hint is never shown or followed
    # ponytail: remembered for the process, so installing Edge or Chrome needs an app restart
    _unavailable = "Edge or Chrome is not installed"
    raise BrowserUnavailable(_unavailable)


def _load_page(pw, url: str) -> Tuple[int, str]:
    """Open, wait, read, close. Never clicks, types or waits out a challenge page (D-16)."""
    browser = launch_headless(pw)
    try:
        page = browser.new_page()
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT_MS)
            try:
                page.wait_for_load_state("networkidle", timeout=IDLE_TIMEOUT_MS)
            except Error:
                pass  # best effort for script-rendered pages
            if not core.http_url(page.url):
                return 0, ""
            return (response.status if response is not None else 0), page.content()
        finally:
            page.close()
    finally:
        browser.close()


def fetch_page(url: str) -> Tuple[int, str]:
    """(status, html) read in the real browser; raises BrowserUnavailable, Error or concurrent.futures.TimeoutError."""
    return submit(lambda pw: _load_page(pw, url)).result(timeout=RESULT_TIMEOUT_SECONDS)
