"""
Databaselag for Spotify Skip Tracker.

Håndterer:
- Tilkoblingspool (ThreadedConnectionPool) for web-laget
- Enkel tilkobling for tracker-loopen
- Skjemaoppsett og migrasjoner
"""

import logging
import threading
import urllib.parse
from contextlib import contextmanager

import psycopg2
import psycopg2.pool

from .config import DATABASE_URL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tilkoblingspool (brukes av web/stats-laget)
# ---------------------------------------------------------------------------

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    with _pool_lock:
        if _pool is None or _pool.closed:
            _pool = psycopg2.pool.ThreadedConnectionPool(1, 10, _clean_dsn(DATABASE_URL))
    return _pool


@contextmanager
def pooled_connection():
    """Kontekstbehandler som låner en tilkobling fra poolen og returnerer den etterpå."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ---------------------------------------------------------------------------
# Direkte tilkobling (brukes av tracker-loopen og CLI-kommandoer)
# ---------------------------------------------------------------------------

def _clean_dsn(dsn: str | None) -> str:
    """
    Fjerner 'channel_binding'-parameteren som Neon legger til i tilkoblingsstrengen.
    Eldre libpq-bygg avviser denne parameteren, mens sslmode=require allerede
    dekker krypteringen.
    """
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL er ikke satt. Legg den til i .env.local eller som miljøvariabel."
        )
    parts = urllib.parse.urlsplit(dsn)
    query = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(parts.query)
        if k != "channel_binding"
    ]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


def connect() -> psycopg2.extensions.connection:
    """Åpner en ny direkte databasetilkobling."""
    return psycopg2.connect(_clean_dsn(DATABASE_URL))


def reconnect() -> psycopg2.extensions.connection | None:
    """Prøver å koble til databasen på nytt. Returnerer None ved feil."""
    try:
        return connect()
    except Exception as exc:
        logger.error("Kunne ikke koble til databasen: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Spørringshjelpefunksjon
# ---------------------------------------------------------------------------

def execute(conn, sql: str, params: tuple = ()):
    """
    Kjører en SQL-spørring med psycopg2-stil (%s) plassholdere.
    Returnerer markøren slik at man kan kalle .fetchall() / .fetchone().
    """
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur


# ---------------------------------------------------------------------------
# Skjemaoppsett og migrasjoner
# ---------------------------------------------------------------------------

def init_db(conn) -> None:
    """
    Oppretter tabeller og kjører eventuelle migrasjoner.
    Trygt å kalle ved hver oppstart — bruker IF NOT EXISTS og sjekker kolonnetyper.
    """
    _create_tables(conn)
    _migrate(conn)
    conn.commit()


def _create_tables(conn) -> None:
    execute(
        conn,
        """
        CREATE TABLE IF NOT EXISTS plays (
            id          SERIAL PRIMARY KEY,
            uri         TEXT        NOT NULL,
            title       TEXT,
            album       TEXT,
            artists     TEXT,
            context_uri TEXT,
            skipped     BOOLEAN     NOT NULL,
            progress_ratio REAL,
            timestamp   TIMESTAMPTZ NOT NULL,
            image_url   TEXT
        )
        """,
    )
    execute(
        conn,
        """
        CREATE TABLE IF NOT EXISTS contexts (
            uri  TEXT PRIMARY KEY,
            name TEXT
        )
        """,
    )
    execute(
        conn,
        """
        CREATE TABLE IF NOT EXISTS now_playing (
            user_id     TEXT        PRIMARY KEY,
            uri         TEXT,
            title       TEXT,
            artists     TEXT,
            album       TEXT,
            image_url   TEXT,
            progress_ms INTEGER,
            duration_ms INTEGER,
            is_playing  BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at  TIMESTAMPTZ NOT NULL
        )
        """,
    )
    execute(
        conn,
        """
        CREATE TABLE IF NOT EXISTS user_tokens (
            user_id       TEXT        PRIMARY KEY,
            refresh_token TEXT        NOT NULL,
            access_token  TEXT,
            expires_at    REAL,
            display_name  TEXT,
            scope         TEXT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_active   TIMESTAMPTZ
        )
        """,
    )


def _migrate(conn) -> None:
    """Kjører inkrementelle skjema-migrasjoner."""
    _migrate_timestamp_to_timestamptz(conn)
    _migrate_add_image_url(conn)
    _migrate_skipped_to_boolean(conn)
    _migrate_smart_skipper(conn)
    _migrate_janitor(conn)
    _migrate_add_user_id(conn)
    _migrate_default_user_to_spotify_id(conn)
    _migrate_add_session_id(conn)
    _migrate_add_indexes(conn)
    _migrate_bootstrap_owner_token(conn)
    _migrate_now_playing_per_user(conn)
    _migrate_smart_skipper_per_user(conn)
    _migrate_add_auto_skips_user_id(conn)


def _migrate_timestamp_to_timestamptz(conn) -> None:
    """
    Konverterer timestamp-kolonnen fra TEXT til TIMESTAMPTZ dersom den fortsatt
    er av typen TEXT (fra den opprinnelige SQLite-baserte designen).
    """
    cur = execute(
        conn,
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'plays' AND column_name = 'timestamp'
        """,
    )
    row = cur.fetchone()
    if row is None or row[0].lower() == "text":
        logger.info("Migrerer timestamp-kolonne fra TEXT til TIMESTAMPTZ …")
        execute(conn, "ALTER TABLE plays ADD COLUMN IF NOT EXISTS ts TIMESTAMPTZ")
        execute(
            conn,
            """
            UPDATE plays
            SET ts = timestamp::TIMESTAMPTZ
            WHERE ts IS NULL AND timestamp IS NOT NULL
            """,
        )
        # Bytt kolonner atomisk
        execute(conn, "ALTER TABLE plays DROP COLUMN IF EXISTS timestamp")
        execute(conn, "ALTER TABLE plays RENAME COLUMN ts TO timestamp")
        logger.info("Migrasjon fullført: timestamp er nå TIMESTAMPTZ.")


