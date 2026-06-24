"""
Playlist Janitor — kandidatidentifikasjon, score-beregning og analyse.

Analyserer spillelister og identifiserer sanger som konsekvent hoppes over,
basert på historisk skip-data i databasen.

Fase D: score-beregning, kandidathenting og run_janitor-kjøring.
Fase E (fjerning, angring, CLI) implementeres i neste fase.
"""

import logging
from datetime import datetime, timezone

from .database import connect, execute, init_db
from .janitor_helpers import get_all_my_playlists, get_playlist_tracks
from .spotify_api import get_access_token, load_creds

logger = logging.getLogger(__name__)


def calculate_janitor_score(
    skip_count: int,
    play_count: int,
    last_completed: datetime | None,
    days_in_playlist: int,
    recent_outcomes: list[bool] | None = None,
) -> float:
    """
    Beregner janitering-score for en sang i en spilleliste.

    Score er et tall mellom 0.0 og 1.0 der høy score indikerer at sangen
    bør foreslås fjernet. Beregnes som en vektet sum av fire komponenter:

        Komponent             Vekt   Høy score når…
        ──────────────────── ──────  ────────────────────────────────────
        skip_component        0.40   Skip-raten er høy
        consistency_component 0.30   Sangen aldri lyttes ferdig
        recency_component     0.20   Det er lenge siden siste fullføring
        reliability           0.10   Det finnes mye data (≥ 3 avspillinger)

    Benådnings-regler (returnerer alltid 0.0):
        - Sangen ble fullført i løpet av de siste 7 dagene, ELLER
        - De siste 3 avspillingene var alle komplette (recent_outcomes = [False, False, False])

    Parametere:
        skip_count        Antall skippede avspillinger i denne spillelisten
        play_count        Totalt antall avspillinger i denne spillelisten
        last_completed    Tidspunkt for siste fullførte avspilling, eller None
        days_in_playlist  Antall dager sangen har vært i spillelisten
        recent_outcomes   Liste over de nyeste avspillingenes skip-status (True=skip).
                          Brukes til å sjekke om de siste 3 var alle komplette.

    Returnerer:
        float mellom 0.0 og 1.0, rundet til 4 desimaler.
        Returnerer 0.0 dersom play_count == 0 (ingen data) eller benådning utløses.
    """
    if play_count == 0:
        return 0.0

    now = datetime.now(tz=timezone.utc)

    # --- Benådnings-sjekk 1: fullført i løpet av de siste 7 dagene ---
    if last_completed is not None:
        lc = last_completed
        if lc.tzinfo is None:
            lc = lc.replace(tzinfo=timezone.utc)
        if (now - lc).days <= 7:
            return 0.0

    # --- Benådnings-sjekk 2: de siste 3 avspillingene var alle komplette ---
    if recent_outcomes is not None and len(recent_outcomes) >= 3:
        if not any(recent_outcomes[-3:]):  # ingen av de 3 siste var skip
            return 0.0

    skip_rate = skip_count / play_count

    # Komponent 1: Skip-rate (0–1)
    skip_component = skip_rate

    # Komponent 2: Konsistens — aldri fullført = 1.0, alltid fullført = 0.0
    completed_count = play_count - skip_count
    consistency_component = 1.0 - (completed_count / play_count)

    # Komponent 3: Tid siden siste fullføring (maks 1.0 etter 180 dager).
    # last_completed kan være enten timezone-aware (TIMESTAMPTZ fra Postgres)
    # eller naive — begge håndteres.
    if last_completed is None:
        recency_component = 1.0
    else:
        lc = last_completed
        if lc.tzinfo is None:
            lc = lc.replace(tzinfo=timezone.utc)
        days_since = (now - lc).days
        recency_component = min(1.0, days_since / 180)

    # Komponent 4: Datapålitelighet (minst 3 avspillinger gir maks score)
    reliability = min(1.0, play_count / 3)

    score = (
        0.40 * skip_component
        + 0.30 * consistency_component
        + 0.20 * recency_component
        + 0.10 * reliability
    )

    return round(score, 4)


def _confidence_level(play_count: int) -> str:
    if play_count >= 10:
        return "Nesten sikkert at du er lei denne"
    if play_count >= 5:
        return "Sterk kandidat"
    return "Mulig kandidat"


def _category(score: float) -> str:
    if score >= 0.75:
        return "Remove"
    if score >= 0.50:
        return "Candidate"
    if score >= 0.30:
        return "Watchlist"
    return "Keep"


