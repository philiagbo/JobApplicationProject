import os
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

import keyring.errors
from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

import alerts
import core
import cv
import db
import sources
import watcher

STATIC = Path(__file__).parent / "static"
DEFAULT_COVER_LETTER = Path(__file__).parent / "cover_letter.txt"  # read-only default (D-15)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
# Saving any of these makes the watcher poll now; interval keys are re-read every tick instead.
WAKE_KEYS = frozenset({"reed_api_key", "career_fields", "location", "min_salary"})
# ponytail: a read cap (not MAX_CONTENT_LENGTH) gives the specific 400; Flask's limit would 413 every oversize request, JSON included.
MAX_CV_BYTES = 10 * 1024 * 1024

app = Flask(__name__, static_folder=None)
db.init_db()


@app.before_request
def local_only():
    # Blocks DNS rebinding and cross-site requests: the API returns keys and can trigger fetches.
    if not request.path.startswith("/api/"):
        return None
    host = urlsplit("//" + request.host).hostname
    origin = request.headers.get("Origin")
    if host not in LOCAL_HOSTS or (origin is not None and urlsplit(origin).hostname not in LOCAL_HOSTS):
        return jsonify(error="Forbidden: local requests only"), 403
    return None


@app.errorhandler(HTTPException)
def api_http_error(e):
    if request.path.startswith("/api/"):
        return jsonify(error=e.name), e.code
    return e


@app.errorhandler(Exception)
def api_unhandled_error(e):
    app.logger.exception("Unhandled error")
    if request.path.startswith("/api/"):
        return jsonify(error="Internal server error"), 500
    return "Internal server error", 500


def get_db():
    if "db" not in g:
        g.db = db.connect()
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@app.get("/api/health")
def health():
    return jsonify(ok=True)


def mask(key):
    # the UI only needs to know a key is set; PUT ignores this exact echo so a form save can't overwrite the key
    return "" if not key else "\u2022" * 4 + key[-4:] if len(key) > 8 else "\u2022" * 8


def public(settings):
    return dict(settings, reed_api_key=mask(settings["reed_api_key"]))


@app.get("/api/settings")
def settings_get():
    return jsonify(public(db.get_settings(get_db())))


@app.put("/api/settings")
def settings_put():
    conn = get_db()
    body = request.get_json(silent=True)
    if isinstance(body, dict) and body.get("reed_api_key") == mask(db.get_settings(conn)["reed_api_key"]):
        body = {k: v for k, v in body.items() if k != "reed_api_key"}
    try:
        db.save_settings(conn, body)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    if WAKE_KEYS & body.keys():
        watcher.WAKE.set()
    settings = db.get_settings(conn)
    db.rescore_new(conn, settings)
    return jsonify(public(settings))


@app.get("/api/stats")
def stats_get():
    return jsonify(db.stats(get_db()))


@app.post("/api/fetch")
def fetch_now():
    conn = get_db()
    settings = db.get_settings(conn)
    if not settings["career_fields"] and not watcher.gmail_account(conn):  # Gmail alone is enough (D-04)
        return jsonify(error="Choose at least one career field in settings"), 400
    if not watcher.FETCH_LOCK.acquire(blocking=False):
        return jsonify(error="Fetch already running"), 409
    try:
        result = watcher.run_fetch(conn, settings)
    finally:
        watcher.FETCH_LOCK.release()
    if result["errors"] and not result["by_source"]:
        return jsonify(error=next(iter(result["errors"].values())), errors=result["errors"]), 502
    return jsonify(result)


@app.get("/api/watcher")
def watcher_status():
    # in-memory status only: never reads settings, so it cannot return a saved key
    return jsonify(watcher.status())


@app.errorhandler(keyring.errors.KeyringError)
def _store_down(e):
    return jsonify(error="Could not use the system credential store: %s: %s" % (type(e).__name__, e)), 503


@app.get("/api/gmail")
def gmail_get():
    address = db.get_raw(get_db(), "gmail_address") or ""
    if not address:
        return jsonify(address="", connected=False)
    return jsonify(address=address, connected=alerts.gmail_password(address) is not None)


@app.put("/api/gmail")
def gmail_put():
    body = request.get_json(silent=True)
    if not (isinstance(body, dict) and set(body) == {"address", "app_password"}
            and all(isinstance(v, str) for v in body.values())):
        return jsonify(error="Send address and app_password"), 400
    address = body["address"]
    if "@" not in address or len(address) > 254 or not address.isascii() or address != "".join(address.split()):
        return jsonify(error="Enter your Gmail address"), 400
    password = "".join(body["app_password"].split())  # Google shows the App Password in four groups
    if not password or len(password) > 64 or not password.isascii():
        return jsonify(error="Paste the Google App Password (letters only, spaces are fine)"), 400
    try:
        alerts.gmail_login(address, password).logout()  # test the login before anything is stored
    except alerts.GmailAuthError as e:
        return jsonify(error=str(e)), 400
    except sources.SourceError as e:
        return jsonify(error=str(e)), 502
    conn = get_db()
    old = db.get_raw(conn, "gmail_address")
    alerts.store_password(address, password)
    if old and old != address:
        alerts.forget_password(old)
    db.set_raw(conn, "gmail_address", address)
    if old != address:
        db.set_raw(conn, "gmail_last_poll", None)  # a new account starts with the 7-day lookback
    watcher.GMAIL_WAKE.set()  # not WAKE: that would trigger an unwanted API poll
    return jsonify(address=address, connected=True)