def _migrate_add_image_url(conn) -> None:
    """Legger til image_url-kolonnen dersom den ikke finnes ennå."""
    cur = execute(
        conn,
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'plays' AND column_name = 'image_url'
        """,
    )
    if cur.fetchone() is None:
        logger.info("Legger til image_url-kolonne i plays-tabellen …")
        execute(conn, "ALTER TABLE plays ADD COLUMN image_url TEXT")


def _migrate_skipped_to_boolean(conn) -> None:
    """
    Konverterer skipped-kolonnen fra INTEGER til BOOLEAN dersom den fortsatt
    er av typen INTEGER (fra den opprinnelige enkeltfil-baserte designen).
    """
    cur = execute(
        conn,
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'plays' AND column_name = 'skipped'
        """,
    )
    row = cur.fetchone()
    if row is not None and row[0].lower() != "boolean":
        logger.info("Migrerer skipped-kolonne fra INTEGER til BOOLEAN …")
        execute(conn, "ALTER TABLE plays ALTER COLUMN skipped TYPE BOOLEAN USING (skipped <> 0)")
        logger.info("Migrasjon fullført: skipped er nå BOOLEAN.")


def _migrate_smart_skipper(conn) -> None:
    """Oppretter Smart Skipper-tabeller hvis de ikke finnes."""
    execute(
        conn,
        """
        CREATE TABLE IF NOT EXISTS auto_skips (
            id           SERIAL PRIMARY KEY,
            user_id      TEXT NOT NULL DEFAULT 'default_user',
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
        """,
    )
    execute(
        conn,
        """
        CREATE TABLE IF NOT EXISTS smart_skipper_config (
            user_id           TEXT PRIMARY KEY,
            enabled           BOOLEAN NOT NULL DEFAULT FALSE,
            threshold         REAL NOT NULL DEFAULT 0.85,
            min_plays         INTEGER NOT NULL DEFAULT 3,
            delay_seconds     INTEGER NOT NULL DEFAULT 5,
            dry_run           BOOLEAN NOT NULL DEFAULT TRUE,
            respect_time      BOOLEAN NOT NULL DEFAULT FALSE,
            excluded_contexts TEXT[] DEFAULT '{}',
            excluded_uris     TEXT[] DEFAULT '{}'
        )
        """,
    )
    logger.info("Smart Skipper-tabeller klar.")


def _migrate_janitor(conn) -> None:
    """Oppretter Playlist Janitor-tabeller hvis de ikke finnes."""
    execute(
        conn,
        """
        CREATE TABLE IF NOT EXISTS janitor_suggestions (
            id            SERIAL PRIMARY KEY,
            playlist_id   TEXT NOT NULL,
            playlist_name TEXT,
            uri           TEXT NOT NULL,
            title         TEXT,
            artists       TEXT,
            skip_rate     REAL NOT NULL,
            janitor_score REAL NOT NULL,
            suggested_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            status        TEXT NOT NULL DEFAULT 'pending',
            acted_at      TIMESTAMPTZ,
            snapshot_id   TEXT
        )
        """,
    )
    execute(
        conn,
        """
        CREATE TABLE IF NOT EXISTS janitor_removals (
            id            SERIAL PRIMARY KEY,
            suggestion_id INTEGER REFERENCES janitor_suggestions(id),
            playlist_id   TEXT NOT NULL,
            playlist_name TEXT,
            uri           TEXT NOT NULL,
            title         TEXT,
            artists       TEXT,
            removed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            snapshot_id   TEXT NOT NULL,
            undone        BOOLEAN NOT NULL DEFAULT FALSE,
            undone_at     TIMESTAMPTZ
        )
        """,
    )
    # Legg til UNIQUE-constraint på (playlist_id, uri) dersom den ikke finnes.
    cur = execute(
        conn,
        """
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'janitor_suggestions'
          AND constraint_name = 'unique_playlist_track'
        """,
    )
    if cur.fetchone() is None:
        # Fjern eventuelle duplikater først — behold raden med høyest id per par.
        # Uten dette steget vil ALTER TABLE feile dersom databasen har duplikate rader
        # (f.eks. innsatt lokalt før constrainten eksisterte).
        execute(
            conn,
            """
            DELETE FROM janitor_suggestions a
            USING janitor_suggestions b
            WHERE a.id < b.id
              AND a.playlist_id = b.playlist_id
              AND a.uri = b.uri
            """,
        )
        conn.commit()

        # Bruk SAVEPOINT for å unngå at en eventuell feil her forgifter
        # den ytre transaksjonen i init_db().
        try:
            execute(conn, "SAVEPOINT add_unique_constraint")
            execute(
                conn,
                """
                ALTER TABLE janitor_suggestions
                ADD CONSTRAINT unique_playlist_track UNIQUE (playlist_id, uri)
                """,
            )
            execute(conn, "RELEASE SAVEPOINT add_unique_constraint")
            logger.info("Lagt til UNIQUE-constraint unique_playlist_track på janitor_suggestions.")
        except Exception as exc:
            execute(conn, "ROLLBACK TO SAVEPOINT add_unique_constraint")
            logger.warning(
                "Kunne ikke legge til unique_playlist_track (finnes kanskje allerede): %s", exc
            )

    logger.info("Playlist Janitor-tabeller klar.")


