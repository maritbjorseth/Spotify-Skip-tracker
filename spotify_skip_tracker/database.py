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
            id          INTEGER DEFAULT 1 PRIMARY KEY,
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


def _migrate(conn) -> None:
    """Kjører inkrementelle skjema-migrasjoner."""
    _migrate_timestamp_to_timestamptz(conn)
    _migrate_add_image_url(conn)
    _migrate_skipped_to_boolean(conn)
    _migrate_smart_skipper(conn)
    _migrate_janitor(conn)


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
        WHERE table_name = 'plays' AND column_name = 'timestamp'
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
        WHERE table_name = 'plays' AND column_name = 'image_url'
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
        WHERE table_name = 'plays' AND column_name = 'skipped'
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
            id                INTEGER PRIMARY KEY DEFAULT 1,
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
    execute(
        conn,
        "INSERT INTO smart_skipper_config (id) VALUES (1) ON CONFLICT DO NOTHING",
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
        WHERE table_name = 'janitor_suggestions'
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
