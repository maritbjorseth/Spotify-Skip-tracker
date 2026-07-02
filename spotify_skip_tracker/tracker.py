"""
Sporingsloop for Spotify Skip Tracker.

Håndterer:
- Skip-deteksjonslogikk (ren funksjon, lett å teste)
- Polling av Spotify-APIet per bruker
- Skriving av avspillinger til databasen
- Trådstyring for multi-user tracking
"""

import logging
import threading
import time
import uuid as _uuid
from datetime import datetime, timezone

import psycopg2
import requests

from .config import MIN_REMAINING_MS, POLL_SECONDS, SESSION_GAP_MINUTES, SKIP_THRESHOLD
from .database import (
    connect, execute, mark_token_invalid, list_active_user_ids,
    ensure_user_smart_skipper_config,
)
from .smart_skipper import SmartSkipper
from .spotify_api import get_access_token, get_context_name, load_creds

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Trådstyring — én tracker-tråd per Spotify-bruker
# ---------------------------------------------------------------------------

_active_trackers: dict[str, threading.Thread] = {}
_trackers_lock = threading.Lock()


def ensure_tracker_running(user_id: str) -> None:
    """
    Starter en tracker-tråd for user_id dersom den ikke allerede kjører.

    Idempotent: kall fra auth_callback() og tracker_manager() uten å bekymre
    deg for duplikater. Bruker is_alive()-sjekk bak en threading.Lock.

    Kalles fra:
        - tracker_manager()  ved oppstart for eksisterende brukere
        - auth_callback()    når en ny bruker logger inn via OAuth
    """
    with _trackers_lock:
        existing = _active_trackers.get(user_id)
        if existing and existing.is_alive():
            logger.debug("[%s] Tracker kjører allerede — ingen ny tråd.", user_id)
            return
        t = threading.Thread(
            target=polling_loop,
            args=(user_id,),
            daemon=True,
            name=f"tracker-{user_id}",
        )
        _active_trackers[user_id] = t
        t.start()
        logger.info("[%s] Tracker-tråd startet.", user_id)


def tracker_manager() -> None:
    """
    Starter tracking-tråder for alle brukere i user_tokens-tabellen.

    Kalles én gang ved oppstart fra server.py. Nye brukere får tracker
    via ensure_tracker_running() i auth_callback().

    Dersom user_tokens er tom og SPOTIFY_REFRESH_TOKEN er satt som env-var
    (enkelt-bruker / legacy-modus), gjøres ett API-kall for å identifisere
    eieren og bootstrappe user_tokens — slik at oppstart alltid fungerer uten
    manuell konfigurasjon av SPOTIFY_USER_ID.
    """
    try:
        conn = connect()
        user_ids = list_active_user_ids(conn)
        conn.close()
    except Exception as exc:
        logger.error("tracker_manager: DB-feil ved oppstart: %s", exc)
        user_ids = []

    if user_ids:
        logger.info(
            "tracker_manager: starter %d tracker-tråd(er) for kjente brukere.",
            len(user_ids),
        )
        for uid in user_ids:
            ensure_tracker_running(uid)
        return

    # Ingen brukere i DB — prøv env-var-bootstrap
    from .config import SPOTIFY_REFRESH_TOKEN
    if SPOTIFY_REFRESH_TOKEN:
        logger.warning(
            "tracker_manager: ingen brukere i user_tokens. "
            "Bootstrapper fra SPOTIFY_REFRESH_TOKEN …"
        )
        _bootstrap_and_start()
    else:
        logger.warning(
            "tracker_manager: ingen brukere i user_tokens og ingen "
            "SPOTIFY_REFRESH_TOKEN. Tracker starter ikke. "
            "Logg inn via /api/auth/login for å starte tracking."
        )