def _migrate_add_user_id(conn) -> None:
    """
    Fase H — Multi-user forberedelse.

    Legger til 'user_id'-kolonnen (VARCHAR, standard 'default_user') i de
    fire kjernetabellene. Bruker information_schema til å sjekke om kolonnen
    allerede finnes, slik at migrasjonen er trygg å kjøre flere ganger.

    I tillegg oppgraderes UNIQUE-constrainten på janitor_suggestions fra
    (playlist_id, uri) til (user_id, playlist_id, uri), slik at to ulike
    brukere kan ha samme sang i samme spilleliste uten nøkkelkollisjon.
    """
    _USER_ID_TABLES = [
        "plays",
        "smart_skipper_config",
        "janitor_suggestions",
        "janitor_removals",
    ]

    # ------------------------------------------------------------------
    # Steg 1: Legg til user_id-kolonne der den mangler
    # ------------------------------------------------------------------
    for table in _USER_ID_TABLES:
        cur = execute(
            conn,
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = 'user_id'
            """,
            (table,),
        )
        if cur.fetchone() is None:
            logger.info("Legger til user_id-kolonne i '%s' …", table)
            execute(
                conn,
                # Tabellnavn kan ikke parameteriseres med %s i psycopg2;
                # verdien er en hardkodet literal i koden — ikke brukerinput.
                f"ALTER TABLE {table} ADD COLUMN user_id VARCHAR NOT NULL DEFAULT 'default_user'",
            )
            logger.info("user_id lagt til i '%s'.", table)

    # ------------------------------------------------------------------
    # Steg 2: Oppgrader UNIQUE-constrainten på janitor_suggestions
    #
    # Gammel constraint: unique_playlist_track        → (playlist_id, uri)
    # Ny constraint:     unique_playlist_track_multiuser → (user_id, playlist_id, uri)
    #
    # Rekkefølge:
    #   a) Sjekk om ny constraint allerede finnes — hopp over hvis ja.
    #   b) Fjern gammel constraint hvis den fortsatt finnes.
    #   c) Dedupliser rader på (user_id, playlist_id, uri) — behold høyest id.
    #   d) Legg til ny constraint.
    #
    # Alt kjøres innenfor et SAVEPOINT slik at en uventet feil ikke
    # ødelegger resten av init_db()-transaksjonen.
    # ------------------------------------------------------------------
    cur = execute(
        conn,
        """
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'janitor_suggestions'
          AND constraint_name = 'unique_playlist_track_multiuser'
        """,
    )
    if cur.fetchone() is not None:
        # Ny constraint finnes allerede — ingenting å gjøre.
        return

    try:
        execute(conn, "SAVEPOINT upgrade_janitor_constraint")

        # a) Fjern gammel to-kolonne-constraint hvis den finnes
        cur2 = execute(
            conn,
            """
            SELECT 1
            FROM information_schema.table_constraints
            WHERE table_schema = 'public'
              AND table_name = 'janitor_suggestions'
              AND constraint_name = 'unique_playlist_track'
            """,
        )
        if cur2.fetchone() is not None:
            execute(
                conn,
                "ALTER TABLE janitor_suggestions DROP CONSTRAINT unique_playlist_track",
            )
            logger.info("Fjernet gammel UNIQUE-constraint 'unique_playlist_track'.")

        # b) Dedupliser på den nye tre-kolonne-nøkkelen — behold raden med høyest id
        execute(
            conn,
            """
            DELETE FROM janitor_suggestions a
            USING janitor_suggestions b
            WHERE a.id < b.id
              AND a.user_id    = b.user_id
              AND a.playlist_id = b.playlist_id
              AND a.uri        = b.uri
            """,
        )

        # c) Legg til ny constraint
        execute(
            conn,
            """
            ALTER TABLE janitor_suggestions
            ADD CONSTRAINT unique_playlist_track_multiuser
            UNIQUE (user_id, playlist_id, uri)
            """,
        )

        execute(conn, "RELEASE SAVEPOINT upgrade_janitor_constraint")
        logger.info(
            "UNIQUE-constraint 'unique_playlist_track_multiuser' "
            "(user_id, playlist_id, uri) lagt til på janitor_suggestions."
        )
    except Exception as exc:
        execute(conn, "ROLLBACK TO SAVEPOINT upgrade_janitor_constraint")
        logger.warning(
            "Kunne ikke oppgradere janitor-constraint — rullet tilbake SAVEPOINT: %s", exc
        )


def _migrate_default_user_to_spotify_id(conn) -> None:
    """
    Bootstrap-migrasjon: slår sammen historiske 'default_user'-rader med den
    ekte Spotify-bruker-IDen i alle kjernetabeller.

    Scenariet den løser
    -------------------
    1. _migrate_add_user_id() la til kolonnen med DEFAULT 'default_user',
       slik at alle eksisterende rader fikk user_id = 'default_user'.
    2. tracker.py ble oppdatert til å hente ekte ID fra /v1/me ved oppstart,
       og nye avspillinger lagres med den ekte ID-en.
    3. Statistikk-spørringer filtrerer på ekte ID → historikk forsvinner.

    Algoritme
    ---------
    Prioritet 1: hent ekte ID fra de nyeste 'plays'-radene som allerede
                 er riktig tagget (trackeren har kjørt etter oppdateringen).
    Prioritet 2: les SPOTIFY_USER_ID-miljøvariabelen som fallback dersom
                 trackeren ikke har kjørt ennå.
    Ingen ID funnet → logg en veiledende advarsel og hopp over.

    Er idempotent: kjøres ved hver oppstart, gjør ingenting dersom det ikke
    finnes 'default_user'-rader.
    """
    # --- Sjekk om det er noe å gjøre ---
    pending = execute(
        conn,
        "SELECT COUNT(*) FROM plays WHERE user_id = 'default_user'",
    ).fetchone()

    if not pending or int(pending[0]) == 0:
        return  # Alt er allerede migrert

    n_pending = int(pending[0])

    # --- Prioritet 1: auto-detekter fra nyeste riktig taggede rad ---
    real_id_row = execute(
        conn,
        """
        SELECT user_id FROM plays
        WHERE user_id != 'default_user'
        ORDER BY id DESC
        LIMIT 1
        """,
    ).fetchone()

    if real_id_row:
        real_user_id = real_id_row[0]
    else:
        # --- Prioritet 2: les fra miljøvariabel ---
        from .config import SPOTIFY_USER_ID
        if not SPOTIFY_USER_ID:
            logger.warning(
                "Bootstrap-migrasjon: %d avspillinger ligger under 'default_user' "
                "og er usynlige på dashbordet. "
                "Sett miljøvariabelen SPOTIFY_USER_ID til din Spotify-bruker-ID "
                "i Railway for å kjøre migrasjonen automatisk ved neste oppstart. "
                "Alternativt: kjør SQL-skriptet i UTVIKLINGSPLAN.md seksjon 5.4 "
                "direkte i Neon-konsollen.",
                n_pending,
            )
            return
        real_user_id = SPOTIFY_USER_ID

    logger.info(
        "Bootstrap-migrasjon: oppdaterer %d rader fra 'default_user' → '%s' …",
        n_pending,
        real_user_id,
    )

    _TABLES = [
        "plays",
        "janitor_suggestions",
        "janitor_removals",
        "smart_skipper_config",
    ]

    for table in _TABLES:
        cur = execute(
            conn,
            f"UPDATE {table} SET user_id = %s WHERE user_id = 'default_user'",
            (real_user_id,),
        )
        if cur.rowcount:
            logger.info("  → %s: %d rad(er) oppdatert.", table, cur.rowcount)

    logger.info("Bootstrap-migrasjon fullført — all historikk er nå synlig på dashbordet.")


def _migrate_add_session_id(conn) -> None:
    """
    Legger til session_id-kolonnen i plays-tabellen og backfiller
    eksisterende rader basert på tidsgap mellom avspillinger.

    En lyttesesjon defineres som en sammenhengende rekke avspillinger
    der ingen to påfølgende avspillinger er mer enn SESSION_GAP_MINUTES
    (30 min) fra hverandre. Nye sesjoner tildeles en tilfeldig UUID.

    Er idempotent: kjøres trygt ved hver oppstart.
    """
    # --- Steg 1: Legg til kolonne hvis den mangler ---
    cur = execute(
        conn,
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'plays' AND column_name = 'session_id'
        """,
    )
    if cur.fetchone() is None:
        logger.info("Legger til session_id-kolonne i plays …")
        execute(conn, "ALTER TABLE plays ADD COLUMN session_id TEXT")
        conn.commit()

    # --- Steg 2: Backfill rader som mangler session_id ---
    pending = execute(
        conn, "SELECT COUNT(*) FROM plays WHERE session_id IS NULL"
    ).fetchone()

    if not pending or int(pending[0]) == 0:
        return

    from .config import SESSION_GAP_MINUTES

    n = int(pending[0])
    logger.info("Backfiller session_id for %d avspillinger (gap=%d min) …", n, SESSION_GAP_MINUTES)
    _backfill_session_ids(conn, gap_seconds=SESSION_GAP_MINUTES * 60)
    logger.info("session_id backfill fullført.")


