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

from .config import (
    CREDS_PATH,
    REDIRECT_URI,
    SCOPE,
    APP_DIR,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REFRESH_TOKEN,
)
from .database import execute, get_user_token_row, update_access_token_cache, upsert_user_token
from .token_crypto import decrypt_token, encrypt_token

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

    def _serve_until_code():
        while "code" not in _auth_code:
            server.handle_request()

    threading.Thread(target=_serve_until_code, daemon=True).start()
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

def load_creds(user_id: str | None = None) -> dict:
    """
    Laster legitimasjon i prioritert rekkefølge:

    Med user_id (multi-user, Steg 5+):
        1. user_tokens-tabellen i databasen
           Finner ingen rad → RuntimeError (brukeren må autentisere på nytt)

    Uten user_id (legacy / enkelt-bruker):
        2. Miljøvariabler / .env.local (SPOTIFY_CLIENT_ID, _SECRET, _REFRESH_TOKEN)
        3. Lokal fil ~/.spotify_skip_tracker/credentials.json

    Creds-dict inneholder alltid nøklene:
        client_id, client_secret, refresh_token, access_token, expires_at

    Når lest fra databasen legges 'user_id' til i dict-en slik at
    save_creds() vet at tilbakeskriving skal gå til DB og ikke til fil.
    """
    if user_id is not None:
        return _load_creds_from_db(user_id)

    # --- Legacy-sti: env-var ---
    if SPOTIFY_REFRESH_TOKEN:
        if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
            raise RuntimeError(
                "SPOTIFY_REFRESH_TOKEN er satt, men SPOTIFY_CLIENT_ID og/eller "
                "SPOTIFY_CLIENT_SECRET mangler i .env.local / miljøvariabler."
            )
        return {
            "client_id": SPOTIFY_CLIENT_ID,
            "client_secret": SPOTIFY_CLIENT_SECRET,
            "refresh_token": SPOTIFY_REFRESH_TOKEN,
            "access_token": "",
            "expires_at": 0,
        }

    # --- Legacy-sti: lokal fil ---
    if not CREDS_PATH.exists():
        print("Ingen innlogging funnet. Kjør 'setup' først (se --help for hjelp).")
        sys.exit(1)
    return json.loads(CREDS_PATH.read_text())


def _load_creds_from_db(user_id: str) -> dict:
    """
    Henter kredentials for user_id fra user_tokens-tabellen.

    Dekrypterer refresh_token med token_crypto.decrypt_token().
    Legger til 'user_id'-nøkkel i returnert dict slik at save_creds()
    vet at persistering skal gå til databasen.

    Raises:
        RuntimeError  dersom user_id ikke finnes i user_tokens.
    """
    from .database import connect
    try:
        conn = connect()
        row = get_user_token_row(conn, user_id)
        conn.close()
    except Exception as exc:
        raise RuntimeError(
            f"Databasefeil ved lasting av token for '{user_id}': {exc}"
        ) from exc

    if row is None:
        raise RuntimeError(
            f"Ingen token funnet i databasen for bruker '{user_id}'. "
            "Brukeren må autentisere via web-OAuth (/api/auth/login)."
        )

    try:
        refresh_token_plain = decrypt_token(row["refresh_token"])
    except Exception as exc:
        raise RuntimeError(
            f"Kunne ikke dekryptere refresh-token for '{user_id}': {exc}"
        ) from exc

    # Klientlegitimasjonen leses alltid fra miljøvariabler — den lagres ikke i DB.
    # Feiler her med en tydelig melding fremfor å sende tomme strenger til Spotify
    # (som ville gitt en lite forklarende 400 invalid_client-feil).
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise RuntimeError(
            "SPOTIFY_CLIENT_ID og/eller SPOTIFY_CLIENT_SECRET mangler i miljøet. "
            "Sett begge variablene i Railway-dashbordet og re-deploy."
        )

    logger.debug(
        "[%s] _load_creds_from_db: client_id[:8]=%s refresh_token[:8]=%s",
        user_id,
        SPOTIFY_CLIENT_ID[:8],
        refresh_token_plain[:8] if refresh_token_plain else "TOMT",
    )

    return {
        "client_id":     SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
        "refresh_token": refresh_token_plain,
        "access_token":  row["access_token"] or "",
        "expires_at":    row["expires_at"] or 0.0,
        "user_id":       user_id,  # signal til save_creds() om å bruke DB-sti
    }


