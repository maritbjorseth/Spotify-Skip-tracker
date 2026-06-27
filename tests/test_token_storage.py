"""
Tester for Steg 1 i multi-user-migreringen:
  - token_crypto.py  — kryptering og dekryptering av refresh-tokens
  - database.py      — CRUD-funksjoner for user_tokens-tabellen
  - spotify_api.py   — load_creds() og save_creds() med DB-sti

TestTokenCrypto kjøres alltid (ingen DB eller nettverkstilgang nødvendig).
TestUserTokensDB og TestLoadCredsDB krever TEST_DATABASE_URL og hoppes
over dersom den ikke er satt — konsekvent med test_stats.py.
"""

import os
import time
import unittest.mock

import pytest

# ---------------------------------------------------------------------------
# Felles fixtures
# ---------------------------------------------------------------------------

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")

needs_db = pytest.mark.skipif(
    not TEST_DB_URL,
    reason="TEST_DATABASE_URL ikke satt — sett en separat testdatabase for å kjøre disse",
)

# Gyldig Fernet-testnøkkel (generert én gang, hardkodet for reproduserbarhet)
_TEST_KEY = "y5jXnMnbT5WfQHWnO1SyI5kqL3c9nV_mzT_cJ1ZdcPs="


# ---------------------------------------------------------------------------
# TestTokenCrypto — alltid kjørt, ingen eksterne avhengigheter
# ---------------------------------------------------------------------------