def _backfill_session_ids(conn, gap_seconds: int = 1800) -> None:
    """
    Tildeler session_id til alle plays-rader som mangler det.

    Algoritme per bruker:
    - Hent alle rader uten session_id sortert etter timestamp.
    - Start ny sesjon (ny UUID) når avstand til forrige avspilling
      overskrider gap_seconds.
    - Batch-oppdater med executemany for effektivitet.
    """
    import uuid as _uuid

    users = execute(
        conn,
        "SELECT DISTINCT user_id FROM plays WHERE session_id IS NULL",
    ).fetchall()

    db_cur = conn.cursor()

    for (user_id,) in users:
        plays = execute(
            conn,
            """
            SELECT id, timestamp FROM plays
            WHERE user_id = %s AND session_id IS NULL
            ORDER BY timestamp ASC
            """,
            (user_id,),
        ).fetchall()

        if not plays:
            continue

        current_session = str(_uuid.uuid4())
        prev_ts = None
        updates: list[tuple[str, int]] = []

        for play_id, ts in plays:
            if prev_ts is None or (ts - prev_ts).total_seconds() > gap_seconds:
                current_session = str(_uuid.uuid4())
            updates.append((current_session, play_id))
            prev_ts = ts

        db_cur.executemany(
            "UPDATE plays SET session_id = %s WHERE id = %s",
            updates,
        )
        logger.debug("  → '%s': %d avspillinger tagget.", user_id, len(updates))

    conn.commit()


