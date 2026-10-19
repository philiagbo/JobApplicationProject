import os
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

import db
import watcher

STATIC = Path(__file__).parent / "static"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

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


@app.get("/api/settings")
def settings_get():
    return jsonify(db.get_settings(get_db()))


@app.put("/api/settings")
def settings_put():
    conn = get_db()
    try:
        db.save_settings(conn, request.get_json(silent=True))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    settings = db.get_settings(conn)
    db.rescore_new(conn, settings)
    return jsonify(settings)


@app.get("/api/stats")
def stats_get():
    return jsonify(db.stats(get_db()))


@app.post("/api/fetch")
def fetch_now():
    conn = get_db()
    settings = db.get_settings(conn)
    if not settings["career_fields"]:
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