@app.delete("/api/gmail")
def gmail_delete():
    conn = get_db()
    address = db.get_raw(conn, "gmail_address")
    if address:
        alerts.forget_password(address)
    db.set_raw(conn, "gmail_address", None)
    db.set_raw(conn, "gmail_last_poll", None)
    return jsonify(address="", connected=False)


@app.get("/api/jobs")
def jobs_list():
    status = request.args.get("status", "new")
    if status not in db.STATUSES:
        return jsonify(error="Unknown status: %s" % status), 400
    return jsonify(db.list_jobs(get_db(), status))


@app.post("/api/jobs/<int:job_id>/<any(dismiss, queue, undo):action>")
def job_action(job_id, action):
    try:
        return jsonify(db.set_status(get_db(), job_id, action))
    except KeyError:
        return jsonify(error="Job not found"), 404
    except ValueError as e:
        return jsonify(error=str(e)), 409


@app.get("/api/answers")
def answers_list():
    return jsonify(db.list_answers(get_db()))


@app.post("/api/answers")
def answers_post():
    body = request.get_json(silent=True)
    try:
        db.check_answer_body(body, partial=False)
        # company is only for the check; it is never stored
        row, created = db.save_answer(get_db(), body["question"], body["answer"], body.get("field_type", ""),
                                      "profile", body.get("company", ""))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    return jsonify(row), 201 if created else 200


@app.put("/api/answers/<int:answer_id>")
def answers_put(answer_id):
    body = request.get_json(silent=True)
    try:
        db.check_answer_body(body, partial=True)
        return jsonify(db.update_answer(get_db(), answer_id, body))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except KeyError:
        return jsonify(error="Answer not found"), 404
    except sqlite3.IntegrityError:
        return jsonify(error="An answer for that question already exists"), 409


@app.delete("/api/answers/<int:answer_id>")
def answers_delete(answer_id):
    try:
        db.delete_answer(get_db(), answer_id)
    except KeyError:
        return jsonify(error="Answer not found"), 404
    return jsonify(ok=True)


def _profile_json(conn):
    return dict(db.get_profile(conn), cv_file=db.cv_file_name())


@app.get("/api/profile")
def profile_get():
    return jsonify(_profile_json(get_db()))


@app.put("/api/profile")
def profile_put():
    conn = get_db()
    try:
        db.save_profile(conn, request.get_json(silent=True))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    db.rescore_new(conn, db.get_settings(conn))  # D-09: after the save, so the new profile is the one used
    return jsonify(_profile_json(conn))


@app.post("/api/profile/cv")
def profile_cv():
    f = request.files.get("cv")
    if f is None or not f.filename:
        return jsonify(error="No file uploaded"), 400
    ext = os.path.splitext(f.filename.lower())[1]  # the client filename is used for nothing else
    if ext not in (".pdf", ".docx"):
        return jsonify(error="Upload a PDF or DOCX file"), 400
    kind = ext[1:]
    data = f.stream.read(MAX_CV_BYTES + 1)
    if len(data) > MAX_CV_BYTES:
        return jsonify(error="CV is larger than 10 MB"), 400
    try:
        text = cv.read_cv_text(data, kind)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    conn = get_db()
    extracted = core.extract_profile(text, db.get_settings(conn)["known_skills"])
    db.store_cv(data, kind)  # parse first, store second: a 400 never changes the file or the profile
    db.save_profile(conn, core.merge_profile(db.get_profile(conn), extracted))
    db.rescore_new(conn, db.get_settings(conn))
    return jsonify(_profile_json(conn))


@app.get("/api/jobs/<int:job_id>/cover-letter")
def job_cover_letter(job_id):
    conn = get_db()
    try:
        job = db.get_job(conn, job_id)
    except KeyError:
        return jsonify(error="Job not found"), 404
    template = db.get_settings(conn)["cover_letter_template"]
    if not template.strip():
        template = DEFAULT_COVER_LETTER.read_text(encoding="utf-8")  # Windows defaults to cp1252
    return jsonify(text=core.cover_letter(db.get_profile(conn), job, template))


# Serve the built React app; unknown paths fall back to index.html so client-side routes work.
@app.get("/", defaults={"path": ""})
@app.get("/<path:path>")
def ui(path):
    if path.startswith("api/"):
        return jsonify(error="not found"), 404
    if path and (STATIC / path).is_file():
        return send_from_directory(STATIC, path)
    if not (STATIC / "index.html").is_file():
        return "UI not built yet: run `npm run build` in ui/", 503
    return send_from_directory(STATIC, "index.html")


if __name__ == "__main__":
    debug = os.environ.get("JOBHELPER_DEBUG") == "1"
    # the debug reloader runs this file twice; only the child (WERKZEUG_RUN_MAIN) starts the watcher
    if not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        watcher.start()
    app.run(host="127.0.0.1", port=8765, debug=debug)
