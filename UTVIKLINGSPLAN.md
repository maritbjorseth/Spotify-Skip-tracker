# Utviklingsplan: Smart Skipper og Playlist Janitor

**Prosjekt:** Spotify Skip Tracker  
**Dokument:** Fremtidige funksjoner — fullstendig teknisk guide  
**Språk:** Norsk  
**Dato:** Juni 2026  

---

## Innholdsfortegnelse

1. [Oversikt og filosofi](#1-oversikt-og-filosofi)
2. [Forutsetninger og API-tilgang](#2-forutsetninger-og-api-tilgang)
3. [Smart Skipper — Automatisk hopping](#3-smart-skipper--automatisk-hopping)
   - 3.1 [Hva er Smart Skipper?](#31-hva-er-smart-skipper)
   - 3.2 [Spotify API-endepunkter](#32-spotify-api-endepunkter)
   - 3.3 [Beslutningslogikk og algoritmer](#33-beslutningslogikk-og-algoritmer)
   - 3.4 [Databaseendringer](#34-databaseendringer)
   - 3.5 [Python-implementasjon](#35-python-implementasjon)
   - 3.6 [Konfigurasjon og brukerinnstillinger](#36-konfigurasjon-og-brukerinnstillinger)
   - 3.7 [Sikkerhetsnett og begrensninger](#37-sikkerhetsnett-og-begrensninger)
   - 3.8 [Frontend-integrasjon](#38-frontend-integrasjon)
   - 3.9 [Testing](#39-testing)
4. [Playlist Janitor — Automatisk opprydding](#4-playlist-janitor--automatisk-opprydding)
   - 4.1 [Hva er Playlist Janitor?](#41-hva-er-playlist-janitor)
   - 4.2 [Spotify API-endepunkter](#42-spotify-api-endepunkter)
   - 4.3 [Kandidatidentifikasjon og rangering](#43-kandidatidentifikasjon-og-rangering)
   - 4.4 [Databaseendringer](#44-databaseendringer)
   - 4.5 [Python-implementasjon](#45-python-implementasjon)
   - 4.6 [Godkjenningsflyt og brukerbekreftelse](#46-godkjenningsflyt-og-brukerbekreftelse)
   - 4.7 [Frontend-integrasjon](#47-frontend-integrasjon)
   - 4.8 [Testing og sikkerhetsnett](#48-testing-og-sikkerhetsnett)
5. [Felles infrastruktur](#5-felles-infrastruktur)
   - 5.1 [OAuth-scope-utvidelse](#51-oauth-scope-utvidelse)
   - 5.2 [Rate limiting og køsystem](#52-rate-limiting-og-køsystem)
   - 5.3 [Audit-logg](#53-audit-logg)
6. [Deployment og konfigurasjon på Railway](#6-deployment-og-konfigurasjon-på-railway)
7. [Anbefalt utviklingsrekkefølge](#7-anbefalt-utviklingsrekkefølge)
8. [Fase G — Musikkcoach og Avansert Innsikt (Insights)](#8-fase-g--musikkcoach-og-avansert-innsikt-insights)
   - 8.1 [Utålmodighets-modus (Sequential Skips)](#81-utålmodighets-modus-sequential-skips)
   - 8.2 [Tids- og kontekstanalyser](#82-tids--og-kontekstanalyser)
   - 8.3 [Låt-DNA (Audio Features)](#83-låt-dna-audio-features)
9. [Fase H — Smart Score og Rapportering (Wrapped)](#9-fase-h--smart-score-og-rapportering-wrapped)
   - 9.1 [Listening Score](#91-listening-score)
   - 9.2 [Månedlig Skip Wrapped](#92-månedlig-skip-wrapped)

---

## 1. Oversikt og filosofi

Spotify Skip Tracker startet som et passivt observasjonsverktøy: den ser, den logger, men den gjør ingenting. De to neste fasene, **Smart Skipper** og **Playlist Janitor**, tar steget fra passiv observasjon til aktiv handling. Dette er et fundamentalt skifte i arkitekturen og krever nøye planlegging.

### Grunnprinsipper for aktive funksjoner

**1. Brukeren har alltid siste ord.**  
Automatiske handlinger skal aldri overraske brukeren negativt. Alt som skjer automatisk skal logges, kunne angres, og ideelt sett bekreftes på forhånd. En sang som blir slettet fra en spilleliste uten brukerens bevissthet er en katastrofe. En sang som blir hoppet over kan oppleves som irriterende. Begge må ha tydelige grenser.

**2. Start konservativt, juster etter data.**  
Alle terskler og grenser skal settes lavt i starten. Det er mye bedre at systemet er for forsiktig enn for aggressivt. En "prøvemodus" der systemet forteller deg hva det *ville* gjort, uten å faktisk gjøre det, er uvurderlig for å bygge tillit.

**3. Aldri ødelegg musikklytting.**  
Smart Skipper skal aldri hoppe over en sang du faktisk vil høre. Playlist Janitor skal aldri slette en sang du er glad i. Begge funksjonene må ha solide sikkerhetsventiler.

**4. All automasjon er deaktivert som standard.**  
Nye brukere skal eksplisitt aktivere Smart Skipper og Playlist Janitor. Ingen overraskelser.

---

## 2. Forutsetninger og API-tilgang

### Nødvendige endringer i OAuth-scope

Nåværende scope i `config.py` er:
```python
SCOPE = "user-read-currently-playing user-read-playback-state"
```

For Smart Skipper trenger du i tillegg:
```
user-modify-playback-state
```

For Playlist Janitor trenger du i tillegg:
```
playlist-modify-public
playlist-modify-private
playlist-read-private
playlist-read-collaborative
```

Fullstendig ny scope-streng:
```python
SCOPE = (
    "user-read-currently-playing "
    "user-read-playback-state "
    "user-modify-playback-state "
    "playlist-modify-public "
    "playlist-modify-private "
    "playlist-read-private "
    "playlist-read-collaborative"
)
```

> **Viktig:** Scope-endring krever at brukeren kjører `python3 -m spotify_skip_tracker setup` på nytt og godkjenner de nye tillatelsene i nettleseren. Det eksisterende refresh-tokenet vil ikke automatisk få de nye tillatelsene. Legg til en tydelig feilmelding i koden som oppdager `403 Forbidden` fra Spotify og forteller brukeren at de må kjøre setup på nytt.

### Spotify API-rate limiting

Spotify Web API har følgende rate limits (per januar 2026, men kan endres):

- Ingen offisiell dokumentert grense for de fleste endepunkter
- I praksis: ca. 180 kall per 30 sekunder for playback-endepunkter
- Tracker-loopen kaller allerede APIet hvert 7. sekund (ca. 8–9 kall/minutt)
- Smart Skipper legger til 1 ekstra kall ved hopp (sjeldent)
- Playlist Janitor-kall bør begrenses til manuell aktivering eller sjeldne batch-jobber

Håndter alltid `429 Too Many Requests` med eksponentiell backoff:

```python
import time

def spotify_request_with_retry(method, url, **kwargs):
    """
    Utfører en Spotify API-forespørsel med automatisk retry ved rate limiting.
    Maks 5 forsøk med eksponentiell backoff: 1s, 2s, 4s, 8s, 16s.
    """
    for attempt in range(5):
        resp = method(url, **kwargs)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 2 ** attempt))
            logger.warning(
                "Rate limit nådd. Venter %d sekunder (forsøk %d/5).",
                retry_after, attempt + 1
            )
            time.sleep(retry_after)
            continue
        return resp
    raise RuntimeError("Spotify API svarte med 429 etter 5 forsøk.")
```

---

## 3. Smart Skipper — Automatisk hopping

### 3.1 Hva er Smart Skipper?

Smart Skipper er en funksjon som automatisk sender en "hopp til neste sang"-kommando til Spotify når den oppdager at du nesten sikkert vil hoppe manuelt. Den bruker din egen historiske skip-data fra databasen til å ta beslutningen.

**Eksempel på brukstilfelle:**  
Du har hoppet over "That Song" 15 av de siste 16 gangene den har dukket opp i spillelisten "Work Focus". Smart Skipper vet dette, og neste gang sangen starter i den spillelisten, venter den 5 sekunder (slik at det ikke er helt umerkelig) og hopper deretter automatisk over.

**Hva Smart Skipper ikke er:**  
- En musikk-anbefaling-motor  
- En straffefunksjon som blokkerer sanger permanent  
- Noe som kjører uten din viten  

### 3.2 Spotify API-endepunkter

#### Hopp til neste sang
```
POST https://api.spotify.com/v1/me/player/next
Authorization: Bearer {access_token}
```

Valgfri query-parameter: `?device_id={device_id}` (anbefalt for presisjon)

Returnerer `204 No Content` ved suksess. Ingen kropp.

Eksempel med `requests`:
```python
def skip_to_next(token: str, device_id: str | None = None) -> bool:
    """
    Sender hopp-til-neste-kommando til Spotify.
    Returnerer True ved suksess, False ved feil.
    """
    url = "https://api.spotify.com/v1/me/player/next"
    params = {"device_id": device_id} if device_id else {}
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
            "Kjør 'python3 -m spotify_skip_tracker setup' på nytt."
        )
        return False
    if resp.status_code == 404:
        logger.warning("Ingen aktiv avspilling funnet.")
        return False
    logger.error("Uventet statuskode fra Spotify: %d", resp.status_code)
    return False
```

#### Hent nåværende avspillingsstatus (allerede implementert)
```
GET https://api.spotify.com/v1/me/player
Authorization: Bearer {access_token}
```

Dette kallet gjøres allerede i `tracker.py`. Smart Skipper kan gjenbruke dataene fra polling-loopen uten ekstra API-kall.

### 3.3 Beslutningslogikk og algoritmer

Dette er hjernekjernen i Smart Skipper. Det finnes flere tilnærminger, rangert fra enkel til sofistikert:

#### Tilnærming A: Enkel skip-rate-terskel (anbefalt å starte med)

Hopp automatisk hvis skip-raten for sangen i *den nåværende konteksten* overstiger en konfigurerbar terskel (f.eks. 85%).

```python
def should_auto_skip(
    conn,
    uri: str,
    context_uri: str | None,
    *,
    threshold: float = 0.85,
    min_plays: int = 3,
) -> tuple[bool, str]:
    """
    Bestemmer om Smart Skipper skal hoppe automatisk over denne sangen.

    Returnerer (skal_hoppe, begrunnelse).

    Logikken:
    - Hent skip-rate for sangen i denne spesifikke spillelisten/albumet.
    - Fallback til global skip-rate for sangen hvis ikke nok kontekst-data.
    - Krev et minimum antall avspillinger for å unngå falske positiver.
    """
    # --- Kontekst-spesifikk skip-rate ---
    if context_uri:
        row = execute(
            conn,
            """
            SELECT
                COUNT(*) AS play_count,
                SUM(CASE WHEN skipped THEN 1 ELSE 0 END) AS skip_count
            FROM plays
            WHERE uri = %s AND context_uri = %s
            """,
            (uri, context_uri),
        ).fetchone()

        if row and row[0] >= min_plays:
            play_count, skip_count = row
            rate = skip_count / play_count
            if rate >= threshold:
                return (
                    True,
                    f"Skip-rate {rate:.0%} i denne spillelisten "
                    f"({skip_count}/{play_count} avspillinger)"
                )

    # --- Global skip-rate som fallback ---
    row = execute(
        conn,
        """
        SELECT
            COUNT(*) AS play_count,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END) AS skip_count
        FROM plays
        WHERE uri = %s
        """,
        (uri,),
    ).fetchone()

    if row and row[0] >= min_plays:
        play_count, skip_count = row
        rate = skip_count / play_count
        if rate >= threshold:
            return (
                True,
                f"Global skip-rate {rate:.0%} "
                f"({skip_count}/{play_count} totale avspillinger)"
            )

    return (False, "Ikke nok data eller under terskel")
```

#### Tilnærming B: Tidspunkt-vektet skip-rate

Nyere avspillinger veier tyngre enn gamle. En sang du hoppet over for 6 måneder siden, men har lyttet ferdig 5 ganger i det siste, bør ikke hoppes over automatisk.

```python
def weighted_skip_rate(conn, uri: str, context_uri: str | None) -> float:
    """
    Beregner en eksponentielt tidsvektet skip-rate.
    Avspillinger de siste 30 dagene vektes 3x.
    Avspillinger de siste 90 dagene vektes 2x.
    Eldre avspillinger vektes 1x.
    """
    rows = execute(
        conn,
        """
        SELECT
            skipped,
            timestamp,
            NOW() - timestamp AS age
        FROM plays
        WHERE uri = %s
          AND (context_uri = %s OR %s IS NULL)
        ORDER BY timestamp DESC
        """,
        (uri, context_uri, context_uri),
    ).fetchall()

    if not rows:
        return 0.0

    weighted_skips = 0.0
    weighted_total = 0.0

    for skipped, timestamp, age in rows:
        age_days = age.total_seconds() / 86400
        if age_days <= 30:
            weight = 3.0
        elif age_days <= 90:
            weight = 2.0
        else:
            weight = 1.0

        weighted_total += weight
        if skipped:
            weighted_skips += weight

    return weighted_skips / weighted_total if weighted_total > 0 else 0.0
```

#### Tilnærming C: Tidspunkt-bevisst hopping

Brukeren hopper mer om mandagsmorgenen enn på fredag kveld. Smart Skipper tar hensyn til dette:

```python
def should_auto_skip_time_aware(
    conn,
    uri: str,
    context_uri: str | None,
    current_hour: int,
    current_weekday: int,  # 0=mandag, 6=søndag
    threshold: float = 0.85,
) -> tuple[bool, str]:
    """
    Sjekker skip-rate for sangen på dette tidspunktet på dagen og ukedagen.
    Mer presis enn en global rate — du hopper kanskje over sørgelig musikk
    på mandager men hører den på søndagskveld.
    """
    row = execute(
        conn,
        """
        SELECT
            COUNT(*) AS play_count,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END) AS skip_count
        FROM plays
        WHERE
            uri = %s
            AND (context_uri = %s OR %s IS NULL)
            AND EXTRACT(HOUR FROM timestamp AT TIME ZONE 'Europe/Oslo')
                BETWEEN %s AND %s
            AND (EXTRACT(ISODOW FROM timestamp AT TIME ZONE 'Europe/Oslo')::INT - 1)
                = %s
        """,
        (uri, context_uri, context_uri,
         max(0, current_hour - 2), min(23, current_hour + 2),
         current_weekday),
    ).fetchone()

    # Krev minimum 2 avspillinger i dette tidsvinduet for å unngå tilfeldigheter
    if row and row[0] >= 2:
        play_count, skip_count = row
        rate = skip_count / play_count
        if rate >= threshold:
            return (
                True,
                f"Skip-rate {rate:.0%} på dette tidspunktet "
                f"({skip_count}/{play_count})"
            )

    # Fallback til Tilnærming A
    return should_auto_skip(conn, uri, context_uri, threshold=threshold)
```

#### Valg av tilnærming

For første versjon: **Tilnærming A**. Enkel, forklarbar, og lett å debugge. Legg til B og C etter at du har samlet brukererfaring.

### 3.4 Databaseendringer

Legg til en tabell for Smart Skipper-hendelser og en konfigurasjonstabell:

```sql
-- Logg over automatiske hopp (for revisjon og angremulighet)
CREATE TABLE IF NOT EXISTS auto_skips (
    id           SERIAL PRIMARY KEY,
    uri          TEXT NOT NULL,
    title        TEXT,
    artists      TEXT,
    context_uri  TEXT,
    skip_rate    REAL NOT NULL,          -- skip-raten som trigget hoppet
    threshold    REAL NOT NULL,          -- terskelen som var konfigurert
    reason       TEXT,                  -- menneskelig forklaring
    timestamp    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    undone       BOOLEAN NOT NULL DEFAULT FALSE,
    undone_at    TIMESTAMPTZ
);

-- Brukerkonfigurasjon for Smart Skipper
CREATE TABLE IF NOT EXISTS smart_skipper_config (
    id                  INTEGER PRIMARY KEY DEFAULT 1,
    enabled             BOOLEAN NOT NULL DEFAULT FALSE,
    threshold           REAL NOT NULL DEFAULT 0.85,
    min_plays           INTEGER NOT NULL DEFAULT 3,
    delay_seconds       INTEGER NOT NULL DEFAULT 5,   -- vent X sek før hopp
    dry_run             BOOLEAN NOT NULL DEFAULT TRUE, -- prøvemodus
    respect_time        BOOLEAN NOT NULL DEFAULT FALSE, -- bruk Tilnærming C
    excluded_contexts   TEXT[] DEFAULT '{}',           -- aldri hopp i disse
    excluded_uris       TEXT[] DEFAULT '{}'            -- aldri hopp over disse
);

-- Sett inn standardkonfigurasjon
INSERT INTO smart_skipper_config (id) VALUES (1) ON CONFLICT DO NOTHING;
```

Legg til migrasjonen i `database.py`'s `init_db()`-funksjon:

```python
def _migrate_smart_skipper(conn) -> None:
    """Oppretter Smart Skipper-tabeller hvis de ikke finnes."""
    execute(conn, """
        CREATE TABLE IF NOT EXISTS auto_skips (
            id           SERIAL PRIMARY KEY,
            uri          TEXT NOT NULL,
            title        TEXT,
            artists      TEXT,
            context_uri  TEXT,
            skip_rate    REAL NOT NULL,
            threshold    REAL NOT NULL,
            reason       TEXT,
            timestamp    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            undone       BOOLEAN NOT NULL DEFAULT FALSE,
            undone_at    TIMESTAMPTZ
        )
    """)
    execute(conn, """
        CREATE TABLE IF NOT EXISTS smart_skipper_config (
            id                  INTEGER PRIMARY KEY DEFAULT 1,
            enabled             BOOLEAN NOT NULL DEFAULT FALSE,
            threshold           REAL NOT NULL DEFAULT 0.85,
            min_plays           INTEGER NOT NULL DEFAULT 3,
            delay_seconds       INTEGER NOT NULL DEFAULT 5,
            dry_run             BOOLEAN NOT NULL DEFAULT TRUE,
            respect_time        BOOLEAN NOT NULL DEFAULT FALSE,
            excluded_contexts   TEXT[] DEFAULT '{}',
            excluded_uris       TEXT[] DEFAULT '{}'
        )
    """)
    execute(conn, """
        INSERT INTO smart_skipper_config (id) VALUES (1) ON CONFLICT DO NOTHING
    """)
    conn.commit()
```

### 3.5 Python-implementasjon

Opprett en ny fil `spotify_skip_tracker/smart_skipper.py`:

```python
"""
Smart Skipper — automatisk hopping basert på historisk skip-data.

Integreres i polling-loopen i tracker.py. Kjøres som en del av
den eksisterende 7-sekunders polling-syklusen, uten egne tråder.
"""

import logging
import time
from datetime import datetime, timezone

import requests

from .database import execute

logger = logging.getLogger(__name__)


def load_config(conn) -> dict:
    """Henter Smart Skipper-konfigurasjon fra databasen."""
    row = execute(
        conn,
        """
        SELECT enabled, threshold, min_plays, delay_seconds,
               dry_run, respect_time, excluded_contexts, excluded_uris
        FROM smart_skipper_config WHERE id = 1
        """,
    ).fetchone()
    if not row:
        return {"enabled": False}
    return {
        "enabled": row[0],
        "threshold": row[1],
        "min_plays": row[2],
        "delay_seconds": row[3],
        "dry_run": row[4],
        "respect_time": row[5],
        "excluded_contexts": row[6] or [],
        "excluded_uris": row[7] or [],
    }


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
    """Skriver en post til auto_skips-tabellen."""
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


class SmartSkipper:
    """
    Tilstandsmaskin for Smart Skipper.

    Instansieres én gang i tracker.py og kalles på hvert poll-syklus
    med nåværende avspillingsstatus.

    Tilstandsflyt:
        IDLE → COUNTING (ny sang med høy skip-rate oppdaget)
        COUNTING → SKIPPING (delay utløpt, sender hopp)
        COUNTING → IDLE (sang endret seg før delay utløp)
        SKIPPING → IDLE (hopp utført)
    """

    def __init__(self):
        self._pending_uri: str | None = None      # sangen vi vurderer å hoppe over
        self._pending_since: float | None = None  # tidspunkt da vi begynte å vente
        self._skipped_this_session: set[str] = set()  # unngå gjentatte auto-hopp

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
        Kalles på hvert poll-syklus. Returnerer True hvis et hopp ble utført.

        Algoritme:
        1. Last konfigurasjon (caches i produksjon, men OK for nå)
        2. Sjekk om auto-hopp er aktuelt for dette sporet
        3. Start nedtelling hvis ja
        4. Utfør hopp når nedtellingen er ferdig
        """
        if not current_uri or not is_playing:
            self._reset()
            return False

        config = load_config(conn)
        if not config.get("enabled"):
            return False

        # Aldri hopp over sanger du allerede har hoppet over automatisk i dag
        if current_uri in self._skipped_this_session:
            return False

        # Sjekk ekskluderte kontekster og sanger
        if context_uri in config["excluded_contexts"]:
            return False
        if current_uri in config["excluded_uris"]:
            return False

        # Ikke hopp de første 3 sekundene — la brukeren se hva som spilles
        if progress_ms < 3000:
            return False

        # Ikke hopp hvis det er under 10 sekunder igjen (sangen er nesten ferdig)
        remaining_ms = duration_ms - progress_ms
        if remaining_ms < 10_000:
            self._reset()
            return False

        # Sjekk om sang har endret seg siden sist vi begynte å telle
        if self._pending_uri and self._pending_uri != current_uri:
            logger.debug(
                "Sang endret seg fra %s til %s — resetter Smart Skipper.",
                self._pending_uri, current_uri
            )
            self._reset()

        # Hent beslutning fra algoritmen
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

        # Start nedtelling hvis ikke allerede startet
        if self._pending_uri is None:
            self._pending_uri = current_uri
            self._pending_since = time.monotonic()
            if config["dry_run"]:
                logger.info(
                    "[DRY RUN] Ville hoppet over: %s — %s (%s)",
                    current_artists, current_title, reason
                )
            else:
                logger.info(
                    "Smart Skipper: starter %d-sekunders nedtelling for '%s' (%s)",
                    config["delay_seconds"], current_title, reason
                )
            return False

        # Sjekk om delay er utløpt
        elapsed = time.monotonic() - self._pending_since
        if elapsed < config["delay_seconds"]:
            return False

        # --- Utfør hopp ---
        uri_to_skip = self._pending_uri
        self._reset()

        if config["dry_run"]:
            logger.info(
                "[DRY RUN] Ville nå ha hoppet over '%s'. "
                "Sett dry_run=FALSE for å aktivere ekte hopp.",
                current_title
            )
            return False

        logger.info(
            "Smart Skipper hopper over: %s — %s",
            current_artists, current_title
        )
        success = skip_to_next(token)

        if success:
            self._skipped_this_session.add(uri_to_skip)
            # Hent gjeldende skip-rate for logging
            row = execute(
                conn,
                "SELECT COUNT(*), SUM(CASE WHEN skipped THEN 1 ELSE 0 END) "
                "FROM plays WHERE uri = %s",
                (uri_to_skip,),
            ).fetchone()
            skip_rate = (row[1] / row[0]) if row and row[0] else 0.0

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

        return success

    def _reset(self):
        self._pending_uri = None
        self._pending_since = None


def should_auto_skip(
    conn,
    uri: str,
    context_uri: str | None,
    threshold: float = 0.85,
    min_plays: int = 3,
) -> tuple[bool, str]:
    """Enkel skip-rate-terskel (Tilnærming A). Se UTVIKLINGSPLAN.md."""
    if context_uri:
        row = execute(
            conn,
            """
            SELECT COUNT(*), SUM(CASE WHEN skipped THEN 1 ELSE 0 END)
            FROM plays WHERE uri = %s AND context_uri = %s
            """,
            (uri, context_uri),
        ).fetchone()
        if row and row[0] >= min_plays:
            rate = (row[1] or 0) / row[0]
            if rate >= threshold:
                return True, f"Kontekst-skip-rate {rate:.0%} ({row[1]}/{row[0]})"

    row = execute(
        conn,
        "SELECT COUNT(*), SUM(CASE WHEN skipped THEN 1 ELSE 0 END) "
        "FROM plays WHERE uri = %s",
        (uri,),
    ).fetchone()
    if row and row[0] >= min_plays:
        rate = (row[1] or 0) / row[0]
        if rate >= threshold:
            return True, f"Global skip-rate {rate:.0%} ({row[1]}/{row[0]})"

    return False, "Under terskel eller for lite data"


def skip_to_next(token: str, device_id: str | None = None) -> bool:
    """Sender hopp-til-neste-kommando til Spotify API."""
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
                "Mangler 'user-modify-playback-state'. Kjør setup på nytt."
            )
        else:
            logger.error("Spotify svarte %d ved hopp-forsøk.", resp.status_code)
        return False
    except requests.RequestException as exc:
        logger.error("Nettverksfeil ved hopp: %s", exc)
        return False
```

### 3.6 Integrering i tracker.py

I `tracker.py`'s polling-loop legger du til Smart Skipper som en tilstandsmaskin:

```python
# Øverst i tracker.py, etter imports:
from .smart_skipper import SmartSkipper

# I polling_loop()-funksjonen, før løkken starter:
skipper = SmartSkipper()

# Inne i løkken, etter at du har hentet nåværende avspillingsstatus:
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
```

### 3.7 Konfigurasjon og brukerinnstillinger

Legg til CLI-kommandoer for å styre Smart Skipper uten å redigere databasen manuelt:

```python
# I __main__.py

def cmd_smart_skipper(args):
    """Håndterer 'smart-skipper'-subkommandoen."""
    conn = connect()
    init_db(conn)

    if args.action == "status":
        config = load_smart_skipper_config(conn)
        print(f"Smart Skipper: {'PÅ' if config['enabled'] else 'AV'}")
        print(f"  Terskel:       {config['threshold']:.0%}")
        print(f"  Min avspill:   {config['min_plays']}")
        print(f"  Forsinkelse:   {config['delay_seconds']}s")
        print(f"  Prøvemodus:    {'JA' if config['dry_run'] else 'NEI'}")

    elif args.action == "enable":
        execute(conn, "UPDATE smart_skipper_config SET enabled=TRUE WHERE id=1")
        conn.commit()
        print("Smart Skipper aktivert.")

    elif args.action == "disable":
        execute(conn, "UPDATE smart_skipper_config SET enabled=FALSE WHERE id=1")
        conn.commit()
        print("Smart Skipper deaktivert.")

    elif args.action == "dry-run":
        val = args.value.lower() in ("on", "true", "1", "ja")
        execute(
            conn,
            "UPDATE smart_skipper_config SET dry_run=%s WHERE id=1",
            (val,)
        )
        conn.commit()
        print(f"Prøvemodus: {'PÅ' if val else 'AV'}")

    elif args.action == "threshold":
        t = float(args.value)
        if not 0.5 <= t <= 1.0:
            print("Feil: terskel må være mellom 0.50 og 1.00")
            return
        execute(
            conn,
            "UPDATE smart_skipper_config SET threshold=%s WHERE id=1",
            (t,)
        )
        conn.commit()
        print(f"Terskel satt til {t:.0%}")

    conn.close()
```

Bruk:
```bash
python3 -m spotify_skip_tracker smart-skipper status
python3 -m spotify_skip_tracker smart-skipper enable
python3 -m spotify_skip_tracker smart-skipper dry-run off
python3 -m spotify_skip_tracker smart-skipper threshold 0.90
```

### 3.8 Sikkerhetsnett og begrensninger

**Gjentatte hopp:** `SmartSkipper._skipped_this_session` holder rede på hva som allerede er hoppet automatisk i denne kjøringen. Sangen kan ikke hoppes automatisk over to ganger på rad.

**Kømusikk (Spotify-køen):** Hvis brukeren manuelt har lagt til en sang i køen, kan den komme inn som "neste sang" uavhengig av spilleliste-konteksten. Smart Skipper bør se på `context_uri` — hvis den er `null` (sangen kom fra køen, ikke fra en spilleliste), hopp ikke automatisk.

**Manuelt inngrep:** Hvis brukeren manuelt hopper over en sang under nedtellingen, vil polling-loopen fange opp ny sang ved neste poll, `_pending_uri` vil ikke stemme, og `_reset()` kalles automatisk.

**Hviteliste (ekskluderte kontekster):** Legg alltid til "Liked Songs" som en standard ekskludert kontekst i den første versjonen. Du vil ikke ha automatiske hopp der.

```python
# I smart_skipper_config, default ekskluderte kontekster:
DEFAULT_EXCLUDED = ["Liked Songs"]
```

**Grense på antall auto-hopp per time:** For å unngå at en ødelagt tilstand spammer Spotify med hopp:

```python
MAX_AUTO_SKIPS_PER_HOUR = 10

# I SmartSkipper.__init__:
self._skip_timestamps: list[float] = []

# I SmartSkipper.evaluate, før hopp:
now = time.monotonic()
recent = [t for t in self._skip_timestamps if now - t < 3600]
if len(recent) >= MAX_AUTO_SKIPS_PER_HOUR:
    logger.warning(
        "Nådd maksimumsgrense på %d auto-hopp per time. Pause.",
        MAX_AUTO_SKIPS_PER_HOUR
    )
    return False
self._skip_timestamps = recent
```

### 3.9 Frontend-integrasjon

Legg til en ny API-rute i `web.py` for Smart Skipper-status og historikk:

```python
@app.route("/api/smart-skipper")
def api_smart_skipper():
    """Henter konfigurasjon og siste 20 auto-hopp."""
    with pooled_connection() as conn:
        config_row = execute(
            conn,
            "SELECT enabled, threshold, min_plays, delay_seconds, dry_run "
            "FROM smart_skipper_config WHERE id = 1"
        ).fetchone()

        history = execute(
            conn,
            """
            SELECT title, artists, skip_rate, reason, timestamp, undone
            FROM auto_skips
            ORDER BY timestamp DESC
            LIMIT 20
            """
        ).fetchall()

    return jsonify({
        "config": {
            "enabled": config_row[0],
            "threshold": config_row[1],
            "min_plays": config_row[2],
            "delay_seconds": config_row[3],
            "dry_run": config_row[4],
        },
        "history": [
            {
                "title": r[0],
                "artists": r[1],
                "skip_rate": r[2],
                "reason": r[3],
                "timestamp": r[4].isoformat(),
                "undone": r[5],
            }
            for r in history
        ],
    })
```

I React-dashbordet kan du legge til en `SmartSkipperPanel`-komponent som viser:
- En på/av-bryter (toggle) med tydelig fargekoding (grønn = aktiv, rød = prøvemodus)
- Terskel-slider (0.50 til 1.00)
- En tidslinje over de siste auto-hoppene med sang, artist, skip-rate og tidspunkt
- En "angre"-knapp for hvert hopp (se Playlist Janitor for lignende mønster)

### 3.9 Testing

Enhetstestene for Smart Skipper kan skrives uten databasetilkobling ved å mocke `execute`:

```python
# tests/test_smart_skipper.py

import pytest
from unittest.mock import MagicMock
from spotify_skip_tracker.smart_skipper import should_auto_skip, SmartSkipper

def make_conn(play_count, skip_count):
    """Lager en falsk databasetilkobling med forhåndsdefinerte data."""
    cursor = MagicMock()
    cursor.fetchone.return_value = (play_count, skip_count)
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn

def test_under_terskel_hopper_ikke():
    conn = make_conn(play_count=10, skip_count=7)  # 70% rate
    should, reason = should_auto_skip(conn, "uri:123", None, threshold=0.85)
    assert not should

def test_over_terskel_hopper():
    conn = make_conn(play_count=10, skip_count=9)  # 90% rate
    should, reason = should_auto_skip(conn, "uri:123", None, threshold=0.85)
    assert should
    assert "90%" in reason

def test_for_lite_data_hopper_ikke():
    conn = make_conn(play_count=2, skip_count=2)  # 100% rate men bare 2 avspill
    should, _ = should_auto_skip(conn, "uri:123", None, min_plays=3)
    assert not should

def test_reset_ved_sangsbytte():
    skipper = SmartSkipper()
    skipper._pending_uri = "uri:gammel"
    skipper._pending_since = 0.0
    # Evaluer med ny sang — skal resette
    # (fullstendig test krever database-mock)
```

---

## 4. Playlist Janitor — Automatisk opprydding

### 4.1 Hva er Playlist Janitor?

Playlist Janitor analyserer spillelistene dine og foreslår (eller utfører automatisk, hvis konfigurert) fjerning av sanger du konsekvent hopper over. Målet er å holde spillelistene "rene" og tilpasset din nåværende smak.

**Viktig distinksjon:** Playlist Janitor jobber bare mot *spillelister du eier*. Den kan aldri fjerne sanger fra andres spillelister, Spotify Radio, Discover Weekly, eller lignende.

**Eksempel på brukstilfelle:**  
Du har en spilleliste kalt "Morning Jog" med 80 sanger. 12 av disse har du hoppet over mer enn 5 ganger uten å høre ferdig. Playlist Janitor lager en liste: "Disse 12 sangene virker ikke å passe i 'Morning Jog'. Vil du fjerne dem?" Du godkjenner, og de fjernes fra spillelisten (men ikke fra Spotify eller andre spillelister).

### 4.2 Spotify API-endepunkter

#### Hent brukerens spillelister
```
GET https://api.spotify.com/v1/me/playlists?limit=50
Authorization: Bearer {access_token}
```

Returnerer paginert liste. Håndter `next`-feltet for å hente alle sider:

```python
def get_all_my_playlists(token: str) -> list[dict]:
    """
    Henter alle spillelister brukeren eier (ikke bare følger).
    Filtrerer ut spillelister eid av andre.
    """
    user_resp = requests.get(
        "https://api.spotify.com/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    user_id = user_resp.json()["id"]

    playlists = []
    url = "https://api.spotify.com/v1/me/playlists?limit=50"

    while url:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        for pl in data["items"]:
            # Filtrer: kun spillelister brukeren selv eier
            if pl["owner"]["id"] == user_id:
                playlists.append({
                    "id": pl["id"],
                    "name": pl["name"],
                    "total_tracks": pl["tracks"]["total"],
                    "uri": pl["uri"],
                })

        url = data.get("next")  # None når vi er på siste side

    return playlists
```

#### Hent sanger i en spilleliste
```
GET https://api.spotify.com/v1/playlists/{playlist_id}/tracks?limit=100
Authorization: Bearer {access_token}
```

```python
def get_playlist_tracks(token: str, playlist_id: str) -> list[dict]:
    """Henter alle spor i en spilleliste (håndterer paginering)."""
    tracks = []
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks?limit=100"

    while url:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        for item in data["items"]:
            track = item.get("track")
            if not track or track.get("type") != "track":
                continue  # hopp over podcoder og lokale filer
            tracks.append({
                "uri": track["uri"],
                "name": track["name"],
                "artists": ", ".join(a["name"] for a in track["artists"]),
            })

        url = data.get("next")

    return tracks
```

#### Fjern sanger fra en spilleliste
```
DELETE https://api.spotify.com/v1/playlists/{playlist_id}/tracks
Authorization: Bearer {access_token}
Content-Type: application/json

Body:
{
  "tracks": [
    {"uri": "spotify:track:abc123"},
    {"uri": "spotify:track:def456"}
  ]
}
```

Maks 100 sanger per kall. Returnerer `200 OK` med en `snapshot_id`.

```python
def remove_tracks_from_playlist(
    token: str,
    playlist_id: str,
    track_uris: list[str],
) -> str | None:
    """
    Fjerner sanger fra en spilleliste.
    Returnerer snapshot_id (brukes til angring), eller None ved feil.

    Maks 100 URIer per kall — splitter automatisk i batcher.
    """
    snapshot_id = None
    batch_size = 100

    for i in range(0, len(track_uris), batch_size):
        batch = track_uris[i : i + batch_size]
        resp = requests.delete(
            f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"tracks": [{"uri": uri} for uri in batch]},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.error(
                "Feil ved fjerning fra spilleliste %s: %d %s",
                playlist_id, resp.status_code, resp.text
            )
            return None
        snapshot_id = resp.json().get("snapshot_id")

    return snapshot_id
```

> **Om `snapshot_id`:** Spotify returnerer en `snapshot_id` etter hvert kall som endrer en spilleliste. Denne IDen representerer en bestemt versjon av spillelisten og kan brukes til å gjenopprette tidligere tilstander. Lagre den alltid i databasen!

#### Legg til sanger på nytt (angring)
```
POST https://api.spotify.com/v1/playlists/{playlist_id}/tracks
Authorization: Bearer {access_token}

Body: {"uris": ["spotify:track:abc123"], "position": 0}
```

### 4.3 Kandidatidentifikasjon og rangering

#### Janitering-score

Hver sang i en spilleliste får en "janitering-score" — et tall mellom 0 og 1 som representerer sannsynligheten for at sangen bør fjernes. En score på 1.0 betyr "fjern denne nå", 0.0 betyr "behold".

```python
def calculate_janitor_score(
    skip_count: int,
    play_count: int,
    last_completed: datetime | None,
    days_in_playlist: int,
) -> float:
    """
    Beregner janitering-score for en sang i en spilleliste.

    Komponenter (vektet sum):
    - Skip-rate (40%): høy skip-rate → høy score
    - Konsistens (30%): hvis du ALDRI hører ferdig → maks poeng
    - Alder siden sist fullførte (20%): lenge siden = høyere score
    - Antall avspillinger (10%): mer data = mer pålitelig score

    Returnerer float mellom 0.0 og 1.0.
    """
    if play_count == 0:
        return 0.0  # ingen data, ikke foreslå fjerning

    skip_rate = skip_count / play_count

    # Komponent 1: Skip-rate (0–1)
    skip_component = skip_rate

    # Komponent 2: Konsistens — aldri fullførte = 1.0, alltid fullført = 0.0
    completed_count = play_count - skip_count
    consistency_component = 1.0 - (completed_count / play_count)

    # Komponent 3: Tid siden sist fullførte (maks 1.0 etter 180 dager)
    if last_completed is None:
        recency_component = 1.0
    else:
        days_since = (datetime.now(tz=timezone.utc) - last_completed).days
        recency_component = min(1.0, days_since / 180)

    # Komponent 4: Datapålitelighet (minst 3 avspillinger = 1.0)
    reliability = min(1.0, play_count / 3)

    score = (
        0.40 * skip_component
        + 0.30 * consistency_component
        + 0.20 * recency_component
        + 0.10 * reliability
    )

    return round(score, 4)
```

#### Hent kandidater for en spilleliste

```python
def get_janitor_candidates(
    conn,
    playlist_id: str,
    track_uris: list[str],
    min_score: float = 0.70,
    min_plays: int = 3,
) -> list[dict]:
    """
    Returnerer sanger i spillelisten som har høy nok janitering-score
    til å bli foreslått for fjerning.

    Sortert etter score (høyest først).
    """
    candidates = []
    uri_placeholders = ",".join(["%s"] * len(track_uris))

    rows = execute(
        conn,
        f"""
        SELECT
            uri,
            MAX(title)                                              AS title,
            MAX(artists)                                            AS artists,
            COUNT(*)                                                AS play_count,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END)               AS skip_count,
            MAX(CASE WHEN NOT skipped THEN timestamp END)           AS last_completed,
            MIN(timestamp)                                          AS first_seen
        FROM plays
        WHERE uri IN ({uri_placeholders})
          AND context_uri = %s
        GROUP BY uri
        HAVING COUNT(*) >= %s
        """,
        (*track_uris, f"spotify:playlist:{playlist_id}", min_plays),
    ).fetchall()

    for uri, title, artists, play_count, skip_count, last_completed, first_seen in rows:
        if first_seen:
            days_in_playlist = (datetime.now(tz=timezone.utc) - first_seen).days
        else:
            days_in_playlist = 0

        score = calculate_janitor_score(
            skip_count=int(skip_count),
            play_count=int(play_count),
            last_completed=last_completed,
            days_in_playlist=days_in_playlist,
        )

        if score >= min_score:
            candidates.append({
                "uri": uri,
                "title": title,
                "artists": artists,
                "play_count": int(play_count),
                "skip_count": int(skip_count),
                "skip_rate": skip_count / play_count,
                "last_completed": last_completed.isoformat() if last_completed else None,
                "score": score,
            })

    return sorted(candidates, key=lambda x: x["score"], reverse=True)
```

### 4.4 Databaseendringer

```sql
-- Foreslåtte fjerninger (venter på brukerbekreftelse)
CREATE TABLE IF NOT EXISTS janitor_suggestions (
    id              SERIAL PRIMARY KEY,
    playlist_id     TEXT NOT NULL,
    playlist_name   TEXT,
    uri             TEXT NOT NULL,
    title           TEXT,
    artists         TEXT,
    skip_rate       REAL NOT NULL,
    janitor_score   REAL NOT NULL,
    suggested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          TEXT NOT NULL DEFAULT 'pending',
    -- status: 'pending', 'approved', 'rejected', 'removed', 'undone'
    acted_at        TIMESTAMPTZ,
    snapshot_id     TEXT  -- Spotify snapshot_id etter fjerning (for angring)
);

-- Audit-logg over faktiske fjerninger
CREATE TABLE IF NOT EXISTS janitor_removals (
    id              SERIAL PRIMARY KEY,
    suggestion_id   INTEGER REFERENCES janitor_suggestions(id),
    playlist_id     TEXT NOT NULL,
    playlist_name   TEXT,
    uri             TEXT NOT NULL,
    title           TEXT,
    artists         TEXT,
    removed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    snapshot_id     TEXT NOT NULL,
    undone          BOOLEAN NOT NULL DEFAULT FALSE,
    undone_at       TIMESTAMPTZ
);
```

### 4.5 Python-implementasjon

Opprett `spotify_skip_tracker/janitor.py`:

```python
"""
Playlist Janitor — analyserer og rydder spillelister basert på skip-historikk.

Kan kjøres manuelt via CLI eller periodisk (f.eks. ukentlig).
Støtter alltid en "preview"-modus som viser forslag uten å gjøre endringer.
"""

import logging
from datetime import datetime, timezone

from .database import connect, execute, init_db
from .spotify_api import get_access_token, load_creds
from .janitor_helpers import (
    get_all_my_playlists,
    get_playlist_tracks,
    get_janitor_candidates,
    remove_tracks_from_playlist,
    calculate_janitor_score,
)

logger = logging.getLogger(__name__)


def run_janitor(
    playlist_filter: str | None = None,
    min_score: float = 0.70,
    min_plays: int = 3,
    dry_run: bool = True,
    auto_approve: bool = False,
) -> dict:
    """
    Hovedfunksjon for Playlist Janitor.

    Args:
        playlist_filter: Navn eller del av navn på spilleliste å analysere.
                         None = alle spillelister.
        min_score:       Minimum janitering-score (0–1) for å foreslå fjerning.
        min_plays:       Minimum antall avspillinger for å vurdere en sang.
        dry_run:         Hvis True, gjør ingenting — vis bare forslag.
        auto_approve:    Hvis True, fjern automatisk uten å be om bekreftelse.
                         KREVER dry_run=False.

    Returnerer:
        dict med 'playlists' (liste av analyser) og 'total_candidates' (antall)
    """
    creds = load_creds()
    token = get_access_token(creds)
    conn = connect()
    init_db(conn)

    playlists = get_all_my_playlists(token)

    if playlist_filter:
        playlists = [
            p for p in playlists
            if playlist_filter.lower() in p["name"].lower()
        ]
        if not playlists:
            logger.warning("Ingen spillelister matchet '%s'.", playlist_filter)
            conn.close()
            return {"playlists": [], "total_candidates": 0}

    logger.info(
        "Analyserer %d spilleliste(r)%s…",
        len(playlists),
        " [DRY RUN]" if dry_run else ""
    )

    results = []
    total_candidates = 0

    for playlist in playlists:
        logger.info("  → %s (%d spor)", playlist["name"], playlist["total_tracks"])

        tracks = get_playlist_tracks(token, playlist["id"])
        if not tracks:
            continue

        track_uris = [t["uri"] for t in tracks]
        candidates = get_janitor_candidates(
            conn,
            playlist_id=playlist["id"],
            track_uris=track_uris,
            min_score=min_score,
            min_plays=min_plays,
        )

        if not candidates:
            logger.info("    Ingen kandidater funnet.")
            results.append({
                "playlist": playlist,
                "candidates": [],
                "removed": [],
            })
            continue

        logger.info("    Fant %d kandidat(er):", len(candidates))
        for c in candidates:
            logger.info(
                "      [%.2f] %s — %s (skip %d/%d)",
                c["score"], c["artists"], c["title"],
                c["skip_count"], c["play_count"]
            )

        total_candidates += len(candidates)

        # Lagre forslag i databasen
        for c in candidates:
            _upsert_suggestion(conn, playlist, c)

        removed = []

        if not dry_run and auto_approve:
            uris_to_remove = [c["uri"] for c in candidates]
            snapshot_id = remove_tracks_from_playlist(
                token, playlist["id"], uris_to_remove
            )
            if snapshot_id:
                removed = candidates
                for c in candidates:
                    _mark_removed(conn, playlist, c, snapshot_id)
                logger.info(
                    "    Fjernet %d sang(er) fra '%s'.",
                    len(removed), playlist["name"]
                )

        results.append({
            "playlist": playlist,
            "candidates": candidates,
            "removed": removed,
        })

    conn.close()
    return {"playlists": results, "total_candidates": total_candidates}


def undo_removal(removal_id: int) -> bool:
    """
    Angrer en tidligere fjerning ved å legge sangen tilbake i spillelisten.
    Bruker Spotify API's POST /playlists/{id}/tracks.

    Returnerer True ved suksess.
    """
    creds = load_creds()
    token = get_access_token(creds)
    conn = connect()

    row = execute(
        conn,
        """
        SELECT jr.playlist_id, jr.uri, jr.title, jr.artists, jr.undone
        FROM janitor_removals jr
        WHERE jr.id = %s
        """,
        (removal_id,),
    ).fetchone()

    if not row:
        logger.error("Fjerning med id %d ikke funnet.", removal_id)
        conn.close()
        return False

    playlist_id, uri, title, artists, already_undone = row

    if already_undone:
        logger.warning("Fjerning %d er allerede angret.", removal_id)
        conn.close()
        return False

    resp = requests.post(
        f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"uris": [uri]},
        timeout=15,
    )

    if resp.status_code == 201:
        execute(
            conn,
            """
            UPDATE janitor_removals
            SET undone=TRUE, undone_at=NOW()
            WHERE id=%s
            """,
            (removal_id,),
        )
        conn.commit()
        logger.info("Angret fjerning av '%s' — %s.", artists, title)
        conn.close()
        return True

    logger.error(
        "Kunne ikke legge '%s' tilbake: %d %s",
        title, resp.status_code, resp.text
    )
    conn.close()
    return False


def _upsert_suggestion(conn, playlist: dict, candidate: dict) -> None:
    execute(
        conn,
        """
        INSERT INTO janitor_suggestions
            (playlist_id, playlist_name, uri, title, artists,
             skip_rate, janitor_score)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (
            playlist["id"], playlist["name"],
            candidate["uri"], candidate["title"], candidate["artists"],
            candidate["skip_rate"], candidate["score"],
        ),
    )
    conn.commit()


def _mark_removed(conn, playlist: dict, candidate: dict, snapshot_id: str) -> None:
    execute(
        conn,
        """
        INSERT INTO janitor_removals
            (playlist_id, playlist_name, uri, title, artists, snapshot_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            playlist["id"], playlist["name"],
            candidate["uri"], candidate["title"], candidate["artists"],
            snapshot_id,
        ),
    )
    conn.commit()
```

### 4.6 CLI-kommandoer for Playlist Janitor

Legg til i `__main__.py`:

```python
# Analyser alle spillelister (prøvemodus — ingen endringer)
python3 -m spotify_skip_tracker janitor

# Analyser kun én spilleliste
python3 -m spotify_skip_tracker janitor --playlist "Morning Jog"

# Sett lavere terskel (70% score i stedet for standard 80%)
python3 -m spotify_skip_tracker janitor --min-score 0.70

# Krev minimum 5 avspillinger (standard 3) — mer konservativt
python3 -m spotify_skip_tracker janitor --min-plays 5

# Faktisk fjerning med bekreftelsesprompt
python3 -m spotify_skip_tracker janitor --no-dry-run

# Fullautomatisk fjerning uten bekreftelse (farlig — bruk med forsiktighet)
python3 -m spotify_skip_tracker janitor --no-dry-run --auto-approve

# Angre siste fjerning
python3 -m spotify_skip_tracker janitor --undo 42
```

### 4.7 Godkjenningsflyt og brukerbekreftelse

For interaktiv modus (uten `--auto-approve`) vises en oppsummeringstabell og brukeren bekrefter:

```python
def interactive_confirm(candidates_by_playlist: list[dict]) -> list[tuple[str, str]]:
    """
    Viser forslag og ber brukeren velge hvilke som skal fjernes.
    Returnerer liste av (playlist_id, track_uri) som skal fjernes.
    """
    approved = []

    for entry in candidates_by_playlist:
        playlist = entry["playlist"]
        candidates = entry["candidates"]

        if not candidates:
            continue

        print(f"\n{'═' * 60}")
        print(f"  Spilleliste: {playlist['name']}")
        print(f"{'═' * 60}")
        print(f"  {'#':<3} {'Score':<7} {'Skip-rate':<10} {'Sang':<35} {'Artist'}")
        print(f"  {'-' * 75}")

        for i, c in enumerate(candidates, 1):
            print(
                f"  {i:<3} {c['score']:.2f}   "
                f"{c['skip_rate']:.0%}        "
                f"{c['title'][:33]:<35} {c['artists'][:30]}"
            )

        print()
        answer = input(
            f"  Fjern alle {len(candidates)} sanger fra '{playlist['name']}'? "
            "[j/n/velg] "
        ).strip().lower()

        if answer == "j":
            approved.extend(
                (playlist["id"], c["uri"]) for c in candidates
            )
        elif answer == "velg":
            nums = input(
                "  Skriv nummerne du vil fjerne, kommaseparert (f.eks. 1,3,5): "
            )
            selected = [int(x.strip()) - 1 for x in nums.split(",") if x.strip().isdigit()]
            for idx in selected:
                if 0 <= idx < len(candidates):
                    approved.append((playlist["id"], candidates[idx]["uri"]))

    return approved
```

### 4.8 Frontend-integrasjon

Playlist Janitor egner seg godt som en egen side eller modal i dashbordet. Forslag-visning:

```
┌─────────────────────────────────────────────────────────────┐
│  Playlist Janitor                              [Kjør analyse]│
├─────────────────────────────────────────────────────────────┤
│  Morning Jog (3 forslag)                                     │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Blinding Lights — The Weeknd                         │  │
│  │  Skip-rate: 91%  |  Score: 0.87  |  12/13 avspill    │  │
│  │  [Fjern fra spilleliste]  [Ignorer]                   │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │  Anti-Hero — Taylor Swift                             │  │
│  │  Skip-rate: 85%  |  Score: 0.81  |  7/8 avspill      │  │
│  │  [Fjern fra spilleliste]  [Ignorer]                   │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

API-rute for frontend:

```python
@app.route("/api/janitor/suggestions")
def api_janitor_suggestions():
    """Returnerer gjeldende forslag fra Playlist Janitor."""
    with pooled_connection() as conn:
        rows = execute(
            conn,
            """
            SELECT
                js.id, js.playlist_name, js.title, js.artists,
                js.skip_rate, js.janitor_score, js.suggested_at, js.status
            FROM janitor_suggestions js
            WHERE js.status IN ('pending', 'rejected')
            ORDER BY js.janitor_score DESC, js.playlist_name
            LIMIT 50
            """
        ).fetchall()

    return jsonify([
        {
            "id": r[0],
            "playlist_name": r[1],
            "title": r[2],
            "artists": r[3],
            "skip_rate": r[4],
            "score": r[5],
            "suggested_at": r[6].isoformat(),
            "status": r[7],
        }
        for r in rows
    ])


@app.route("/api/janitor/approve/<int:suggestion_id>", methods=["POST"])
def api_janitor_approve(suggestion_id: int):
    """Godkjenner ett forslag og fjerner sangen fra spillelisten."""
    # Hent legitimasjon og utfør fjerning via Spotify API
    # Oppdater janitor_suggestions.status = 'removed'
    # Opprett rad i janitor_removals med snapshot_id
    ...


@app.route("/api/janitor/undo/<int:removal_id>", methods=["POST"])
def api_janitor_undo(removal_id: int):
    """Angrer en fjerning ved å legge sangen tilbake."""
    success = undo_removal(removal_id)
    return jsonify({"success": success})
```

### 4.8 Testing og sikkerhetsnett

**Aldri kjør mot produksjonsspillelister under utvikling.** Opprett en dedikert testspilleliste i Spotify kalt "Janitor Test" og bruk alltid `--playlist "Janitor Test"` under testing.

```python
# tests/test_janitor.py

def test_janitor_score_høy_skiprate():
    score = calculate_janitor_score(
        skip_count=9, play_count=10,
        last_completed=None,  # aldri fullført
        days_in_playlist=60,
    )
    assert score >= 0.85, f"Forventet høy score, fikk {score}"

def test_janitor_score_lav_skiprate():
    score = calculate_janitor_score(
        skip_count=1, play_count=10,
        last_completed=datetime.now(tz=timezone.utc),
        days_in_playlist=30,
    )
    assert score < 0.30, f"Forventet lav score, fikk {score}"

def test_janitor_score_ingen_data():
    score = calculate_janitor_score(
        skip_count=0, play_count=0,
        last_completed=None,
        days_in_playlist=0,
    )
    assert score == 0.0

def test_janitor_score_nylig_fullfort():
    """En sang du fullførte i går bør ikke fjernes."""
    from datetime import timedelta
    yesterday = datetime.now(tz=timezone.utc) - timedelta(days=1)
    score = calculate_janitor_score(
        skip_count=5, play_count=8,
        last_completed=yesterday,
        days_in_playlist=90,
    )
    # Nylig fullføring trekker ned scoren selv med 62% skip-rate
    assert score < 0.60
```

**Snapshot-basert angring:** Spotify's `snapshot_id` gir deg en eksakt versjon av spillelisten. Lagre denne etter hvert kall. Angring legger bare sangen til på nytt (ikke nødvendigvis samme posisjon), men det er godt nok for de fleste brukstilfeller.

---

## 5. Felles infrastruktur

### 5.1 OAuth-scope-utvidelse

Legg til denne migrasjonssjekken i `spotify_api.py` for å varsle brukeren når scopet er for smalt:

```python
def check_scope(token: str, required_scopes: list[str]) -> list[str]:
    """
    Sjekker om access-tokenet har de nødvendige scope-tillatelsene.
    Returnerer liste over manglende scope (tom liste = alt OK).
    """
    resp = requests.get(
        "https://api.spotify.com/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    # Spotify legger ikke scope direkte i /me-responsen,
    # men vi kan teste via et faktisk endepunkt:
    test_resp = requests.put(
        "https://api.spotify.com/v1/me/player/shuffle?state=false",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if test_resp.status_code == 403:
        return ["user-modify-playback-state"]
    return []
```

### 5.2 Rate limiting og køsystem

Når Playlist Janitor og Smart Skipper kjører samtidig med tracker-loopen, kan API-kall hope seg opp. Implementer et enkelt token-bucket-system:

```python
import threading
import time


class TokenBucket:
    """
    Enkel token-bucket for Spotify API rate limiting.
    Standard: 180 tokens (kall) per 30 sekunder.
    """

    def __init__(self, capacity: int = 180, refill_rate: float = 6.0):
        # refill_rate: tokens per sekund
        self.capacity = capacity
        self.tokens = float(capacity)
        self.refill_rate = refill_rate
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, tokens: int = 1, block: bool = True) -> bool:
        """
        Forbruker tokens fra bøtten.
        Hvis block=True, venter til tokens er tilgjengelig.
        Returnerer True hvis vellykket.
        """
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            if not block:
                return False

        # Vent og prøv igjen
        wait_time = (tokens - self.tokens) / self.refill_rate
        time.sleep(wait_time)
        return self.consume(tokens, block=True)

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now


# Global instans (importeres av tracker.py, smart_skipper.py og janitor.py)
spotify_rate_limiter = TokenBucket()
```

### 5.3 Audit-logg

Begge funksjonene skriver til audit-tabeller (`auto_skips` og `janitor_removals`). Legg til en felles visning i `stats.py`:

```python
def get_action_log(conn, limit: int = 50) -> list[dict]:
    """
    Henter en kombinert logg over alle automatiske handlinger
    (Smart Skipper-hopp og Playlist Janitor-fjerninger),
    sortert etter tidspunkt (nyeste først).
    """
    rows = execute(
        conn,
        """
        SELECT
            'auto_skip'     AS type,
            title, artists, reason AS detail,
            timestamp, undone
        FROM auto_skips

        UNION ALL

        SELECT
            'janitor'       AS type,
            title, artists,
            playlist_name   AS detail,
            removed_at      AS timestamp,
            undone
        FROM janitor_removals

        ORDER BY timestamp DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()

    return [
        {
            "type": r[0],
            "title": r[1],
            "artists": r[2],
            "detail": r[3],
            "timestamp": r[4].isoformat(),
            "undone": r[5],
        }
        for r in rows
    ]
```

---

## 6. Deployment og konfigurasjon på Railway

### Miljøvariabler som må legges til på Railway

Når Smart Skipper og Playlist Janitor er implementert, legg til disse miljøvariablene i Railway-dashbordet:

```
SMART_SKIPPER_ENABLED=false
SMART_SKIPPER_THRESHOLD=0.85
SMART_SKIPPER_MIN_PLAYS=3
SMART_SKIPPER_DELAY_SECONDS=5
SMART_SKIPPER_DRY_RUN=true

JANITOR_ENABLED=false
JANITOR_MIN_SCORE=0.70
JANITOR_MIN_PLAYS=3
JANITOR_AUTO_APPROVE=false
```

### Periodisk kjøring av Playlist Janitor (cron-lignende)

Siden Railway kjører en enkelt prosess uten innebygd cron, kan du implementere ukentlig Janitor-kjøring direkte i `server.py`:

```python
import threading
import time
from datetime import datetime, timezone

def _janitor_scheduler():
    """
    Kjører Playlist Janitor ukentlig (søndag kl. 02:00 Oslo-tid).
    Kjøres som en daemon-tråd fra server.py.
    """
    import pytz
    oslo = pytz.timezone("Europe/Oslo")

    while True:
        now = datetime.now(tz=oslo)
        # Kjør søndager kl. 02:00–02:07
        if now.weekday() == 6 and now.hour == 2 and now.minute < 7:
            logger.info("Starter ukentlig Playlist Janitor-kjøring…")
            try:
                from spotify_skip_tracker.janitor import run_janitor
                results = run_janitor(
                    dry_run=os.environ.get("JANITOR_DRY_RUN", "true").lower() == "true",
                    auto_approve=os.environ.get("JANITOR_AUTO_APPROVE", "false").lower() == "true",
                    min_score=float(os.environ.get("JANITOR_MIN_SCORE", "0.70")),
                    min_plays=int(os.environ.get("JANITOR_MIN_PLAYS", "3")),
                )
                logger.info(
                    "Janitor ferdig. Totalt %d kandidater funnet.",
                    results["total_candidates"]
                )
            except Exception as exc:
                logger.error("Janitor-kjøring feilet: %s", exc)
            time.sleep(600)  # sov 10 min etter kjøring for å unngå dobbelkjøring
        else:
            time.sleep(60)  # sjekk hvert minutt


# I server.py, legg til:
threading.Thread(target=_janitor_scheduler, daemon=True).start()
```

---

## 7. Anbefalt utviklingsrekkefølge

Følg denne rekkefølgen for å minimere risiko og maksimere nytten av tidlig testing:

### Fase A — Grunnlag (1–2 dager)
1. Oppdater OAuth-scope og kjør `setup` på nytt
2. Legg til `_migrate_smart_skipper()` og `_migrate_janitor()` i `init_db()`
3. Verifiser at migrasjoner kjøres uten feil (sjekk at tabellene opprettes)
4. Skriv og kjør enhetstester for `should_auto_skip()` og `calculate_janitor_score()`

### Fase B — Smart Skipper, prøvemodus (3–5 dager)
5. Implementer `smart_skipper.py` med `should_auto_skip()` og `SmartSkipper`-klassen
6. Integrer i `tracker.py` (kun prøvemodus — ingen faktiske hopp ennå)
7. Observer loggene i 3–5 dager: ville Smart Skipper ha hoppet over riktige sanger?
8. Juster terskel og min_plays basert på observasjoner

### Fase C — Smart Skipper, aktiv modus (1–2 dager)
9. Sett `dry_run=False` og `enabled=True` i databasen
10. Observer aktive hopp i en uke
11. Legg til frontend-panel med historikk og on/off-bryter

### Fase D — Playlist Janitor, analyse (2–3 dager)
12. Implementer `janitor.py` med `run_janitor()` og `get_janitor_candidates()`
13. Kjør analyse-modus (`dry_run=True`) og verifiser forslagene
14. Gjennomgå forslagene manuelt — stemmer de med din intuisjon?

### Fase E — Playlist Janitor, aktiv fjerning (2–3 dager)
15. Test fjerning mot en dedikert testspilleliste
16. Implementer angre-funksjonalitet og verifiser at den fungerer
17. Legg til frontend-panel med forslag, godkjenning og angring

### Fase F — Produksjon og overvåking (løpende)
18. Aktiver på Railway med konservative innstillinger
19. Overvåk audit-logg ukentlig
20. Juster innstillinger basert på erfaring

---

*Dette dokumentet er ment som en levende guide. Oppdater det etter hvert som implementasjonen skrider frem og nye innsikter oppstår. Lykke til!*

---

## 8. Fase G — Musikkcoach og Avansert Innsikt (Insights)

Fase G tar skip-trackeren fra et loggverktøy til en aktiv musikkcoach. Ved å analysere mønstre på tvers av tid, kontekst og lydegenskaper kan systemet gi brukeren presis, personlig innsikt om egne lyttevaner — og bruke disse innsiktene til å gjøre Smart Skipper enda smartere i sanntid.

### 8.1 Utålmodighets-modus (Sequential Skips)

**Konsept:**  
Forskning på musikklytting viser at skip-atferd er sterkt sekvensavhengig: en bruker som har hoppet over de siste 2–3 sangene på rad befinner seg i en "utålmodig tilstand" der sannsynligheten for neste hopp er betydelig høyere enn baseline-raten. Denne observasjonen, kjent fra *Sequential Skip Prediction*-forskning (Brost et al., Spotify Research 2019), utnyttes her til dynamisk terskel-justering i Smart Skipper.

**Implementasjon i `tracker.py` og `smart_skipper.py`:**

Polling-loopen holder allerede rede på rekkefølgen av avspillinger i inneværende sesjon. Utvid `SmartSkipper`-klassen med en sekvensielt skip-teller:

```python
# I SmartSkipper.__init__:
self._recent_outcomes: list[bool] = []   # True = skippet, False = fullført
self._impatience_active: bool = False

# Konstanter:
IMPATIENCE_WINDOW = 3         # vurder de siste N sangene
IMPATIENCE_SKIP_THRESHOLD = 2 # minst X av N må være skippet
IMPATIENCE_FACTOR = 0.85      # reduser terskel med denne faktoren
```

Når en sang avsluttes (enten ved skip eller fullføring), registreres utfallet:

```python
def record_outcome(self, skipped: bool) -> None:
    """
    Registrerer utfall for sist avsluttede sang og oppdaterer
    utålmodighets-tilstanden for inneværende sesjon.

    Kalles av polling-loopen i tracker.py umiddelbart etter at
    log_play() har skrevet til databasen, mens forrige sang
    fortsatt er tilgjengelig i lokalt minne.
    """
    self._recent_outcomes.append(skipped)
    # Behold bare de siste N utfallene
    if len(self._recent_outcomes) > IMPATIENCE_WINDOW:
        self._recent_outcomes.pop(0)

    recent_skips = sum(self._recent_outcomes)
    was_impatient = self._impatience_active
    self._impatience_active = (
        len(self._recent_outcomes) >= IMPATIENCE_WINDOW
        and recent_skips >= IMPATIENCE_SKIP_THRESHOLD
    )

    if self._impatience_active and not was_impatient:
        logger.info(
            "Utålmodighets-modus aktivert: %d av %d siste sanger skippet.",
            recent_skips, len(self._recent_outcomes)
        )
    elif not self._impatience_active and was_impatient:
        logger.info("Utålmodighets-modus deaktivert.")
```

I `evaluate()`-metoden justeres terskelen dynamisk dersom utålmodighets-modus er aktiv:

```python
# I SmartSkipper.evaluate(), etter at config er lastet:
effective_threshold = config["threshold"]
if self._impatience_active:
    effective_threshold = config["threshold"] * IMPATIENCE_FACTOR
    logger.debug(
        "Utålmodighets-modus aktiv — terskel senket fra %.0f%% til %.0f%%.",
        config["threshold"] * 100, effective_threshold * 100
    )

# Bruk effective_threshold i stedet for config["threshold"] videre:
should_skip, reason = should_auto_skip(
    conn,
    uri=current_uri,
    context_uri=context_uri,
    threshold=effective_threshold,
    min_plays=config["min_plays"],
)
if should_skip and self._impatience_active:
    reason += " [utålmodighets-boost]"
```

**Databasekolonne for sesjonssporing:**

For å persistere utålmodighets-hendelser (nyttig for innsikt-visninger i frontend), legg til en kolonne i `auto_skips`:

```sql
ALTER TABLE auto_skips
    ADD COLUMN IF NOT EXISTS impatience_active BOOLEAN NOT NULL DEFAULT FALSE;
```

**Integrasjon med `tracker.py`:**

`record_outcome()` kalles fra polling-loopen like etter at `log_play()` er fullført, med det som ble logget for *forrige* sang:

```python
# I polling_loop(), etter at en ny sang er oppdaget og forrige er logget:
skipper.record_outcome(skipped=was_skipped)
```

### 8.2 Tids- og kontekstanalyser

**Konsept:**  
Brukere har sterkt tidsmønstrede lyttevaner. Systemet skal beregne statistikk som kan presenteres i dashbordet som meningsfulle setninger fremfor rå tall: "Du skipper 43% mer etter kl. 22:00" eller "Mandager er din mest utålmodige dag."

**Statistikk-modul i `stats.py`:**

Legg til en dedikert funksjon `compute_insight_stats()` som beregner alle innsikter i én databaserunde:

```python
def compute_insight_stats(conn) -> dict:
    """
    Beregner avanserte tids- og kontekstbaserte innsikter for dashboard.

    Returnerer en dict med nøklene:
        - hourly_skip_delta:  skip-rate per time relativt til dagsgjennomsnittet
        - weekday_skip_rate:  skip-rate per ukedag (0=mandag, 6=søndag)
        - most_impatient_day: ukedag med høyest skip-rate
        - night_vs_day_delta: prosentforskjell i skip-rate kl. 22–06 vs. 07–21
        - top_skipped_hour:   timen med høyest skip-rate (0–23)
    """
    # --- Timesbasert skip-rate ---
    hourly_rows = execute(
        conn,
        """
        SELECT
            EXTRACT(HOUR FROM timestamp AT TIME ZONE 'Europe/Oslo')::INT AS hour,
            COUNT(*)                                                       AS plays,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END)                      AS skips
        FROM plays
        GROUP BY hour
        ORDER BY hour
        """,
    ).fetchall()

    hourly = {h: {"plays": p, "skips": s, "rate": s / p if p else 0.0}
              for h, p, s in hourly_rows}

    total_plays = sum(r["plays"] for r in hourly.values())
    total_skips = sum(r["skips"] for r in hourly.values())
    global_rate = total_skips / total_plays if total_plays else 0.0

    hourly_skip_delta = {
        h: round((v["rate"] - global_rate) * 100, 1)
        for h, v in hourly.items()
    }

    top_skipped_hour = max(hourly, key=lambda h: hourly[h]["rate"], default=None)

    # --- Ukedagsbasert skip-rate ---
    weekday_rows = execute(
        conn,
        """
        SELECT
            (EXTRACT(ISODOW FROM timestamp AT TIME ZONE 'Europe/Oslo')::INT - 1)
                AS weekday,  -- 0=mandag, 6=søndag
            COUNT(*)                                              AS plays,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END)             AS skips
        FROM plays
        GROUP BY weekday
        ORDER BY weekday
        """,
    ).fetchall()

    WEEKDAY_NAMES = ["Mandag", "Tirsdag", "Onsdag", "Torsdag",
                     "Fredag", "Lørdag", "Søndag"]

    weekday_skip_rate = {
        WEEKDAY_NAMES[wd]: round(s / p * 100, 1) if p else 0.0
        for wd, p, s in weekday_rows
    }

    most_impatient_day = max(
        weekday_skip_rate, key=weekday_skip_rate.get, default=None
    )

    # --- Natt vs. dag ---
    night_plays = sum(
        v["plays"] for h, v in hourly.items() if h >= 22 or h < 6
    )
    night_skips = sum(
        v["skips"] for h, v in hourly.items() if h >= 22 or h < 6
    )
    day_plays = total_plays - night_plays
    day_skips = total_skips - night_skips

    night_rate = night_skips / night_plays if night_plays else 0.0
    day_rate = day_skips / day_plays if day_plays else 0.0
    night_vs_day_delta = round((night_rate - day_rate) * 100, 1)

    return {
        "hourly_skip_delta": hourly_skip_delta,
        "weekday_skip_rate": weekday_skip_rate,
        "most_impatient_day": most_impatient_day,
        "night_vs_day_delta": night_vs_day_delta,
        "top_skipped_hour": top_skipped_hour,
        "global_skip_rate": round(global_rate * 100, 1),
    }
```

**API-rute i `web.py`:**

```python
@app.route("/api/insights")
def api_insights():
    """Returnerer tids- og kontekstbaserte innsikter for dashbordet."""
    with pooled_connection() as conn:
        data = compute_insight_stats(conn)
    return jsonify(data)
```

**Eksempel på frontend-visning:**

Innsiktene rendres som menneskevennlige setninger i et eget "Musikkcoach"-panel:

```
┌─────────────────────────────────────────────────────────────┐
│  Din musikkprofil                                            │
├─────────────────────────────────────────────────────────────┤
│  Mest utålmodige dag:   Mandag  (+18% over snittet)         │
│  Mest utålmodige time:  Kl. 23  (+31% over snittet)         │
│  Natt vs. dag:          Du skipper 43% mer etter kl. 22     │
│  Global skip-rate:      34%                                  │
└─────────────────────────────────────────────────────────────┘
```

### 8.3 Låt-DNA (Audio Features)

**Konsept:**  
Spotifys `/v1/audio-features`-endepunkt returnerer akustiske egenskaper for hvert spor: tempo (BPM), `acousticness`, `danceability`, `energy`, `valence` (positivitet) m.fl. Ved å koble disse til skip-historikken kan systemet avdekke om brukeren systematisk hopper over sanger med bestemte lydegenskaper — f.eks. sakte sanger om morgenen, eller akustiske sanger på treningsdager.

**Spotify API-endepunkt:**

```
GET https://api.spotify.com/v1/audio-features?ids={comma_separated_track_ids}
Authorization: Bearer {access_token}
```

Maks 100 spor per kall. Returnerer en liste med `audio_features`-objekter.

**Eksempel på respons for ett spor:**

```json
{
  "id": "4iV5W9uYEdYUVa79Axb7Rh",
  "danceability": 0.735,
  "energy": 0.578,
  "tempo": 98.002,
  "acousticness": 0.00242,
  "valence": 0.636,
  "speechiness": 0.0461,
  "instrumentalness": 0.0,
  "liveness": 0.159,
  "loudness": -11.840,
  "duration_ms": 255349
}
```

**Databaseendringer:**

Legg til en ny tabell for audio features som caches lokalt for å unngå repeterte API-kall:

```sql
CREATE TABLE IF NOT EXISTS audio_features (
    uri              TEXT PRIMARY KEY,
    danceability     REAL,
    energy           REAL,
    tempo            REAL,
    acousticness     REAL,
    valence          REAL,
    speechiness      REAL,
    instrumentalness REAL,
    liveness         REAL,
    loudness         REAL,
    fetched_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Python-funksjon for batch-henting og caching:**

```python
def fetch_and_cache_audio_features(
    conn,
    token: str,
    uris: list[str],
) -> dict[str, dict]:
    """
    Henter audio features for en liste med spor-URIer.
    Sjekker lokal cache (audio_features-tabellen) først.
    Henter manglende spor fra Spotify API i batcher på 100.

    Returnerer dict: {uri: {danceability, energy, tempo, ...}}
    """
    # Finn hvilke URIer som allerede er cachet
    cached_rows = execute(
        conn,
        """
        SELECT uri, danceability, energy, tempo, acousticness,
               valence, speechiness, instrumentalness, liveness, loudness
        FROM audio_features
        WHERE uri = ANY(%s)
        """,
        (uris,),
    ).fetchall()

    result = {}
    cached_uris = set()

    for row in cached_rows:
        uri = row[0]
        result[uri] = {
            "danceability": row[1], "energy": row[2], "tempo": row[3],
            "acousticness": row[4], "valence": row[5], "speechiness": row[6],
            "instrumentalness": row[7], "liveness": row[8], "loudness": row[9],
        }
        cached_uris.add(uri)

    missing_uris = [u for u in uris if u not in cached_uris]

    if not missing_uris:
        return result

    # Batch-hent manglende fra Spotify (maks 100 per kall)
    batch_size = 100
    for i in range(0, len(missing_uris), batch_size):
        batch = missing_uris[i : i + batch_size]
        # Konverter spotify:track:XXX → XXX (kun ID-delen)
        ids = [u.split(":")[-1] for u in batch]

        resp = requests.get(
            "https://api.spotify.com/v1/audio-features",
            headers={"Authorization": f"Bearer {token}"},
            params={"ids": ",".join(ids)},
            timeout=15,
        )

        if resp.status_code != 200:
            logger.warning(
                "Klarte ikke hente audio features (status %d).", resp.status_code
            )
            continue

        for feat in resp.json().get("audio_features") or []:
            if not feat:
                continue  # Spotify returnerer null for lokale filer/podcaster
            uri = f"spotify:track:{feat['id']}"
            features = {
                "danceability": feat["danceability"],
                "energy": feat["energy"],
                "tempo": feat["tempo"],
                "acousticness": feat["acousticness"],
                "valence": feat["valence"],
                "speechiness": feat["speechiness"],
                "instrumentalness": feat["instrumentalness"],
                "liveness": feat["liveness"],
                "loudness": feat["loudness"],
            }
            result[uri] = features

            # Cache i databasen
            execute(
                conn,
                """
                INSERT INTO audio_features
                    (uri, danceability, energy, tempo, acousticness,
                     valence, speechiness, instrumentalness, liveness, loudness)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (uri) DO NOTHING
                """,
                (uri,
                 features["danceability"], features["energy"], features["tempo"],
                 features["acousticness"], features["valence"], features["speechiness"],
                 features["instrumentalness"], features["liveness"], features["loudness"]),
            )

        conn.commit()

    return result
```

**Analyseeksempel — BPM og skip-rate koblet til ukedag:**

```python
def compute_audio_feature_skip_correlation(conn) -> list[dict]:
    """
    Beregner gjennomsnittlig BPM, energy og danceability for
    skippede vs. fullførte sanger, brutt ned på ukedag.

    Eksempel på output:
        [
          {"weekday": "Mandag", "skipped_avg_tempo": 118.2,
           "completed_avg_tempo": 95.4, "delta_tempo": 22.8},
          ...
        ]

    Positiv delta_tempo betyr at brukeren skipper raskere sanger
    denne ukedagen relativt til hva de fullfører.
    """
    rows = execute(
        conn,
        """
        SELECT
            (EXTRACT(ISODOW FROM p.timestamp AT TIME ZONE 'Europe/Oslo')::INT - 1)
                AS weekday,
            p.skipped,
            AVG(af.tempo)       AS avg_tempo,
            AVG(af.energy)      AS avg_energy,
            AVG(af.danceability) AS avg_danceability
        FROM plays p
        JOIN audio_features af ON af.uri = p.uri
        GROUP BY weekday, p.skipped
        ORDER BY weekday, p.skipped
        """,
    ).fetchall()

    WEEKDAY_NAMES = ["Mandag", "Tirsdag", "Onsdag", "Torsdag",
                     "Fredag", "Lørdag", "Søndag"]

    by_day: dict[int, dict] = {}
    for wd, skipped, tempo, energy, dance in rows:
        key = "skipped" if skipped else "completed"
        if wd not in by_day:
            by_day[wd] = {}
        by_day[wd][key] = {
            "tempo": round(tempo, 1) if tempo else None,
            "energy": round(energy, 3) if energy else None,
            "danceability": round(dance, 3) if dance else None,
        }

    result = []
    for wd in sorted(by_day):
        skipped_data = by_day[wd].get("skipped", {})
        completed_data = by_day[wd].get("completed", {})
        delta_tempo = None
        if skipped_data.get("tempo") and completed_data.get("tempo"):
            delta_tempo = round(skipped_data["tempo"] - completed_data["tempo"], 1)
        result.append({
            "weekday": WEEKDAY_NAMES[wd],
            "skipped": skipped_data,
            "completed": completed_data,
            "delta_tempo": delta_tempo,
        })

    return result
```

**Fremtidig integrasjon med Smart Skipper:**

Når audio-features-cachen er fylt opp (typisk etter 2–4 uker med tracking), kan `should_auto_skip()` utvides med en tredje faktor: om den nåværende sangens tempo/danceability passer inn i brukerens historiske preferanseprofil for dette tidspunktet. Dette beskrives nærmere i Fase G sin planlagte kode-iterasjon og er naturlig å implementere som Tilnærming D (utover A, B, C i seksjon 3.3).

---

## 9. Fase H — Smart Score og Rapportering (Wrapped)

Fase H introduserer to overordnede rapporteringsverktøy: en kontinuerlig **Listening Score** som gir brukeren et enkelt, forståelig tall for lyttekvaliteten sin, og en månedlig **Skip Wrapped** — en personlig oppsummering inspirert av Spotify Wrapped, men utelukkende fokusert på skip-atferd og musikklojalitet.

### 9.1 Listening Score

**Konsept:**  
Listening Score er et enkelt tall fra 0 til 100 som oppsummerer hvor "tålmodig" og "engasjert" brukeren er som lytter. En score på 100 betyr at brukeren fullfører nesten alle sanger, lytter i lange sesjoner uten avbrudd, og er konsistent over tid. En lav score betyr mye hopping, korte sesjoner og uforutsigbar atferd. Scoren er ikke ment som dom, men som et speil og et sammenligningspunkt over tid.

**Algoritme:**

Scoren beregnes fra tre vektede komponenter, hver normalisert til 0–100:

```python
def compute_listening_score(conn, days: int = 30) -> dict:
    """
    Beregner Listening Score (0–100) basert på de siste N dagene.

    Komponenter og vekting:
        1. Completion Rate (50%):
           Andelen sanger fullført (ikke skippet) av totalt antall avspillinger.
           100 = fullfører alt, 0 = hopper over alt.

        2. Gjennomsnittlig sesjonslengde uten skip (30%):
           Gjennomsnittlig antall sanger på rad uten skip.
           Normalisert: 1 = score 0, 10+ = score 100.

        3. Skip-konsistens (20%):
           Standardavvik i daglig skip-rate over perioden.
           Lavt avvik = høy konsistens = høy delscore.
           Normalisert: stddev 0 = 100, stddev 0.5+ = 0.

    Returnerer:
        {
            "score": int (0–100),
            "completion_rate": float,
            "avg_streak": float,
            "consistency": float,
            "breakdown": {"completion": int, "streak": int, "consistency": int}
        }
    """
    cutoff = f"NOW() - INTERVAL '{days} days'"

    # --- Komponent 1: Completion Rate ---
    cr_row = execute(
        conn,
        f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN NOT skipped THEN 1 ELSE 0 END) AS completed
        FROM plays
        WHERE timestamp >= {cutoff}
        """,
    ).fetchone()

    total = cr_row[0] or 0
    completed = cr_row[1] or 0
    completion_rate = completed / total if total > 0 else 0.0
    completion_score = round(completion_rate * 100)

    # --- Komponent 2: Gjennomsnittlig streak (sanger på rad uten skip) ---
    # Beregnes ved å identifisere sekvenser av ikke-skippede sanger
    streak_rows = execute(
        conn,
        f"""
        SELECT skipped
        FROM plays
        WHERE timestamp >= {cutoff}
        ORDER BY timestamp ASC
        """,
    ).fetchall()

    streaks = []
    current_streak = 0
    for (skipped,) in streak_rows:
        if not skipped:
            current_streak += 1
        else:
            if current_streak > 0:
                streaks.append(current_streak)
            current_streak = 0
    if current_streak > 0:
        streaks.append(current_streak)

    avg_streak = sum(streaks) / len(streaks) if streaks else 0.0
    # Normaliser: 1 sang = score 0, 10+ sanger = score 100
    streak_score = round(min(100, max(0, (avg_streak - 1) / 9 * 100)))

    # --- Komponent 3: Skip-konsistens (daglig stddev) ---
    daily_rows = execute(
        conn,
        f"""
        SELECT
            DATE(timestamp AT TIME ZONE 'Europe/Oslo') AS day,
            AVG(CASE WHEN skipped THEN 1.0 ELSE 0.0 END) AS daily_skip_rate
        FROM plays
        WHERE timestamp >= {cutoff}
        GROUP BY day
        ORDER BY day
        """,
    ).fetchall()

    if len(daily_rows) >= 2:
        rates = [r[1] for r in daily_rows]
        mean = sum(rates) / len(rates)
        variance = sum((r - mean) ** 2 for r in rates) / len(rates)
        stddev = variance ** 0.5
    else:
        stddev = 0.0

    # Normaliser: stddev 0 = 100, stddev 0.5 = 0
    consistency_score = round(max(0, (1.0 - stddev / 0.5) * 100))

    # --- Vektet samlet score ---
    final_score = round(
        0.50 * completion_score
        + 0.30 * streak_score
        + 0.20 * consistency_score
    )

    return {
        "score": final_score,
        "completion_rate": round(completion_rate * 100, 1),
        "avg_streak": round(avg_streak, 1),
        "consistency_stddev": round(stddev, 3),
        "breakdown": {
            "completion": completion_score,
            "streak": streak_score,
            "consistency": consistency_score,
        },
        "based_on_days": days,
        "total_plays": total,
    }
```

**API-rute:**

```python
@app.route("/api/listening-score")
def api_listening_score():
    """
    Returnerer Listening Score for siste 30 dager (standard)
    eller valgfri periode via ?days=N.
    """
    days = min(int(request.args.get("days", 30)), 365)
    with pooled_connection() as conn:
        data = compute_listening_score(conn, days=days)
    return jsonify(data)
```

**Frontend-visning:**

Listening Score rendres som en stor sirkulær progressindikator (f.eks. en SVG-arc) i toppen av dashbordet, med en kort forklaring av hva scoren betyr. Under vises en trekkspill-seksjon med de tre delkomponentene og tilhørende forklaringstekster.

**Historisk sporing av scoren:**

For å la brukeren se utvikling over tid, lagres scoren ukentlig i en ny tabell:

```sql
CREATE TABLE IF NOT EXISTS listening_score_history (
    id          SERIAL PRIMARY KEY,
    score       INTEGER NOT NULL,
    completion  INTEGER NOT NULL,
    streak      INTEGER NOT NULL,
    consistency INTEGER NOT NULL,
    total_plays INTEGER NOT NULL,
    period_days INTEGER NOT NULL DEFAULT 30,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

En daemon-tråd (tilsvarende `_janitor_scheduler` i seksjon 6) skriver en ny rad søndager kl. 03:00. Dette gir et ukentlig datapunkt som kan tegnes som en enkel linjegraf i dashbordet under tittelen "Din score over tid".

### 9.2 Månedlig Skip Wrapped

**Konsept:**  
Skip Wrapped genererer en månedlig personlig rapport inspirert av Spotify Wrapped, men utelukkende fokusert på skip-atferd. Den svarer på spørsmål som: Hvilken artist skippet du mest? Hvilken sang var du mest lojal mot? Ble du mer eller mindre tålmodig sammenlignet med forrige måned?

**Datastruktur:**

```python
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class SkipWrappedData:
    """
    Fullstendig datastruktur for månedlig Skip Wrapped-rapport.
    Genereres av build_skip_wrapped() og serialiseres til JSON for API.
    """
    month: int                          # 1–12
    year: int
    period_label: str                   # f.eks. "Juni 2026"

    # Totaltall
    total_plays: int
    total_skips: int
    global_skip_rate: float             # 0.0–1.0

    # Mest skippede artist
    most_skipped_artist: str
    most_skipped_artist_skips: int
    most_skipped_artist_plays: int
    most_skipped_artist_rate: float

    # Mest trofaste sang (lavest skip-rate blant sanger med nok avspillinger)
    most_loyal_track_title: str
    most_loyal_track_artists: str
    most_loyal_track_plays: int
    most_loyal_track_skip_rate: float   # typisk 0.0

    # Mest skippede sang
    most_skipped_track_title: str
    most_skipped_track_artists: str
    most_skipped_track_skips: int
    most_skipped_track_plays: int

    # Utålmodighets-topper
    most_impatient_day: str             # ukedagnavn
    most_impatient_hour: int            # 0–23

    # Trendlinje: daglige skip-rater for hele måneden
    daily_skip_rates: list[dict]        # [{date: "2026-06-01", rate: 0.34}, ...]

    # Sammenlignet med forrige måned
    prev_month_skip_rate: Optional[float]
    trend: str                          # "bedre", "verre", "uendret", "ukjent"
    trend_delta: Optional[float]        # prosentpoeng endring
```

**Byggefunksjon i `wrapped.py`:**

```python
def build_skip_wrapped(conn, month: int, year: int) -> SkipWrappedData:
    """
    Bygger komplett Skip Wrapped-rapport for gitt måned og år.

    Bruker én felles CTE-basert spørring for de fleste totaltall,
    og separate spørringer for rangeringer og trendlinjer.
    """
    import calendar

    period_label = f"{calendar.month_name[month]} {year}"
    start = f"{year}-{month:02d}-01"
    # Finn siste dag i måneden
    last_day = calendar.monthrange(year, month)[1]
    end = f"{year}-{month:02d}-{last_day}"

    # --- Totaltall ---
    totals = execute(
        conn,
        """
        SELECT
            COUNT(*) AS total_plays,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END) AS total_skips
        FROM plays
        WHERE DATE(timestamp AT TIME ZONE 'Europe/Oslo')
              BETWEEN %s AND %s
        """,
        (start, end),
    ).fetchone()

    total_plays = totals[0] or 0
    total_skips = totals[1] or 0
    global_skip_rate = total_skips / total_plays if total_plays else 0.0

    # --- Mest skippede artist ---
    artist_row = execute(
        conn,
        """
        SELECT
            artists,
            COUNT(*) AS plays,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END) AS skips
        FROM plays
        WHERE DATE(timestamp AT TIME ZONE 'Europe/Oslo')
              BETWEEN %s AND %s
          AND artists IS NOT NULL
        GROUP BY artists
        ORDER BY skips DESC, plays DESC
        LIMIT 1
        """,
        (start, end),
    ).fetchone()

    # --- Mest trofaste sang (0% skip-rate, minst 3 avspillinger) ---
    loyal_row = execute(
        conn,
        """
        SELECT
            title, artists, COUNT(*) AS plays,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END) AS skips
        FROM plays
        WHERE DATE(timestamp AT TIME ZONE 'Europe/Oslo')
              BETWEEN %s AND %s
          AND title IS NOT NULL
        GROUP BY title, artists
        HAVING COUNT(*) >= 3
        ORDER BY
            (SUM(CASE WHEN skipped THEN 1 ELSE 0 END)::REAL / COUNT(*)) ASC,
            COUNT(*) DESC
        LIMIT 1
        """,
        (start, end),
    ).fetchone()

    # --- Mest skippede sang ---
    skipped_track_row = execute(
        conn,
        """
        SELECT
            title, artists,
            COUNT(*) AS plays,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END) AS skips
        FROM plays
        WHERE DATE(timestamp AT TIME ZONE 'Europe/Oslo')
              BETWEEN %s AND %s
          AND title IS NOT NULL
        GROUP BY title, artists
        HAVING COUNT(*) >= 2
        ORDER BY skips DESC, plays DESC
        LIMIT 1
        """,
        (start, end),
    ).fetchone()

    # --- Mest utålmodige ukedag og time ---
    impatient_day_row = execute(
        conn,
        """
        SELECT
            (EXTRACT(ISODOW FROM timestamp AT TIME ZONE 'Europe/Oslo')::INT - 1)
                AS weekday,
            AVG(CASE WHEN skipped THEN 1.0 ELSE 0.0 END) AS skip_rate
        FROM plays
        WHERE DATE(timestamp AT TIME ZONE 'Europe/Oslo')
              BETWEEN %s AND %s
        GROUP BY weekday
        ORDER BY skip_rate DESC
        LIMIT 1
        """,
        (start, end),
    ).fetchone()

    impatient_hour_row = execute(
        conn,
        """
        SELECT
            EXTRACT(HOUR FROM timestamp AT TIME ZONE 'Europe/Oslo')::INT AS hour,
            AVG(CASE WHEN skipped THEN 1.0 ELSE 0.0 END) AS skip_rate
        FROM plays
        WHERE DATE(timestamp AT TIME ZONE 'Europe/Oslo')
              BETWEEN %s AND %s
        GROUP BY hour
        ORDER BY skip_rate DESC
        LIMIT 1
        """,
        (start, end),
    ).fetchone()

    WEEKDAY_NAMES = ["Mandag", "Tirsdag", "Onsdag", "Torsdag",
                     "Fredag", "Lørdag", "Søndag"]

    # --- Daglig trendlinje ---
    daily_rows = execute(
        conn,
        """
        SELECT
            DATE(timestamp AT TIME ZONE 'Europe/Oslo') AS day,
            COUNT(*) AS plays,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END) AS skips
        FROM plays
        WHERE DATE(timestamp AT TIME ZONE 'Europe/Oslo')
              BETWEEN %s AND %s
        GROUP BY day
        ORDER BY day
        """,
        (start, end),
    ).fetchall()

    daily_skip_rates = [
        {
            "date": str(row[0]),
            "plays": row[1],
            "skips": row[2],
            "rate": round(row[2] / row[1] * 100, 1) if row[1] else 0.0,
        }
        for row in daily_rows
    ]

    # --- Sammenligning med forrige måned ---
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    prev_last_day = calendar.monthrange(prev_year, prev_month)[1]
    prev_start = f"{prev_year}-{prev_month:02d}-01"
    prev_end = f"{prev_year}-{prev_month:02d}-{prev_last_day}"

    prev_row = execute(
        conn,
        """
        SELECT
            COUNT(*),
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END)
        FROM plays
        WHERE DATE(timestamp AT TIME ZONE 'Europe/Oslo')
              BETWEEN %s AND %s
        """,
        (prev_start, prev_end),
    ).fetchone()

    prev_month_skip_rate = None
    trend = "ukjent"
    trend_delta = None

    if prev_row and prev_row[0] and prev_row[0] >= 10:
        prev_month_skip_rate = round(prev_row[1] / prev_row[0] * 100, 1)
        current_pct = round(global_skip_rate * 100, 1)
        trend_delta = round(current_pct - prev_month_skip_rate, 1)
        if abs(trend_delta) < 2.0:
            trend = "uendret"
        elif trend_delta < 0:
            trend = "bedre"   # færre skips = bedre
        else:
            trend = "verre"

    return SkipWrappedData(
        month=month,
        year=year,
        period_label=period_label,
        total_plays=total_plays,
        total_skips=total_skips,
        global_skip_rate=round(global_skip_rate * 100, 1),
        most_skipped_artist=artist_row[0] if artist_row else "—",
        most_skipped_artist_skips=artist_row[2] if artist_row else 0,
        most_skipped_artist_plays=artist_row[1] if artist_row else 0,
        most_skipped_artist_rate=round(
            artist_row[2] / artist_row[1] * 100, 1
        ) if artist_row and artist_row[1] else 0.0,
        most_loyal_track_title=loyal_row[0] if loyal_row else "—",
        most_loyal_track_artists=loyal_row[1] if loyal_row else "—",
        most_loyal_track_plays=loyal_row[2] if loyal_row else 0,
        most_loyal_track_skip_rate=round(
            loyal_row[3] / loyal_row[2] * 100, 1
        ) if loyal_row and loyal_row[2] else 0.0,
        most_skipped_track_title=skipped_track_row[0] if skipped_track_row else "—",
        most_skipped_track_artists=skipped_track_row[1] if skipped_track_row else "—",
        most_skipped_track_skips=skipped_track_row[3] if skipped_track_row else 0,
        most_skipped_track_plays=skipped_track_row[2] if skipped_track_row else 0,
        most_impatient_day=WEEKDAY_NAMES[impatient_day_row[0]]
            if impatient_day_row else "—",
        most_impatient_hour=impatient_hour_row[0] if impatient_hour_row else 0,
        daily_skip_rates=daily_skip_rates,
        prev_month_skip_rate=prev_month_skip_rate,
        trend=trend,
        trend_delta=trend_delta,
    )
```

**CLI-kommando:**

```bash
# Generer Wrapped for gjeldende måned
python3 -m spotify_skip_tracker skip-wrapped

# Generer for en spesifikk måned
python3 -m spotify_skip_tracker skip-wrapped --month 5 --year 2026

# Eksporter som JSON
python3 -m spotify_skip_tracker skip-wrapped --format json --output wrapped_mai_2026.json
```

**API-rute:**

```python
@app.route("/api/skip-wrapped")
def api_skip_wrapped():
    """
    Returnerer månedlig Skip Wrapped-rapport.
    Valgfrie query-parametere: ?month=N&year=YYYY
    Standardverdier: inneværende måned og år.
    """
    from datetime import date as _date
    today = _date.today()
    month = int(request.args.get("month", today.month))
    year = int(request.args.get("year", today.year))

    with pooled_connection() as conn:
        data = build_skip_wrapped(conn, month=month, year=year)

    # Konverter dataclass til dict for JSON-serialisering
    from dataclasses import asdict
    return jsonify(asdict(data))
```

**Frontend-visning:**

Skip Wrapped rendres som en kortbasert oppsummering, tilsvarende Spotify Wrapped-kortene, med én seksjon per innsikt:

```
┌─────────────────────────────────────────────────────────────┐
│  Din Juni 2026 — Skip Wrapped                                │
├────────────────┬────────────────────────────────────────────┤
│  Din måned     │  432 avspillinger  ·  34% skip-rate        │
│                │  Trend vs. mai: ↓ 4.2 pp  (bedre!)         │
├────────────────┼────────────────────────────────────────────┤
│  Verst artist  │  The Chainsmokers                          │
│                │  12 skips av 13 avspillinger (92%)          │
├────────────────┼────────────────────────────────────────────┤
│  Trofast sang  │  Bohemian Rhapsody — Queen                 │
│                │  8 avspillinger  ·  0% skip                │
├────────────────┼────────────────────────────────────────────┤
│  Utålmodig     │  Mandager kl. 08  (+28 pp over snittet)    │
├────────────────┼────────────────────────────────────────────┤
│  Trendlinje    │  [Miniatyr-linjegraf for hele måneden]      │
└────────────────┴────────────────────────────────────────────┘
```

**Persistering av månedlige rapporter:**

For å unngå å regenerere historiske rapporter fra databasen ved hvert API-kall, lagres ferdigbygde Wrapped-rapporter i en cache-tabell:

```sql
CREATE TABLE IF NOT EXISTS skip_wrapped_cache (
    id          SERIAL PRIMARY KEY,
    month       INTEGER NOT NULL,
    year        INTEGER NOT NULL,
    data        JSONB NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (month, year)
);
```

Bygger automatisk cache for forrige måned den 1. i hver ny måned, trigget av samme daemon-tråd som Listening Score-historikken. Rapporten for inneværende måned genereres alltid ferskt fra databasen og caches ikke.

---

*Dette dokumentet er ment som en levende guide. Oppdater det etter hvert som implementasjonen skrider frem og nye innsikter oppstår. Lykke til!*
