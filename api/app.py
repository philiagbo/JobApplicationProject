from pathlib import Path

from flask import Flask, g, jsonify, request, send_from_directory

import db
import sources

STATIC = Path(__file__).parent / "static"

app = Flask(__name__, static_folder=None)
db.init_db()


def get_db():
    if "db" not in g:
        g.db = db.connect()
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def run_fetch(conn, settings):
    jobs = sources.fetch_remotive(settings["career_fields"])
    counts = {"remotive": db.insert_jobs(conn, jobs, settings)}
    return {"new": sum(counts.values()), "by_source": counts}


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
    return jsonify(db.get_settings(conn))


@app.post("/api/fetch")
def fetch_now():
    conn = get_db()
    settings = db.get_settings(conn)
    if not settings["career_fields"]:
        return jsonify(error="Choose at least one career field in settings"), 400
    try:
        return jsonify(run_fetch(conn, settings))
    except sources.SourceError as e:
        return jsonify(error=str(e)), 502


@app.get("/api/jobs")
def jobs_list():
    return jsonify(db.list_jobs(get_db(), "new"))


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
    app.run(port=8765, debug=True)
