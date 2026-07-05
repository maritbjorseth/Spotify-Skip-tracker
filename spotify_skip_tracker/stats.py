"""
Statistikkberegning for Spotify Skip Tracker.

compute_stats() brukes av Flask-endepunktet /api/stats og returnerer
et JSON-serialiserbart dict med alle data dashbordet trenger.

Hourly- og weekday-aggregering gjøres nå i SQL (ikke Python),
noe som skalerer langt bedre med mange avspillinger.

Alle funksjoner tar en 'user_id'-parameter slik at dataene isoleres
per bruker (Fase H — multi-user forberedelse).

Caching:
    compute_stats() er dekorert med en enkel TTL-cache (60 sekunder).
    Dette eliminerer gjentatte DB-kall ved parallelle forespørsler og
    under Neon cold-start-perioder. Cachen er per user_id.
"""

import logging
import threading
import time as _time

from .database import execute, pooled_connection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enkel TTL-cache for compute_stats()
# ---------------------------------------------------------------------------

_stats_cache: dict[str, tuple[dict, float]] = {}  # user_id → (result, expires_at)
_stats_cache_lock = threading.Lock()
_STATS_CACHE_TTL = 60  # sekunder


def calculate_listening_score(user_id: str = "default_user") -> int:
    """
    Beregner en lyttescore mellom 0 og 100 for brukeren.

    Tre vektede komponenter:
        Fullføringsgrad   50%  — andelen sanger brukeren faktisk hører ferdig
        Lengste streak    30%  — lengste sammenhengende rekke uten ett eneste skip
        Daglig konsistens 20%  — lavt standardavvik i daglig skip-rate = forutsigbar lytting

    Returnerer 75 (nøytralt) dersom det finnes færre enn 10 avspillinger.
    """
    DEFAULT_SCORE = 75

    with pooled_connection() as conn:
        # --- Grunnlagstall ---
        base = execute(
            conn,
            """
            SELECT
                COUNT(*)                                            AS total_plays,
                SUM(CASE WHEN skipped THEN 1 ELSE 0 END)           AS total_skips
            FROM plays
            WHERE user_id = %s
            """,
            (user_id,),
        ).fetchone()

        if not base or (base[0] or 0) < 10:
            return DEFAULT_SCORE

        total_plays = int(base[0])
        total_skips = int(base[1] or 0)

        # --- Komponent 1: Fullføringsgrad (50%) ---
        completion_rate = 1.0 - (total_skips / total_plays)

        # --- Komponent 2: Lengste sammenhengende streak uten skip (30%) ---
        # «Gaps and islands»-teknikk: gruppenummer = absolutt radnummer minus
        # radnummer innenfor samme skipped-verdi. Alle rader i samme øy
        # (sammenhengende ikke-skippa sanger) får samme grp-verdi.
        streak_row = execute(
            conn,
            """
            WITH numbered AS (
                SELECT
                    skipped,
                    ROW_NUMBER() OVER (ORDER BY timestamp)
                    - ROW_NUMBER() OVER (PARTITION BY skipped ORDER BY timestamp) AS grp
                FROM plays
                WHERE user_id = %s
            ),
            streaks AS (
                SELECT COUNT(*) AS streak_len
                FROM numbered
                WHERE NOT skipped
                GROUP BY grp
            )
            SELECT COALESCE(MAX(streak_len), 0) AS max_streak
            FROM streaks
            """,
            (user_id,),
        ).fetchone()

        max_streak = int(streak_row[0]) if streak_row else 0
        # 20 sanger på rad uten skip = full score på denne komponenten
        streak_score = min(1.0, max_streak / 20.0)

        # --- Komponent 3: Daglig konsistens — siste 30 dager (20%) ---
        # Lav standardavvik i daglig skip-rate = forutsigbar lytteadferd = høyere score.
        # STDDEV_POP = 0 betyr at skip-raten er identisk hver dag (perfekt konsistens).
        # STDDEV_POP >= 0,5 regnes som høyt kaos → score 0.
        consistency_row = execute(
            conn,
            """
            SELECT COALESCE(STDDEV_POP(daily_rate), 0.0)
            FROM (
                SELECT
                    SUM(CASE WHEN skipped THEN 1 ELSE 0 END)::REAL
                        / NULLIF(COUNT(*), 0)                       AS daily_rate
                FROM plays
                WHERE user_id = %s
                  AND timestamp >= NOW() - INTERVAL '30 days'
                GROUP BY DATE(timestamp AT TIME ZONE 'Europe/Oslo')
                HAVING COUNT(*) >= 3
            ) daily
            """,
            (user_id,),
        ).fetchone()

        stddev = float(consistency_row[0]) if consistency_row and consistency_row[0] else 0.0
        consistency_score = max(0.0, 1.0 - stddev * 2.0)

        # --- Kombiner og skaler til 0–100 ---
        raw = (
            0.50 * completion_rate
            + 0.30 * streak_score
            + 0.20 * consistency_score
        )
        return max(0, min(100, round(raw * 100)))


