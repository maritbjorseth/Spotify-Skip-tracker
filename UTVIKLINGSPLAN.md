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