def _bootstrap_and_start() -> None:
    """
    Engangs-bootstrap for legacy-modus: henter bruker-ID fra Spotify API
    ved hjelp av env-var-legitimasjon, skriver token til user_tokens og
    starter tracker-tråd.

    Kalles av tracker_manager() dersom user_tokens er tom men
    SPOTIFY_REFRESH_TOKEN er satt. Dette dekker ferske deploy-er der
    bootstrap-migrasjonen ikke fant en user_id (f.eks. fordi SPOTIFY_USER_ID
    ikke var satt og databasen var ny).
    """
    from .config import SPOTIFY_REFRESH_TOKEN, SCOPE
    from .database import upsert_user_token
    from .token_crypto import encrypt_token

    try:
        creds = load_creds()  # env-var-sti
        token = get_access_token(creds)

        resp = requests.get(
            "https://api.spotify.com/v1/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        user_id = resp.json().get("id")
        display_name = resp.json().get("display_name")

        if not user_id:
            logger.error("_bootstrap_and_start: /v1/me returnerte ingen bruker-ID.")
            return

        conn = connect()
        upsert_user_token(
            conn,
            user_id=user_id,
            refresh_token_encrypted=encrypt_token(SPOTIFY_REFRESH_TOKEN),
            access_token=token,
            expires_at=creds.get("expires_at"),
            display_name=display_name,
            scope=SCOPE,
        )
        ensure_user_smart_skipper_config(conn, user_id)
        conn.close()

        logger.info(
            "_bootstrap_and_start: token for '%s' (%s) lagret — starter tracker.",
            user_id, display_name or "–",
        )
        ensure_tracker_running(user_id)

    except Exception as exc:
        logger.error("_bootstrap_and_start feilet: %s", exc)


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
    user_id: str = "default_user",
    session_id: str | None = None,
) -> None:
    """Logger én avspilling (ferdig eller skippet) til databasen."""
    execute(
        conn,
        """
        INSERT INTO plays
            (uri, title, album, artists, context_uri, skipped, progress_ratio,
             timestamp, image_url, user_id, session_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            user_id,
            session_id,
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Hoved-polling-loop (per bruker)
# ---------------------------------------------------------------------------

def polling_loop(user_id: str) -> None:
    """
    Poller Spotify-APIet for én bruker hvert POLL_SECONDS sekund.

    Parametere:
        user_id  Spotify-bruker-ID — brukes til å laste creds fra user_tokens,
                 tagge alle avspillinger og filtrere DB-spørringer korrekt.

    Avsluttes dersom:
        - Creds ikke finnes i databasen (RuntimeError)
        - Spotifys token-endepunkt svarer 400/401 (ugyldig/tilbakekalt token)
          Token markeres da som ugyldig i user_tokens for å hindre gjentatte forsøk.

    Skip-deteksjonen fungerer retroaktivt: vi vet at et spor ble skippet
    først når neste spor starter — da sjekker vi hvor langt det forrige sporet kom.
    """
    logger.info("[%s] Tracker starter.", user_id)

    # --- Last legitimasjon fra user_tokens (feiler fort ved manglende rad) ---
    try:
        creds = load_creds(user_id)
    except RuntimeError as exc:
        logger.error("[%s] Kunne ikke laste creds: %s", user_id, exc)
        return

    conn = connect()
    # init_db() er allerede kjørt av server.py — ikke gjør det igjen her.

    skipper = SmartSkipper()
    _session_gap_seconds = SESSION_GAP_MINUTES * 60
    current_session_id: str = str(_uuid.uuid4())
    last_play_logged_at: datetime | None = None
    logger.info("[%s] Lyttesesjon startet: %s", user_id, current_session_id)

    last_uri: str | None = None
    last_progress_ms: float = 0
    last_duration_ms: float = 0
    last_title: str | None = None
    last_album: str | None = None
    last_artists: str | None = None
    last_context: str | None = None
    last_shuffle_state: bool | None = None
    last_image_url: str | None = None

    logger.info("[%s] Poller hvert %ds.", user_id, POLL_SECONDS)

    while True:
        # --- Hent/forny access-token —----------------------------------------
        # 400/401 fra Spotify betyr refresh-token er ugyldig eller tilbakekalt.
        # I det tilfellet markerer vi tokenet i DB og avslutter tråden.
        try:
            token = get_access_token(creds)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (400, 401):
                logger.warning(
                    "[%s] Spotify avviste refresh-token (HTTP %d). "
                    "Markerer som ugyldig og avslutter tråd.",
                    user_id, status,
                )
                try:
                    mark_token_invalid(conn, user_id)
                except Exception:
                    pass
                return
            logger.warning("[%s] HTTP-feil ved token-refresh: %s.", user_id, exc)
            time.sleep(POLL_SECONDS)
            continue
        except requests.RequestException as exc:
            logger.warning("[%s] Nettverksfeil ved token-refresh: %s.", user_id, exc)
            time.sleep(POLL_SECONDS)
            continue

        # --- Poll Spotify-player API ------------------------------------------
        try:
            resp = requests.get(
                "https://api.spotify.com/v1/me/player",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )

            # 204 = ingenting spilles; 429 = rate limit
            if resp.status_code in (204, 429) or not resp.content:
                time.sleep(POLL_SECONDS)
                continue
            if resp.status_code != 200:
                logger.warning(
                    "[%s] Spotify %d: %s",
                    user_id,
                    resp.status_code,
                    resp.text,
                    )
                time.sleep(POLL_SECONDS)
                continue

            data = resp.json()
            item = data.get("item")

            # Filtrer bort podcast-episoder
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

            images = (item.get("album") or {}).get("images") or []
            image_url: str | None = images[0]["url"] if images else None

            # Oppdater now_playing-tabellen på hver poll
            conn = _upsert_now_playing(
                conn, uri, title, album, artists, image_url,
                int(progress_ms), int(duration_ms), is_playing,
                user_id=user_id,
            )

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
                        now = datetime.now(timezone.utc)
                        if (
                            last_play_logged_at is None
                            or (now - last_play_logged_at).total_seconds() > _session_gap_seconds
                        ):
                            current_session_id = str(_uuid.uuid4())
                            logger.info(
                                "[%s] Ny lyttesesjon startet: %s",
                                user_id, current_session_id,
                            )
                        last_play_logged_at = now

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
                            user_id,
                            current_session_id,
                        )
                        skipper.record_outcome(skipped)
                        if last_context:
                            get_context_name(conn, token, last_context)
                    except psycopg2.Error as exc:
                        logger.error("[%s] DB-feil ved skriving: %s", user_id, exc)
                        try:
                            conn.close()
                        except Exception:
                            pass
                        from .database import reconnect
                        new_conn = reconnect()
                        if new_conn is not None:
                            conn = new_conn
                            logger.info("[%s] Koblet til databasen på nytt.", user_id)

                last_uri = uri
                last_title = title
                last_album = album
                last_artists = artists
                last_context = context_uri
                last_image_url = image_url

            # Edge case A: spolt bakover i samme sang
            if uri == last_uri and progress_ms < last_progress_ms - 5_000:
                logger.debug(
                    "[%s] Progress spolet bakover — nullstiller SmartSkipper.", user_id
                )
                skipper._reset()

            last_progress_ms = progress_ms
            last_duration_ms = duration_ms
            last_shuffle_state = shuffle_state

            # Smart Skipper — feil her skal aldri krasje tracking-loopen
            try:
                skipper.evaluate(
                    conn=conn,
                    token=token,
                    current_uri=uri,
                    current_title=title,
                    current_artists=artists,
                    context_uri=context_uri,
                    progress_ms=int(progress_ms),
                    duration_ms=int(duration_ms),
                    is_playing=is_playing,
                    user_id=user_id,
                )
            except Exception as exc:
                logger.warning(
                    "[%s] Smart Skipper-feil (ignorerer): %s", user_id, exc
                )

        except requests.RequestException as exc:
            logger.warning("[%s] Nettverksfeil, prøver igjen: %s", user_id, exc)
        except Exception as exc:
            logger.exception("[%s] Uventet feil i polling-loop: %s", user_id, exc)

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
    user_id: str = "default_user",
):
    """
    Oppdaterer now_playing-tabellen med nåværende avspilling for én bruker.

    Upsert på user_id: én rad per Spotify-bruker.

    Returnerer tilkoblingen som faktisk ble brukt — samme `conn` ved suksess,
    eller en ny tilkobling dersom den gamle var død og måtte fornyes.
    """
    from .database import reconnect
    try:
        execute(
            conn,
            """
            INSERT INTO now_playing
                (user_id, uri, title, artists, album, image_url,
                 progress_ms, duration_ms, is_playing, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
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
            (user_id, uri, title, artists, album, image_url, progress_ms, duration_ms, is_playing),
        )
        conn.commit()
        return conn
    except Exception as exc:
        logger.warning("[%s] Kunne ikke oppdatere now_playing: %s", user_id, exc)
        try:
            conn.close()
        except Exception:
            pass
        new_conn = reconnect()
        if new_conn is not None:
            logger.info("[%s] Koblet til databasen på nytt (now_playing).", user_id)
            return new_conn
        logger.critical(
            "[%s] Kunne ikke koble til databasen på nytt. "
            "Hopper over poll-syklus og prøver igjen om %ds.", user_id, POLL_SECONDS
        )
        time.sleep(POLL_SECONDS)
        return conn