def compute_insight_stats(db_cursor, user_id: str = "default_user") -> dict:
    """
    Beregner coach-innsikter for /api/coach/insights-endepunktet.

    Parametere:
        db_cursor  En åpen psycopg2-markør mot databasen.
        user_id    Spotify-bruker-ID — filtrerer data til kun denne brukeren.

    Returnerer et dict med:
        top_skipped_hour      — timen på døgnet (0–23) med flest registrerte skips
        most_impatient_day    — ukedagnavn (norsk) med høyest skip-rate
        weekday_skip_rate     — skip-raten for den mest utålmodige ukedagen (0.0–1.0)
        janitor_pending_count — antall sanger i janitor_suggestions som venter (status='pending')
    """
    WEEKDAY_NAMES = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"]

    # --- Time på døgnet med flest skips ---
    db_cursor.execute(
        """
        SELECT
            EXTRACT(HOUR FROM timestamp AT TIME ZONE 'Europe/Oslo')::INT AS hour,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END) AS skip_count
        FROM plays
        WHERE user_id = %s
        GROUP BY hour
        ORDER BY skip_count DESC
        LIMIT 1
        """,
        (user_id,),
    )
    hour_row = db_cursor.fetchone()
    top_skipped_hour = int(hour_row[0]) if hour_row else None

    # --- Ukedag med høyest skip-rate ---
    db_cursor.execute(
        """
        SELECT
            (EXTRACT(ISODOW FROM timestamp AT TIME ZONE 'Europe/Oslo')::INT - 1) AS weekday,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END)::REAL / NULLIF(COUNT(*), 0) AS skip_rate
        FROM plays
        WHERE user_id = %s
        GROUP BY weekday
        ORDER BY skip_rate DESC
        LIMIT 1
        """,
        (user_id,),
    )
    weekday_row = db_cursor.fetchone()
    most_impatient_day = None
    weekday_skip_rate = None
    if weekday_row:
        wd_index = int(weekday_row[0])
        most_impatient_day = WEEKDAY_NAMES[wd_index] if 0 <= wd_index <= 6 else None
        weekday_skip_rate = round(float(weekday_row[1]), 3) if weekday_row[1] is not None else None

    # --- Antall ventende janitor-forslag ---
    db_cursor.execute(
        """
        SELECT COUNT(*)
        FROM janitor_suggestions
        WHERE user_id = %s
          AND status = 'pending'
        """,
        (user_id,),
    )
    pending_row = db_cursor.fetchone()
    janitor_pending_count = int(pending_row[0]) if pending_row else 0

    return {
        "top_skipped_hour": top_skipped_hour,
        "most_impatient_day": most_impatient_day,
        "weekday_skip_rate": weekday_skip_rate,
        "janitor_pending_count": janitor_pending_count,
    }


def compute_stats(user_id: str = "default_user") -> dict:
    """
    Henter all statistikk fra databasen og returnerer den som et dict.
    Bruker connection-poolen slik at dashboard-forespørsler ikke åpner
    en ny tilkobling for hvert kall.

    Resultatet caches i _STATS_CACHE_TTL sekunder per user_id for å
    unngå gjentatte DB-kall ved parallelle forespørsler eller Neon
    cold-start-perioder.

    Parametere:
        user_id  Spotify-bruker-ID — filtrerer all statistikk til kun denne brukeren.
    """
    now = _time.monotonic()
    with _stats_cache_lock:
        cached = _stats_cache.get(user_id)
        if cached is not None and cached[1] > now:
            return cached[0]

    with pooled_connection() as conn:
        result = _compute(conn, user_id)

    with _stats_cache_lock:
        _stats_cache[user_id] = (result, now + _STATS_CACHE_TTL)

    return result