def save_creds(creds: dict) -> None:
    """
    Persisterer legitimasjon etter at tokens er oppdatert.

    Med 'user_id' i creds-dict (DB-sti, multi-user):
        Krypterer refresh_token og skriver access_token-cache til databasen.
        Brukes av tracker-loopen (Steg 5) etter token-refresh.

    Uten 'user_id' (legacy-sti, enkelt-bruker):
        Gjør ingenting om SPOTIFY_REFRESH_TOKEN er satt (env-var roterer ikke).
        Skriver ellers til lokal credentials.json-fil.
    """
    user_id = creds.get("user_id")

    if user_id:
        _save_creds_to_db(user_id, creds)
        return

    # --- Legacy-sti ---
    if SPOTIFY_REFRESH_TOKEN:
        return
    CREDS_PATH.write_text(json.dumps(creds, indent=2))


def _save_creds_to_db(user_id: str, creds: dict) -> None:
    """
    Skriver oppdaterte tokens til user_tokens-tabellen.

    Krypterer refresh_token på nytt ved hver skriving. Krypteringen er
    deterministisk billig (AES-operasjon), og sikrer at et rotert
    refresh-token alltid lagres kryptert selv om det er uendret.

    Feil logges men propageres ikke — en mislykket skriving fører til at
    neste tracker-poll forsøker en full re-autentisering i verste fall.
    """
    from .database import connect
    try:
        encrypted_refresh = encrypt_token(creds["refresh_token"])
        conn = connect()
        upsert_user_token(
            conn,
            user_id=user_id,
            refresh_token_encrypted=encrypted_refresh,
            access_token=creds.get("access_token"),
            expires_at=creds.get("expires_at"),
        )
        conn.close()
    except Exception as exc:
        logger.error(
            "Kunne ikke lagre oppdatert token for '%s' i DB: %s",
            user_id, exc,
        )


# ---------------------------------------------------------------------------
# Token-håndtering
# ---------------------------------------------------------------------------

def get_access_token(creds: dict) -> str:
    """
    Returnerer et gyldig access-token. Oppdaterer automatisk via refresh-token
    dersom tokenet utløper innen 30 sekunder.

    Dersom creds inneholder 'user_id' (DB-sti), skrives oppdatert access-token
    og eventuelt nytt refresh-token tilbake til user_tokens-tabellen.
    """
    user_id = creds.get("user_id", "legacy")
    expires_at = creds.get("expires_at", 0)
    now = time.time()

    if expires_at > now + 30:
        logger.info("[%s] TOKEN: bruker cachet access-token (utløper om %.0fs)", user_id, expires_at - now)
        return creds["access_token"]

    logger.info("[%s] TOKEN: access-token utløpt/mangler (expires_at=%s now=%s) — starter refresh", user_id, expires_at, now)
    logger.info("[%s] TOKEN: refresh_token[:8]=%s client_id[:8]=%s",
                user_id,
                (creds.get("refresh_token") or "")[:8] or "MANGLER",
                (creds.get("client_id") or "")[:8] or "MANGLER")

    try:
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
        logger.info("[%s] TOKEN: refresh-svar status=%d", user_id, resp.status_code)
        if resp.status_code != 200:
            # Plukk ut Spotifys strukturerte feilkoder slik at årsaken vises klart i loggen.
            # Typiske verdier: error=invalid_client (feil client_id/secret),
            #                  error=invalid_grant (refresh-token ugyldig/tilbakekalt)
            try:
                err_json = resp.json()
                spotify_error = err_json.get("error", "–")
                spotify_error_desc = err_json.get("error_description", "–")
            except Exception:
                spotify_error = "–"
                spotify_error_desc = resp.text[:300]
            logger.error(
                "[%s] TOKEN: refresh feilet — status=%d  "
                "spotify_error=%r  spotify_error_description=%r",
                user_id, resp.status_code, spotify_error, spotify_error_desc,
            )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("[%s] TOKEN: refresh-forespørsel kastet unntak: %s", user_id, exc)
        raise

    token_data = resp.json()

    creds["access_token"] = token_data["access_token"]
    creds["expires_at"] = time.time() + token_data["expires_in"]
    logger.info("[%s] TOKEN: nytt access-token hentet, utløper om %ds", user_id, token_data["expires_in"])

    # Spotify roterer av og til refresh-tokenet — ta vare på det nye
    if "refresh_token" in token_data:
        logger.info("[%s] TOKEN: refresh-token rotert av Spotify", user_id)
        creds["refresh_token"] = token_data["refresh_token"]

    # Skriv tilbake til riktig lager (DB eller fil avhengig av creds-innhold)
    logger.info("[%s] TOKEN: kaller save_creds() (DB-sti=%s)", user_id, bool(creds.get("user_id")))
    try:
        save_creds(creds)
        logger.info("[%s] TOKEN: save_creds() fullført", user_id)
    except Exception as exc:
        logger.error("[%s] TOKEN: save_creds() feilet: %s", user_id, exc)

    return creds["access_token"]