class TestTokenCrypto:
    """
    Tester kryptering og dekryptering i token_crypto.py.

    Alle tester kjøres uten database og uten nettverkstilgang.
    TOKEN_ENCRYPTION_KEY patches via unittest.mock for å teste
    både kryptert og ukryptert modus.
    """

    def _with_key(self):
        """
        Kontekstbehandler som setter en gyldig testnøkkel.

        Patcher spotify_skip_tracker.config.TOKEN_ENCRYPTION_KEY fordi
        token_crypto.py leser nøkkelen lazily via 'from .config import ...'
        inne i _get_fernet() ved hvert kall — ikke ved import-tid.
        """
        return unittest.mock.patch(
            "spotify_skip_tracker.config.TOKEN_ENCRYPTION_KEY",
            _TEST_KEY,
        )

    def _without_key(self):
        """Kontekstbehandler som simulerer at nøkkelen ikke er satt."""
        return unittest.mock.patch(
            "spotify_skip_tracker.config.TOKEN_ENCRYPTION_KEY",
            None,
        )

    # --- Kryptert modus (TOKEN_ENCRYPTION_KEY satt) ---

    def test_encrypt_decrypt_roundtrip(self):
        """encrypt → decrypt skal returnere original streng."""
        from spotify_skip_tracker.token_crypto import encrypt_token, decrypt_token
        original = "AQD_refresh_token_abc123"
        with self._with_key():
            stored = encrypt_token(original)
            result = decrypt_token(stored)
        assert result == original

    def test_encrypted_har_enc_prefiks(self):
        """Kryptert token skal starte med 'enc:'."""
        from spotify_skip_tracker.token_crypto import encrypt_token
        with self._with_key():
            stored = encrypt_token("some_token")
        assert stored.startswith("enc:")

    def test_kryptert_token_er_ikke_lesbar_i_klartekst(self):
        """Selve token-strengen skal ikke dukke opp i den krypterte outputen."""
        from spotify_skip_tracker.token_crypto import encrypt_token
        secret = "super_secret_refresh_token"
        with self._with_key():
            stored = encrypt_token(secret)
        assert secret not in stored

    def test_to_krypteringer_gir_ulike_ciphertekster(self):
        """Fernet bruker tilfeldig IV — to krypteringer av samme plaintext er ulike."""
        from spotify_skip_tracker.token_crypto import encrypt_token
        token = "same_token"
        with self._with_key():
            enc1 = encrypt_token(token)
            enc2 = encrypt_token(token)
        assert enc1 != enc2

    def test_feil_nokkel_gir_exception_ved_dekryptering(self):
        """Dekryptering med feil nøkkel skal kaste InvalidToken."""
        from cryptography.fernet import InvalidToken
        from spotify_skip_tracker.token_crypto import encrypt_token, decrypt_token

        # Krypter med testnøkkel
        with self._with_key():
            stored = encrypt_token("my_token")

        # Forsøk å dekryptere med en annen nøkkel
        from cryptography.fernet import Fernet
        wrong_key = Fernet.generate_key().decode()
        with unittest.mock.patch(
            "spotify_skip_tracker.config.TOKEN_ENCRYPTION_KEY", wrong_key
        ):
            with pytest.raises(InvalidToken):
                decrypt_token(stored)

    # --- Klartekst-modus (TOKEN_ENCRYPTION_KEY ikke satt) ---

    def test_uten_nokkel_lagres_med_plain_prefiks(self):
        """Uten nøkkel skal encrypt_token returnere 'plain:'-prefiks."""
        from spotify_skip_tracker.token_crypto import encrypt_token
        with self._without_key():
            stored = encrypt_token("my_token")
        assert stored == "plain:my_token"

    def test_uten_nokkel_roundtrip(self):
        """Krypter og dekrypter uten nøkkel skal fungere."""
        from spotify_skip_tracker.token_crypto import encrypt_token, decrypt_token
        original = "plaintext_token"
        with self._without_key():
            stored = encrypt_token(original)
            result = decrypt_token(stored)
        assert result == original

    def test_dekrypter_plain_prefiks(self):
        """'plain:'-prefiks skal strippes og resten returneres."""
        from spotify_skip_tracker.token_crypto import decrypt_token
        result = decrypt_token("plain:AQD_my_token")
        assert result == "AQD_my_token"

    def test_dekrypter_legacy_ingen_prefiks(self):
        """Token uten prefiks (legacy) skal returneres uendret."""
        from spotify_skip_tracker.token_crypto import decrypt_token
        result = decrypt_token("legacy_token_no_prefix")
        assert result == "legacy_token_no_prefix"

    def test_kryptert_token_mangler_nokkel_gir_runtime_error(self):
        """Forsøk på å dekryptere enc:-token uten nøkkel skal gi RuntimeError."""
        from spotify_skip_tracker.token_crypto import encrypt_token, decrypt_token

        with self._with_key():
            stored = encrypt_token("my_token")

        with self._without_key():
            with pytest.raises(RuntimeError, match="TOKEN_ENCRYPTION_KEY"):
                decrypt_token(stored)

    def test_ugyldig_nokkel_gir_value_error(self):
        """En ugyldig nøkkel (ikke gyldig base64) skal gi ValueError."""
        from spotify_skip_tracker.token_crypto import encrypt_token
        with unittest.mock.patch(
            "spotify_skip_tracker.config.TOKEN_ENCRYPTION_KEY",
            "ikke_en_gyldig_fernet_nokkel!!",
        ):
            with pytest.raises(ValueError, match="ugyldig"):
                encrypt_token("token")

    def test_tom_streng_roundtrip(self):
        """Tom streng skal krypteres og dekrypteres uten feil."""
        from spotify_skip_tracker.token_crypto import encrypt_token, decrypt_token
        with self._with_key():
            stored = encrypt_token("")
            result = decrypt_token(stored)
        assert result == ""

    def test_unicode_token_roundtrip(self):
        """Unicode i token-streng skal håndteres korrekt."""
        from spotify_skip_tracker.token_crypto import encrypt_token, decrypt_token
        token = "AQD_æøå_日本語_token"
        with self._with_key():
            stored = encrypt_token(token)
            result = decrypt_token(stored)
        assert result == token


# ---------------------------------------------------------------------------
# TestUserTokensDB — krever TEST_DATABASE_URL
# ---------------------------------------------------------------------------

