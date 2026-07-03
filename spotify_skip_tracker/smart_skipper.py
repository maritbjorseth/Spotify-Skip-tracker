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

def load_config(conn, user_id: str = "default_user") -> dict:
    """
    Henter Smart Skipper-konfigurasjon for en bestemt bruker.

    Returnerer alltid et gyldig dict — ved manglende rad er enabled=False,
    slik at tracker-loopen aldri krasjer om raden mangler.

    Parametere:
        user_id  Spotify-bruker-ID — filtrerer til brukerens egne innstillinger.
    """
    row = execute(
        conn,
        """
        SELECT enabled, threshold, min_plays, delay_seconds,
               dry_run, respect_time, excluded_contexts, excluded_uris
        FROM smart_skipper_config
        WHERE user_id = %s
        """,
        (user_id,),
    ).fetchone()

    if not row:
        logger.debug(
            "Ingen Smart Skipper-konfigurasjon funnet for '%s' — bruker standardverdier.",
            user_id,
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
    user_id: str = "default_user",
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

    Parametere:
        user_id  Spotify-bruker-ID — avgjørende for at beslutningen baseres
                 på brukerens egne data, ikke alle brukeres data kombinert.
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
            WHERE uri = %s AND context_uri = %s AND user_id = %s
            """,
            (uri, context_uri, user_id),
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

    # --- Global skip-rate som fallback (kun brukerens egne data) ---
    row = execute(
        conn,
        """
        SELECT
            COUNT(*)                                                AS play_count,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END)               AS skip_count
        FROM plays
        WHERE uri = %s AND user_id = %s
        """,
        (uri, user_id),
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
    user_id: str = "default_user",
) -> None:
    """Skriver én post til auto_skips-tabellen (audit-logg) for én bruker."""
    # Nullstill eventuelle uferdige eller avbrutte transaksjoner på tilkoblingen
    # før vi skriver. SELECTs i evaluate() kan ha etterlatt en åpen transaksjon,
    # og en mislykket kontekstnavn-oppslag kan ha satt tilkoblingen i aborted-tilstand.
    # Rollback her er ufarlig — alle foregående lese-spørringer trenger ikke commit.
    try:
        conn.rollback()
    except Exception:
        pass

    execute(
        conn,
        """
        INSERT INTO auto_skips
            (user_id, uri, title, artists, context_uri, skip_rate, threshold, reason)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (user_id, uri, title, artists, context_uri, skip_rate, threshold, reason),
    )
    conn.commit()
    logger.info(
        "Auto-skip skrevet til audit-logg: user_id=%s, uri=%s, reason=%s",
        user_id, uri, reason,
    )


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
        if resp.status_code == 200:
            # Spotify returnerer av og til 200 i stedet for 204 i visse
            # playback-kontekster. Dette er udokumentert serveradferd —
            # dokumentasjonen spesifiserer 204 som eneste suksess-kode —
            # men sangen hopper faktisk. Behandles som suksess.
            logger.warning(
                "Spotify svarte 200 (forventet 204) ved hopp — "
                "behandler som suksess. Body: %s", resp.text or "(tom)",
            )
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
            "Uventet statuskode fra Spotify ved hopp: %d\n"
            "  URL:     %s\n"
            "  Params:  %s\n"
            "  Headers: %s\n"
            "  Body:    %s",
            resp.status_code,
            url,
            params,
            dict(resp.headers),
            resp.text,
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
        # Utålmodighetslogikk (Fase G — Musikkcoach)
        self._recent_outcomes: list[bool] = []   # True = skippet, False = fullført
        self._impatience_active: bool = False    # True når brukeren er i utålmodig modus
        self.IMPATIENCE_FACTOR: float = 0.15     # Senk terskelen med 15% under utålmodighet

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
        user_id: str = "default_user",
    ) -> bool:
        """
        Kalles ved hvert poll-syklus. Returnerer True hvis et faktisk hopp
        ble utført (ikke bare loggført i dry-run-modus).

        Parametere:
            conn            Aktiv database-tilkobling
            token           Gyldig Spotify access token
            current_uri     URI for sangen som spilles nå
            current_title   Tittel (for logging)
            current_artists Artistnavn (for logging)
            context_uri     Spotify-URI for nåværende spilleliste/album
            progress_ms     Antall millisekunder inn i sangen
            duration_ms     Total lengde på sangen i millisekunder
            is_playing      True dersom noe faktisk spilles
            user_id         Spotify-bruker-ID — sikrer at skip-beslutninger
                            baseres kun på brukerens egne avspillinger.
        """
        # --- Grunnleggende sanity-sjekker ---
        if not current_uri or not is_playing:
            self._reset()
            return False

        # --- Hent konfigurasjon fra DB (per bruker) ---
        config = load_config(conn, user_id)
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
        # I utålmodighets-modus senkes terskelen med IMPATIENCE_FACTOR (f.eks. 85% → 70%)
        effective_threshold = config["threshold"]
        if self._impatience_active:
            effective_threshold = max(0.0, effective_threshold - self.IMPATIENCE_FACTOR)
            logger.debug(
                "Smart Skipper: utålmodighets-modus aktiv — terskel senket fra %.0f%% til %.0f%%.",
                config["threshold"] * 100,
                effective_threshold * 100,
            )

        should_skip, reason = should_auto_skip(
            conn,
            uri=current_uri,
            context_uri=context_uri,
            threshold=effective_threshold,
            min_plays=config["min_plays"],
            user_id=user_id,
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

        # Hent gjeldende global skip-rate for audit-loggen (kun brukerens data)
        rate_row = execute(
            conn,
            """
            SELECT COUNT(*), SUM(CASE WHEN skipped THEN 1 ELSE 0 END)
            FROM plays WHERE uri = %s AND user_id = %s
            """,
            (uri_to_skip, user_id),
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
                user_id=user_id,
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
                user_id=user_id,
            )
        else:
            logger.warning(
                "Smart Skipper: hopp-kommando mislyktes for '%s'.", current_title
            )

        return success

    # ------------------------------------------------------------------
    # Utålmodighetsregistrering — kalles av tracker.py etter hvert sporbytte
    # ------------------------------------------------------------------

    def record_outcome(self, is_skipped: bool) -> None:
        """
        Registrerer utfallet av sangen som nettopp ble avsluttet.

        is_skipped=True  → sangen ble skippet
        is_skipped=False → sangen ble spilt helt ferdig

        Holder kun de 3 siste sangene i minnet. Dersom minst 2 av de
        3 siste ble skippet, aktiveres utålmodighets-modus, noe som senker
        skip-terskelen med IMPATIENCE_FACTOR i neste evaluate()-kall.
        """
        self._recent_outcomes.append(is_skipped)
        self._recent_outcomes = self._recent_outcomes[-3:]

        if len(self._recent_outcomes) == 3:
            self._impatience_active = self._recent_outcomes.count(True) >= 2
        else:
            self._impatience_active = False

        if self._impatience_active:
            logger.debug(
                "Smart Skipper: utålmodighets-modus aktivert "
                "(minst 2 av 3 siste sanger skippet)."
            )
        else:
            logger.debug(
                "Smart Skipper: utålmodighets-modus ikke aktiv "
                "(utfall siste %d sanger: %s).",
                len(self._recent_outcomes),
                self._recent_outcomes,
            )

    # ------------------------------------------------------------------
    # Intern hjelpefunksjon
    # ------------------------------------------------------------------

    def _reset(self) -> None:
        """Nullstiller nedtellingstilstand. Påvirker ikke session-historikk."""
        self._pending_uri = None
        self._pending_since = None
        self._recent_outcomes = []
        self._impatience_active = False
