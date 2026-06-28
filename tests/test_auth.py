"""
Tester for auth-logikken etter Spotify OAuth-only-refaktorering.

Dekker:
  - require_auth-dekoratoren (401 uten session, 200 med session)
  - /api/auth/status (returnerer authenticated basert utelukkende på session)
  - /api/auth/password (returnerer 410 — fjernet)
  - /api/auth/logout (tømmer session)
  - auth_callback() (lagrer token i DB, setter session) — mocket Spotify API

Alle tester bruker Flask test client og monkeypatch.
Ingen eksterne nettverkskall og ingen ekte DB-tilkobling.
"""

import unittest.mock
import pytest


# ---------------------------------------------------------------------------
# Felles fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    from spotify_skip_tracker.web import create_flask_app
    flask_app = create_flask_app()
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"
    flask_app.config["SESSION_COOKIE_SECURE"] = False
    flask_app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# TestRequireAuth
# ---------------------------------------------------------------------------

class TestRequireAuth:

    def test_beskyttet_rute_uten_session_returnerer_401(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "Ikke innlogget"

    def test_beskyttet_rute_med_user_id_i_session_slipper_gjennom(
        self, client, monkeypatch
    ):
        monkeypatch.setattr(
            "spotify_skip_tracker.web.compute_stats",
            lambda uid: {"total_plays": 0, "total_skips": 0},
        )
        with client.session_transaction() as sess:
            sess["user_id"] = "testuser"
        resp = client.get("/api/stats")
        assert resp.status_code == 200

    def test_beskyttet_rute_med_tom_user_id_returnerer_401(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = ""
        resp = client.get("/api/stats")
        assert resp.status_code == 401

    def test_health_krever_ikke_innlogging(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_auth_status_krever_ikke_innlogging(self, client):
        """auth/status er alltid åpent — brukes til å sjekke auth-tilstand."""
        resp = client.get("/api/auth/status")
        assert resp.status_code == 200

    def test_auth_login_krever_ikke_innlogging(self, client, monkeypatch):
        """auth/login starter OAuth-flyten — må alltid være tilgjengelig."""
        monkeypatch.setattr("spotify_skip_tracker.web.REDIRECT_URI_WEB", "https://ex.com/cb")
        monkeypatch.setattr("spotify_skip_tracker.web.SPOTIFY_CLIENT_ID", "cid")
        resp = client.get("/api/auth/login")
        assert resp.status_code == 302  # redirect til Spotify


# ---------------------------------------------------------------------------
# TestAuthStatus
# ---------------------------------------------------------------------------

class TestAuthStatus:

    def test_uten_session_returnerer_ikke_autentisert(self, client):
        resp = client.get("/api/auth/status")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["authenticated"] is False
        assert data["user_id"] is None

    def test_med_session_returnerer_autentisert_og_user_id(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = "alice"
        resp = client.get("/api/auth/status")
        data = resp.get_json()
        assert data["authenticated"] is True
        assert data["user_id"] == "alice"

    def test_ingen_auto_innlogging_uten_session(self, client):
        """Serveren skal ALDRI sette user_id automatisk uten OAuth."""
        client.get("/api/auth/status")
        with client.session_transaction() as sess:
            assert "user_id" not in sess


# ---------------------------------------------------------------------------
# TestAuthPassword — fjernet, returnerer 410
# ---------------------------------------------------------------------------

class TestAuthPassword:

    def test_returnerer_410_gone(self, client):
        resp = client.post("/api/auth/password", json={"password": "noe"})
        assert resp.status_code == 410

    def test_setter_ikke_session(self, client):
        client.post("/api/auth/password", json={"password": "noe"})
        with client.session_transaction() as sess:
            assert "user_id" not in sess


# ---------------------------------------------------------------------------
# TestAuthLogout
# ---------------------------------------------------------------------------

class TestAuthLogout:

    def test_logout_fjerner_user_id(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = "alice"
        client.post("/api/auth/logout")
        with client.session_transaction() as sess:
            assert "user_id" not in sess

    def test_logout_returnerer_success(self, client):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_etter_logout_er_beskyttede_ruter_blokkert(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = "alice"
        client.post("/api/auth/logout")
        resp = client.get("/api/stats")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# TestAuthCallback
# ---------------------------------------------------------------------------

class TestAuthCallback:

    def _add_state(self, app):
        import spotify_skip_tracker.web as web_module
        state = "test_csrf_state_xyz"
        web_module._oauth_states.add(state)
        return state

    def _mock_spotify(self, monkeypatch, user_id="new_user", display_name="New User"):
        def mock_post(*args, **kwargs):
            m = unittest.mock.MagicMock()
            m.raise_for_status = lambda: None
            m.json.return_value = {
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "expires_in": 3600,
            }
            return m

        def mock_get(url, *args, **kwargs):
            m = unittest.mock.MagicMock()
            m.raise_for_status = lambda: None
            m.json.return_value = {"id": user_id, "display_name": display_name}
            return m

        monkeypatch.setattr("spotify_skip_tracker.web.http_requests.post", mock_post)
        monkeypatch.setattr("spotify_skip_tracker.web.http_requests.get", mock_get)

    def test_callback_uten_gyldig_state_redirecter_med_feil(self, client):
        resp = client.get("/api/auth/callback?code=abc&state=ugyldig_state")
        assert resp.status_code == 302
        assert "auth_error=1" in resp.headers["Location"]

    def test_callback_med_error_param_redirecter_med_feil(self, client, app):
        state = self._add_state(app)
        resp = client.get(f"/api/auth/callback?error=access_denied&state={state}")
        assert resp.status_code == 302
        assert "auth_error=1" in resp.headers["Location"]

    def test_vellykket_callback_setter_user_id_i_session(
        self, client, app, monkeypatch
    ):
        monkeypatch.setattr("spotify_skip_tracker.web.REDIRECT_URI_WEB", "https://ex.com/cb")
        monkeypatch.setattr("spotify_skip_tracker.web.SPOTIFY_CLIENT_ID", "cid")
        monkeypatch.setattr("spotify_skip_tracker.web.SPOTIFY_CLIENT_SECRET", "csec")
        self._mock_spotify(monkeypatch, user_id="new_user")

        monkeypatch.setattr("spotify_skip_tracker.web.upsert_user_token", lambda conn, **kw: None)
        monkeypatch.setattr("spotify_skip_tracker.web.encrypt_token", lambda t: f"plain:{t}")
        monkeypatch.setattr(
            "spotify_skip_tracker.web.ensure_user_smart_skipper_config",
            lambda conn, uid: None,
        )
        mock_conn = unittest.mock.MagicMock()
        mock_cm = unittest.mock.MagicMock()
        mock_cm.__enter__ = lambda s: mock_conn
        mock_cm.__exit__ = unittest.mock.MagicMock(return_value=False)
        monkeypatch.setattr("spotify_skip_tracker.web.pooled_connection", lambda: mock_cm)

        state = self._add_state(app)
        resp = client.get(f"/api/auth/callback?code=auth_code&state={state}")

        assert resp.status_code == 302
        assert "auth_error" not in resp.headers["Location"]
        with client.session_transaction() as sess:
            assert sess.get("user_id") == "new_user"

    def test_vellykket_callback_redirecter_til_frontend(
        self, client, app, monkeypatch
    ):
        monkeypatch.setattr("spotify_skip_tracker.web.REDIRECT_URI_WEB", "https://ex.com/cb")
        monkeypatch.setattr("spotify_skip_tracker.web.SPOTIFY_CLIENT_ID", "cid")
        monkeypatch.setattr("spotify_skip_tracker.web.SPOTIFY_CLIENT_SECRET", "csec")
        monkeypatch.setattr("spotify_skip_tracker.web.FRONTEND_URL", "https://frontend.example.com")
        self._mock_spotify(monkeypatch)
        monkeypatch.setattr("spotify_skip_tracker.web.upsert_user_token", lambda conn, **kw: None)
        monkeypatch.setattr("spotify_skip_tracker.web.encrypt_token", lambda t: f"plain:{t}")
        monkeypatch.setattr(
            "spotify_skip_tracker.web.ensure_user_smart_skipper_config",
            lambda conn, uid: None,
        )
        mock_conn = unittest.mock.MagicMock()
        mock_cm = unittest.mock.MagicMock()
        mock_cm.__enter__ = lambda s: mock_conn
        mock_cm.__exit__ = unittest.mock.MagicMock(return_value=False)
        monkeypatch.setattr("spotify_skip_tracker.web.pooled_connection", lambda: mock_cm)

        state = self._add_state(app)
        resp = client.get(f"/api/auth/callback?code=code&state={state}")

        assert resp.status_code == 302
        assert "https://frontend.example.com" in resp.headers["Location"]

    def test_callback_uten_redirect_uri_web_gir_feil(self, client, app, monkeypatch):
        monkeypatch.setattr("spotify_skip_tracker.web.REDIRECT_URI_WEB", None)
        state = self._add_state(app)
        resp = client.get(f"/api/auth/callback?code=abc&state={state}")
        assert "auth_error=1" in resp.headers["Location"]