# ---------------------------------------------------------------------------
# Kontekstnavn (spilleliste / album)
# ---------------------------------------------------------------------------

def get_context_name(conn, token: str, context_uri: str) -> str | None:
    """
    Slår opp visningsnavnet for en Spotify-kontekst (spilleliste eller album).
    Resultatet caches i contexts-tabellen for å unngå gjentatte API-kall.

    Spesialtilfelle: spotify:user:<id>:collection er «Liked Songs» / Likte sanger.
    Spotify eksponerer ikke dette som et vanlig API-endepunkt, så vi hardkoder
    visningsnavnet og lagrer det i contexts-tabellen med én gang.
    """
    if not context_uri:
        return None

    row = execute(
        conn, "SELECT name FROM contexts WHERE uri = %s", (context_uri,)
    ).fetchone()
    if row:
        return row[0]

    # spotify:user:<bruker-id>:collection → «Liked Songs»
    parts = context_uri.split(":")
    if len(parts) == 4 and parts[1] == "user" and parts[3] == "collection":
        name = "Liked Songs"
        execute(
            conn,
            "INSERT INTO contexts (uri, name) VALUES (%s, %s) "
            "ON CONFLICT (uri) DO UPDATE SET name = EXCLUDED.name",
            (context_uri, name),
        )
        conn.commit()
        return name

    try:
        if len(parts) < 3:
            return None
        # Eldre spillelistelenker har formatet spotify:user:<bruker>:playlist:<id>
        if parts[1] == "user" and len(parts) >= 5:
            kind, id_ = parts[3], parts[4]
        else:
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
        # Nullstill tilkoblingen slik at en mislykket INSERT/commit ikke etterlater
        # den i aborted-tilstand, noe som ville fått påfølgende DB-kall til å feile.
        try:
            conn.rollback()
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# Tilbakefylling av manglende albumcover
# ---------------------------------------------------------------------------

def backfill_covers() -> int:
    """
    Går gjennom alle avspillinger med NULL image_url, slår opp albumcover
    fra Spotify APIet og oppdaterer databasen.

    Returnerer antall unike spor som ble oppdatert.
    """
    from .database import connect, execute, init_db

    creds = load_creds()
    token = get_access_token(creds)
    conn = connect()
    init_db(conn)

    # Hent unike URI-er som mangler image_url
    rows = execute(
        conn,
        """
        SELECT DISTINCT p.uri, MAX(p.title) AS title
        FROM plays p
        WHERE p.image_url IS NULL
        GROUP BY p.uri
        """,
    ).fetchall()

    if not rows:
        logger.info("Ingen manglende albumcover funnet.")
        conn.close()
        return 0

    logger.info("Fant %d spor som mangler albumcover. Starter oppslag …", len(rows))

    updated = 0
    for uri, title in rows:
        try:
            # Oppdater token ved behov — tokens utløper etter 1 time
            token = get_access_token(creds)

            # spotify:track:ABC123 → track ID = ABC123
            parts = uri.split(":")
            if len(parts) < 3 or parts[1] != "track":
                continue
            track_id = parts[2]

            resp = requests.get(
                f"https://api.spotify.com/v1/tracks/{track_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning("Kunne ikke hente info for %s (status %d)", uri, resp.status_code)
                time.sleep(0.5)
                continue

            item = resp.json()
            images = (item.get("album") or {}).get("images") or []
            if not images:
                time.sleep(0.5)
                continue

            image_url = images[0]["url"]

            execute(
                conn,
                "UPDATE plays SET image_url = %s WHERE uri = %s AND image_url IS NULL",
                (image_url, uri),
            )

            # Oppdater også now_playing hvis dette er det aktuelle sporet
            execute(
                conn,
                "UPDATE now_playing SET image_url = %s WHERE uri = %s",
                (image_url, uri),
            )

            conn.commit()
            updated += 1
            logger.info("  ✓ %s — %s", title or uri, image_url)

            # Liten pause for å unngå rate limits
            time.sleep(0.25)

        except requests.RequestException as exc:
            logger.warning("Nettverksfeil for %s: %s", uri, exc)
            time.sleep(1)
        except Exception as exc:
            logger.warning("Uventet feil for %s: %s", uri, exc)

    logger.info("Ferdig! Oppdaterte %d spor med albumcover.", updated)
    conn.close()
    return updated
