"""
Smart Skipper — automatisk hopping basert på historisk skip-data.

Integreres i polling-loopen i tracker.py. Kjøres som en del av
den eksisterende 7-sekunders polling-syklusen, uten egne tråder.

Bruk:
    # I tracker.py, én gang ved oppstart:
    skipper = SmartSkipper()

    # Inne i polling-loopen, etter at avspillingsstatus er hentet:
    skipper.evaluate(
        conn=conn,
        token=token,
        current_uri=item.get("uri"),
        current_title=item.get("name"),
        current_artists=", ".join(a["name"] for a in item.get("artists", [])),
        context_uri=context.get("uri") if context else None,
        progress_ms=state.get("progress_ms", 0),
        duration_ms=item.get("duration_ms", 0),
        is_playing=state.get("is_playing", False),
    )
"""

import logging
import time

import requests

from .database import execute

logger = logging.getLogger(__name__)

# Sikkerhetsgrense: maks X automatiske hopp per 60 minutter.
# Hindrer at en feil tilstand spammer Spotify med hopp.
MAX_AUTO_SKIPS_PER_HOUR = 10


# ---------------------------------------------------------------------------
# Konfigurasjonshenting
# ---------------------------------------------------------------------------

def load_config(conn) -> dict:
    """
    Henter Smart Skipper-konfigurasjon fra smart_skipper_config-tabellen.
    Returnerer alltid et gyldig dict — ved manglende rad er enabled=False.
    """
    row = execute(
        conn,
        """
        SELECT enabled, threshold, min_plays, delay_seconds,
               dry_run, respect_time, excluded_contexts, excluded_uris
        FROM smart_skipper_config
        WHERE id = 1
        """,
    ).fetchone()

    if not row:
        logger.warning(
            "smart_skipper_config-tabellen er tom. "
            "Kjør init_db() for å opprette standardkonfigurasjon."
        )
        return {"enabled": False}

    return {
        "enabled": bool(row[0]),
        "threshold": float(row[1]),
        "min_plays": int(row[2]),
        "delay_seconds": int(row[3]),
        "dry_run": bool(row[4]),
        "respect_time": bool(row[5]),
        "excluded_contexts": list(row[6]) if row[6] else [],
        "excluded_uris": list(row[7]) if row[7] else [],
    }


# ---------------------------------------------------------------------------
# Beslutningslogikk (Tilnærming A — enkel skip-rate-terskel)
# ---------------------------------------------------------------------------

def should_auto_skip(
    conn,
    uri: str,
    context_uri: str | None,
    threshold: float = 0.85,
    min_plays: int = 3,
) -> tuple[bool, str]:
    """
    Bestemmer om Smart Skipper skal hoppe automatisk over denne sangen.

    Returnerer (skal_hoppe, begrunnelse_tekst).

    Logikk (Tilnærming A fra UTVIKLINGSPLAN.md seksjon 3.3):
    1. Sjekk skip-rate i nåværende kontekst (spilleliste/album).
       Krev minimum min_plays avspillinger i denne konteksten.
    2. Fallback til global skip-rate for sangen dersom kontekst-data
       er utilstrekkelig.
    3. Returnerer False dersom ingen av dem overskrider terskelen.
    """
    # --- Kontekst-spesifikk skip-rate ---
    if context_uri:
        row = execute(
            conn,
            """
            SELECT
                COUNT(*)                                            AS play_count,
                SUM(CASE WHEN skipped THEN 1 ELSE 0 END)           AS skip_count
            FROM plays
            WHERE uri = %s AND context_uri = %s
            """,
            (uri, context_uri),
        ).fetchone()

        if row and row[0] >= min_plays:
            play_count, skip_count = int(row[0]), int(row[1] or 0)
            rate = skip_count / play_count
            if rate >= threshold:
                return (
                    True,
                    f"Kontekst-skip-rate {rate:.0%} "
                    f"({skip_count}/{play_count} i denne spillelisten)",
                )

    # --- Global skip-rate som fallback ---
    row = execute(
        conn,
        """
        SELECT
            COUNT(*)                                                AS play_count,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END)               AS skip_count
        FROM plays
        WHERE uri = %s
        """,
        (uri,),
    ).fetchone()

    if row and row[0] >= min_plays:
        play_count, skip_count = int(row[0]), int(row[1] or 0)
        rate = skip_count / play_count
        if rate >= threshold:
            return (
                True,
                f"Global skip-rate {rate:.0%} "
                f"({skip_count}/{play_count} totale avspillinger)",
            )

    return (False, "Under terskel eller for lite data")


# ---------------------------------------------------------------------------
# Audit-logging
# ---------------------------------------------------------------------------

