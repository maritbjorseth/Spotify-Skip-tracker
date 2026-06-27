"""
Tester for Steg 5 i multi-user-migreringen: tracker_manager og per-bruker polling.

Dekker:
  - ensure_tracker_running() starter ny tråd, er idempotent
  - tracker_manager() starter tråder for alle brukere i user_tokens
  - tracker_manager() kaller _bootstrap_and_start() ved tom user_tokens + env-var
  - tracker_manager() logger advarsel ved tom DB og ingen env-var
  - polling_loop(user_id) avslutter rent ved RuntimeError (manglende creds)
  - polling_loop(user_id) avslutter rent og markerer token ved 401

Alle tester kjøres uten ekte DB eller Spotify API (mocking).
"""

import threading
import time
import unittest.mock

import pytest


# ---------------------------------------------------------------------------
# TestEnsureTrackerRunning
# ---------------------------------------------------------------------------

class TestEnsureTrackerRunning:

    def setup_method(self):
        """Rydd _active_trackers mellom tester."""
        import spotify_skip_tracker.tracker as tracker_mod
        tracker_mod._active_trackers.clear()

    def test_starter_ny_traad_for_ny_bruker(self, monkeypatch):
        from spotify_skip_tracker.tracker import ensure_tracker_running, _active_trackers

        started = []

        def fake_loop(uid):
            started.append(uid)
            time.sleep(0.05)

        monkeypatch.setattr("spotify_skip_tracker.tracker.polling_loop", fake_loop)
        ensure_tracker_running("alice")

        time.sleep(0.02)
        assert "alice" in _active_trackers
        assert _active_trackers["alice"].is_alive()
        assert "alice" in started

    def test_starter_ikke_duplikat_traad(self, monkeypatch):
        from spotify_skip_tracker.tracker import ensure_tracker_running, _active_trackers

        call_count = [0]

        def fake_loop(uid):
            call_count[0] += 1
            time.sleep(0.1)

        monkeypatch.setattr("spotify_skip_tracker.tracker.polling_loop", fake_loop)

        ensure_tracker_running("bob")
        ensure_tracker_running("bob")  # Skal ikke starte ny tråd
        ensure_tracker_running("bob")  # Skal ikke starte ny tråd

        time.sleep(0.02)
        assert call_count[0] == 1  # Kun én tråd startet

    def test_starter_ny_traad_etter_at_gammel_er_ferdig(self, monkeypatch):
        from spotify_skip_tracker.tracker import ensure_tracker_running, _active_trackers

        call_count = [0]

        def fast_loop(uid):
            call_count[0] += 1
            # Avslutter umiddelbart

        monkeypatch.setattr("spotify_skip_tracker.tracker.polling_loop", fast_loop)

        ensure_tracker_running("charlie")
        time.sleep(0.05)  # La tråden avslutte

        ensure_tracker_running("charlie")  # Skal starte ny
        time.sleep(0.05)

        assert call_count[0] == 2

    def test_isolerte_traader_per_bruker(self, monkeypatch):
        from spotify_skip_tracker.tracker import ensure_tracker_running, _active_trackers

        started_users = []

        def fake_loop(uid):
            started_users.append(uid)
            time.sleep(0.1)

        monkeypatch.setattr("spotify_skip_tracker.tracker.polling_loop", fake_loop)

        ensure_tracker_running("user1")
        ensure_tracker_running("user2")
        ensure_tracker_running("user3")

        time.sleep(0.02)
        assert set(started_users) == {"user1", "user2", "user3"}
        assert len(_active_trackers) == 3


# ---------------------------------------------------------------------------
# TestTrackerManager
# ---------------------------------------------------------------------------

class TestTrackerManager:

    def setup_method(self):
        import spotify_skip_tracker.tracker as tracker_mod
        tracker_mod._active_trackers.clear()

    def _make_list_users_patch(self, monkeypatch, user_ids):
        """Patcher list_active_user_ids og connect() slik at ingen ekte DB trengs."""
        mock_conn = unittest.mock.MagicMock()
        monkeypatch.setattr(
            "spotify_skip_tracker.tracker.connect",
            lambda: mock_conn,
        )
        monkeypatch.setattr(
            "spotify_skip_tracker.tracker.list_active_user_ids",
            lambda conn: user_ids,
        )

    def test_starter_traader_for_alle_kjente_brukere(self, monkeypatch):
        from spotify_skip_tracker.tracker import tracker_manager, _active_trackers

        started = []

        def fake_loop(uid):
            started.append(uid)
            time.sleep(0.1)

        self._make_list_users_patch(monkeypatch, ["alice", "bob"])
        monkeypatch.setattr("spotify_skip_tracker.tracker.polling_loop", fake_loop)

        tracker_manager()
        time.sleep(0.02)

        assert set(started) == {"alice", "bob"}

    def test_tom_user_tokens_med_env_var_kaller_bootstrap(self, monkeypatch):
        from spotify_skip_tracker.tracker import tracker_manager

        bootstrap_called = [False]

        def fake_bootstrap():
            bootstrap_called[0] = True

        self._make_list_users_patch(monkeypatch, [])
        monkeypatch.setattr(
            "spotify_skip_tracker.config.SPOTIFY_REFRESH_TOKEN", "AQD_token"
        )
        monkeypatch.setattr(
            "spotify_skip_tracker.tracker._bootstrap_and_start", fake_bootstrap
        )

        tracker_manager()
        assert bootstrap_called[0] is True

    def test_tom_user_tokens_uten_env_var_logger_advarsel(self, monkeypatch, caplog):
        from spotify_skip_tracker.tracker import tracker_manager
        import logging

        self._make_list_users_patch(monkeypatch, [])
        monkeypatch.setattr("spotify_skip_tracker.config.SPOTIFY_REFRESH_TOKEN", None)
        monkeypatch.setattr(
            "spotify_skip_tracker.tracker.SPOTIFY_REFRESH_TOKEN", None,
            raising=False,
        )

        with caplog.at_level(logging.WARNING, logger="spotify_skip_tracker.tracker"):
            tracker_manager()

        assert any("ingen brukere" in r.message.lower() for r in caplog.records)

    def test_db_feil_ved_oppstart_krasjer_ikke(self, monkeypatch):
        """DB-feil i tracker_manager() skal logges men ikke krasje prosessen."""
        from spotify_skip_tracker.tracker import tracker_manager

        monkeypatch.setattr(
            "spotify_skip_tracker.tracker.connect",
            lambda: (_ for _ in ()).throw(RuntimeError("DB nede")),
        )
        monkeypatch.setattr("spotify_skip_tracker.config.SPOTIFY_REFRESH_TOKEN", None)
        monkeypatch.setattr(
            "spotify_skip_tracker.tracker.SPOTIFY_REFRESH_TOKEN", None,
            raising=False,
        )

        # Skal ikke kaste exception
        tracker_manager()


