"""
Very small REST service that exposes one GET endpoint:

    GET /api/tex2html?file=<repo‑relative‑path>.tex

It validates the path, invokes tex-to-html.py,
and streams the resulting HTML back to the caller.
"""

from __future__ import annotations
import os, subprocess, pathlib, logging
from flask import Flask, request, abort, Response, jsonify
from werkzeug.exceptions import HTTPException
from functools import lru_cache
from pathlib import Path   #  add this line at the top

# ──────────────────────────────────────────────────────────────
# Configuration (edit these four lines or use env vars)
# ──────────────────────────────────────────────────────────────
BASE_DIR = (Path(__file__).parent / "classes").resolve()
TEX2HTML = (Path(__file__).parent / "scripts" / "tex-to-html.py").resolve()
PYTHON_EXE = os.getenv("T2H_PYTHON", "python3")
PORT       = int(os.getenv("PORT", 8000))

# ──────────────────────────────────────────────────────────────
# Flask setup
# ──────────────────────────────────────────────────────────────
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Optional: allow JS running on another origin to call us
#   (Only do this if your Pages site and API live on different domains)
@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

# ──────────────────────────────────────────────────────────────
# Error→JSON helper so callers can parse failures programmatically
# ──────────────────────────────────────────────────────────────
@app.errorhandler(HTTPException)
def handle_http_exc(exc: HTTPException):
    return jsonify(error=exc.description), exc.code

# ──────────────────────────────────────────────────────────────
# Compile‑and‑cache helper
# ──────────────────────────────────────────────────────────────
@lru_cache(maxsize=256)
def tex_to_html(tex_path: pathlib.Path) -> str:
    """Run tex‑to‑html.py and return the generated HTML string."""
    proc = subprocess.run(
        [PYTHON_EXE, str(TEX2HTML), str(tex_path)],   # ← use tex_path here
        capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or "tex‑to‑html.py failed")
    return proc.stdout

# ──────────────────────────────────────────────────────────────
# The single public endpoint
# ──────────────────────────────────────────────────────────────
@app.get("/api/tex2html")
def tex2html_endpoint():
    rel = request.args.get("file", type=str, default="").lstrip("/")
    # Basic validation
    if not rel.endswith(".tex") or ".." in rel:
        abort(400, "Bad file parameter")

    tex_file = (BASE_DIR / rel).resolve()
    # Ensure we stay inside BASE_DIR
    if not str(tex_file).startswith(str(BASE_DIR)):
        abort(400, "Attempted directory traversal")
    if not tex_file.exists():
        abort(404, "File not found")

    try:
        html = tex_to_html(tex_file)
    except RuntimeError as e:
        abort(500, str(e))

    return Response(html, mimetype="text/html")

# ──────────────────────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)