def log_auto_skip(
    conn,
    uri: str,
    title: str | None,
    artists: str | None,
    context_uri: str | None,
    skip_rate: float,
    threshold: float,
    reason: str,
) -> None:
    """Skriver én post til auto_skips-tabellen (audit-logg)."""
    execute(
        conn,
        """
        INSERT INTO auto_skips
            (uri, title, artists, context_uri, skip_rate, threshold, reason)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (uri, title, artists, context_uri, skip_rate, threshold, reason),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Spotify API — hopp til neste sang
# ---------------------------------------------------------------------------

def skip_to_next(token: str, device_id: str | None = None) -> bool:
    """
    Sender POST /v1/me/player/next til Spotify.
    Returnerer True ved 204 No Content (suksess), False ved alle feil.

    403 = mangler 'user-modify-playback-state'-scope → brukeren må kjøre
    'python3 -m spotify_skip_tracker setup' på nytt.
    404 = ingen aktiv avspilling akkurat nå.
    """
    url = "https://api.spotify.com/v1/me/player/next"
    params = {"device_id": device_id} if device_id else {}
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=10,
        )
        if resp.status_code == 204:
            return True
        if resp.status_code == 403:
            logger.error(
                "Mangler 'user-modify-playback-state'-tillatelse. "
                "Kjør 'python3 -m spotify_skip_tracker setup' på nytt for å gi "
                "Smart Skipper tilgang til å styre avspillingen."
            )
            return False
        if resp.status_code == 404:
            logger.warning(
                "Spotify svarte 404 ved hopp-forsøk — ingen aktiv avspilling funnet."
            )
            return False
        logger.error(
            "Uventet statuskode fra Spotify ved hopp: %d %s",
            resp.status_code, resp.text[:120],
        )
        return False
    except requests.RequestException as exc:
        logger.error("Nettverksfeil ved forsøk på å hoppe: %s", exc)
        return False


# ---------------------------------------------------------------------------
# SmartSkipper — tilstandsmaskin
# ---------------------------------------------------------------------------

class SmartSkipper:
    """
    Tilstandsmaskin for Smart Skipper.

    Instansieres én gang i tracker.py og kalles ved hvert poll-syklus
    med gjeldende avspillingsstatus. Krever ingen egne tråder.

    Tilstandsflyt:
        IDLE      → COUNTING  (ny sang med høy skip-rate oppdaget)
        COUNTING  → SKIPPING  (delay-nedtellingen er ferdig)
        COUNTING  → IDLE      (sangen endret seg før nedtellingen var ferdig)
        SKIPPING  → IDLE      (hopp ble utført eller mislyktes)

    Sikkerhetsnett (alle sjekkes i evaluate()):
        • dry_run=True          → logger hva som *ville* skjedd, gjør ingenting
        • enabled=False         → hele funksjonen er deaktivert
        • context_uri=None      → hopper aldri over kø-musikk uten kontekst
        • progress_ms < 3 s     → lar brukeren rekke å se hva som spilles
        • remaining_ms < 10 s   → sangen er nesten ferdig, ikke verdt å hoppe
        • _skipped_this_session → aldri hopp over samme sang to ganger på rad
        • excluded_contexts     → aldri hopp i opplistede spillelister
        • excluded_uris         → aldri hopp over opplistede sanger
        • MAX_AUTO_SKIPS/TIME   → maks 10 automatiske hopp per 60 minutter
    """

    def __init__(self) -> None:
        self._pending_uri: str | None = None
        self._pending_since: float | None = None
        self._skipped_this_session: set[str] = set()
        # Tidsstempel (monotonic) for hvert gjennomførte auto-hopp denne sesjonen.
        # Brukes til å håndheve MAX_AUTO_SKIPS_PER_HOUR.
        self._skip_timestamps: list[float] = []

    # ------------------------------------------------------------------
    # Hoved-evaluering — kalles ved hvert poll-syklus
    # ------------------------------------------------------------------

    def evaluate(
        self,
        conn,
        token: str,
        current_uri: str | None,
        current_title: str | None,
        current_artists: str | None,
        context_uri: str | None,
        progress_ms: int,
        duration_ms: int,
        is_playing: bool,
    ) -> bool:
        """
        Kalles ved hvert poll-syklus. Returnerer True hvis et faktisk hopp
        ble utført (ikke bare loggført i dry-run-modus).

        Parametere:
            conn           Aktiv database-tilkobling
            token          Gyldig Spotify access token
            current_uri    URI for sangen som spilles nå
            current_title  Tittel (for logging)
            current_artists Artistnavn (for logging)
            context_uri    Spotify-URI for nåværende spilleliste/album
            progress_ms    Antall millisekunder inn i sangen
            duration_ms    Total lengde på sangen i millisekunder
            is_playing     True dersom noe faktisk spilles
        """
        # --- Grunnleggende sanity-sjekker ---
        if not current_uri or not is_playing:
            self._reset()
            return False

        # --- Hent konfigurasjon fra DB ---
        config = load_config(conn)
        if not config.get("enabled"):
            return False

        # --- Sikkerhetsnett 1: aldri hopp over kø-musikk (ingen kontekst) ---
        if not context_uri:
            return False

        # --- Sikkerhetsnett 2: allerede hoppet over denne sangen i dag ---
        if current_uri in self._skipped_this_session:
            return False

        # --- Sikkerhetsnett 3: ekskluderte kontekster og sanger ---
        if context_uri in config["excluded_contexts"]:
            return False
        if current_uri in config["excluded_uris"]:
            return False

        # --- Sikkerhetsnett 4: vent minst 3 sekunder (la brukeren se hva som spilles) ---
        if progress_ms < 3_000:
            return False

        # --- Sikkerhetsnett 5: hopp ikke hvis under 10 sekunder igjen ---
        remaining_ms = duration_ms - progress_ms
        if remaining_ms < 10_000:
            self._reset()
            return False

        # --- Sikkerhetsnett 6: maks 10 auto-hopp per time ---
        now = time.monotonic()
        recent_skips = [t for t in self._skip_timestamps if now - t < 3600]
        if len(recent_skips) >= MAX_AUTO_SKIPS_PER_HOUR:
            logger.warning(
                "Smart Skipper: nådd maksimumsgrense på %d automatiske hopp "
                "per time. Pause til neste time.",
                MAX_AUTO_SKIPS_PER_HOUR,
            )
            return False
        # Oppdater listen (fjern gamle, behold gjeldende vindu)
        self._skip_timestamps = recent_skips

        # --- Reset hvis sangen har endret seg siden sist vi telte ned ---
        if self._pending_uri and self._pending_uri != current_uri:
            logger.debug(
                "Sang endret seg fra %s til %s — resetter Smart Skipper-nedtelling.",
                self._pending_uri,
                current_uri,
            )
            self._reset()

        # --- Sjekk om sangen kvalifiserer for auto-hopp ---
        should_skip, reason = should_auto_skip(
            conn,
            uri=current_uri,
            context_uri=context_uri,
            threshold=config["threshold"],
            min_plays=config["min_plays"],
        )

        if not should_skip:
            self._reset()
            return False

        # --- Start nedtelling hvis ikke allerede i gang ---
        if self._pending_uri is None:
            self._pending_uri = current_uri
            self._pending_since = time.monotonic()

            if config["dry_run"]:
                logger.info(
                    "[DRY RUN] Smart Skipper ville startet %ds-nedtelling for: "
                    "%s — %s (%s)",
                    config["delay_seconds"],
                    current_artists,
                    current_title,
                    reason,
                )
            else:
                logger.info(
                    "Smart Skipper: starter %ds-nedtelling for '%s' (%s)",
                    config["delay_seconds"],
                    current_title,
                    reason,
                )
            return False

        # --- Er nedtellingen ferdig? ---
        elapsed = time.monotonic() - self._pending_since  # type: ignore[operator]
        if elapsed < config["delay_seconds"]:
            return False

        # ------------------------------------------------------------------
        # Nedtellingen er ferdig — tid for å hoppe
        # ------------------------------------------------------------------
        uri_to_skip = self._pending_uri
        self._reset()

        # Hent gjeldende global skip-rate for audit-loggen
        rate_row = execute(
            conn,
            """
            SELECT COUNT(*), SUM(CASE WHEN skipped THEN 1 ELSE 0 END)
            FROM plays WHERE uri = %s
            """,
            (uri_to_skip,),
        ).fetchone()
        skip_rate = (
            int(rate_row[1] or 0) / int(rate_row[0])
            if rate_row and rate_row[0]
            else 0.0
        )

        # --- Sikkerhetsnett 7: dry_run hindrer faktisk hopp ---
        if config["dry_run"]:
            logger.info(
                "[DRY RUN] Smart Skipper ville nå hoppet over '%s' — %s "
                "(skip-rate %.0f%%). Sett dry_run=FALSE i databasen for "
                "å aktivere ekte hopp.",
                current_title,
                current_artists,
                skip_rate * 100,
            )
            # Logger likevel til audit-tabellen, merket som dry-run i reason
            log_auto_skip(
                conn,
                uri=uri_to_skip,
                title=current_title,
                artists=current_artists,
                context_uri=context_uri,
                skip_rate=skip_rate,
                threshold=config["threshold"],
                reason=f"[DRY RUN] {reason}",
            )
            return False

        # --- Gjennomfør hoppet ---
        logger.info(
            "Smart Skipper: hopper over '%s' — %s (skip-rate %.0f%%, %s)",
            current_title,
            current_artists,
            skip_rate * 100,
            reason,
        )
        success = skip_to_next(token)

        if success:
            # Registrer tidspunkt for rate-limiting
            self._skip_timestamps.append(time.monotonic())
            # Marker sangen som hoppet over denne sesjonen
            self._skipped_this_session.add(uri_to_skip)
            # Skriv til audit-logg
            log_auto_skip(
                conn,
                uri=uri_to_skip,
                title=current_title,
                artists=current_artists,
                context_uri=context_uri,
                skip_rate=skip_rate,
                threshold=config["threshold"],
                reason=reason,
            )
        else:
            logger.warning(
                "Smart Skipper: hopp-kommando mislyktes for '%s'.", current_title
            )

        return success

    # ------------------------------------------------------------------
    # Intern hjelpefunksjon
    # ------------------------------------------------------------------

    def _reset(self) -> None:
        """Nullstiller nedtellingstilstand. Påvirker ikke session-historikk."""
        self._pending_uri = None
        self._pending_since = None
