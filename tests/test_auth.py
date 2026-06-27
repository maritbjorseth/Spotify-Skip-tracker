"""
Tester for Steg 2 i multi-user-migreringen: session bærer user_id.

Dekker:
  - require_auth-dekoratoren (401 uten session, 200 med session)
  - /api/auth/status (åpen modus og passord-modus)
  - /api/auth/password (setter session['user_id'], rate limiting)
  - /api/auth/logout (tømmer session)
  - _resolve_user_id() (leser fra session, fallback i åpen modus)
  - auth_callback() (lagrer token i DB, setter session) — mocket Spotify API

Alle tester bruker Flask test client og monkeypatch.
Ingen eksterne nettverkskall og ingen ekte DB-tilkobling.
"""

import unittest.mock
import pytest


# ---------------------------------------------------------------------------
# Felles fixture: Flask test-app og client
# ---------------------------------------------------------------------------

@pytest.fixture()
def app(monkeypatch):
    """
    Oppretter Flask-appen med DASHBOARD_PASSWORD satt slik at
    autentisering er aktivert i de fleste tester.

    Patches:
      - DASHBOARD_PASSWORD = "testpassord"
      - _get_owner_user_id() → "owner_user"
      - pooled_connection() → no-op (unngår DB-avhengighet)
      - list_active_user_ids() → ["owner_user"] (for _get_owner_user_id DB-sti)
    """
    monkeypatch.setattr(
        "spotify_skip_tracker.config.DASHBOARD_PASSWORD", "testpassord"
    )
    monkeypatch.setattr(
        "spotify_skip_tracker.web.DASHBOARD_PASSWORD", "testpassord"
    )

    # Hindre at _get_owner_user_id() treffer ekte DB eller Spotify API
    monkeypatch.setattr(
        "spotify_skip_tracker.web._get_owner_user_id",
        lambda: "owner_user",
    )
    # Nullstill cache mellom tester
    monkeypatch.setattr("spotify_skip_tracker.web._owner_user_id_cache", None)

    from spotify_skip_tracker.web import create_flask_app
    flask_app = create_flask_app()
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"
    # Tillat cookies i test uten HTTPS
    flask_app.config["SESSION_COOKIE_SECURE"] = False
    flask_app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def open_app(monkeypatch):
    """Flask-app uten passord (åpen modus)."""
    monkeypatch.setattr("spotify_skip_tracker.config.DASHBOARD_PASSWORD", None)
    monkeypatch.setattr("spotify_skip_tracker.web.DASHBOARD_PASSWORD", None)
    monkeypatch.setattr(
        "spotify_skip_tracker.web._get_owner_user_id",
        lambda: "owner_user",
    )
    monkeypatch.setattr("spotify_skip_tracker.web._owner_user_id_cache", None)

    from spotify_skip_tracker.web import create_flask_app
    flask_app = create_flask_app()
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"
    flask_app.config["SESSION_COOKIE_SECURE"] = False
    flask_app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    return flask_app


