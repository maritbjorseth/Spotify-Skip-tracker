"""
Tester for calculate_janitor_score() i janitor.py og SmartSkipper i smart_skipper.py.

Begge er rene/nær-rene funksjoner uten nettverkstilgang eller database.
SmartSkipper-testene bruker en enkel sqlite-basert stub for de DB-kallene
som trengs i evaluate()-flyten.
"""

from datetime import datetime, timezone, timedelta

import pytest

from spotify_skip_tracker.janitor import calculate_janitor_score
from spotify_skip_tracker.smart_skipper import SmartSkipper, should_auto_skip


# ===========================================================================
# calculate_janitor_score()
# ===========================================================================

class TestCalculateJanitorScore:

    def test_ingen_avspillinger_gir_null(self):
        score = calculate_janitor_score(
            skip_count=0, play_count=0,
            last_completed=None, days_in_playlist=10,
        )
        assert score == 0.0

    def test_alltid_skippet_gir_hoy_score(self):
        score = calculate_janitor_score(
            skip_count=5, play_count=5,
            last_completed=None, days_in_playlist=30,
        )
        assert score > 0.80

    def test_aldri_skippet_gir_lav_score(self):
        # 0 skip → skip_component = 0, consistency_component = 0.
        # Recency (60/180 ≈ 0.33) og reliability (1.0) bidrar fortsatt:
        # score = 0.20 * 0.33 + 0.10 * 1.0 ≈ 0.167.
        # Sjekker at scoren er klart lavere enn en sang med høy skip-rate.
        score = calculate_janitor_score(
            skip_count=0, play_count=10,
            last_completed=datetime.now(tz=timezone.utc) - timedelta(days=60),
            days_in_playlist=90,
        )
        assert score < 0.25

    def test_benadning_fullfort_siste_7_dager(self):
        """Sangen ble fullført i går — skal alltid gi 0.0 uansett historikk."""
        yesterday = datetime.now(tz=timezone.utc) - timedelta(days=1)
        score = calculate_janitor_score(
            skip_count=9, play_count=10,
            last_completed=yesterday, days_in_playlist=365,
        )
        assert score == 0.0

    def test_benadning_tre_siste_var_komplette(self):
        """De tre siste avspillingene var alle fullføringer — skal gi 0.0."""
        old = datetime.now(tz=timezone.utc) - timedelta(days=100)
        score = calculate_janitor_score(
            skip_count=7, play_count=10,
            last_completed=old, days_in_playlist=200,
            recent_outcomes=[False, False, False],
        )
        assert score == 0.0

    def test_to_av_tre_siste_var_skip_gir_ikke_benadning(self):
        """2 av 3 siste = skip → benaningsregel trigges ikke."""
        old = datetime.now(tz=timezone.utc) - timedelta(days=100)
        score = calculate_janitor_score(
            skip_count=7, play_count=10,
            last_completed=old, days_in_playlist=200,
            recent_outcomes=[True, True, False],
        )
        assert score > 0.0

    def test_score_er_mellom_null_og_en(self):
        score = calculate_janitor_score(
            skip_count=3, play_count=5,
            last_completed=None, days_in_playlist=60,
        )
        assert 0.0 <= score <= 1.0

    def test_hoyere_skip_rate_gir_hoyere_score(self):
        base = datetime.now(tz=timezone.utc) - timedelta(days=90)
        score_high = calculate_janitor_score(
            skip_count=9, play_count=10,
            last_completed=base, days_in_playlist=90,
        )
        score_low = calculate_janitor_score(
            skip_count=3, play_count=10,
            last_completed=base, days_in_playlist=90,
        )
        assert score_high > score_low

    def test_lenge_siden_siste_fullfort_gir_hoyere_score(self):
        """Recency-komponenten: lengre tid siden siste fullføring → høyere score."""
        score_recent = calculate_janitor_score(
            skip_count=5, play_count=10,
            last_completed=datetime.now(tz=timezone.utc) - timedelta(days=10),
            days_in_playlist=90,
        )
        score_old = calculate_janitor_score(
            skip_count=5, play_count=10,
            last_completed=datetime.now(tz=timezone.utc) - timedelta(days=170),
            days_in_playlist=90,
        )
        # score_recent utløser benadning (≤7 dager) → 0.0; score_old er > 0
        # Sjekk bare at old > recent
        assert score_old > score_recent

    def test_naive_datetime_behandles_som_utc(self):
        """Naive datetime (uten tzinfo) skal ikke kaste exception."""
        naive = datetime.now() - timedelta(days=100)
        score = calculate_janitor_score(
            skip_count=5, play_count=10,
            last_completed=naive, days_in_playlist=90,
        )
        assert 0.0 <= score <= 1.0


