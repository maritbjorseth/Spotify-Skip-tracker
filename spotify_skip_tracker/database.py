"""
Databaselag for Spotify Skip Tracker.

Håndterer:
- Tilkoblingspool (ThreadedConnectionPool) for web-laget
- Enkel tilkobling for tracker-loopen
- Skjemaoppsett og migrasjoner
"""

import logging
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


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
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
