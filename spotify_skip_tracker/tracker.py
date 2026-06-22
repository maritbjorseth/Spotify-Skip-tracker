"""
Sporingsloop for Spotify Skip Tracker.

Håndterer:
- Skip-deteksjonslogikk (ren funksjon, lett å teste)
- Polling av Spotify-APIet
- Skriving av avspillinger til databasen
"""

import logging
import time
from datetime import datetime, timezone

import psycopg2
import requests

from .config import MIN_REMAINING_MS, POLL_SECONDS, SKIP_THRESHOLD
from .database import connect, execute, init_db, reconnect
from .spotify_api import get_access_token, get_context_name, load_creds

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Skip-deteksjon (ren funksjon — ingen bivirkninger, enkel å teste)
# ---------------------------------------------------------------------------

def is_skip(
    ratio: float,
    remaining_ms: float,
    shuffle_toggled: bool,
    context_switched: bool,
) -> bool:
    """
    Returnerer True dersom forrige spor ble skippet.

    Regler:
    - Fremgangen må være under SKIP_THRESHOLD (90 %)
    - Minst MIN_REMAINING_MS (30 s) må ha gjenstått
    - Shuffle-bytte regnes ikke som skip (Spotify hopper automatisk til neste spor)
    - Kontekstbytte (ny spilleliste/album) regnes ikke som skip
    """
    return (
        ratio < SKIP_THRESHOLD
        and remaining_ms >= MIN_REMAINING_MS
        and not shuffle_toggled
        and not context_switched
    )


# ---------------------------------------------------------------------------
# Databaseskriving
# ---------------------------------------------------------------------------