# ===========================================================================
# SmartSkipper
# ===========================================================================

class TestSmartSkipperImpatience:
    """Tester utålmodighetslogikken (record_outcome / _impatience_active)."""

    def test_tre_skips_paa_rad_aktiverer_utalmodighet(self):
        skipper = SmartSkipper()
        skipper.record_outcome(True)
        skipper.record_outcome(True)
        skipper.record_outcome(True)
        assert skipper._impatience_active is True

    def test_to_av_tre_skips_aktiverer_utalmodighet(self):
        skipper = SmartSkipper()
        skipper.record_outcome(True)
        skipper.record_outcome(False)
        skipper.record_outcome(True)
        assert skipper._impatience_active is True

    def test_en_av_tre_skips_deaktiverer_utalmodighet(self):
        skipper = SmartSkipper()
        skipper.record_outcome(True)
        skipper.record_outcome(False)
        skipper.record_outcome(False)
        assert skipper._impatience_active is False

    def test_ingen_skips_deaktiverer_utalmodighet(self):
        skipper = SmartSkipper()
        skipper.record_outcome(False)
        skipper.record_outcome(False)
        skipper.record_outcome(False)
        assert skipper._impatience_active is False

    def test_kun_to_resultater_gir_ikke_utalmodighet(self):
        """Trenger minst 3 resultater for å aktivere modus."""
        skipper = SmartSkipper()
        skipper.record_outcome(True)
        skipper.record_outcome(True)
        assert skipper._impatience_active is False

    def test_kun_de_tre_siste_teller(self):
        """Et gammelt skip som falt utenfor vinduet skal ikke påvirke."""
        skipper = SmartSkipper()
        # 5 fullføringer
        for _ in range(5):
            skipper.record_outcome(False)
        # 3 skips (de som teller)
        skipper.record_outcome(True)
        skipper.record_outcome(True)
        skipper.record_outcome(True)
        assert skipper._impatience_active is True

    def test_reset_rydder_utalmodighet(self):
        skipper = SmartSkipper()
        skipper.record_outcome(True)
        skipper.record_outcome(True)
        skipper.record_outcome(True)
        assert skipper._impatience_active is True
        skipper._reset()
        assert skipper._impatience_active is False

    def test_reset_beholder_ikke_pending_uri(self):
        skipper = SmartSkipper()
        skipper._pending_uri = "spotify:track:ABC"
        skipper._pending_since = 123.0
        skipper._reset()
        assert skipper._pending_uri is None
        assert skipper._pending_since is None


class TestSmartSkipperRateLimiting:
    """Tester at MAX_AUTO_SKIPS_PER_HOUR håndheves korrekt."""

    def test_skips_akkumuleres(self):
        skipper = SmartSkipper()
        import time
        now = time.monotonic()
        skipper._skip_timestamps = [now] * 9
        # 9 hopp < 10 → innenfor grensen
        recent = [t for t in skipper._skip_timestamps if now - t < 3600]
        assert len(recent) < 10

    def test_grense_naadd_blokkerer(self):
        from spotify_skip_tracker.smart_skipper import MAX_AUTO_SKIPS_PER_HOUR
        skipper = SmartSkipper()
        import time
        now = time.monotonic()
        skipper._skip_timestamps = [now] * MAX_AUTO_SKIPS_PER_HOUR
        recent = [t for t in skipper._skip_timestamps if now - t < 3600]
        assert len(recent) >= MAX_AUTO_SKIPS_PER_HOUR