def _migrate_add_indexes(conn) -> None:
    """
    Oppretter indekser på plays-tabellen for å unngå fulle tabellskann.

    Kjøres etter _migrate_add_user_id() og _migrate_add_session_id() slik
    at alle kolonner garantert finnes. IF NOT EXISTS gjør det trygt å kjøre
    ved hver oppstart — Postgres hopper over eksisterende indekser.

    Indekser:
        idx_plays_user_timestamp  — filtrering per bruker, sortert på tid
                                    (brukes av nesten alle stats-spørringer)
        idx_plays_user_uri        — skip-rate per sang per bruker
        idx_plays_uri             — global URI-oppslag (SmartSkipper fallback)
        idx_plays_user_context    — kontekst-aggregering (Janitor, stats)
        idx_plays_session         — session_id-oppslag (insights)
    """
    indexes = [
        (
            "idx_plays_user_timestamp",
            "CREATE INDEX IF NOT EXISTS idx_plays_user_timestamp "
            "ON plays (user_id, timestamp DESC)",
        ),
        (
            "idx_plays_user_uri",
            "CREATE INDEX IF NOT EXISTS idx_plays_user_uri "
            "ON plays (user_id, uri)",
        ),
        (
            "idx_plays_uri",
            "CREATE INDEX IF NOT EXISTS idx_plays_uri "
            "ON plays (uri)",
        ),
        (
            "idx_plays_user_context",
            "CREATE INDEX IF NOT EXISTS idx_plays_user_context "
            "ON plays (user_id, context_uri)",
        ),
        (
            "idx_plays_session",
            "CREATE INDEX IF NOT EXISTS idx_plays_session "
            "ON plays (session_id) WHERE session_id IS NOT NULL",
        ),
    ]
    for name, ddl in indexes:
        try:
            execute(conn, ddl)
            logger.debug("Indeks klar: %s", name)
        except Exception as exc:
            logger.warning("Kunne ikke opprette indeks '%s': %s", name, exc)
    conn.commit()
    logger.info("Indeks-migrasjon fullført.")


