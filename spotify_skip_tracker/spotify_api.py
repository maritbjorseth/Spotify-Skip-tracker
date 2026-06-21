"""
Spotify Web API-integrasjon.

Håndterer:
- OAuth-flyt (setup)
- Token-oppdatering
- Oppslag av kontekstnavn (spilleliste / album)
"""

import json
import logging
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

from .config import CREDS_PATH, REDIRECT_URI, SCOPE, APP_DIR
from .database import execute

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OAuth-oppsett (kjøres én gang lokalt)
# ---------------------------------------------------------------------------

_auth_code: dict = {}


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            _auth_code["code"] = params["code"][0]
            msg = (
                b"<html><body><h2>Innlogging OK! "
                b"Du kan lukke denne fanen og g\xc3\xa5 tilbake til terminalen.</h2></body></html>"
            )
        else:
            msg = b"<html><body><h2>Noe gikk feil. Se terminalen for detaljer.</h2></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(msg)

    def log_message(self, format, *args):  # noqa: A002
        pass  # stopp standard request-logging


def run_setup(client_id: str, client_secret: str) -> None:
    """Kjører OAuth-autorisasjonsflyten og lagrer legitimasjon lokalt."""
    APP_DIR.mkdir(parents=True, exist_ok=True)

    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
        }
    )
    logger.info("Åpner nettleseren for innlogging …")
    print(f"Hvis nettleseren ikke åpner automatisk, gå til:\n{auth_url}\n")

    server = HTTPServer(("127.0.0.1", 8888), _CallbackHandler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    webbrowser.open(auth_url)

    deadline = time.time() + 120
    while "code" not in _auth_code and time.time() < deadline:
        time.sleep(0.5)

    if "code" not in _auth_code:
        logger.error("Tidsavbrudd — ingen innlogging mottatt. Prøv igjen.")
        sys.exit(1)

    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": _auth_code["code"],
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )
    resp.raise_for_status()
    token_data = resp.json()

    creds = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": token_data["refresh_token"],
        "access_token": token_data["access_token"],
        "expires_at": time.time() + token_data["expires_in"],
    }
    CREDS_PATH.write_text(json.dumps(creds, indent=2))
    logger.info("Innlogging lagret i %s.", CREDS_PATH)
    print(f"Innlogging lagret i {CREDS_PATH}.")
    print("Du kan nå kjøre: python -m spotify_skip_tracker run")


# ---------------------------------------------------------------------------
# Legitimasjon (lokal fil eller miljøvariabler)
# ---------------------------------------------------------------------------

def load_creds() -> dict:
    """
    Laster legitimasjon fra miljøvariabler (cloud) eller lokal fil.
    Avslutter programmet med en feilmelding dersom ingen legitimasjon finnes.
    """
    import os

    if os.environ.get("SPOTIFY_REFRESH_TOKEN"):
        client_id = os.environ.get("SPOTIFY_CLIENT_ID")
        client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise RuntimeError(
                "SPOTIFY_REFRESH_TOKEN er satt, men SPOTIFY_CLIENT_ID og/eller "
                "SPOTIFY_CLIENT_SECRET mangler som miljøvariabler."
            )
        return {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": os.environ["SPOTIFY_REFRESH_TOKEN"],
            "access_token": "",
            "expires_at": 0,
        }
    if not CREDS_PATH.exists():
        print("Ingen innlogging funnet. Kjør 'setup' først (se --help for hjelp).")
        sys.exit(1)
    return json.loads(CREDS_PATH.read_text())


def save_creds(creds: dict) -> None:
    """
    Lagrer legitimasjon lokalt. Gjør ingenting i cloud-modus (refresh-tokenet
    roterer ikke, så miljøvariabelen er alltid gyldig etter en omstart).
    """
    import os

    if os.environ.get("SPOTIFY_REFRESH_TOKEN"):
        return
    CREDS_PATH.write_text(json.dumps(creds, indent=2))


# ---------------------------------------------------------------------------
# Token-håndtering
# ---------------------------------------------------------------------------

def get_access_token(creds: dict) -> str:
    """
    Returnerer et gyldig access-token. Oppdaterer automatisk via refresh-token
    dersom tokenet utløper innen 30 sekunder.
    """
    if creds["expires_at"] > time.time() + 30:
        return creds["access_token"]

    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": creds["refresh_token"],
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
        },
        timeout=15,
    )
    resp.raise_for_status()
    token_data = resp.json()

    creds["access_token"] = token_data["access_token"]
    creds["expires_at"] = time.time() + token_data["expires_in"]
    if "refresh_token" in token_data:
        creds["refresh_token"] = token_data["refresh_token"]
    save_creds(creds)
    return creds["access_token"]


# ---------------------------------------------------------------------------
# Kontekstnavn (spilleliste / album)
# ---------------------------------------------------------------------------

def get_context_name(conn, token: str, context_uri: str) -> str | None:
    """
    Slår opp visningsnavnet for en Spotify-kontekst (spilleliste eller album).
    Resultatet caches i contexts-tabellen for å unngå gjentatte API-kall.
    """
    if not context_uri:
        return None

    row = execute(
        conn, "SELECT name FROM contexts WHERE uri = %s", (context_uri,)
    ).fetchone()
    if row:
        return row[0]

    try:
        parts = context_uri.split(":")
        if len(parts) < 3:
            return None
        kind, id_ = parts[1], parts[2]
        if kind not in ("playlist", "album"):
            return None

        url = f"https://api.spotify.com/v1/{kind}s/{id_}"
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code != 200:
            return None

        name = resp.json().get("name")
        execute(
            conn,
            "INSERT INTO contexts (uri, name) VALUES (%s, %s) "
            "ON CONFLICT (uri) DO UPDATE SET name = EXCLUDED.name",
            (context_uri, name),
        )
        conn.commit()
        return name
    except Exception as exc:
        logger.warning("Kunne ikke hente kontekstnavn for %s: %s", context_uri, exc)
        return None