# ---------------------------------------------------------------------------
# TestPollingLoopExit
# ---------------------------------------------------------------------------

class TestPollingLoopExit:
    """
    Tester at polling_loop(user_id) avslutter korrekt i feilsituasjoner.
    Bruker korte-livede tråder med event-signalering.
    """

    def test_avslutter_ved_manglende_creds(self, monkeypatch):
        """RuntimeError fra load_creds() skal avslutte tråden rent."""
        from spotify_skip_tracker.tracker import polling_loop

        monkeypatch.setattr(
            "spotify_skip_tracker.tracker.load_creds",
            lambda uid: (_ for _ in ()).throw(
                RuntimeError("Ingen token funnet i databasen for bruker 'ghost'")
            ),
        )

        done = threading.Event()
        result = [None]

        def run():
            try:
                polling_loop("ghost")
                result[0] = "exited_cleanly"
            except Exception as e:
                result[0] = f"exception: {e}"
            finally:
                done.set()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        assert done.wait(timeout=2.0), "Tråden avsluttet ikke innen 2 sekunder"
        assert result[0] == "exited_cleanly"

    def test_avslutter_ved_401_fra_token_refresh(self, monkeypatch):
        """HTTP 401 fra Spotify token-endepunktet skal avslutte tråden."""
        import requests as _req
        from spotify_skip_tracker.tracker import polling_loop

        # Simuler gyldig creds-lasting
        monkeypatch.setattr(
            "spotify_skip_tracker.tracker.load_creds",
            lambda uid: {
                "client_id": "cid", "client_secret": "csec",
                "refresh_token": "rev_token", "access_token": "",
                "expires_at": 0, "user_id": uid,
            },
        )

        # Simuler 401 fra token-endepunktet
        mock_resp = unittest.mock.MagicMock()
        mock_resp.status_code = 401
        http_error = _req.HTTPError(response=mock_resp)

        monkeypatch.setattr(
            "spotify_skip_tracker.tracker.get_access_token",
            lambda creds: (_ for _ in ()).throw(http_error),
        )

        # mark_token_invalid trenger en DB-tilkobling — mock den
        monkeypatch.setattr(
            "spotify_skip_tracker.tracker.connect",
            lambda: unittest.mock.MagicMock(),
        )
        monkeypatch.setattr(
            "spotify_skip_tracker.tracker.mark_token_invalid",
            lambda conn, uid: None,
        )

        done = threading.Event()
        result = [None]

        def run():
            try:
                polling_loop("revoked_user")
                result[0] = "exited_cleanly"
            except Exception as e:
                result[0] = f"exception: {e}"
            finally:
                done.set()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        assert done.wait(timeout=2.0), "Tråden avsluttet ikke innen 2 sekunder"
        assert result[0] == "exited_cleanly"

    def test_avslutter_ved_400_ugyldig_refresh_token(self, monkeypatch):
        """HTTP 400 (invalid_grant) skal også avslutte tråden."""
        import requests as _req
        from spotify_skip_tracker.tracker import polling_loop

        monkeypatch.setattr(
            "spotify_skip_tracker.tracker.load_creds",
            lambda uid: {
                "client_id": "cid", "client_secret": "csec",
                "refresh_token": "bad_token", "access_token": "",
                "expires_at": 0,
            },
        )
        mock_resp = unittest.mock.MagicMock()
        mock_resp.status_code = 400
        monkeypatch.setattr(
            "spotify_skip_tracker.tracker.get_access_token",
            lambda creds: (_ for _ in ()).throw(_req.HTTPError(response=mock_resp)),
        )
        monkeypatch.setattr(
            "spotify_skip_tracker.tracker.connect",
            lambda: unittest.mock.MagicMock(),
        )
        monkeypatch.setattr(
            "spotify_skip_tracker.tracker.mark_token_invalid",
            lambda conn, uid: None,
        )

        done = threading.Event()

        def run():
            polling_loop("bad_token_user")
            done.set()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        assert done.wait(timeout=2.0)
