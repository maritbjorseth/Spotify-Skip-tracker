"""
Statistikkberegning for Spotify Skip Tracker.

compute_stats() brukes av Flask-endepunktet /api/stats og returnerer
et JSON-serialiserbart dict med alle data dashbordet trenger.

Hourly- og weekday-aggregering gjøres nå i SQL (ikke Python),
noe som skalerer langt bedre med mange avspillinger.
"""

import logging

from .database import execute, pooled_connection

logger = logging.getLogger(__name__)


def compute_stats() -> dict:
    """
    Henter all statistikk fra databasen og returnerer den som et dict.
    Bruker connection-poolen slik at dashboard-forespørsler ikke åpner
    en ny tilkobling for hvert kall.
    """
    with pooled_connection() as conn:
        return _compute(conn)


def _compute(conn) -> dict:
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
            COALESCE(c.name, p.context_uri)                     AS context_name,
            SUM(CASE WHEN p.skipped THEN 1 ELSE 0 END)         AS skip_count,
            COUNT(*)                                            AS play_count,
            MAX(p.image_url)                                    AS image_url
        FROM plays p
        LEFT JOIN contexts c ON c.uri = p.context_uri
        GROUP BY p.uri, context_name
        HAVING SUM(CASE WHEN p.skipped THEN 1 ELSE 0 END) > 0
        ORDER BY skip_count DESC
        """,
    ).fetchall()

    tracks = []
    contexts: set[str] = set()
    for uri, title, artists, context_name, skip_count, play_count, image_url in track_rows:
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
        WHERE artists IS NOT NULL AND artists != ''
        GROUP BY artists
        HAVING SUM(CASE WHEN skipped THEN 1 ELSE 0 END) > 0
        ORDER BY skip_count DESC
        LIMIT 10
        """,
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
        WHERE artists IS NOT NULL AND artists != ''
        GROUP BY artists
        ORDER BY play_count DESC
        LIMIT 10
        """,
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
            COALESCE(c.name, p.context_uri)                     AS context_name,
            SUM(CASE WHEN p.skipped THEN 1 ELSE 0 END)         AS skip_count,
            COUNT(*)                                            AS play_count
        FROM plays p
        LEFT JOIN contexts c ON c.uri = p.context_uri
        WHERE p.context_uri IS NOT NULL
        GROUP BY context_name
        HAVING COUNT(*) >= 2
        ORDER BY (SUM(CASE WHEN p.skipped THEN 1 ELSE 0 END)::REAL / COUNT(*)) DESC
        LIMIT 10
        """,
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
    # Mest spilte sanger (alle, sortert etter avspillingsantall)
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
        GROUP BY uri
        ORDER BY play_count DESC
        LIMIT 100
        """,
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
        GROUP BY uri
        HAVING COUNT(*) >= 2
        ORDER BY
            (SUM(CASE WHEN skipped THEN 1 ELSE 0 END)::REAL / COUNT(*)) ASC,
            play_count DESC
        LIMIT 10
        """,
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
        GROUP BY hour
        ORDER BY hour
        """,
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
        GROUP BY weekday
        ORDER BY weekday
        """,
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
        "SELECT COALESCE(SUM(CASE WHEN skipped THEN 1 ELSE 0 END), 0) FROM plays",
    ).fetchone()[0]
    total_plays = execute(conn, "SELECT COUNT(*) FROM plays").fetchone()[0]
    unique_tracks = execute(
        conn,
        "SELECT COUNT(DISTINCT uri) FROM plays WHERE skipped = TRUE",
    ).fetchone()[0]

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
        WHERE timestamp >= NOW() - INTERVAL '365 days'
        GROUP BY day
        ORDER BY day
        """,
    ).fetchall()
    daily = {
        str(day): {"skips": int(skips), "plays": int(plays)}
        for day, skips, plays in daily_rows
    }

    return {
        "tracks": tracks,
        "contexts": sorted(contexts),
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
    }
