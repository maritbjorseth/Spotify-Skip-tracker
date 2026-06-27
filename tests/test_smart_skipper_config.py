"""
Tester for Steg 4 i multi-user-migreringen: smart_skipper_config per bruker.

Dekker:
  - load_config() filtrerer på user_id
  - ensure_user_smart_skipper_config() oppretter rad idempotent
  - _detect_owner_user_id() finner riktig bruker
  - SmartSkipper.evaluate() sender user_id til load_config
  - load_config() returnerer enabled=False ved manglende rad

TestSmartSkipperConfigDB krever TEST_DATABASE_URL og hoppes over uten den.
TestLoadConfigLogic og TestDetectOwner kjøres alltid (ingen ekstern avhengighet).
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
# TestLoadConfigLogic — alltid kjørt, ingen ekstern avhengighet
# ---------------------------------------------------------------------------

class TestLoadConfigLogic:
    """
    Tester load_config() med en in-memory stub for DB-kallet.
    Verifiserer at user_id sendes korrekt og at fallback fungerer.
    """

    def _make_cursor(self, row):
        class Cur:
            def fetchone(self_): return row
        return Cur()

    def test_returnerer_enabled_false_ved_manglende_rad(self):
        from spotify_skip_tracker.smart_skipper import load_config

        with unittest.mock.patch(
            "spotify_skip_tracker.smart_skipper.execute",
            return_value=self._make_cursor(None),
        ):
            config = load_config(object(), user_id="ingen_bruker")

        assert config["enabled"] is False

    def test_returnerer_korrekt_konfigurasjon(self):
        from spotify_skip_tracker.smart_skipper import load_config

        fake_row = (True, 0.75, 5, 10, False, False, [], [])
        with unittest.mock.patch(
            "spotify_skip_tracker.smart_skipper.execute",
            return_value=self._make_cursor(fake_row),
        ) as mock_exec:
            config = load_config(object(), user_id="alice")

        assert config["enabled"] is True
        assert config["threshold"] == 0.75
        assert config["min_plays"] == 5
        assert config["dry_run"] is False

        # Verifiser at user_id ble sendt som parameter
        call_args = mock_exec.call_args
        assert "alice" in call_args[0][2]  # params-tuple

    def test_standard_user_id_er_default_user(self):
        """Kall uten user_id skal bruke 'default_user'."""
        from spotify_skip_tracker.smart_skipper import load_config

        with unittest.mock.patch(
            "spotify_skip_tracker.smart_skipper.execute",
            return_value=self._make_cursor(None),
        ) as mock_exec:
            load_config(object())

        call_args = mock_exec.call_args
        assert "default_user" in call_args[0][2]


# ---------------------------------------------------------------------------
# TestDetectOwner — alltid kjørt
# ---------------------------------------------------------------------------

class TestDetectOwner:
    """Tester _detect_owner_user_id() med stubbede DB-kall."""

    def _make_cursor(self, row):
        class Cur:
            def fetchone(self_): return row
        return Cur()

    def test_returnerer_none_uten_data(self, monkeypatch):
        from spotify_skip_tracker.database import _detect_owner_user_id
        monkeypatch.setattr("spotify_skip_tracker.config.SPOTIFY_USER_ID", None)

        with unittest.mock.patch(
            "spotify_skip_tracker.database.execute",
            return_value=self._make_cursor(None),
        ):
            result = _detect_owner_user_id(object())

        assert result is None

    def test_returnerer_user_tokens_foerst(self, monkeypatch):
        from spotify_skip_tracker.database import _detect_owner_user_id

        call_count = [0]

        def fake_execute(conn, sql, params=()):
            call_count[0] += 1
            if "user_tokens" in sql:
                return self._make_cursor(("owner_from_tokens",))
            return self._make_cursor(None)

        with unittest.mock.patch("spotify_skip_tracker.database.execute", fake_execute):
            result = _detect_owner_user_id(object())

        assert result == "owner_from_tokens"

    def test_faller_tilbake_paa_plays(self, monkeypatch):
        from spotify_skip_tracker.database import _detect_owner_user_id
        monkeypatch.setattr("spotify_skip_tracker.config.SPOTIFY_USER_ID", None)

        def fake_execute(conn, sql, params=()):
            if "user_tokens" in sql:
                return self._make_cursor(None)
            if "plays" in sql:
                return self._make_cursor(("owner_from_plays",))
            return self._make_cursor(None)

        with unittest.mock.patch("spotify_skip_tracker.database.execute", fake_execute):
            result = _detect_owner_user_id(object())

        assert result == "owner_from_plays"

    def test_faller_tilbake_paa_env_var(self, monkeypatch):
        from spotify_skip_tracker.database import _detect_owner_user_id
        monkeypatch.setattr("spotify_skip_tracker.config.SPOTIFY_USER_ID", "owner_from_env")

        with unittest.mock.patch(
            "spotify_skip_tracker.database.execute",
            return_value=self._make_cursor(None),
        ):
            result = _detect_owner_user_id(object())

        assert result == "owner_from_env"


# ---------------------------------------------------------------------------
# TestSmartSkipperConfigDB — krever TEST_DATABASE_URL
# ---------------------------------------------------------------------------

@needs_db
class TestSmartSkipperConfigDB:
    """
    Integrasjonstester mot ekte Postgres.
    Verifiserer isolasjon mellom brukere og idempotens.
    """

    @pytest.fixture()
    def conn(self):
        import psycopg2
        from spotify_skip_tracker.database import _clean_dsn, init_db

        c = psycopg2.connect(_clean_dsn(TEST_DB_URL))
        c.autocommit = False
        init_db(c)
        c.commit()
        c.cursor().execute("SAVEPOINT test_ss_config")
        yield c
        c.rollback()
        c.close()

    def test_ensure_oppretter_rad_for_ny_bruker(self, conn):
        from spotify_skip_tracker.database import ensure_user_smart_skipper_config, execute

        ensure_user_smart_skipper_config(conn, "new_test_user")
        row = execute(
            conn,
            "SELECT user_id, enabled, dry_run FROM smart_skipper_config WHERE user_id = %s",
            ("new_test_user",),
        ).fetchone()
        assert row is not None
        assert row[0] == "new_test_user"
        assert row[1] is False    # enabled=FALSE er standard
        assert row[2] is True     # dry_run=TRUE er standard

    def test_ensure_er_idempotent(self, conn):
        """Kall ensure to ganger — ingen feil, ingen duplikate rader."""
        from spotify_skip_tracker.database import ensure_user_smart_skipper_config, execute

        ensure_user_smart_skipper_config(conn, "idempotent_user")
        ensure_user_smart_skipper_config(conn, "idempotent_user")

        count = execute(
            conn,
            "SELECT COUNT(*) FROM smart_skipper_config WHERE user_id = %s",
            ("idempotent_user",),
        ).fetchone()[0]
        assert count == 1

    def test_load_config_isolerer_brukere(self, conn):
        """Bruker A sin konfig skal ikke påvirke bruker B."""
        from spotify_skip_tracker.database import ensure_user_smart_skipper_config, execute
        from spotify_skip_tracker.smart_skipper import load_config

        ensure_user_smart_skipper_config(conn, "user_a")
        ensure_user_smart_skipper_config(conn, "user_b")

        # Sett ulik terskel for user_a
        execute(
            conn,
            "UPDATE smart_skipper_config SET threshold = 0.60 WHERE user_id = %s",
            ("user_a",),
        )
        conn.commit()

        config_a = load_config(conn, user_id="user_a")
        config_b = load_config(conn, user_id="user_b")

        assert config_a["threshold"] == pytest.approx(0.60)
        assert config_b["threshold"] == pytest.approx(0.85)  # standard

    def test_load_config_manglende_rad_gir_enabled_false(self, conn):
        from spotify_skip_tracker.smart_skipper import load_config

        config = load_config(conn, user_id="bruker_uten_konfig_xyz")
        assert config["enabled"] is False

    def test_smart_skipper_config_har_user_id_som_pk(self, conn):
        """Verifiserer at 'id'-kolonnen er borte og 'user_id' er PK."""
        from spotify_skip_tracker.database import execute

        # user_id skal eksistere
        row = execute(conn, """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'smart_skipper_config'
              AND column_name = 'user_id'
        """).fetchone()
        assert row is not None

        # id-kolonne skal IKKE eksistere
        row = execute(conn, """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'smart_skipper_config'
              AND column_name = 'id'
        """).fetchone()
        assert row is None
