"""
Tester for Steg 6 i multi-user-migreringen: auto_skips per bruker.

Dekker:
  - log_auto_skip() lagrer user_id korrekt
  - log_auto_skip() har 'default_user' som standard
  - /api/smart-skipper returnerer kun innlogget brukers historikk
  - Isolasjon: bruker A ser ikke bruker B sin historikk

TestAutoSkipsDB krever TEST_DATABASE_URL og hoppes over uten den.
TestAutoSkipsAPI bruker Flask test client med mocket DB.
"""

import os
import unittest.mock

import pytest

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")

needs_db = pytest.mark.skipif(
    not TEST_DB_URL,
    reason="TEST_DATABASE_URL ikke satt",
)


# ---------------------------------------------------------------------------
# TestLogAutoSkipSignature — alltid kjørt
# ---------------------------------------------------------------------------

class TestLogAutoSkipSignature:
    """Verifiserer at log_auto_skip() sender user_id til DB-kallet."""

    def _make_cursor(self):
        class Cur:
            def fetchone(self_): return None
        return Cur()

    def test_sender_user_id_til_insert(self):
        from spotify_skip_tracker.smart_skipper import log_auto_skip

        captured = {}

        def fake_execute(conn, sql, params=()):
            captured["sql"] = sql
            captured["params"] = params
            return self._make_cursor()

        mock_conn = unittest.mock.MagicMock()
        mock_conn.commit = lambda: None

        with unittest.mock.patch(
            "spotify_skip_tracker.smart_skipper.execute", fake_execute
        ):
            log_auto_skip(
                mock_conn,
                uri="spotify:track:ABC",
                title="Test",
                artists="Artist",
                context_uri=None,
                skip_rate=0.9,
                threshold=0.85,
                reason="test",
                user_id="alice",
            )

        assert "alice" in captured["params"]
        assert "user_id" in captured["sql"]

    def test_default_user_id_er_default_user(self):
        from spotify_skip_tracker.smart_skipper import log_auto_skip

        captured = {}

        def fake_execute(conn, sql, params=()):
            captured["params"] = params
            class Cur:
                def fetchone(self_): return None
            return Cur()

        mock_conn = unittest.mock.MagicMock()
        mock_conn.commit = lambda: None

        with unittest.mock.patch(
            "spotify_skip_tracker.smart_skipper.execute", fake_execute
        ):
            log_auto_skip(
                mock_conn,
                uri="spotify:track:X",
                title="T", artists="A",
                context_uri=None,
                skip_rate=0.9, threshold=0.85, reason="r",
            )

        assert "default_user" in captured["params"]


# ---------------------------------------------------------------------------
# TestAutoSkipsDB — krever TEST_DATABASE_URL
# ---------------------------------------------------------------------------

@needs_db
class TestAutoSkipsDB:

    @pytest.fixture()
    def conn(self):
        import psycopg2
        from spotify_skip_tracker.database import _clean_dsn, init_db

        c = psycopg2.connect(_clean_dsn(TEST_DB_URL))
        c.autocommit = False
        init_db(c)
        c.commit()
        c.cursor().execute("SAVEPOINT test_auto_skips")
        yield c
        c.rollback()
        c.close()

    def _insert(self, conn, user_id="testuser", uri="spotify:track:T"):
        from spotify_skip_tracker.smart_skipper import log_auto_skip
        log_auto_skip(
            conn,
            uri=uri, title="Test", artists="Artist",
            context_uri=None, skip_rate=0.9,
            threshold=0.85, reason="test",
            user_id=user_id,
        )

    def test_auto_skips_har_user_id_kolonne(self, conn):
        from spotify_skip_tracker.database import execute
        row = execute(conn, """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'auto_skips' AND column_name = 'user_id'
        """).fetchone()
        assert row is not None

    def test_lagrer_user_id_korrekt(self, conn):
        from spotify_skip_tracker.database import execute
        self._insert(conn, user_id="alice")
        row = execute(
            conn,
            "SELECT user_id FROM auto_skips WHERE user_id = 'alice' LIMIT 1",
        ).fetchone()
        assert row is not None
        assert row[0] == "alice"

    def test_to_brukere_er_isolert(self, conn):
        from spotify_skip_tracker.database import execute
        self._insert(conn, user_id="alice", uri="spotify:track:A")
        self._insert(conn, user_id="bob",   uri="spotify:track:B")

        alice_rows = execute(
            conn,
            "SELECT uri FROM auto_skips WHERE user_id = 'alice'",
        ).fetchall()
        bob_rows = execute(
            conn,
            "SELECT uri FROM auto_skips WHERE user_id = 'bob'",
        ).fetchall()

        assert len(alice_rows) == 1 and alice_rows[0][0] == "spotify:track:A"
        assert len(bob_rows)  == 1 and bob_rows[0][0]  == "spotify:track:B"