def get_janitor_candidates(
    conn,
    playlist_id: str,
    track_uris: list[str],
    min_score: float = 0.0,
    min_plays: int = 2,
) -> list[dict]:
    """
    Returnerer alle sanger fra spillelisten med beregnet score, kategori og
    konfidensnivå. Ingen øvre filtrering på score — kategorisering overlates
    til kallende kode og frontend.

    Henter aggregert avspillingsdata fra databasen for de oppgitte URI-ene
    innenfor den spesifikke spilleliste-konteksten.

    Parametere:
        conn         Aktiv database-tilkobling
        playlist_id  Spotify-playlist-ID (uten "spotify:playlist:"-prefiks)
        track_uris   Liste over Spotify-URI-er for sangene i spillelisten
        min_score    Minimum score for å inkludere (standard 0.0 = alt)
        min_plays    Minimum antall avspillinger (standard 2)

    Returnerer:
        Liste av dicts sortert etter score (høyest først). Hvert element:
        {
            "uri":              str,
            "title":            str | None,
            "artists":          str | None,
            "play_count":       int,
            "skip_count":       int,
            "skip_rate":        float,
            "last_completed":   str | None,  # ISO 8601
            "score":            float,
            "category":         str,         # "Remove"|"Candidate"|"Watchlist"|"Keep"
            "confidence_level": str,
        }
    """
    if not track_uris:
        return []

    context_uri = f"spotify:playlist:{playlist_id}"
    placeholders = ",".join(["%s"] * len(track_uris))

    try:
        rows = execute(
            conn,
            f"""
            SELECT
                uri,
                MAX(title)                                          AS title,
                MAX(artists)                                        AS artists,
                COUNT(*)                                            AS play_count,
                SUM(CASE WHEN skipped THEN 1 ELSE 0 END)           AS skip_count,
                MAX(CASE WHEN NOT skipped THEN timestamp END)       AS last_completed,
                MIN(timestamp)                                      AS first_seen
            FROM plays
            WHERE uri IN ({placeholders})
              AND context_uri = %s
            GROUP BY uri
            HAVING COUNT(*) >= %s
            """,
            (*track_uris, context_uri, min_plays),
        ).fetchall()
    except Exception as exc:
        logger.error(
            "DB-feil ved henting av Janitor-kandidater for spilleliste %s: %s",
            playlist_id, exc,
        )
        return []

    candidates: list[dict] = []

    for uri, title, artists, play_count, skip_count, last_completed, first_seen in rows:
        play_count = int(play_count)
        skip_count = int(skip_count or 0)

        if first_seen is not None:
            if first_seen.tzinfo is None:
                first_seen = first_seen.replace(tzinfo=timezone.utc)
            days_in_playlist = (datetime.now(tz=timezone.utc) - first_seen).days
        else:
            days_in_playlist = 0

        # Hent de 3 nyeste avspillingene for benådnings-sjekk
        try:
            recent_rows = execute(
                conn,
                """
                SELECT skipped FROM plays
                WHERE uri = %s AND context_uri = %s
                ORDER BY timestamp DESC
                LIMIT 3
                """,
                (uri, context_uri),
            ).fetchall()
            recent_outcomes = [bool(r[0]) for r in recent_rows]
        except Exception:
            recent_outcomes = None

        score = calculate_janitor_score(
            skip_count=skip_count,
            play_count=play_count,
            last_completed=last_completed,
            days_in_playlist=days_in_playlist,
            recent_outcomes=recent_outcomes,
        )

        if score >= min_score:
            candidates.append({
                "uri": uri,
                "title": title,
                "artists": artists,
                "play_count": play_count,
                "skip_count": skip_count,
                "skip_rate": skip_count / play_count,
                "last_completed": (
                    last_completed.isoformat() if last_completed is not None else None
                ),
                "score": score,
                "category": _category(score),
                "confidence_level": _confidence_level(play_count),
            })

    return sorted(candidates, key=lambda x: x["score"], reverse=True)


def _upsert_suggestion(conn, playlist: dict, candidate: dict) -> None:
    """
    Lagrer en janitor-kandidat i janitor_suggestions-tabellen.

    Bruker ON CONFLICT DO NOTHING for å unngå duplikater — samme
    (playlist_id, uri)-kombinasjon med 'pending'-status settes bare inn én gang.
    """
    execute(
        conn,
        """
        INSERT INTO janitor_suggestions
            (playlist_id, playlist_name, uri, title, artists,
             skip_rate, janitor_score, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
        ON CONFLICT (playlist_id, uri) DO NOTHING
        """,
        (
            playlist["id"],
            playlist["name"],
            candidate["uri"],
            candidate["title"],
            candidate["artists"],
            candidate["skip_rate"],
            candidate["score"],
        ),
    )
    conn.commit()