def log_play(
    conn,
    uri: str,
    title: str | None,
    album: str | None,
    artists: str | None,
    context_uri: str | None,
    skipped: bool,
    ratio: float,
    image_url: str | None,
) -> None:
    """Logger én avspilling (ferdig eller skippet) til databasen."""
    execute(
        conn,
        """
        INSERT INTO plays
            (uri, title, album, artists, context_uri, skipped, progress_ratio, timestamp, image_url)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            uri,
            title,
            album,
            artists,
            context_uri,
            skipped,
            ratio,
            datetime.now(timezone.utc),
            image_url,
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Hoved-polling-loop
# ---------------------------------------------------------------------------

def polling_loop() -> None:
    """
    Poller Spotify-APIet hvert POLL_SECONDS sekund og logger avspillinger.

    Skip-deteksjonen fungerer retroaktivt: vi vet at et spor ble skippet
    først når neste spor starter — da sjekker vi hvor langt det forrige
    sporet kom.
    """
    creds = load_creds()
    conn = connect()
    init_db(conn)

    # Tilstand fra forrige poll-syklus
    last_uri: str | None = None
    last_progress_ms: float = 0
    last_duration_ms: float = 0
    last_title: str | None = None
    last_album: str | None = None
    last_artists: str | None = None
    last_context: str | None = None
    last_shuffle_state: bool | None = None
    last_image_url: str | None = None

    logger.info("Tracker startet. Poller hvert %ds.", POLL_SECONDS)

    while True:
        try:
            token = get_access_token(creds)
            resp = requests.get(
                "https://api.spotify.com/v1/me/player",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )

            # 204 = ingenting spilles; 429 = rate limit; andre feil → prøv igjen
            if resp.status_code in (204, 429) or not resp.content:
                time.sleep(POLL_SECONDS)
                continue
            if resp.status_code != 200:
                logger.warning("Uventet statuskode fra Spotify: %d", resp.status_code)
                time.sleep(POLL_SECONDS)
                continue

            data = resp.json()
            item = data.get("item")

            # Filtrer bort podcast-episoder — vi sporer kun musikk
            if not item or item.get("type") != "track":
                time.sleep(POLL_SECONDS)
                continue

            uri: str = item["uri"]
            duration_ms: float = item.get("duration_ms") or 1
            progress_ms: float = data.get("progress_ms") or 0
            is_playing: bool = bool(data.get("is_playing", True))
            title: str | None = item.get("name")
            album: str | None = (item.get("album") or {}).get("name")
            artists: str = ", ".join(a.get("name", "") for a in item.get("artists", []))
            context_uri: str | None = (data.get("context") or {}).get("uri")
            shuffle_state: bool | None = data.get("shuffle_state")

            # Velg albumcover: foretrekk ~640px (indeks 0), fall tilbake på første
            images = (item.get("album") or {}).get("images") or []
            image_url: str | None = None
            if images:
                image_url = images[0]["url"]

            # Oppdater now_playing-tabellen på hver poll
            conn = _upsert_now_playing(conn, uri, title, album, artists, image_url, int(progress_ms), int(duration_ms), is_playing)

            if uri != last_uri:
                if last_uri is not None:
                    ratio = last_progress_ms / last_duration_ms if last_duration_ms else 0
                    remaining_ms = last_duration_ms - last_progress_ms
                    shuffle_toggled = (
                        last_shuffle_state is not None
                        and shuffle_state != last_shuffle_state
                    )
                    context_switched = (
                        last_context is not None and context_uri != last_context
                    )
                    skipped = is_skip(ratio, remaining_ms, shuffle_toggled, context_switched)

                    try:
                        log_play(
                            conn,
                            last_uri,
                            last_title,
                            last_album,
                            last_artists,
                            last_context,
                            skipped,
                            ratio,
                            last_image_url,
                        )
                        if last_context:
                            get_context_name(conn, token, last_context)
                    except psycopg2.Error as exc:
                        # DB-tilkoblingen kan ha falt ut (f.eks. Neon inaktivitetstimeout).
                        # Vi mister dette ene datapunktet, men loopen holder seg i live.
                        logger.error("DB-feil ved skriving: %s", exc)
                        try:
                            conn.close()
                        except Exception:
                            pass
                        new_conn = reconnect()
                        if new_conn is not None:
                            conn = new_conn
                            logger.info("Koblet til databasen på nytt.")

                last_uri = uri
                last_title = title
                last_album = album
                last_artists = artists
                last_context = context_uri
                last_image_url = image_url

            last_progress_ms = progress_ms
            last_duration_ms = duration_ms
            last_shuffle_state = shuffle_state

        except requests.RequestException as exc:
            logger.warning("Nettverksfeil, prøver igjen: %s", exc)
        except Exception as exc:
            logger.exception("Uventet feil i polling-loop: %s", exc)

        time.sleep(POLL_SECONDS)


def _upsert_now_playing(
    conn,
    uri: str,
    title: str | None,
    album: str | None,
    artists: str | None,
    image_url: str | None,
    progress_ms: int,
    duration_ms: int,
    is_playing: bool,
):
    """
    Oppdaterer now_playing-tabellen med nåværende avspilling (upsert på rad 1).

    Returnerer tilkoblingen som faktisk ble brukt - samme `conn` ved suksess,
    eller en ny tilkobling dersom den gamle var død og måtte fornyes. Uten
    dette ville en avbrutt tilkobling (f.eks. Neon inaktivitetstimeout) gjort
    at hver poll-syklus feilet stille i opptil ett minutt, til et sporbytte
    tilfeldigvis trigget gjenoppkobling et annet sted i koden.
    """
    try:
        execute(
            conn,
            """
            INSERT INTO now_playing
                (id, uri, title, artists, album, image_url, progress_ms, duration_ms, is_playing, updated_at)
            VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO UPDATE SET
                uri         = EXCLUDED.uri,
                title       = EXCLUDED.title,
                artists     = EXCLUDED.artists,
                album       = EXCLUDED.album,
                image_url   = EXCLUDED.image_url,
                progress_ms = EXCLUDED.progress_ms,
                duration_ms = EXCLUDED.duration_ms,
                is_playing  = EXCLUDED.is_playing,
                updated_at  = NOW()
            """,
            (uri, title, artists, album, image_url, progress_ms, duration_ms, is_playing),
        )
        conn.commit()
        return conn
    except Exception as exc:
        logger.warning("Kunne ikke oppdatere now_playing, kobler til på nytt: %s", exc)
        try:
            conn.close()
        except Exception:
            pass
        new_conn = reconnect()
        if new_conn is not None:
            logger.info("Koblet til databasen på nytt (now_playing).")
            return new_conn
        return conn
