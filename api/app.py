from pathlib import Path

from flask import Flask, jsonify, send_from_directory

STATIC = Path(__file__).parent / "static"

app = Flask(__name__, static_folder=None)


@app.get("/api/health")
def health():
    return jsonify(ok=True)


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