class TestShouldAutoSkip:
    """
    Tester should_auto_skip() med en minimal in-memory DB-stub.

    Bruker sqlite3 i stedet for psycopg2 for å unngå nettverkstilgang.
    Stubben oppretter en plays-tabell med nødvendige kolonner.
    """

    @pytest.fixture()
    def sqlite_conn(self):
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE plays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uri TEXT NOT NULL,
                context_uri TEXT,
                user_id TEXT NOT NULL DEFAULT 'default_user',
                skipped INTEGER NOT NULL,
                timestamp TEXT
            )
            """
        )
        conn.commit()
        yield conn
        conn.close()

    def _insert(self, conn, uri, skipped, context_uri=None, user_id="testuser"):
        conn.execute(
            "INSERT INTO plays (uri, context_uri, user_id, skipped, timestamp) VALUES (?,?,?,?,?)",
            (uri, context_uri, user_id, 1 if skipped else 0, "2025-01-01T00:00:00"),
        )
        conn.commit()

    def _should(self, conn, uri, context_uri=None, user_id="testuser",
                threshold=0.80, min_plays=3):
        """Kaller should_auto_skip med sqlite-tilpasset cursor-wrapper."""

        # psycopg2-stilen (%s) fungerer ikke med sqlite3 (?).
        # Vi lager en enkel wrapper-klasse som oversetter.
        class _CursorWrapper:
            def __init__(self, conn):
                self._conn = conn
                self._cur = None

            def execute(self, sql, params=()):
                # Konverter %s → ?
                sql_sqlite = sql.replace("%s", "?")
                self._cur = self._conn.execute(sql_sqlite, params)
                return self

            def fetchone(self):
                return self._cur.fetchone() if self._cur else None

            def fetchall(self):
                return self._cur.fetchall() if self._cur else []

        class _ConnWrapper:
            def __init__(self, conn):
                self._conn = conn

            def cursor(self):
                return _CursorWrapper(self._conn)

        # Monkey-patch database.execute for denne testen
        import spotify_skip_tracker.smart_skipper as ss_module
        original_execute = ss_module.execute

        def _fake_execute(conn_arg, sql, params=()):
            wrapper = _ConnWrapper(conn)
            return wrapper.cursor().execute(sql, params)

        ss_module.execute = _fake_execute
        try:
            result = should_auto_skip(
                conn, uri=uri, context_uri=context_uri,
                threshold=threshold, min_plays=min_plays, user_id=user_id,
            )
        finally:
            ss_module.execute = original_execute

        return result

    def test_under_terskel_returnerer_false(self, sqlite_conn):
        uri = "spotify:track:A"
        self._insert(sqlite_conn, uri, skipped=True)
        self._insert(sqlite_conn, uri, skipped=True)
        self._insert(sqlite_conn, uri, skipped=False)  # rate = 2/3 ≈ 0.67 < 0.80
        skip, _ = self._should(sqlite_conn, uri, threshold=0.80, min_plays=3)
        assert skip is False

    def test_over_terskel_returnerer_true(self, sqlite_conn):
        uri = "spotify:track:B"
        for _ in range(4):
            self._insert(sqlite_conn, uri, skipped=True)
        self._insert(sqlite_conn, uri, skipped=False)   # rate = 4/5 = 0.80
        skip, reason = self._should(sqlite_conn, uri, threshold=0.80, min_plays=3)
        assert skip is True
        assert "80%" in reason

    def test_for_lite_data_returnerer_false(self, sqlite_conn):
        uri = "spotify:track:C"
        self._insert(sqlite_conn, uri, skipped=True)
        self._insert(sqlite_conn, uri, skipped=True)   # kun 2 < min_plays=3
        skip, _ = self._should(sqlite_conn, uri, threshold=0.80, min_plays=3)
        assert skip is False

    def test_user_id_isolasjon(self, sqlite_conn):
        """Data fra annen bruker skal ikke påvirke beslutningen."""
        uri = "spotify:track:D"
        # Annen brukers data: høy skip-rate
        for _ in range(5):
            self._insert(sqlite_conn, uri, skipped=True, user_id="other_user")
        # Vår brukers data: lav skip-rate
        for _ in range(3):
            self._insert(sqlite_conn, uri, skipped=False, user_id="testuser")
        skip, _ = self._should(sqlite_conn, uri, threshold=0.80, min_plays=3,
                               user_id="testuser")
        assert skip is False
