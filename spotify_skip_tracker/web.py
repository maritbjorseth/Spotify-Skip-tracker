"""
Flask-app for Spotify Skip Tracker-dashbordet.

Endepunkter:
  GET /           — serverer React-build (frontend/dist/) eller fallback dashboard.html
  GET /api/stats  — statistikk som JSON
  GET /api/now    — nåværende avspilling fra now_playing-tabellen
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path

from flask import Flask, Response, jsonify, send_from_directory

from .stats import compute_stats
from .database import pooled_connection, execute

_HERE = Path(__file__).parent
_DIST_DIR = _HERE.parent / "frontend" / "dist"

try:
    _DASHBOARD_HTML = (_HERE / "dashboard.html").read_text(encoding="utf-8")
except FileNotFoundError:
    _DASHBOARD_HTML = "<h1>Dashboard ikke funnet</h1>"


def create_flask_app() -> Flask:
    app = Flask(__name__, static_folder=None)

    # ------------------------------------------------------------------
    # API-endepunkter
    # ------------------------------------------------------------------

    @app.route("/api/stats")
    def stats():
        return jsonify(compute_stats())

    @app.route("/api/now")
    def now_playing():
        """
        Returnerer nåværende avspilling fra now_playing-tabellen.
        Trackeren (Railway) skriver hit hvert 7. sekund.
        Dersom updated_at er eldre enn 30 s, regnes ingenting som spilt.
        """
        try:
            with pooled_connection() as conn:
                row = execute(
                    conn,
                    """
                    SELECT uri, title, artists, album, image_url,
                           progress_ms, duration_ms, is_playing, updated_at
                    FROM now_playing
                    WHERE id = 1
                    """,
                ).fetchone()

                if row is None:
                    return jsonify({"is_playing": False}), 200

                uri, title, artists, album, image_url, progress_ms, duration_ms, is_playing, updated_at = row

                # Stale-sjekk: hvis updated_at er eldre enn 30 s → ikke spilt
                if updated_at and (datetime.now(timezone.utc) - updated_at) > timedelta(seconds=30):
                    is_playing = False

                # Historisk skip-rate — samme tilkobling
                skip_rate = None
                if uri:
                    result = execute(
                        conn,
                        """
                        SELECT
                            SUM(CASE WHEN skipped THEN 1 ELSE 0 END)::REAL / NULLIF(COUNT(*), 0)
                        FROM plays WHERE uri = %s
                        """,
                        (uri,),
                    ).fetchone()
                    if result and result[0] is not None:
                        skip_rate = round(float(result[0]), 3)

        except Exception:
            return jsonify({"is_playing": False}), 200

        return jsonify({
            "is_playing": bool(is_playing),
            "uri": uri,
            "title": title,
            "artists": artists,
            "album": album,
            "image_url": image_url,
            "progress_ms": progress_ms or 0,
            "duration_ms": duration_ms or 1,
            "skip_rate": skip_rate,
            "updated_at": updated_at.isoformat() if updated_at else None,
        })

    # ------------------------------------------------------------------
    # Statisk serving: React-build hvis tilgjengelig, ellers gammel HTML
    # ------------------------------------------------------------------

    if _DIST_DIR.exists():
        @app.route("/assets/<path:filename>")
        def assets(filename):
            return send_from_directory(_DIST_DIR / "assets", filename)

        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def spa(path):
            # Serve faktisk fil hvis den finnes (f.eks. favicon.ico)
            full = _DIST_DIR / path
            if path and full.exists() and full.is_file():
                return send_from_directory(_DIST_DIR, path)
            return send_from_directory(_DIST_DIR, "index.html")
    else:
        @app.route("/")
        def index():
            return Response(_DASHBOARD_HTML, mimetype="text/html")

    return app
