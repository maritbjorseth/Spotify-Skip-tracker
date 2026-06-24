"""
"Wrapped"-rapport for Spotify Skip Tracker.

Genererer en statisk HTML-side med personlige høydepunkter basert på
alle loggede avspillinger — inspirert av Spotify Wrapped.
"""

import html as _html
import logging
import sys
import webbrowser

import requests as _requests

from .config import WRAPPED_PATH, APP_DIR
from .database import connect, execute, init_db
from .spotify_api import get_access_token, load_creds

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Datainnhenting
# ---------------------------------------------------------------------------

def build_wrapped_data(
    month: int | None = None,
    year: int | None = None,
    user_id: str = "default_user",
) -> dict:
    """
    Henter statistikk for Wrapped-rapporten.

    Args:
        month:   Filtrer på måned (1–12). None = alle måneder.
        year:    Filtrer på år. None = alle år.
        user_id: Spotify-bruker-ID — filtrerer data til kun denne brukeren.
    """
    conn = connect()
    try:
        return _build_data(conn, month=month, year=year, user_id=user_id)
    finally:
        conn.close()


def _date_filter(
    month: int | None,
    year: int | None,
    user_id: str = "default_user",
) -> tuple[str, tuple]:
    """
    Returnerer en SQL WHERE-klausul og parametre for bruker- og dato-filtrering.
    user_id er alltid inkludert som første filter.
    """
    clauses = ["user_id = %s"]
    params: list = [user_id]
    if year is not None:
        clauses.append(
            "EXTRACT(YEAR FROM timestamp AT TIME ZONE 'Europe/Oslo') = %s"
        )
        params.append(year)
    if month is not None:
        clauses.append(
            "EXTRACT(MONTH FROM timestamp AT TIME ZONE 'Europe/Oslo') = %s"
        )
        params.append(month)

    where = "WHERE " + " AND ".join(clauses)
    return where, tuple(params)


def _build_data(conn, month: int | None, year: int | None, user_id: str = "default_user") -> dict:
    where, params = _date_filter(month, year, user_id)

    total_skips = execute(
        conn,
        f"SELECT COALESCE(SUM(CASE WHEN skipped THEN 1 ELSE 0 END), 0) FROM plays {where}",
        params,
    ).fetchone()[0]
    total_plays = execute(
        conn, f"SELECT COUNT(*) FROM plays {where}", params
    ).fetchone()[0]

    top_track = execute(
        conn,
        f"""
        SELECT MAX(title), MAX(artists),
               SUM(CASE WHEN skipped THEN 1 ELSE 0 END) AS skip_count,
               COUNT(*) AS play_count
        FROM plays {where}
        GROUP BY uri
        HAVING SUM(CASE WHEN skipped THEN 1 ELSE 0 END) > 0
        ORDER BY skip_count DESC
        LIMIT 1
        """,
        params,
    ).fetchone()

    top_listened_artist = execute(
        conn,
        f"""
        SELECT artists, COUNT(*) AS play_count
        FROM plays
        {where + (" AND " if where else "WHERE ")}artists IS NOT NULL AND artists != ''
        GROUP BY artists
        ORDER BY play_count DESC
        LIMIT 1
        """,
        params,
    ).fetchone()

    # Legg til artists-filter i WHERE
    artist_where = (
        (where + " AND artists IS NOT NULL AND artists != ''")
        if where
        else "WHERE artists IS NOT NULL AND artists != ''"
    )

    most_loyal_artist = execute(
        conn,
        f"""
        SELECT artists,
               SUM(CASE WHEN skipped THEN 1 ELSE 0 END) AS skip_count,
               COUNT(*) AS play_count
        FROM plays {artist_where}
        GROUP BY artists
        HAVING COUNT(*) >= 2
        ORDER BY (SUM(CASE WHEN skipped THEN 1 ELSE 0 END)::REAL / COUNT(*)) ASC,
                 play_count DESC
        LIMIT 1
        """,
        params,
    ).fetchone()

    context_where = (
        (where + " AND p.context_uri IS NOT NULL")
        if where
        else "WHERE p.context_uri IS NOT NULL"
    )
    top_context = execute(
        conn,
        f"""
        SELECT COALESCE(c.name, p.context_uri) AS context_name,
               COUNT(*) AS play_count
        FROM plays p
        LEFT JOIN contexts c ON c.uri = p.context_uri
        {context_where}
        GROUP BY context_name
        ORDER BY play_count DESC
        LIMIT 1
        """,
        params,
    ).fetchone()

    most_completed_track = execute(
        conn,
        f"""
        SELECT MAX(title), MAX(artists), COUNT(*) AS play_count
        FROM plays {where}
        GROUP BY uri
        HAVING SUM(CASE WHEN skipped THEN 1 ELSE 0 END) = 0 AND COUNT(*) >= 2
        ORDER BY play_count DESC
        LIMIT 1
        """,
        params,
    ).fetchone()

    return {
        "total_skips": int(total_skips),
        "total_plays": int(total_plays),
        "overall_skip_rate": total_skips / total_plays if total_plays else 0,
        "top_track": top_track,
        "top_listened_artist": top_listened_artist,
        "most_loyal_artist": most_loyal_artist,
        "top_context": top_context,
        "most_completed_track": most_completed_track,
    }