@needs_db
class TestUserTokensDB:
    """
    Integrasjonstester for CRUD-funksjonene i database.py.

    Bruker en isolert transaksjons-savepoint (rulles tilbake etter hver test)
    mot TEST_DATABASE_URL — aldri mot produksjonsdatabasen.
    """

    @pytest.fixture()
    def conn(self):
        import psycopg2
        from spotify_skip_tracker.database import _clean_dsn, init_db

        c = psycopg2.connect(_clean_dsn(TEST_DB_URL))
        c.autocommit = False
        init_db(c)
        c.commit()
        c.cursor().execute("SAVEPOINT test_token_isolation")
        yield c
        c.rollback()
        c.close()

    def _insert_token(
        self, conn, user_id="testuser",
        refresh_enc="plain:test_refresh", access=None, expires=None,
        display_name=None,
    ):
        from spotify_skip_tracker.database import upsert_user_token
        upsert_user_token(
            conn,
            user_id=user_id,
            refresh_token_encrypted=refresh_enc,
            access_token=access,
            expires_at=expires,
            display_name=display_name,
        )

    # --- get_user_token_row ---

    def test_get_ukjent_bruker_returnerer_none(self, conn):
        from spotify_skip_tracker.database import get_user_token_row
        assert get_user_token_row(conn, "ukjent_bruker") is None

    def test_upsert_og_get_roundtrip(self, conn):
        from spotify_skip_tracker.database import get_user_token_row
        self._insert_token(
            conn,
            user_id="alice",
            refresh_enc="enc:some_encrypted_token",
            access="short_lived_token",
            expires=9999999999.0,
            display_name="Alice",
        )
        row = get_user_token_row(conn, "alice")
        assert row is not None
        assert row["user_id"] == "alice"
        assert row["refresh_token"] == "enc:some_encrypted_token"
        assert row["access_token"] == "short_lived_token"
        assert row["expires_at"] == pytest.approx(9999999999.0)
        assert row["display_name"] == "Alice"

    def test_upsert_oppdaterer_eksisterende_refresh_token(self, conn):
        from spotify_skip_tracker.database import get_user_token_row, upsert_user_token

        self._insert_token(conn, refresh_enc="plain:old_token")
        upsert_user_token(
            conn,
            user_id="testuser",
            refresh_token_encrypted="plain:new_token",
        )
        row = get_user_token_row(conn, "testuser")
        assert row["refresh_token"] == "plain:new_token"

    def test_upsert_bevarer_display_name_ved_none(self, conn):
        """ON CONFLICT DO UPDATE bruker COALESCE — eksisterende display_name beholdes."""
        from spotify_skip_tracker.database import get_user_token_row, upsert_user_token

        self._insert_token(conn, display_name="Bob")
        # Oppdater uten display_name (None)
        upsert_user_token(
            conn,
            user_id="testuser",
            refresh_token_encrypted="plain:new_refresh",
            display_name=None,
        )
        row = get_user_token_row(conn, "testuser")
        assert row["display_name"] == "Bob"

    # --- update_access_token_cache ---

    def test_update_access_token_cache(self, conn):
        from spotify_skip_tracker.database import (
            get_user_token_row, update_access_token_cache,
        )

        self._insert_token(conn, access="old_access", expires=1000.0)
        update_access_token_cache(conn, "testuser", "new_access", 2000.0)

        row = get_user_token_row(conn, "testuser")
        assert row["access_token"] == "new_access"
        assert row["expires_at"] == pytest.approx(2000.0)
        # refresh_token skal være uendret
        assert row["refresh_token"] == "plain:test_refresh"

    # --- list_active_user_ids ---

    def test_list_active_user_ids_tom_tabell(self, conn):
        from spotify_skip_tracker.database import list_active_user_ids
        assert list_active_user_ids(conn) == []

    def test_list_active_user_ids_returnerer_alle(self, conn):
        from spotify_skip_tracker.database import list_active_user_ids

        self._insert_token(conn, user_id="user_a")
        self._insert_token(conn, user_id="user_b")
        self._insert_token(conn, user_id="user_c")
        result = list_active_user_ids(conn)
        assert set(result) == {"user_a", "user_b", "user_c"}

    # --- mark_token_invalid ---

    def test_mark_token_invalid_nullstiller_access_token(self, conn):
        from spotify_skip_tracker.database import get_user_token_row, mark_token_invalid

        self._insert_token(conn, access="valid_access", expires=9999999999.0)
        mark_token_invalid(conn, "testuser")

        row = get_user_token_row(conn, "testuser")
        assert row["access_token"] is None
        assert row["expires_at"] is None
        # refresh_token skal fortsatt finnes
        assert row["refresh_token"] == "plain:test_refresh"

    def test_mark_token_invalid_ukjent_bruker_er_no_op(self, conn):
        """Kall på ukjent bruker skal ikke kaste exception."""
        from spotify_skip_tracker.database import mark_token_invalid
        mark_token_invalid(conn, "finnes_ikke")  # skal ikke kaste