@pytest.fixture()
def open_client(open_app):
    return open_app.test_client()


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
        # Patch compute_stats slik at vi ikke trenger ekte DB
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

    def test_aapen_modus_slipper_gjennom_uten_session(
        self, open_client, monkeypatch
    ):
        monkeypatch.setattr(
            "spotify_skip_tracker.web.compute_stats",
            lambda uid: {"total_plays": 0, "total_skips": 0},
        )
        resp = open_client.get("/api/stats")
        assert resp.status_code == 200

    def test_health_krever_ikke_innlogging(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# TestAuthStatus
# ---------------------------------------------------------------------------

class TestAuthStatus:

    def test_passord_modus_uten_session_returnerer_ikke_autentisert(self, client):
        resp = client.get("/api/auth/status")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["authenticated"] is False
        assert data["user_id"] is None

    def test_passord_modus_med_session_returnerer_autentisert(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = "testuser"
        resp = client.get("/api/auth/status")
        data = resp.get_json()
        assert data["authenticated"] is True
        assert data["user_id"] == "testuser"

    def test_aapen_modus_returnerer_alltid_autentisert(self, open_client):
        resp = open_client.get("/api/auth/status")
        data = resp.get_json()
        assert data["authenticated"] is True

    def test_aapen_modus_setter_user_id_i_session(self, open_client):
        """Første kall til /api/auth/status i åpen modus skal sette session['user_id']."""
        resp = open_client.get("/api/auth/status")
        data = resp.get_json()
        assert data["user_id"] == "owner_user"

    def test_aapen_modus_beholder_eksisterende_session_user_id(self, open_client):
        """Dersom session allerede har user_id, skal den beholdes."""
        with open_client.session_transaction() as sess:
            sess["user_id"] = "annen_bruker"
        resp = open_client.get("/api/auth/status")
        data = resp.get_json()
        assert data["user_id"] == "annen_bruker"


# ---------------------------------------------------------------------------
# TestAuthPassword
# ---------------------------------------------------------------------------

class TestAuthPassword:

    def test_riktig_passord_setter_user_id_i_session(self, client):
        resp = client.post(
            "/api/auth/password",
            json={"password": "testpassord"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

        # Verifiser at session har user_id
        with client.session_transaction() as sess:
            assert sess.get("user_id") == "owner_user"

    def test_feil_passord_returnerer_401(self, client):
        resp = client.post(
            "/api/auth/password",
            json={"password": "galt_passord"},
        )
        assert resp.status_code == 401
        assert "error" in resp.get_json()

    def test_feil_passord_setter_ikke_session(self, client):
        client.post("/api/auth/password", json={"password": "galt"})
        with client.session_transaction() as sess:
            assert "user_id" not in sess

    def test_aapen_modus_setter_session_uten_passord(self, open_client):
        resp = open_client.post("/api/auth/password", json={})
        assert resp.status_code == 200
        with open_client.session_transaction() as sess:
            assert sess.get("user_id") == "owner_user"

    def test_rate_limiting_etter_mange_forsok(self, client):
        """11 forsøk med feil passord skal gi 429 på det siste."""
        for _ in range(10):
            client.post("/api/auth/password", json={"password": "feil"})
        resp = client.post("/api/auth/password", json={"password": "feil"})
        assert resp.status_code == 429

    def test_rate_limit_blokkerer_ikke_riktig_passord_foerst(self, client):
        """Riktig passord på første forsøk skal alltid fungere."""
        resp = client.post(
            "/api/auth/password", json={"password": "testpassord"}
        )
        assert resp.status_code == 200

    def test_session_inneholder_ikke_authenticated_nykkel(self, client):
        """Den gamle 'authenticated'-nøkkelen skal ikke lenger brukes."""
        client.post("/api/auth/password", json={"password": "testpassord"})
        with client.session_transaction() as sess:
            assert "authenticated" not in sess
            assert "user_id" in sess


# ---------------------------------------------------------------------------
# TestAuthLogout
# ---------------------------------------------------------------------------

class TestAuthLogout:

    def test_logout_fjerner_user_id_fra_session(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = "testuser"
        client.post("/api/auth/logout")
        with client.session_transaction() as sess:
            assert "user_id" not in sess

    def test_logout_returnerer_success(self, client):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_etter_logout_er_beskyttede_ruter_blokkert(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = "testuser"
        client.post("/api/auth/logout")
        resp = client.get("/api/stats")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# TestAuthCallback
# ---------------------------------------------------------------------------

class TestAuthCallback:
    """
    Tester for /api/auth/callback.

    Spotify API-kall mockes. DB-kall mockes med unittest.mock.patch.
    """

    def _add_state(self, app):
        """Legger til en gyldig CSRF-state og returnerer den."""
        import spotify_skip_tracker.web as web_module
        state = "test_csrf_state_xyz"
        web_module._oauth_states.add(state)
        return state

    def _mock_spotify(self, monkeypatch, user_id="new_user", display_name="New User"):
        """
        Patcher http_requests.post (token-bytte) og http_requests.get (/v1/me).
        """
        import time

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
        resp = client.get(
            f"/api/auth/callback?error=access_denied&state={state}"
        )
        assert resp.status_code == 302
        assert "auth_error=1" in resp.headers["Location"]

    def test_vellykket_callback_setter_user_id_i_session(
        self, client, app, monkeypatch
    ):
        monkeypatch.setattr(
            "spotify_skip_tracker.web.REDIRECT_URI_WEB", "https://example.com/callback"
        )
        monkeypatch.setattr(
            "spotify_skip_tracker.web.SPOTIFY_CLIENT_ID", "client_id"
        )
        monkeypatch.setattr(
            "spotify_skip_tracker.web.SPOTIFY_CLIENT_SECRET", "client_secret"
        )
        self._mock_spotify(monkeypatch, user_id="new_user", display_name="New User")

        # Patcher upsert_user_token og encrypt_token — ingen ekte DB
        monkeypatch.setattr(
            "spotify_skip_tracker.web.upsert_user_token",
            lambda conn, **kwargs: None,
        )
        monkeypatch.setattr(
            "spotify_skip_tracker.web.encrypt_token",
            lambda t: f"plain:{t}",
        )

        # Mock pooled_connection som kontekstbehandler
        mock_conn = unittest.mock.MagicMock()
        mock_cm = unittest.mock.MagicMock()
        mock_cm.__enter__ = lambda s: mock_conn
        mock_cm.__exit__ = unittest.mock.MagicMock(return_value=False)
        monkeypatch.setattr(
            "spotify_skip_tracker.web.pooled_connection",
            lambda: mock_cm,
        )

        state = self._add_state(app)
        resp = client.get(f"/api/auth/callback?code=auth_code&state={state}")

        assert resp.status_code == 302
        assert "auth_error" not in resp.headers["Location"]

        with client.session_transaction() as sess:
            assert sess.get("user_id") == "new_user"

    def test_vellykket_callback_redirecter_til_frontend(
        self, client, app, monkeypatch
    ):
        monkeypatch.setattr(
            "spotify_skip_tracker.web.REDIRECT_URI_WEB", "https://example.com/cb"
        )
        monkeypatch.setattr("spotify_skip_tracker.web.SPOTIFY_CLIENT_ID", "cid")
        monkeypatch.setattr("spotify_skip_tracker.web.SPOTIFY_CLIENT_SECRET", "csec")
        monkeypatch.setattr("spotify_skip_tracker.web.FRONTEND_URL", "https://frontend.example.com")
        self._mock_spotify(monkeypatch)
        monkeypatch.setattr(
            "spotify_skip_tracker.web.upsert_user_token", lambda conn, **kw: None
        )
        monkeypatch.setattr(
            "spotify_skip_tracker.web.encrypt_token", lambda t: f"plain:{t}"
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
        assert "auth_error" not in resp.headers["Location"]

    def test_callback_uten_redirect_uri_web_gir_feil(self, client, app, monkeypatch):
        monkeypatch.setattr("spotify_skip_tracker.web.REDIRECT_URI_WEB", None)
        state = self._add_state(app)
        resp = client.get(f"/api/auth/callback?code=abc&state={state}")
        assert "auth_error=1" in resp.headers["Location"]
