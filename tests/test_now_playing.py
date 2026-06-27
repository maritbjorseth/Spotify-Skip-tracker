"""
Tester for Steg 3 i multi-user-migreringen: now_playing per bruker.

Dekker:
  - _upsert_now_playing() — ny user_id-parameter, isolasjon mellom brukere
  - /api/now — returnerer kun innlogget brukers nåværende sang
  - /api/now — returnerer is_playing=False når ingen rad finnes for brukeren
  - /api/now — stale-sjekk ved gammel updated_at

TestNowPlayingDB krever TEST_DATABASE_URL og hoppes over uten den.
TestNowPlayingAPI bruker Flask test client med mocket DB.
"""

import os
import unittest.mock
from datetime import datetime, timezone, timedelta

import pytest

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")

needs_db = pytest.mark.skipif(
    not TEST_DB_URL,
    reason="TEST_DATABASE_URL ikke satt",
)


# ---------------------------------------------------------------------------
# TestNowPlayingDB — DB-integrasjonstester (krever TEST_DATABASE_URL)
# ---------------------------------------------------------------------------

@needs_db
class TestNowPlayingDB:
    """
    Tester _upsert_now_playing() direkte mot en ekte Postgres-database.
    Bruker savepoints for isolasjon — ingen data lekker mellom tester.
    """

    @pytest.fixture()
    def conn(self):
        import psycopg2
        from spotify_skip_tracker.database import _clean_dsn, init_db

        c = psycopg2.connect(_clean_dsn(TEST_DB_URL))
        c.autocommit = False
        init_db(c)
        c.commit()
        c.cursor().execute("SAVEPOINT test_now_playing")
        yield c
        c.rollback()
        c.close()

    def _upsert(self, conn, user_id="user_a", uri="spotify:track:X",
                title="Song X", is_playing=True, progress_ms=30_000, duration_ms=200_000):
        from spotify_skip_tracker.tracker import _upsert_now_playing
        return _upsert_now_playing(
            conn, uri=uri, title=title, album="Album", artists="Artist",
            image_url=None, progress_ms=progress_ms, duration_ms=duration_ms,
            is_playing=is_playing, user_id=user_id,
        )

    def test_upsert_oppretter_rad_for_bruker(self, conn):
        self._upsert(conn, user_id="alice")
        row = conn.cursor()
        row.execute("SELECT user_id, uri FROM now_playing WHERE user_id = 'alice'")
        result = row.fetchone()
        assert result is not None
        assert result[0] == "alice"
        assert result[1] == "spotify:track:X"

    def test_upsert_oppdaterer_eksisterende_rad(self, conn):
        self._upsert(conn, user_id="bob", uri="spotify:track:A")
        self._upsert(conn, user_id="bob", uri="spotify:track:B")

        cur = conn.cursor()
        cur.execute("SELECT uri FROM now_playing WHERE user_id = 'bob'")
        assert cur.fetchone()[0] == "spotify:track:B"

    def test_to_brukere_er_isolert(self, conn):
        """Upsert for bruker A skal ikke påvirke bruker B."""
        self._upsert(conn, user_id="alice", uri="spotify:track:ALICE")
        self._upsert(conn, user_id="bob",   uri="spotify:track:BOB")

        cur = conn.cursor()
        cur.execute("SELECT uri FROM now_playing WHERE user_id = 'alice'")
        assert cur.fetchone()[0] == "spotify:track:ALICE"

        cur.execute("SELECT uri FROM now_playing WHERE user_id = 'bob'")
        assert cur.fetchone()[0] == "spotify:track:BOB"

    def test_bruker_uten_rad_gir_none(self, conn):
        cur = conn.cursor()
        cur.execute("SELECT * FROM now_playing WHERE user_id = 'ingen_slik_bruker'")
        assert cur.fetchone() is None

    def test_now_playing_tabell_har_user_id_som_pk(self, conn):
        """Verifiserer at skjema faktisk bruker user_id som primærnøkkel."""
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'now_playing'
              AND column_name = 'user_id'
        """)
        assert cur.fetchone() is not None

    def test_now_playing_tabell_har_ikke_id_kolonne(self, conn):
        """Den gamle singleton-kolonnen 'id' skal ikke eksistere."""
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'now_playing'
              AND column_name = 'id'
        """)
        assert cur.fetchone() is None


# ---------------------------------------------------------------------------
# TestNowPlayingAPI — Flask test client (alltid kjørt)
# ---------------------------------------------------------------------------

@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setattr("spotify_skip_tracker.web.DASHBOARD_PASSWORD", None)
    monkeypatch.setattr("spotify_skip_tracker.config.DASHBOARD_PASSWORD", None)
    monkeypatch.setattr(
        "spotify_skip_tracker.web._get_owner_user_id", lambda: "test_user"
    )
    monkeypatch.setattr("spotify_skip_tracker.web._owner_user_id_cache", None)

    from spotify_skip_tracker.web import create_flask_app
    flask_app = create_flask_app()
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test"
    flask_app.config["SESSION_COOKIE_SECURE"] = False
    flask_app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


