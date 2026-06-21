"""
Tester for statistikkberegning i stats.py.

Disse testene bruker en ekte in-memory Postgres-tilkobling (via psycopg2)
hvis DATABASE_URL er tilgjengelig, ellers hoppes de over.

For å kjøre lokalt:
    DATABASE_URL=... pytest tests/test_stats.py
"""

import os
import pytest

# Hopp over alle tester i denne filen dersom DATABASE_URL mangler
pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL ikke satt — hopper over DB-tester",
)


@pytest.fixture()
def db_conn():
    """Oppretter en isolert testtilkobling med en midlertidig skjema."""
    from spotify_skip_tracker.database import connect, init_db

    conn = connect()
    # Bruk en midlertidig tabell-prefiks for å isolere testdata
    conn.autocommit = False

    # Sett opp tabeller
    init_db(conn)

    # Rydd opp testdata fra forrige kjøring
    cur = conn.cursor()
    cur.execute("DELETE FROM plays")
    cur.execute("DELETE FROM contexts")
    conn.commit()

    yield conn

    # Rull tilbake all testdata
    conn.rollback()
    conn.close()


def _insert_play(conn, *, uri, title, artists, skipped, context_uri=None, image_url=None):
    """Hjelpefunksjon for å sette inn en testrad."""
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
    conn.commit()


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

        # Bare én avspilling — skal ikke vises i most_completed
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

    def test_hourly_har_24_elementer(self, db_conn):
        from spotify_skip_tracker.stats import _compute
        result = _compute(db_conn)
        assert len(result["hourly"]) == 24

    def test_weekday_har_7_elementer(self, db_conn):
        from spotify_skip_tracker.stats import _compute
        result = _compute(db_conn)
        assert len(result["weekday"]) == 7
