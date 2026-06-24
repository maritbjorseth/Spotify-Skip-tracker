"""
Flask-app for Spotify Skip Tracker-dashbordet.

Endepunkter:
  GET /           — serverer React-build (frontend/dist/) eller fallback dashboard.html
  GET /api/stats  — statistikk som JSON
  GET /api/now    — nåværende avspilling fra now_playing-tabellen
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path

import logging

import requests as http_requests

from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

from .stats import compute_stats
from .database import pooled_connection, execute
from .spotify_api import get_access_token, load_creds

logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent
_DIST_DIR = _HERE.parent / "frontend" / "dist"

try:
    _DASHBOARD_HTML = (_HERE / "dashboard.html").read_text(encoding="utf-8")
except FileNotFoundError:
    _DASHBOARD_HTML = "<h1>Dashboard ikke funnet</h1>"


def create_flask_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    CORS(app, origins=["https://spotify-skip-tracker.vercel.app", "http://localhost:5173", "http://localhost:5000"])

    # ------------------------------------------------------------------
    # API-endepunkter
    # ------------------------------------------------------------------

    @app.route("/api/stats")
    def stats():
        try:
            return jsonify(compute_stats())
        except Exception as exc:
            logger.exception("Feil i /api/stats: %s", exc)
            return jsonify({"error": "Kunne ikke hente statistikk"}), 500

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

                # Stale-sjekk: 60 s terskel for å tåle Neon cold-start latens
                if updated_at and (datetime.now(timezone.utc) - updated_at) > timedelta(seconds=60):
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

    @app.route("/api/smart-skipper")
    def smart_skipper():
        try:
            with pooled_connection() as conn:
                config_row = execute(
                    conn,
                    """
                    SELECT enabled, threshold, min_plays, delay_seconds, dry_run
                    FROM smart_skipper_config
                    WHERE id = 1
                    """,
                ).fetchone()

                history_rows = execute(
                    conn,
                    """
                    SELECT title, artists, skip_rate, reason, timestamp, undone
                    FROM auto_skips
                    ORDER BY timestamp DESC
                    LIMIT 20
                    """,
                ).fetchall()

        except Exception as exc:
            logger.exception("Feil i /api/smart-skipper: %s", exc)
            return jsonify({"error": "Kunne ikke hente Smart Skipper-data"}), 500

        config = {}
        if config_row:
            config = {
                "enabled": bool(config_row[0]),
                "threshold": float(config_row[1]),
                "min_plays": int(config_row[2]),
                "delay_seconds": int(config_row[3]),
                "dry_run": bool(config_row[4]),
            }

        history = [
            {
                "title": r[0],
                "artists": r[1],
                "skip_rate": float(r[2]) if r[2] is not None else None,
                "reason": r[3],
                "timestamp": r[4].isoformat() if r[4] else None,
                "undone": bool(r[5]),
            }
            for r in history_rows
        ]

        return jsonify({"config": config, "history": history})

    @app.route("/api/janitor/suggestions")
    def janitor_suggestions():
        from .janitor import _confidence_level, _category

        try:
            with pooled_connection() as conn:
                rows = execute(
                    conn,
                    """
                    SELECT
                        id, playlist_id, playlist_name, uri,
                        title, artists, skip_rate, janitor_score,
                        suggested_at, status,
                        (
                            SELECT COUNT(*) FROM plays p
                            WHERE p.uri = js.uri
                              AND p.context_uri = 'spotify:playlist:' || js.playlist_id
                        ) AS play_count
                    FROM janitor_suggestions js
                    WHERE status IN ('pending', 'rejected')
                    ORDER BY janitor_score DESC, playlist_name
                    LIMIT 200
                    """,
                ).fetchall()
        except Exception as exc:
            logger.exception("Feil i /api/janitor/suggestions: %s", exc)
            return jsonify({"error": "Kunne ikke hente Janitor-forslag"}), 500

        return jsonify([
            {
                "id": r[0],
                "playlist_id": r[1],
                "playlist_name": r[2],
                "uri": r[3],
                "title": r[4],
                "artists": r[5],
                "skip_rate": float(r[6]) if r[6] is not None else None,
                "janitor_score": float(r[7]) if r[7] is not None else None,
                "suggested_at": r[8].isoformat() if r[8] else None,
                "status": r[9],
                "play_count": int(r[10]) if r[10] is not None else 0,
                "confidence_level": _confidence_level(int(r[10] or 0)),
                "category": _category(float(r[7] or 0)),
            }
            for r in rows
        ])

    @app.route("/api/janitor/remove", methods=["POST"])
    def janitor_remove():
        body = request.get_json(silent=True) or {}
        playlist_id = body.get("playlist_id")
        track_uri = body.get("track_uri")

        if not playlist_id or not track_uri:
            return jsonify({"error": "playlist_id og track_uri er påkrevd"}), 400

        try:
            creds = load_creds()
            token = get_access_token(creds)

            spotify_resp = http_requests.delete(
                f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"tracks": [{"uri": track_uri}]},
                timeout=15,
            )
            spotify_resp.raise_for_status()

            snapshot_id = spotify_resp.json().get("snapshot_id", "")

            with pooled_connection() as conn:
                # Hent metadata fra eksisterende forslag for å berike fjernings-loggen
                suggestion = execute(
                    conn,
                    """
                    SELECT id, title, artists, playlist_name
                    FROM janitor_suggestions
                    WHERE playlist_id = %s AND uri = %s
                    LIMIT 1
                    """,
                    (playlist_id, track_uri),
                ).fetchone()

                suggestion_id   = suggestion[0] if suggestion else None
                title           = suggestion[1] if suggestion else None
                artists         = suggestion[2] if suggestion else None
                playlist_name   = suggestion[3] if suggestion else None

                # Merk forslaget som fjernet
                execute(
                    conn,
                    """
                    UPDATE janitor_suggestions
                    SET status = 'removed', acted_at = NOW(),
                        snapshot_id = %s
                    WHERE playlist_id = %s AND uri = %s
                    """,
                    (snapshot_id, playlist_id, track_uri),
                )

                # Logg fjerningen i audit-tabellen
                execute(
                    conn,
                    """
                    INSERT INTO janitor_removals
                        (suggestion_id, playlist_id, playlist_name,
                         uri, title, artists, snapshot_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (suggestion_id, playlist_id, playlist_name,
                     track_uri, title, artists, snapshot_id),
                )

                conn.commit()

        except http_requests.HTTPError as exc:
            logger.error(
                "Spotify-feil ved fjerning av %s fra %s: %s",
                track_uri, playlist_id, exc,
            )
            return jsonify({"error": str(exc)}), 500
        except Exception as exc:
            logger.exception(
                "Uventet feil i /api/janitor/remove: %s", exc
            )
            return jsonify({"error": str(exc)}), 500

        return jsonify({"success": True, "snapshot_id": snapshot_id}), 200

    # ------------------------------------------------------------------
    # Statisk serving: React-build hvis tilgjengelig, ellers gammel HTML
    # ------------------------------------------------------------------

    if _DIST_DIR.exists():
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