# ---------------------------------------------------------------------------
# HTML-generering
# ---------------------------------------------------------------------------

_TEMPLATE = """\
<!doctype html>
<html lang="no">
<head>
<meta charset="utf-8">
<title>Din Skip Wrapped{period}</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; background: #0d0d0d;
          color: #eee; margin: 0; padding: 40px 20px; }}
  .wrap {{ max-width: 640px; margin: 0 auto; }}
  h1 {{ color: #1db954; font-size: 2.2em; text-align: center; margin-bottom: 4px; }}
  .subtitle {{ text-align: center; color: #999; margin-bottom: 40px; }}
  .stat {{ background: #181818; border: 1px solid #2a2a2a; border-radius: 14px;
           padding: 28px; margin-bottom: 18px; text-align: center; }}
  .stat .label {{ color: #999; font-size: 0.95em; margin-bottom: 8px; }}
  .stat .value {{ color: #1db954; font-size: 1.7em; font-weight: bold; }}
  .stat .sub {{ color: #ccc; font-size: 0.95em; margin-top: 4px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Din Skip Wrapped{period}</h1>
  <div class="subtitle">Basert på {total_plays} loggede avspillinger</div>
  {cards}
</div>
</body>
</html>
"""


def _card(label: str, value: str, sub: str | None = None) -> str:
    label = _html.escape(label)
    value = _html.escape(value)
    sub_html = f'<div class="sub">{_html.escape(sub)}</div>' if sub else ""
    return (
        f'<div class="stat">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}</div>'
        f"{sub_html}"
        f"</div>"
    )


_MONTH_NAMES = [
    "", "januar", "februar", "mars", "april", "mai", "juni",
    "juli", "august", "september", "oktober", "november", "desember",
]


def build_wrapped_html(
    data: dict,
    month: int | None = None,
    year: int | None = None,
) -> str:
    cards: list[str] = []

    if data["top_track"]:
        title, artists, skip_count, play_count = data["top_track"]
        cards.append(_card(
            "Sangen du skipper mest",
            str(title),
            f"{artists} — skippet {skip_count} ganger",
        ))

    if data["top_listened_artist"]:
        artists, play_count = data["top_listened_artist"]
        cards.append(_card(
            "Artisten du hører mest på",
            str(artists),
            f"{play_count} avspillinger",
        ))

    if data["most_loyal_artist"]:
        artists, skip_count, play_count = data["most_loyal_artist"]
        rate = round(100 * skip_count / play_count) if play_count else 0
        cards.append(_card(
            "Din mest trofaste artist",
            str(artists),
            f"kun {rate}% skip-rate over {play_count} avspillinger",
        ))

    if data["top_context"]:
        context_name, play_count = data["top_context"]
        cards.append(_card(
            "Spilleliste/album du bruker mest",
            str(context_name or "Ukjent"),
            f"{play_count} avspillinger",
        ))

    if data["most_completed_track"]:
        title, artists, play_count = data["most_completed_track"]
        cards.append(_card(
            "Sangen du aldri skipper",
            str(title),
            f"{artists} — hørt {play_count} ganger uten et eneste skip",
        ))

    cards.append(_card(
        "Total skip-rate",
        f"{round(data['overall_skip_rate'] * 100)}%",
        f"{data['total_skips']} skip av {data['total_plays']} avspillinger",
    ))

    # Periodetekst for tittel
    if month and year:
        period = f" — {_MONTH_NAMES[month].capitalize()} {year}"
    elif year:
        period = f" — {year}"
    else:
        period = ""

    # Escape { og } i cards-innholdet så str.format() ikke feiltolker dem
    cards_html = "\n  ".join(cards).replace("{", "{{").replace("}", "}}")
    return _TEMPLATE.format(
        period=period,
        total_plays=data["total_plays"],
        cards=cards_html,
    )


# ---------------------------------------------------------------------------
# CLI-handling
# ---------------------------------------------------------------------------

def run_wrapped(month: int | None = None, year: int | None = None) -> None:
    """Genererer Wrapped-rapporten og åpner den i nettleseren."""
    # Hent Spotify-bruker-ID for å filtrere data til riktig bruker
    user_id = "default_user"
    try:
        creds = load_creds()
        token = get_access_token(creds)
        _me = _requests.get(
            "https://api.spotify.com/v1/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if _me.status_code == 200:
            user_id = _me.json().get("id") or "default_user"
    except Exception as exc:
        logger.warning("Wrapped: kunne ikke hente bruker-ID: %s. Bruker 'default_user'.", exc)

    data = build_wrapped_data(month=month, year=year, user_id=user_id)
    if data["total_plays"] == 0:
        print("Ingen data logget ennå. Kjør 'run' og hør på musikk en stund først.")
        sys.exit(1)

    html = build_wrapped_html(data, month=month, year=year)
    APP_DIR.mkdir(parents=True, exist_ok=True)
    WRAPPED_PATH.write_text(html, encoding="utf-8")

    logger.info("Wrapped-rapport generert: %s", WRAPPED_PATH)
    print(f"Wrapped-rapport generert: {WRAPPED_PATH}")
    webbrowser.open(WRAPPED_PATH.as_uri())
