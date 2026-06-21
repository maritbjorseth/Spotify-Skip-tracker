"""
Tester for statistikkberegning i stats.py.

VIKTIG: Disse testene krever en separat testdatabase. Sett TEST_DATABASE_URL
til en tom Postgres-database som kan slettes fritt.

    TEST_DATABASE_URL=postgresql://... pytest tests/test_stats.py -v

Testene er hoppet over (skip) dersom TEST_DATABASE_URL ikke er satt.
De kjøres ALDRI mot produksjonsdatabasen (DATABASE_URL).
"""

import os
import pytest

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DB_URL,
    reason="TEST_DATABASE_URL ikke satt — sett en separat testdatabase for å kjøre disse",
)


@pytest.fixture()
def db_conn():
    """
    Isolert DB-tilkobling via savepoints.

    Alle endringer rulles tilbake etter hver test — ingen data
    blir liggende i testdatabasen.
    """
    import psycopg2
    from spotify_skip_tracker.database import _clean_dsn, init_db

    conn = psycopg2.connect(_clean_dsn(TEST_DB_URL))
    conn.autocommit = False

    init_db(conn)
    conn.commit()

    # Savepoint som vi ruller tilbake til etter testen
    cur = conn.cursor()
    cur.execute("SAVEPOINT test_isolation")

    yield conn

    conn.rollback()  # ruller tilbake til savepoint (effektivt: ROLLBACK TO SAVEPOINT)
    conn.close()


def _insert_play(conn, *, uri, title, artists, skipped, context_uri=None, image_url=None):
    """Setter inn en testrad uten å committe (for å holde savepoint-isolasjonen intakt)."""
    from datetime import datetime, timezone
    from spotify_skip_tracker.database import execute

    execute(
        conn,
        """
        INSERT INTO plays
            (uri, title, album, artists, context_uri, skipped, progress_ratio, timestamp, image_url)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            uri, title, "Test Album", artists,
            context_uri, skipped, 0.5 if not skipped else 0.3,
            datetime.now(timezone.utc), image_url,
        ),
    )
    # Ingen conn.commit() — savepoint håndterer isolasjonen


class TestComputeStats:
    def test_tom_database_returnerer_nuller(self, db_conn):
        from spotify_skip_tracker.stats import _compute
        result = _compute(db_conn)
        assert result["total_plays"] == 0
        assert result["total_skips"] == 0
        assert result["unique_tracks"] == 0
        assert result["tracks"] == []

    def test_skip_telles_korrekt(self, db_conn):
        from spotify_skip_tracker.stats import _compute

        _insert_play(db_conn, uri="spotify:track:A", title="Song A", artists="Artist A", skipped=True)
        _insert_play(db_conn, uri="spotify:track:A", title="Song A", artists="Artist A", skipped=False)
        _insert_play(db_conn, uri="spotify:track:A", title="Song A", artists="Artist A", skipped=True)

        result = _compute(db_conn)
        assert result["total_plays"] == 3
        assert result["total_skips"] == 2
        track = result["tracks"][0]
        assert track["skip_count"] == 2
        assert track["play_count"] == 3
        assert abs(track["skip_rate"] - 2 / 3) < 1e-9

    def test_sang_uten_skip_vises_ikke_i_tracks(self, db_conn):
        from spotify_skip_tracker.stats import _compute

        _insert_play(db_conn, uri="spotify:track:B", title="Never Skip", artists="Artist B", skipped=False)
        _insert_play(db_conn, uri="spotify:track:B", title="Never Skip", artists="Artist B", skipped=False)

        result = _compute(db_conn)
        assert result["unique_tracks"] == 0
        assert all(t["uri"] != "spotify:track:B" for t in result["tracks"])

    def test_most_played_inkluderer_alle_spor(self, db_conn):
        from spotify_skip_tracker.stats import _compute

        _insert_play(db_conn, uri="spotify:track:C", title="C", artists="X", skipped=False)
        _insert_play(db_conn, uri="spotify:track:C", title="C", artists="X", skipped=False)
        _insert_play(db_conn, uri="spotify:track:D", title="D", artists="Y", skipped=True)

        result = _compute(db_conn)
        uris = [t["uri"] for t in result["most_played"]]
        assert "spotify:track:C" in uris
        assert "spotify:track:D" in uris
        # C spilt flest ganger → skal stå øverst
        assert result["most_played"][0]["uri"] == "spotify:track:C"

    def test_most_completed_krever_minst_to_avspillinger(self, db_conn):
        from spotify_skip_tracker.stats import _compute

        _insert_play(db_conn, uri="spotify:track:E", title="E", artists="Z", skipped=False)

        result = _compute(db_conn)
        assert all(t["uri"] != "spotify:track:E" for t in result["most_completed"])

    def test_most_completed_vises_med_to_avspillinger(self, db_conn):
        from spotify_skip_tracker.stats import _compute

        _insert_play(db_conn, uri="spotify:track:F", title="F", artists="Z", skipped=False)
        _insert_play(db_conn, uri="spotify:track:F", title="F", artists="Z", skipped=False)

        result = _compute(db_conn)
        uris = [t["uri"] for t in result["most_completed"]]
        assert "spotify:track:F" in uris

    def test_image_url_lagres_og_returneres(self, db_conn):
        from spotify_skip_tracker.stats import _compute

        _insert_play(
            db_conn,
            uri="spotify:track:G", title="G", artists="A",
            skipped=True, image_url="https://i.scdn.co/image/test",
        )

        result = _compute(db_conn)
        track = next(t for t in result["tracks"] if t["uri"] == "spotify:track:G")
        assert track["image_url"] == "https://i.scdn.co/image/test"

    def test_unique_tracks_teller_distinkte_uri(self, db_conn):
        from spotify_skip_tracker.stats import _compute

        # Samme sang i to spillelister — skal bare telle som 1 unik sang
        _insert_play(db_conn, uri="spotify:track:H", title="H", artists="A",
                     skipped=True, context_uri="spotify:playlist:P1")
        _insert_play(db_conn, uri="spotify:track:H", title="H", artists="A",
                     skipped=True, context_uri="spotify:playlist:P2")

        result = _compute(db_conn)
        assert result["unique_tracks"] == 1

    def test_hourly_har_24_elementer(self, db_conn):
        from spotify_skip_tracker.stats import _compute
        result = _compute(db_conn)
        assert len(result["hourly"]) == 24

    def test_weekday_har_7_elementer(self, db_conn):
        from spotify_skip_tracker.stats import _compute
        result = _compute(db_conn)
        assert len(result["weekday"]) == 7