def run_janitor(
    playlist_filter: str | None = None,
    min_score: float = 0.70,
    min_plays: int = 3,
    dry_run: bool = True,
) -> dict:
    """
    Hovedfunksjon for Playlist Janitor — analyserer spillelister og
    lagrer forslag til fjerning i janitor_suggestions-tabellen.

    Parametere:
        playlist_filter  Filtrer på spillelistenavn (case-insensitive delstreng).
                         None = analyser alle spillelister brukeren eier.
        min_score        Minimum janitering-score for å inkludere en kandidat (0–1).
        min_plays        Minimum antall avspillinger i spillelisten for å vurdere sangen.
        dry_run          Hvis True: analyser og logg, men gjør ingen endringer i DB.

    Returnerer en dict med oppsummering:
        {
            "playlists_analysed": int,   # antall analyserte spillelister
            "playlists_skipped":  int,   # spillelister uten nok data / ingen spor
            "total_candidates":   int,   # totalt antall kandidater funnet
            "dry_run":            bool,
            "results": [
                {
                    "playlist_id":   str,
                    "playlist_name": str,
                    "candidates":    list[dict],
                },
                ...
            ],
        }
    """
    creds = load_creds()
    token = get_access_token(creds)

    conn = connect()
    init_db(conn)

    # Hent alle spillelister brukeren eier
    playlists = get_all_my_playlists(token)

    # Filtrer på navn dersom playlist_filter er oppgitt
    if playlist_filter:
        needle = playlist_filter.lower()
        playlists = [p for p in playlists if needle in p["name"].lower()]
        if not playlists:
            logger.warning(
                "Janitor: ingen spillelister matchet filteret '%s'.", playlist_filter
            )
            conn.close()
            return {
                "playlists_analysed": 0,
                "playlists_skipped": 0,
                "total_candidates": 0,
                "dry_run": dry_run,
                "results": [],
            }

    logger.info("=" * 60)
    logger.info(
        "JANITOR START — %s",
        datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )
    logger.info(
        "Parametere: min_score=%.2f  min_plays=%d  dry_run=%s  filter=%s",
        min_score, min_plays, dry_run, playlist_filter or "(alle)",
    )
    logger.info(
        "Analyserer %d spilleliste(r)%s.",
        len(playlists),
        " [DRY RUN — ingen DB-skriving]" if dry_run else "",
    )

    results: list[dict] = []
    total_candidates = 0
    playlists_skipped = 0

    for playlist in playlists:
        playlist_id = playlist["id"]
        playlist_name = playlist["name"]

        tracks = get_playlist_tracks(token, playlist_id)
        if not tracks:
            logger.info("  → '%s': ingen spor hentet, hopper over.", playlist_name)
            playlists_skipped += 1
            continue

        track_uris = [t["uri"] for t in tracks]

        candidates = get_janitor_candidates(
            conn,
            playlist_id=playlist_id,
            track_uris=track_uris,
            min_score=min_score,
            min_plays=min_plays,
        )

        total_candidates += len(candidates)

        if candidates:
            logger.info(
                "  → '%s': %d kandidat(er) over score %.2f",
                playlist_name, len(candidates), min_score,
            )
            for c in candidates:
                logger.info(
                    "     [%.4f] %s — %s  (skip %d/%d)",
                    c["score"], c["artists"], c["title"],
                    c["skip_count"], c["play_count"],
                )
                if not dry_run:
                    _upsert_suggestion(conn, playlist, c)
        else:
            logger.info(
                "  → '%s': ingen kandidater over terskelen.", playlist_name
            )

        results.append({
            "playlist_id": playlist_id,
            "playlist_name": playlist_name,
            "candidates": candidates,
        })

    conn.close()

    logger.info(
        "JANITOR FERDIG — %d spilleliste(r) analysert, %d hoppet over, "
        "%d kandidat(er) totalt%s.",
        len(playlists),
        playlists_skipped,
        total_candidates,
        " (ingen DB-endringer, dry_run=True)" if dry_run else " — lagret i janitor_suggestions",
    )
    logger.info("=" * 60)

    return {
        "playlists_analysed": len(playlists),
        "playlists_skipped": playlists_skipped,
        "total_candidates": total_candidates,
        "dry_run": dry_run,
        "results": results,
    }