# ---------------------------------------------------------------------------
# TestSmartSkipperAPIHistory — Flask test client
# ---------------------------------------------------------------------------

@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setattr("spotify_skip_tracker.web.DASHBOARD_PASSWORD", None)
    monkeypatch.setattr("spotify_skip_tracker.config.DASHBOARD_PASSWORD", None)
    monkeypatch.setattr(
        "spotify_skip_tracker.web._get_owner_user_id", lambda: "owner"
    )
    monkeypatch.setattr("spotify_skip_tracker.web._owner_user_id_cache", None)

    from spotify_skip_tracker.web import create_flask_app
    flask_app = create_flask_app()
    flask_app.config.update(
        TESTING=True, SECRET_KEY="test",
        SESSION_COOKIE_SECURE=False, SESSION_COOKIE_SAMESITE="Lax",
    )
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


class TestSmartSkipperAPIHistory:

    def _mock_smart_skipper(self, monkeypatch, config_row, history_rows):
        """Patcher pooled_connection slik at /api/smart-skipper returnerer testdata."""
        call_count = [0]

        class _FakeCursor:
            def __init__(self_, rows):
                self_._rows = rows
                self_._one = rows[0] if rows else None
            def fetchone(self_): return self_._one
            def fetchall(self_): return self_._rows

        class _FakeConn:
            def cursor(self_): return None

        executed_queries = []

        def fake_execute(conn, sql, params=()):
            executed_queries.append((sql.strip(), params))
            call_count[0] += 1
            # ensure_user_smart_skipper_config er patched til no-op,
            # så første execute-kall er config-SELECT, andre er history-SELECT.
            if call_count[0] == 1:
                return _FakeCursor([config_row] if config_row else [])
            # history SELECT
            return _FakeCursor(history_rows)

        class _FakeCM:
            def __enter__(self_): return _FakeConn()
            def __exit__(self_, *a): pass

        monkeypatch.setattr("spotify_skip_tracker.web.execute", fake_execute)
        monkeypatch.setattr("spotify_skip_tracker.web.pooled_connection", lambda: _FakeCM())
        monkeypatch.setattr(
            "spotify_skip_tracker.web.ensure_user_smart_skipper_config",
            lambda conn, uid: None,
        )
        return executed_queries

    def test_historikk_filtrerer_paa_user_id(self, client, monkeypatch):
        """Verifiserer at user_id sendes som parameter til auto_skips-spørringen."""
        from datetime import datetime, timezone

        config_row = (False, 0.85, 3, 5, True)
        history_rows = []

        executed = self._mock_smart_skipper(monkeypatch, config_row, history_rows)

        with client.session_transaction() as sess:
            sess["user_id"] = "owner"

        resp = client.get("/api/smart-skipper")
        assert resp.status_code == 200

        # Finn auto_skips-spørringen og sjekk at user_id er med
        auto_skips_queries = [
            (sql, params) for sql, params in executed
            if "auto_skips" in sql
        ]
        assert len(auto_skips_queries) >= 1
        _, params = auto_skips_queries[0]
        assert "owner" in params

    def test_tom_historikk_returnerer_tom_liste(self, client, monkeypatch):
        config_row = (False, 0.85, 3, 5, True)
        self._mock_smart_skipper(monkeypatch, config_row, [])

        with client.session_transaction() as sess:
            sess["user_id"] = "owner"

        data = client.get("/api/smart-skipper").get_json()
        assert data["history"] == []