def _make_now_playing_row(
    uri="spotify:track:T",
    title="Test Song",
    artists="Test Artist",
    album="Test Album",
    image_url=None,
    progress_ms=45_000,
    duration_ms=200_000,
    is_playing=True,
    updated_at=None,
):
    """Lager en now_playing-rad slik databasen returnerer den."""
    if updated_at is None:
        updated_at = datetime.now(timezone.utc)
    return (uri, title, artists, album, image_url, progress_ms, duration_ms, is_playing, updated_at)


class TestNowPlayingAPI:

    def _mock_db(self, monkeypatch, row, skip_rate=None):
        """
        Patcher pooled_connection() og execute() slik at /api/now
        returnerer den oppgitte raden uten ekte DB.
        """
        call_count = [0]

        class _FakeCursor:
            def fetchone(self_):
                call_count[0] += 1
                if call_count[0] == 1:
                    return row       # now_playing-oppslaget
                return (skip_rate,)  # skip-rate-oppslaget

        class _FakeConn:
            def cursor(self_): return _FakeCursor()

        class _FakeCM:
            def __enter__(self_): return _FakeConn()
            def __exit__(self_, *a): pass

        monkeypatch.setattr("spotify_skip_tracker.web.execute", lambda *a, **kw: _FakeCursor())
        monkeypatch.setattr("spotify_skip_tracker.web.pooled_connection", lambda: _FakeCM())

    def test_returnerer_is_playing_false_uten_rad(self, client, monkeypatch):
        class _FakeCursor:
            def fetchone(self_): return None

        class _FakeConn:
            def cursor(self_): return _FakeCursor()

        class _FakeCM:
            def __enter__(self_): return _FakeConn()
            def __exit__(self_, *a): pass

        monkeypatch.setattr("spotify_skip_tracker.web.execute", lambda *a, **kw: _FakeCursor())
        monkeypatch.setattr("spotify_skip_tracker.web.pooled_connection", lambda: _FakeCM())

        with client.session_transaction() as sess:
            sess["user_id"] = "test_user"

        resp = client.get("/api/now")
        assert resp.status_code == 200
        assert resp.get_json()["is_playing"] is False

    def test_returnerer_korrekt_data_for_aktiv_sang(self, client, monkeypatch):
        row = _make_now_playing_row(
            uri="spotify:track:ABC",
            title="My Song",
            artists="My Artist",
            progress_ms=30_000,
            duration_ms=180_000,
        )
        self._mock_db(monkeypatch, row, skip_rate=0.25)

        with client.session_transaction() as sess:
            sess["user_id"] = "test_user"

        resp = client.get("/api/now")
        data = resp.get_json()

        assert data["is_playing"] is True
        assert data["uri"] == "spotify:track:ABC"
        assert data["title"] == "My Song"
        assert data["progress_ms"] == 30_000
        assert data["duration_ms"] == 180_000

    def test_stale_updated_at_gir_is_playing_false(self, client, monkeypatch):
        """updated_at eldre enn 20 s skal gi is_playing=False."""
        stale_time = datetime.now(timezone.utc) - timedelta(seconds=25)
        row = _make_now_playing_row(is_playing=True, updated_at=stale_time)
        self._mock_db(monkeypatch, row)

        with client.session_transaction() as sess:
            sess["user_id"] = "test_user"

        resp = client.get("/api/now")
        assert resp.get_json()["is_playing"] is False

    def test_fersk_updated_at_beholder_is_playing(self, client, monkeypatch):
        """updated_at innenfor 20 s skal beholde is_playing=True."""
        fresh_time = datetime.now(timezone.utc) - timedelta(seconds=5)
        row = _make_now_playing_row(is_playing=True, updated_at=fresh_time)
        self._mock_db(monkeypatch, row)

        with client.session_transaction() as sess:
            sess["user_id"] = "test_user"

        resp = client.get("/api/now")
        assert resp.get_json()["is_playing"] is True

    def test_krever_innlogging_i_passord_modus(self, monkeypatch):
        monkeypatch.setattr("spotify_skip_tracker.web.DASHBOARD_PASSWORD", "secret")
        monkeypatch.setattr("spotify_skip_tracker.config.DASHBOARD_PASSWORD", "secret")
        monkeypatch.setattr("spotify_skip_tracker.web._owner_user_id_cache", None)

        from spotify_skip_tracker.web import create_flask_app
        pw_app = create_flask_app()
        pw_app.config.update(TESTING=True, SECRET_KEY="test",
                             SESSION_COOKIE_SECURE=False, SESSION_COOKIE_SAMESITE="Lax")
        pw_client = pw_app.test_client()

        resp = pw_client.get("/api/now")
        assert resp.status_code == 401
