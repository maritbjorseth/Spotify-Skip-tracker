"""
Flask-app for Spotify Skip Tracker-dashbordet.

Endepunkter:
  GET /           — serverer React-build (frontend/dist/) eller fallback dashboard.html
  GET /api/stats  — statistikk som JSON
  GET /api/now    — nåværende avspilling fra now_playing-tabellen
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import hmac
import json as _json
import os
import secrets
import threading
import time as _time
import urllib.parse

import logging

import requests as http_requests

from flask import Flask, Response, jsonify, redirect, request, send_from_directory, session
from flask_cors import CORS

from .stats import compute_stats, compute_insight_stats, calculate_listening_score
from .insights import generate_insights
from .database import pooled_connection, execute
from .spotify_api import get_access_token, load_creds
from .config import (
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET,
    REDIRECT_URI_WEB, FRONTEND_URL,
    APP_DIR, CREDS_PATH, SCOPE,
    FLASK_SECRET_KEY, DASHBOARD_PASSWORD,
)

logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent
_DIST_DIR = _HERE.parent / "frontend" / "dist"

try:
    _DASHBOARD_HTML = (_HERE / "dashboard.html").read_text(encoding="utf-8")
except FileNotFoundError:
    _DASHBOARD_HTML = "<h1>Dashboard ikke funnet</h1>"

# ---------------------------------------------------------------------------
# Spotify-bruker-ID (caches for hele prosessens levetid)
# ---------------------------------------------------------------------------

_cached_user_id: str | None = None
_user_id_lock = threading.Lock()

# Sett med éngangskoder brukt for å hindre CSRF under web-OAuth-flyten.
_oauth_states: set[str] = set()


def _resolve_user_id() -> str:
    """
    Returnerer den innloggede brukerens Spotify-ID.

    Kaller GET /v1/me første gang og cacher resultatet i minnet.
    Faller trygt tilbake på 'default_user' dersom API-kallet feiler
    (f.eks. ved nettverksproblemer eller manglende legitimasjon).
    """
    global _cached_user_id
    if _cached_user_id is not None:
        return _cached_user_id
    with _user_id_lock:
        # Dobbel sjekk inne i låsen
        if _cached_user_id is not None:
            return _cached_user_id
        try:
            creds = load_creds()
            token = get_access_token(creds)
            resp = http_requests.get(
                "https://api.spotify.com/v1/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            resp.raise_for_status()
            _cached_user_id = resp.json().get("id") or "default_user"
            logger.info("Spotify-bruker-ID cachet: '%s'.", _cached_user_id)
        except Exception as exc:
            logger.warning(
                "Kunne ikke hente Spotify-bruker-ID: %s. Bruker 'default_user'.", exc
            )
            _cached_user_id = "default_user"
        return _cached_user_id


def create_flask_app() -> Flask:
    app = Flask(__name__, static_folder=None)

    # -------------------------------------------------------------------
    # Session-konfigurasjon for cross-domain cookies (Vercel → Railway)
    #
    # SameSite=None + Secure=True er påkrevd for at nettleseren skal sende
    # cookien på tvers av domener. I lokal utvikling uten DASHBOARD_PASSWORD
    # brukes aldri session, så dette er ufarlig for dev-miljøet.
    # -------------------------------------------------------------------
    app.secret_key = FLASK_SECRET_KEY
    app.config['SESSION_COOKIE_SAMESITE'] = 'None'
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True

    _allowed_origins = [
        o for o in [FRONTEND_URL, "http://localhost:5173", "http://localhost:5000"]
        if o
    ]
    CORS(app, supports_credentials=True, origins=_allowed_origins)

    # ------------------------------------------------------------------
    # Autentiserings-endepunkter
    # ------------------------------------------------------------------

    @app.route("/api/auth/status")
    def auth_status():
        """
        Sjekker om denne nettleseren har en gyldig dashbordsesjon.

        Tilgangsmodi:
          - DASHBOARD_PASSWORD ikke satt (lokal utvikling) → alltid authenticated
          - DASHBOARD_PASSWORD satt → krever at session['authenticated'] er True
        """
        if DASHBOARD_PASSWORD is None:
            # Åpen modus — ingen passord konfigurert
            return jsonify({"authenticated": True, "user_id": _resolve_user_id()})

        if session.get("authenticated"):
            return jsonify({"authenticated": True, "user_id": _resolve_user_id()})

        return jsonify({"authenticated": False, "user_id": None})

    @app.route("/api/auth/password", methods=["POST"])
    def auth_password():
        """
        Validerer dashbordpassordet fra POST-body.

        Bruker hmac.compare_digest for konstant-tid-sammenligning slik at
        timingbaserte angrepsforsøk ikke gir informasjon om passordet.
        Setter session['authenticated'] = True ved suksess.
        """
        if DASHBOARD_PASSWORD is None:
            # Ingen passord konfigurert — la alle inn
            session["authenticated"] = True
            return jsonify({"success": True})

        body = request.get_json(silent=True) or {}
        candidate = str(body.get("password", ""))

        if not hmac.compare_digest(candidate, DASHBOARD_PASSWORD):
            logger.warning("Feil dashbordpassord forsøkt fra %s.", request.remote_addr)
            return jsonify({"error": "Feil passord"}), 401

        session["authenticated"] = True
        logger.info("Dashbordsesjon opprettet.")
        return jsonify({"success": True})

    @app.route("/api/auth/logout", methods=["POST"])
    def auth_logout():
        """Avslutter dashbordsesjonen ved å tømme session-cookien."""
        session.clear()
        logger.info("Dashbordsesjon avsluttet.")
        return jsonify({"success": True})

    @app.route("/api/auth/login")
    def auth_login():
        """
        Starter web-OAuth-flyten mot Spotify.
        Krever at REDIRECT_URI_WEB er satt i miljøvariabler og er registrert
        i Spotify Developer Dashboard.
        Genererer en CSRF-state og redirecter nettleseren til Spotify.
        """
        if not REDIRECT_URI_WEB or not SPOTIFY_CLIENT_ID:
            return jsonify({
                "error": (
                    "REDIRECT_URI_WEB og SPOTIFY_CLIENT_ID må være satt "
                    "i miljøvariabler for å bruke web-OAuth."
                )
            }), 501

        state = secrets.token_urlsafe(16)
        _oauth_states.add(state)

        auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
            "client_id": SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI_WEB,
            "scope": SCOPE,
            "state": state,
        })
        return redirect(auth_url)

    @app.route("/api/auth/callback")
    def auth_callback():
        """
        Tar imot Spotifys redirect etter vellykket OAuth-autorisasjon.
        Bytter autorisasjonskoden mot tokens, lagrer legitimasjonen lokalt
        (nyttig for lokal utvikling), tømmer bruker-ID-cachen og sender
        nettleseren tilbake til frontenden.
        """
        code = request.args.get("code")
        state = request.args.get("state")
        error = request.args.get("error")

        if error or not state or state not in _oauth_states:
            logger.warning("OAuth-callback avvist: error=%s, state=%s", error, state)
            return redirect(f"{FRONTEND_URL}?auth_error=1")

        _oauth_states.discard(state)

        if not REDIRECT_URI_WEB or not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
            return redirect(f"{FRONTEND_URL}?auth_error=1")

        try:
            token_resp = http_requests.post(
                "https://accounts.spotify.com/api/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT_URI_WEB,
                    "client_id": SPOTIFY_CLIENT_ID,
                    "client_secret": SPOTIFY_CLIENT_SECRET,
                },
                timeout=15,
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()

            new_creds = {
                "client_id": SPOTIFY_CLIENT_ID,
                "client_secret": SPOTIFY_CLIENT_SECRET,
                "refresh_token": token_data["refresh_token"],
                "access_token": token_data["access_token"],
                "expires_at": _time.time() + token_data.get("expires_in", 3600),
            }

            # Lagre til fil (virker for lokal utvikling og Railway-containere
            # som ikke bruker refresh-token-env-variabelen).
            APP_DIR.mkdir(parents=True, exist_ok=True)
            CREDS_PATH.write_text(_json.dumps(new_creds, indent=2))
            logger.info("Web-OAuth fullført — legitimasjon lagret i %s.", CREDS_PATH)

        except Exception as exc:
            logger.error("Token-bytte feilet i OAuth-callback: %s", exc)
            return redirect(f"{FRONTEND_URL}?auth_error=1")

        # Tøm cache slik at neste kall henter riktig bruker-ID
        global _cached_user_id
        with _user_id_lock:
            _cached_user_id = None

        return redirect(FRONTEND_URL)

    # ------------------------------------------------------------------
    # API-endepunkter
    # ------------------------------------------------------------------

    @app.route("/api/stats")
    def stats():
        try:
            return jsonify(compute_stats(_resolve_user_id()))
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
                        FROM plays
                        WHERE uri = %s
                          AND user_id = %s
                        """,
                        (uri, _resolve_user_id()),
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

    @app.route("/api/stats/score")
    def listening_score():
        """
        Returnerer brukerens lyttescore (0–100) basert på fullføringsgrad,
        lengste streak og daglig konsistens.
        """
        try:
            score = calculate_listening_score(_resolve_user_id())
            return jsonify({"score": score})
        except Exception as exc:
            logger.exception("Feil i /api/stats/score: %s", exc)
            return jsonify({"error": "Kunne ikke beregne lyttescore"}), 500

    @app.route("/api/coach/insights")
    def coach_insights():
        """
        Returnerer strukturerte Insight-objekter for Musikkcoach-panelet.

        Hvert objekt har feltene: id, category, stadium, observation,
        context, explanation, action, value, trend, trend_is_positive.

        Stadium angir informasjonsnivå:
          1 = observasjon (hva er tallet?)
          2 = kontekst    (hva betyr det vs. noe annet?)
          3 = forklaring  (hvorfor, og hva kan du gjøre?)

        Responsen er en JSON-liste sortert med høyeste stadium øverst.
        """
        try:
            insights = generate_insights(_resolve_user_id())
            return jsonify([i.to_dict() for i in insights])
        except Exception as exc:
            logger.exception("Feil i /api/coach/insights: %s", exc)
            return jsonify({"error": "Kunne ikke hente coach-innsikter"}), 500

    @app.route("/api/janitor/suggestions")
    def janitor_suggestions():
        from .janitor import _confidence_level, _category

        user_id = _resolve_user_id()
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
                              AND p.user_id = js.user_id
                              AND p.context_uri = 'spotify:playlist:' || js.playlist_id
                        ) AS play_count
                    FROM janitor_suggestions js
                    WHERE js.user_id = %s
                      AND js.status IN ('pending', 'rejected')
                    ORDER BY janitor_score DESC, playlist_name
                    LIMIT 200
                    """,
                    (user_id,),
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

        user_id = _resolve_user_id()

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
                    WHERE user_id = %s
                      AND playlist_id = %s
                      AND uri = %s
                    LIMIT 1
                    """,
                    (user_id, playlist_id, track_uri),
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
                    WHERE user_id = %s
                      AND playlist_id = %s
                      AND uri = %s
                    """,
                    (snapshot_id, user_id, playlist_id, track_uri),
                )

                # Logg fjerningen i audit-tabellen
                execute(
                    conn,
                    """
                    INSERT INTO janitor_removals
                        (user_id, suggestion_id, playlist_id, playlist_name,
                         uri, title, artists, snapshot_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, suggestion_id, playlist_id, playlist_name,
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