def _migrate_bootstrap_owner_token(conn) -> None:
    """
    Bootstrap-migrasjon: flytter eierens refresh-token fra SPOTIFY_REFRESH_TOKEN-
    miljøvariabelen til user_tokens-tabellen.

    Kjøres idempotent ved hver oppstart — gjør ingenting dersom tabellen
    allerede har minst én rad.

    Algoritme for å finne user_id (ingen Spotify API-kall):
        Prioritet 1: SPOTIFY_USER_ID-miljøvariabelen
        Prioritet 2: nyeste non-default_user-rad i plays-tabellen
        Ingen treffer → hopper over med veiledende advarsel

    Krypterer tokenet med token_crypto.encrypt_token() dersom
    TOKEN_ENCRYPTION_KEY er satt; lagrer ellers i klartekst ('plain:'-prefiks).
    """
    # Sjekk om det er noe å gjøre
    existing_count = execute(conn, "SELECT COUNT(*) FROM user_tokens").fetchone()[0]
    if existing_count > 0:
        return  # Allerede migrert

    from .config import SPOTIFY_REFRESH_TOKEN, SPOTIFY_CLIENT_ID, SPOTIFY_USER_ID

    if not SPOTIFY_REFRESH_TOKEN:
        return  # Ingen env-var-token å migrere

    if not SPOTIFY_CLIENT_ID:
        logger.warning(
            "Bootstrap: SPOTIFY_REFRESH_TOKEN er satt, men SPOTIFY_CLIENT_ID "
            "mangler — kan ikke bekrefte token. Hopper over bootstrap."
        )
        return

    # Finn user_id uten API-kall
    real_user_id: str | None = SPOTIFY_USER_ID

    if not real_user_id:
        row = execute(
            conn,
            """
            SELECT user_id FROM plays
            WHERE user_id != 'default_user'
            ORDER BY id DESC
            LIMIT 1
            """,
        ).fetchone()
        if row:
            real_user_id = row[0]

    if not real_user_id:
        logger.warning(
            "Bootstrap: SPOTIFY_REFRESH_TOKEN funnet, men kunne ikke bestemme "
            "bruker-ID (ingen SPOTIFY_USER_ID i miljøet og ingen avspillinger "
            "i databasen). Sett SPOTIFY_USER_ID i Railway-miljøet og start "
            "tjenesten på nytt for å fullføre bootstrap-migrasjonen."
        )
        return

    # Krypter og lagre
    try:
        from .token_crypto import encrypt_token
        encrypted = encrypt_token(SPOTIFY_REFRESH_TOKEN)
    except Exception as exc:
        logger.error(
            "Bootstrap: kunne ikke kryptere SPOTIFY_REFRESH_TOKEN: %s. "
            "Hopper over bootstrap.", exc
        )
        return

    try:
        execute(
            conn,
            """
            INSERT INTO user_tokens (user_id, refresh_token, last_active)
            VALUES (%s, %s, NOW())
            ON CONFLICT (user_id) DO NOTHING
            """,
            (real_user_id, encrypted),
        )
        conn.commit()
        logger.info(
            "Bootstrap: refresh-token for '%s' er migrert til user_tokens-tabellen.",
            real_user_id,
        )
    except Exception as exc:
        logger.error("Bootstrap: DB-feil ved skriving av token: %s", exc)
        conn.rollback()