# ---------------------------------------------------------------------------
# TestLoadCredsDB — krever TEST_DATABASE_URL
# ---------------------------------------------------------------------------

@needs_db
class TestLoadCredsDB:
    """
    Tester load_creds(user_id) og save_creds(creds) mot ekte Postgres.

    Verifiserer at data flyter riktig mellom spotify_api.py og databasen,
    inkludert at kryptering/dekryptering er koblet korrekt.
    """

    @pytest.fixture()
    def isolated_db(self, monkeypatch):
        """
        Patcher DATABASE_URL til å peke på testdatabasen, slik at connect()
        inne i load_creds() og save_creds() bruker testdatabasen og ikke
        produksjonsdatabasen.
        """
        import psycopg2
        from spotify_skip_tracker.database import _clean_dsn, init_db

        monkeypatch.setenv("DATABASE_URL", TEST_DB_URL)
        # Patch config.DATABASE_URL og database.DATABASE_URL
        monkeypatch.setattr("spotify_skip_tracker.config.DATABASE_URL", TEST_DB_URL)
        monkeypatch.setattr("spotify_skip_tracker.database.DATABASE_URL", TEST_DB_URL)

        # Sett TOKEN_ENCRYPTION_KEY for disse testene
        monkeypatch.setattr(
            "spotify_skip_tracker.token_crypto.TOKEN_ENCRYPTION_KEY", _TEST_KEY
        )

        conn = psycopg2.connect(_clean_dsn(TEST_DB_URL))
        conn.autocommit = False
        init_db(conn)
        conn.commit()

        yield conn

        # Rydd opp user_tokens-rader opprettet av disse testene
        conn.rollback()
        conn.execute = None  # hindre videre bruk
        conn.close()

    def test_load_creds_ukjent_bruker_gir_runtime_error(self, isolated_db):
        from spotify_skip_tracker.spotify_api import load_creds
        with pytest.raises(RuntimeError, match="Ingen token funnet"):
            load_creds(user_id="ukjent_bruker_xyz")

    def test_save_og_load_roundtrip(self, isolated_db):
        """save_creds → load_creds skal returnere riktig plaintext refresh-token."""
        import psycopg2
        from spotify_skip_tracker.database import _clean_dsn, upsert_user_token
        from spotify_skip_tracker.spotify_api import load_creds
        from spotify_skip_tracker.token_crypto import encrypt_token

        user_id = "roundtrip_test_user"
        original_refresh = "AQD_roundtrip_token_xyz"

        # Lagre direkte i DB (simulerer det OAuth-callback vil gjøre i Steg 2)
        conn2 = psycopg2.connect(_clean_dsn(TEST_DB_URL))
        upsert_user_token(
            conn2,
            user_id=user_id,
            refresh_token_encrypted=encrypt_token(original_refresh),
            access_token="short_lived",
            expires_at=time.time() + 3600,
        )
        conn2.close()

        # load_creds skal dekryptere og returnere plaintext
        creds = load_creds(user_id=user_id)
        assert creds["refresh_token"] == original_refresh
        assert creds["user_id"] == user_id
        assert creds["access_token"] == "short_lived"

        # Rydd opp
        import psycopg2
        c = psycopg2.connect(_clean_dsn(TEST_DB_URL))
        c.cursor().execute("DELETE FROM user_tokens WHERE user_id = %s", (user_id,))
        c.commit()
        c.close()