def _compute(conn, user_id: str) -> dict:
    # ------------------------------------------------------------------
    # Sanger med minst ett skip
    # ------------------------------------------------------------------
    track_rows = execute(
        conn,
        """
        SELECT
            p.uri,
            MAX(p.title)                                        AS title,
            MAX(p.artists)                                      AS artists,
            COALESCE(
                c.name,
                CASE WHEN p.context_uri LIKE 'spotify:user:%%:collection'
                     THEN 'Liked Songs'
                END
            )                                                   AS context_name,
            SUM(CASE WHEN p.skipped THEN 1 ELSE 0 END)         AS skip_count,
            COUNT(*)                                            AS play_count,
            MAX(p.image_url)                                    AS image_url,
            MAX(p.context_uri)                                  AS context_uri
        FROM plays p
        LEFT JOIN contexts c ON c.uri = p.context_uri
        WHERE p.user_id = %s
        GROUP BY p.uri, context_name
        HAVING SUM(CASE WHEN p.skipped THEN 1 ELSE 0 END) > 0
        ORDER BY skip_count DESC
        LIMIT 500
        """,
        (user_id,),
    ).fetchall()

    tracks = []
    contexts: set[str] = set()
    playlist_contexts: set[str] = set()
    album_contexts: set[str] = set()
    for uri, title, artists, context_name, skip_count, play_count, image_url, context_uri in track_rows:
        tracks.append(
            {
                "uri": uri,
                "title": title,
                "artists": artists,
                "context_name": context_name,
                "skip_count": int(skip_count),
                "play_count": int(play_count),
                "skip_rate": skip_count / play_count if play_count else 0,
                "image_url": image_url,
            }
        )
        if context_name:
            contexts.add(context_name)
            if context_uri and context_uri.startswith("spotify:album:"):
                album_contexts.add(context_name)
            else:
                playlist_contexts.add(context_name)

    # ------------------------------------------------------------------
    # Mest skippede artister (topp 10)
    # ------------------------------------------------------------------
    artist_rows = execute(
        conn,
        """
        SELECT
            artists,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END) AS skip_count,
            COUNT(*)                                  AS play_count
        FROM plays
        WHERE user_id = %s
          AND artists IS NOT NULL AND artists != ''
        GROUP BY artists
        HAVING COUNT(*) >= 5
          AND SUM(CASE WHEN skipped THEN 1 ELSE 0 END) > 0
        ORDER BY (SUM(CASE WHEN skipped THEN 1 ELSE 0 END)::REAL / COUNT(*)) DESC
        LIMIT 10
        """,
        (user_id,),
    ).fetchall()
    top_artists = [
        {
            "artists": a,
            "skip_count": int(sc),
            "play_count": int(pc),
            "skip_rate": sc / pc if pc else 0,
        }
        for a, sc, pc in artist_rows
    ]

    # ------------------------------------------------------------------
    # Mest hørte artister (topp 10)
    # ------------------------------------------------------------------
    listened_rows = execute(
        conn,
        """
        SELECT
            artists,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END) AS skip_count,
            COUNT(*)                                  AS play_count
        FROM plays
        WHERE user_id = %s
          AND artists IS NOT NULL AND artists != ''
        GROUP BY artists
        ORDER BY play_count DESC
        LIMIT 10
        """,
        (user_id,),
    ).fetchall()
    top_listened_artists = [
        {
            "artists": a,
            "skip_count": int(sc),
            "play_count": int(pc),
            "skip_rate": sc / pc if pc else 0,
        }
        for a, sc, pc in listened_rows
    ]

    # ------------------------------------------------------------------
    # Spillelister/album med høyest skip-rate (topp 10, min 2 avspillinger)
    # ------------------------------------------------------------------
    context_rows = execute(
        conn,
        """
        SELECT
            COALESCE(
                c.name,
                CASE WHEN p.context_uri LIKE 'spotify:user:%%:collection'
                     THEN 'Liked Songs'
                END
            )                                                   AS context_name,
            SUM(CASE WHEN p.skipped THEN 1 ELSE 0 END)         AS skip_count,
            COUNT(*)                                            AS play_count
        FROM plays p
        LEFT JOIN contexts c ON c.uri = p.context_uri
        WHERE p.user_id = %s
          AND p.context_uri IS NOT NULL
        GROUP BY context_name
        HAVING COUNT(*) >= 2
        ORDER BY (SUM(CASE WHEN p.skipped THEN 1 ELSE 0 END)::REAL / COUNT(*)) DESC
        LIMIT 10
        """,
        (user_id,),
    ).fetchall()
    top_contexts = [
        {
            "context_name": cn,
            "skip_count": int(sc),
            "play_count": int(pc),
            "skip_rate": sc / pc if pc else 0,
        }
        for cn, sc, pc in context_rows
    ]

    # ------------------------------------------------------------------
    # Mest spilte sanger (topp 100, sortert etter avspillingsantall)
    # ------------------------------------------------------------------
    played_rows = execute(
        conn,
        """
        SELECT
            uri,
            MAX(title)                                          AS title,
            MAX(artists)                                        AS artists,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END)           AS skip_count,
            COUNT(*)                                            AS play_count,
            MAX(image_url)                                      AS image_url
        FROM plays
        WHERE user_id = %s
        GROUP BY uri
        ORDER BY play_count DESC
        LIMIT 100
        """,
        (user_id,),
    ).fetchall()
    most_played = [
        {
            "uri": uri,
            "title": t,
            "artists": a,
            "context_name": None,
            "skip_count": int(sc),
            "play_count": int(pc),
            "skip_rate": sc / pc if pc else 0,
            "image_url": img,
        }
        for uri, t, a, sc, pc, img in played_rows
    ]

    # ------------------------------------------------------------------
    # Sanger du nesten aldri skipper (topp 10, min 2 avspillinger)
    # ------------------------------------------------------------------
    completed_rows = execute(
        conn,
        """
        SELECT
            uri,
            MAX(title)                                          AS title,
            MAX(artists)                                        AS artists,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END)           AS skip_count,
            COUNT(*)                                            AS play_count,
            MAX(image_url)                                      AS image_url
        FROM plays
        WHERE user_id = %s
        GROUP BY uri
        HAVING COUNT(*) >= 2
        ORDER BY
            (SUM(CASE WHEN skipped THEN 1 ELSE 0 END)::REAL / COUNT(*)) ASC,
            play_count DESC
        LIMIT 10
        """,
        (user_id,),
    ).fetchall()
    most_completed = [
        {
            "uri": uri,
            "title": t,
            "artists": a,
            "context_name": None,
            "skip_count": int(sc),
            "play_count": int(pc),
            "skip_rate": sc / pc if pc else 0,
            "image_url": img,
        }
        for uri, t, a, sc, pc, img in completed_rows
    ]

    # ------------------------------------------------------------------
    # Skip per time på døgnet (SQL GROUP BY — ikke Python-loop over alle rader)
    # ------------------------------------------------------------------
    hourly_rows = execute(
        conn,
        """
        SELECT
            EXTRACT(HOUR FROM timestamp AT TIME ZONE 'Europe/Oslo')::INT AS hour,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END)                    AS skips,
            COUNT(*)                                                      AS plays
        FROM plays
        WHERE user_id = %s
        GROUP BY hour
        ORDER BY hour
        """,
        (user_id,),
    ).fetchall()
    hourly = [{"skips": 0, "plays": 0} for _ in range(24)]
    for hour, skips, plays in hourly_rows:
        if 0 <= hour <= 23:
            hourly[hour] = {"skips": int(skips), "plays": int(plays)}

    # ------------------------------------------------------------------
    # Skip per ukedag (0 = mandag, 6 = søndag)
    # ISODOW: 1=mandag … 7=søndag → konverter til 0-indeksert
    # ------------------------------------------------------------------
    weekday_rows = execute(
        conn,
        """
        SELECT
            (EXTRACT(ISODOW FROM timestamp AT TIME ZONE 'Europe/Oslo')::INT - 1) AS weekday,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END)                             AS skips,
            COUNT(*)                                                               AS plays
        FROM plays
        WHERE user_id = %s
        GROUP BY weekday
        ORDER BY weekday
        """,
        (user_id,),
    ).fetchall()
    weekday = [{"skips": 0, "plays": 0} for _ in range(7)]
    for wd, skips, plays in weekday_rows:
        if 0 <= wd <= 6:
            weekday[wd] = {"skips": int(skips), "plays": int(plays)}

    # ------------------------------------------------------------------
    # Totaler
    # ------------------------------------------------------------------
    total_skips = execute(
        conn,
        """
        SELECT COALESCE(SUM(CASE WHEN skipped THEN 1 ELSE 0 END), 0)
        FROM plays
        WHERE user_id = %s
        """,
        (user_id,),
    ).fetchone()[0]
    total_plays = execute(
        conn,
        "SELECT COUNT(*) FROM plays WHERE user_id = %s",
        (user_id,),
    ).fetchone()[0]
    unique_tracks = execute(
        conn,
        "SELECT COUNT(DISTINCT uri) FROM plays WHERE user_id = %s AND skipped = TRUE",
        (user_id,),
    ).fetchone()[0]

    # ------------------------------------------------------------------
    # Smart Skipper — kandidater over skip-rate-terskel
    # Henter terskelen fra smart_skipper_config (standard 0.85).
    # Krever minst min_plays avspillinger for å unngå falske positiver.
    # ------------------------------------------------------------------
    config_row = execute(
        conn,
        "SELECT threshold, min_plays FROM smart_skipper_config WHERE user_id = %s",
        (user_id,),
    ).fetchone()
    ss_threshold = float(config_row[0]) if config_row else 0.85
    ss_min_plays = int(config_row[1]) if config_row else 3

    candidate_rows = execute(
        conn,
        """
        SELECT
            uri,
            MAX(title)                                              AS title,
            MAX(artists)                                            AS artists,
            MAX(image_url)                                          AS image_url,
            COUNT(*)                                                AS play_count,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END)               AS skip_count
        FROM plays
        WHERE user_id = %s
          AND uri NOT IN (
              SELECT uri
              FROM janitor_removals
              WHERE user_id = %s
                AND undone = FALSE
          )
        GROUP BY uri
        HAVING
            COUNT(*) >= %s
            AND (SUM(CASE WHEN skipped THEN 1 ELSE 0 END)::REAL / COUNT(*)) >= %s
        ORDER BY (SUM(CASE WHEN skipped THEN 1 ELSE 0 END)::REAL / COUNT(*)) DESC
        """,
        (user_id, user_id, ss_min_plays, ss_threshold),
    ).fetchall()
    auto_skip_candidates = [
        {
            "uri": uri,
            "title": title,
            "artists": artists,
            "image_url": image_url,
            "play_count": int(play_count),
            "skip_count": int(skip_count),
            "skip_rate": skip_count / play_count if play_count else 0,
        }
        for uri, title, artists, image_url, play_count, skip_count in candidate_rows
    ]

    # ------------------------------------------------------------------
    # Daglig aktivitet for heatmap (siste 365 dager)
    # ------------------------------------------------------------------
    daily_rows = execute(
        conn,
        """
        SELECT
            DATE(timestamp AT TIME ZONE 'Europe/Oslo')              AS day,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END)               AS skips,
            COUNT(*)                                                 AS plays
        FROM plays
        WHERE user_id = %s
          AND timestamp >= NOW() - INTERVAL '365 days'
        GROUP BY day
        ORDER BY day
        """,
        (user_id,),
    ).fetchall()
    daily = {
        str(day): {"skips": int(skips), "plays": int(plays)}
        for day, skips, plays in daily_rows
    }

    return {
        "tracks": tracks,
        "contexts": sorted(contexts),
        "playlist_contexts": sorted(playlist_contexts),
        "album_contexts": sorted(album_contexts),
        "top_artists": top_artists,
        "top_listened_artists": top_listened_artists,
        "top_contexts": top_contexts,
        "most_played": most_played,
        "most_completed": most_completed,
        "hourly": hourly,
        "weekday": weekday,
        "daily": daily,
        "total_skips": int(total_skips),
        "total_plays": int(total_plays),
        "unique_tracks": int(unique_tracks),
        "auto_skip_candidates": auto_skip_candidates,
        "smart_skipper_threshold": ss_threshold,
    }