def _migrate_now_playing_per_user(conn) -> None:
    """
    Migrerer now_playing-tabellen fra singleton-design (én rad med id=1)
    til per-bruker-design (én rad per bruker med user_id som primærnøkkel).

    Idempotent: hopper over dersom user_id-kolonnen allerede finnes.

    Strategi: drop og recreate.
    now_playing inneholder kun øyeblikkets avspillingsstatus — ikke historikk.
    Det er derfor trygt å forkaste den gamle raden; trackeren fyller tabellen
    på nytt innen neste poll-syklus (≤ 7 sekunder etter oppstart).

    Den nye tabellen er identisk med definisjonen i _create_tables(), slik
    at nye og migrerte databaser havner i samme tilstand.
    """
    cur = execute(
        conn,
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'now_playing' AND column_name = 'user_id'
        """,
    )
    if cur.fetchone() is not None:
        return  # Allerede migrert

    logger.info(
        "Migrerer now_playing fra singleton (id=1) til per-bruker (user_id) …"
    )

    try:
        execute(conn, "SAVEPOINT migrate_now_playing")
        execute(conn, "DROP TABLE IF EXISTS now_playing")
        execute(
            conn,
            """
            CREATE TABLE now_playing (
                user_id     TEXT        PRIMARY KEY,
                uri         TEXT,
                title       TEXT,
                artists     TEXT,
                album       TEXT,
                image_url   TEXT,
                progress_ms INTEGER,
                duration_ms INTEGER,
                is_playing  BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at  TIMESTAMPTZ NOT NULL
            )
            """,
        )
        execute(conn, "RELEASE SAVEPOINT migrate_now_playing")
        conn.commit()
        logger.info("now_playing migrert. Trackeren fyller tabellen ved neste poll.")
    except Exception as exc:
        execute(conn, "ROLLBACK TO SAVEPOINT migrate_now_playing")
        logger.error("Feil under now_playing-migrasjon: %s", exc)


# ---------------------------------------------------------------------------
# user_tokens — offentlige CRUD-funksjoner
# ---------------------------------------------------------------------------

def upsert_user_token(
    conn,
    user_id: str,
    refresh_token_encrypted: str,
    access_token: str | None = None,
    expires_at: float | None = None,
    display_name: str | None = None,
    scope: str | None = None,
) -> None:
    """
    Lagrer eller oppdaterer token-informasjon for én bruker.

    refresh_token_encrypted skal allerede være kryptert av token_crypto.encrypt_token()
    — denne funksjonen tar imot og lagrer den krypterte strengen direkte.

    Ved konflikt (user_id finnes allerede):
        - refresh_token, access_token, expires_at og last_active oppdateres alltid.
        - display_name og scope oppdateres kun dersom den nye verdien er ikke-NULL
          (slik at eksisterende verdier beholdes om ikke satt eksplisitt).
    """
    execute(
        conn,
        """
        INSERT INTO user_tokens
            (user_id, refresh_token, access_token, expires_at,
             display_name, scope, last_active)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            refresh_token = EXCLUDED.refresh_token,
            access_token  = EXCLUDED.access_token,
            expires_at    = EXCLUDED.expires_at,
            display_name  = COALESCE(EXCLUDED.display_name, user_tokens.display_name),
            scope         = COALESCE(EXCLUDED.scope, user_tokens.scope),
            last_active   = NOW()
        """,
        (user_id, refresh_token_encrypted, access_token, expires_at, display_name, scope),
    )
    conn.commit()


def update_access_token_cache(
    conn,
    user_id: str,
    access_token: str,
    expires_at: float,
) -> None:
    """
    Oppdaterer access_token og expires_at uten å røre refresh_token.

    Kalles av get_access_token() etter et vellykket token-refresh. Siden
    access-tokens er kortlevde (1 time) og ikke sensitive nok til å kreve
    kryptering, lagres de som klartekst.
    """
    execute(
        conn,
        """
        UPDATE user_tokens
        SET access_token = %s,
            expires_at   = %s,
            last_active  = NOW()
        WHERE user_id = %s
        """,
        (access_token, expires_at, user_id),
    )
    conn.commit()


def get_user_token_row(conn, user_id: str) -> dict | None:
    """
    Henter token-rad for user_id.

    Returnerer None dersom brukeren ikke finnes i user_tokens.
    Returnerer rådata med kryptert refresh_token — dekryptering skjer i
    spotify_api.py sin load_creds()-funksjon.

    Returformat:
        {
            "user_id":       str,
            "refresh_token": str,   # kryptert streng (enc: eller plain:-prefiks)
            "access_token":  str | None,
            "expires_at":    float | None,
            "display_name":  str | None,
            "scope":         str | None,
        }
    """
    row = execute(
        conn,
        """
        SELECT user_id, refresh_token, access_token, expires_at, display_name, scope
        FROM user_tokens
        WHERE user_id = %s
        """,
        (user_id,),
    ).fetchone()

    if row is None:
        return None

    return {
        "user_id":       row[0],
        "refresh_token": row[1],
        "access_token":  row[2],
        "expires_at":    float(row[3]) if row[3] is not None else None,
        "display_name":  row[4],
        "scope":         row[5],
    }


def list_active_user_ids(conn) -> list[str]:
    """
    Returnerer alle user_id-er som har refresh-tokens lagret i databasen,
    sortert med den sist aktive brukeren først.

    Brukes av tracker_manager() (Steg 5) for å starte tracking-tråder
    ved oppstart.
    """
    rows = execute(
        conn,
        "SELECT user_id FROM user_tokens ORDER BY last_active DESC NULLS LAST",
    ).fetchall()
    return [row[0] for row in rows]


def mark_token_invalid(conn, user_id: str) -> None:
    """
    Markerer brukerens token som ugyldig ved å nullstille access_token og expires_at.

    Refresh-tokenet beholdes slik at brukeren kan re-autentisere via
    /api/auth/login uten å miste user_id-assosiasjonen.

    Kalles av tracker-loopen (Steg 5) dersom Spotify svarer 401 Unauthorized,
    noe som indikerer at refresh-tokenet er utløpt eller tilbakekalt.
    """
    execute(
        conn,
        """
        UPDATE user_tokens
        SET access_token = NULL,
            expires_at   = NULL
        WHERE user_id = %s
        """,
        (user_id,),
    )
    conn.commit()
    logger.info("Token markert som ugyldig for bruker '%s'.", user_id)


# ---------------------------------------------------------------------------
# Hjelpefunksjoner for multi-user CLI og migrasjoner
# ---------------------------------------------------------------------------

def _detect_owner_user_id(conn) -> str | None:
    """
    Finner eierens Spotify-bruker-ID fra databasen uten API-kall.

    Brukes av migrasjoner og CLI-kommandoer der Flask-session ikke er
    tilgjengelig. Prioritert rekkefølge:
        1. user_tokens (mest pålitelig — satt av Steg 1 bootstrap)
        2. plays (siste rad med ekte bruker-ID)
        3. SPOTIFY_USER_ID-miljøvariabel

    Returnerer None dersom ingen kilde er tilgjengelig.
    """
    try:
        row = execute(
            conn,
            "SELECT user_id FROM user_tokens ORDER BY last_active DESC NULLS LAST LIMIT 1",
        ).fetchone()
        if row:
            return row[0]
    except Exception:
        pass

    try:
        row = execute(
            conn,
            """
            SELECT user_id FROM plays
            WHERE user_id != 'default_user'
            ORDER BY id DESC LIMIT 1
            """,
        ).fetchone()
        if row:
            return row[0]
    except Exception:
        pass

    from .config import SPOTIFY_USER_ID
    return SPOTIFY_USER_ID or None


def ensure_user_smart_skipper_config(conn, user_id: str) -> None:
    """
    Oppretter en standard Smart Skipper-konfigurasjon for brukeren
    dersom den ikke allerede finnes.

    Idempotent: bruker ON CONFLICT DO NOTHING.

    Kalles fra:
        - auth_callback() (web.py) etter vellykket OAuth-innlogging
        - CLI-kommandoer i __main__.py
    """
    execute(
        conn,
        """
        INSERT INTO smart_skipper_config (user_id)
        VALUES (%s)
        ON CONFLICT (user_id) DO NOTHING
        """,
        (user_id,),
    )
    conn.commit()


def _migrate_smart_skipper_per_user(conn) -> None:
    """
    Migrerer smart_skipper_config fra singleton (id=1) til per-bruker (user_id PK).

    Idempotent: hopper over dersom 'id'-kolonnen ikke finnes i tabellen.

    Strategi: drop og recreate med bevaring av eksisterende konfigurasjonsverider.
    Konfigurasjonen (enabled, threshold, dry_run, osv.) tilhører eieren og
    preserveres til eierens user_id-rad i det nye skjemaet.

    Eier-ID detekteres via _detect_owner_user_id() — user_tokens → plays → env-var.
    Finner vi ingen eier-ID, opprettes tabellen uten seed-rad; eieren får
    standardverdier neste gang ensure_user_smart_skipper_config() kalles.
    """
    cur = execute(
        conn,
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'smart_skipper_config' AND column_name = 'id'
        """,
    )
    if cur.fetchone() is None:
        return  # Allerede migrert

    logger.info("Migrerer smart_skipper_config fra singleton til per-bruker …")

    # Les eksisterende konfigurasjonsverider fra gammel tabell
    old_row = execute(
        conn,
        """
        SELECT enabled, threshold, min_plays, delay_seconds,
               dry_run, respect_time, excluded_contexts, excluded_uris
        FROM smart_skipper_config
        WHERE id = 1
        """,
    ).fetchone()

    owner_id = _detect_owner_user_id(conn)

    try:
        execute(conn, "SAVEPOINT migrate_ss_per_user")
        execute(conn, "DROP TABLE IF EXISTS smart_skipper_config")
        execute(
            conn,
            """
            CREATE TABLE smart_skipper_config (
                user_id           TEXT PRIMARY KEY,
                enabled           BOOLEAN NOT NULL DEFAULT FALSE,
                threshold         REAL NOT NULL DEFAULT 0.85,
                min_plays         INTEGER NOT NULL DEFAULT 3,
                delay_seconds     INTEGER NOT NULL DEFAULT 5,
                dry_run           BOOLEAN NOT NULL DEFAULT TRUE,
                respect_time      BOOLEAN NOT NULL DEFAULT FALSE,
                excluded_contexts TEXT[] DEFAULT '{}',
                excluded_uris     TEXT[] DEFAULT '{}'
            )
            """,
        )

        if old_row and owner_id:
            execute(
                conn,
                """
                INSERT INTO smart_skipper_config
                    (user_id, enabled, threshold, min_plays, delay_seconds,
                     dry_run, respect_time, excluded_contexts, excluded_uris)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (owner_id, *old_row),
            )
            logger.info(
                "smart_skipper_config: eksisterende innstillinger bevart for '%s'.",
                owner_id,
            )
        elif owner_id:
            logger.info(
                "smart_skipper_config: ingen gammel konfigurasjon å bevare — "
                "eier '%s' får standardverdier.", owner_id,
            )
        else:
            logger.warning(
                "smart_skipper_config: kunne ikke bestemme eier-ID. "
                "Tabellen er klar — kjør ensure_user_smart_skipper_config() "
                "for å opprette en standardrad."
            )

        execute(conn, "RELEASE SAVEPOINT migrate_ss_per_user")
        conn.commit()
        logger.info("smart_skipper_config migrert til per-bruker-skjema.")
    except Exception as exc:
        execute(conn, "ROLLBACK TO SAVEPOINT migrate_ss_per_user")
        logger.error("Feil under smart_skipper_config-migrasjon: %s", exc)


def _migrate_add_auto_skips_user_id(conn) -> None:
    """
    Legger til user_id-kolonnen i auto_skips-tabellen (Smart Skipper audit-logg).

    Idempotent: hopper over dersom kolonnen allerede finnes.

    Backfill: eksisterende rader (generert før multi-user) tilordnes eierens
    user_id via _detect_owner_user_id(). Finner vi ingen eier, beholdes
    DEFAULT-verdien 'default_user' — audit-historikken forblir synlig.
    """
    cur = execute(
        conn,
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'auto_skips' AND column_name = 'user_id'
        """,
    )
    if cur.fetchone() is not None:
        return  # Allerede migrert

    logger.info("Legger til user_id-kolonne i auto_skips …")
    execute(
        conn,
        "ALTER TABLE auto_skips ADD COLUMN user_id TEXT NOT NULL DEFAULT 'default_user'",
    )
    conn.commit()

    # Backfill: oppdater eksisterende rader til eierens bruker-ID
    owner_id = _detect_owner_user_id(conn)
    if owner_id:
        cur = execute(
            conn,
            "UPDATE auto_skips SET user_id = %s WHERE user_id = 'default_user'",
            (owner_id,),
        )
        conn.commit()
        logger.info(
            "auto_skips: %d rad(er) oppdatert til user_id='%s'.",
            cur.rowcount, owner_id,
        )
    else:
        logger.info(
            "auto_skips: ingen eier-ID funnet — rader beholder 'default_user'."
        )

    logger.info("auto_skips user_id-migrasjon fullført.")
