"""
Innsiktsgenerator for Spotify Skip Tracker — Fase J.

Returnerer strukturerte Insight-objekter i stedet for ferdige tekststrenger.
Hvert objekt har fire lag som tilsvarer tre modningsstadier:

  Stadium 1 — Observasjon:   hva er tallet?
  Stadium 2 — Kontekst:      hva betyr det sammenlignet med noe annet?
  Stadium 3 — Forklaring:    hvorfor er det slik, og hva kan du gjøre?

Frontenden rendrer kun feltene som er fylt ut, slik at alle innsikter
kan oppgraderes fra stadium 1 til 3 uten API-endringer.

Innsikter som er implementert:
  weekly_skip_rate      — ukentlig skip-rate med trend vs. forrige uke
  impatient_day         — mest utålmodige ukedag vs. daglig snitt
  peak_skip_hour        — time på døgnet med høyest skip-rate
  best_streak           — lengste rekke sanger uten skip (all-time + gjeldende)
  janitor_status        — ventende Janitor-forslag med handlingsoppfordring
  session_start_pattern — høyere skip-rate på første sang i sesjon (krever session_id)
"""

import logging
from dataclasses import dataclass, asdict

from .database import execute, pooled_connection

logger = logging.getLogger(__name__)

_WEEKDAY_GEN = [
    "Mandager", "Tirsdager", "Onsdager", "Torsdager",
    "Fredager", "Lørdager", "Søndager",
]


# ---------------------------------------------------------------------------
# Dataklasse
# ---------------------------------------------------------------------------

@dataclass
class Insight:
    """
    Strukturert innsiktsobjekt.

    Feltene bygger oppå hverandre i stadier:
      Stadium 1: kun observation
      Stadium 2: observation + context + trend
      Stadium 3: alle fire felt

    Frontenden bruker stadium til å avgjøre hvilke felt som rendres
    og med hvilken visuell vekt.
    """
    id: str                        # Unik ID — for deduplicering og caching
    category: str                  # "skip_rate"|"streak"|"session"|"janitor"|"pattern"
    stadium: int                   # 1, 2 eller 3
    observation: str               # Alltid til stede — selve faktumet
    context: str | None = None     # Sammenligning/trend (stadium 2+)
    explanation: str | None = None # Årsaksforklaring (stadium 3)
    action: str | None = None      # Konkret handling brukeren kan ta (stadium 3)
    value: float | None = None     # Råverdi for grafer og sortering
    trend: str | None = None       # "up" | "down" | "stable"
    trend_is_positive: bool | None = None  # True=grønn, False=rød, None=nøytral

    def to_dict(self) -> dict:
        """Serialiserer til JSON-kompatibelt dict."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Innsiktsgeneratorer
# ---------------------------------------------------------------------------

def _insight_weekly_skip_rate(conn, user_id: str) -> Insight | None:
    """
    Ukentlig skip-rate med trend mot forrige uke.
    Stadium 1 om forrige uke mangler data, ellers stadium 2.
    """
    row = execute(
        conn,
        """
        SELECT
            COUNT(*) FILTER (WHERE timestamp >= NOW() - INTERVAL '7 days')
                AS tw_plays,
            SUM(CASE WHEN skipped AND timestamp >= NOW() - INTERVAL '7 days'
                THEN 1 ELSE 0 END)
                AS tw_skips,
            COUNT(*) FILTER (
                WHERE timestamp >= NOW() - INTERVAL '14 days'
                  AND timestamp <  NOW() - INTERVAL '7 days')
                AS lw_plays,
            SUM(CASE WHEN skipped
                      AND timestamp >= NOW() - INTERVAL '14 days'
                      AND timestamp <  NOW() - INTERVAL '7 days'
                THEN 1 ELSE 0 END)
                AS lw_skips
        FROM plays
        WHERE user_id = %s
        """,
        (user_id,),
    ).fetchone()

    tw_plays = int(row[0] or 0)
    tw_skips = int(row[1] or 0)
    lw_plays = int(row[2] or 0)
    lw_skips = int(row[3] or 0)

    if tw_plays < 5:
        return None

    tw_rate = tw_skips / tw_plays
    tw_pct = round(tw_rate * 100)
    observation = f"Din skip-rate denne uken er {tw_pct}%"

    if lw_plays < 5:
        return Insight(
            id="weekly_skip_rate", category="skip_rate", stadium=1,
            observation=observation,
            value=float(tw_pct),
        )

    lw_rate = lw_skips / lw_plays
    lw_pct = round(lw_rate * 100)
    delta = tw_rate - lw_rate
    delta_pp = round(abs(delta * 100), 1)

    if delta < -0.02:
        trend, tip = "down", True
        context = f"Forrige uke: {lw_pct}% — du er i bedring"
        explanation = "Du hører mer musikk ferdig enn forrige uke"
    elif delta > 0.02:
        trend, tip = "up", False
        context = f"Forrige uke: {lw_pct}% — du er mer utålmodig nå"
        explanation = None
    else:
        trend, tip = "stable", None
        context = f"Stabilt — forrige uke var det også {lw_pct}%"
        explanation = None

    return Insight(
        id="weekly_skip_rate", category="skip_rate", stadium=2,
        observation=observation, context=context, explanation=explanation,
        value=float(tw_pct), trend=trend, trend_is_positive=tip,
    )


def _insight_impatient_day(conn, user_id: str) -> Insight | None:
    """
    Mest utålmodige ukedag sammenlignet med daglig gjennomsnitt.
    Stadium 2 dersom avviket er > 5 pp, ellers stadium 1.
    """
    rows = execute(
        conn,
        """
        SELECT
            (EXTRACT(ISODOW FROM timestamp AT TIME ZONE 'Europe/Oslo')::INT - 1) AS wd,
            COUNT(*) AS plays,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END)::REAL / NULLIF(COUNT(*), 0) AS rate
        FROM plays
        WHERE user_id = %s
        GROUP BY wd
        HAVING COUNT(*) >= 5
        ORDER BY rate DESC
        """,
        (user_id,),
    ).fetchall()

    if not rows:
        return None

    rates = [float(r[2]) for r in rows if r[2] is not None]
    if not rates:
        return None

    avg_rate = sum(rates) / len(rates)
    top_wd, _, top_rate = rows[0]
    wd_idx = int(top_wd)
    day_name = _WEEKDAY_GEN[wd_idx] if 0 <= wd_idx <= 6 else "?"
    day_pct = round(float(top_rate) * 100)
    avg_pct = round(avg_rate * 100)
    delta_pp = round((float(top_rate) - avg_rate) * 100)

    observation = f"{day_name} er din mest utålmodige dag ({day_pct}% skip-rate)"

    if delta_pp >= 5:
        context = f"Ditt daglige snitt er {avg_pct}%"
        return Insight(
            id="impatient_day", category="pattern", stadium=2,
            observation=observation, context=context,
            value=float(day_pct), trend_is_positive=False,
        )

    return Insight(
        id="impatient_day", category="pattern", stadium=1,
        observation=observation,
        value=float(day_pct),
    )


def _insight_peak_hour(conn, user_id: str) -> Insight | None:
    """
    Time på døgnet med høyest skip-rate vs. globalt timessnitt.
    """
    row = execute(
        conn,
        """
        SELECT
            EXTRACT(HOUR FROM timestamp AT TIME ZONE 'Europe/Oslo')::INT AS hour,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END)::REAL / NULLIF(COUNT(*), 0) AS rate
        FROM plays
        WHERE user_id = %s
        GROUP BY hour
        HAVING COUNT(*) >= 5
        ORDER BY rate DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()

    if not row:
        return None

    hour = int(row[0])
    rate_pct = round(float(row[1]) * 100)

    avg_row = execute(
        conn,
        """
        SELECT SUM(CASE WHEN skipped THEN 1 ELSE 0 END)::REAL / NULLIF(COUNT(*), 0)
        FROM plays WHERE user_id = %s
        """,
        (user_id,),
    ).fetchone()
    avg_pct = round(float(avg_row[0]) * 100) if avg_row and avg_row[0] else 0
    delta_pp = rate_pct - avg_pct

    observation = f"Du skipper mest rundt kl. {hour}:00 ({rate_pct}% skip-rate)"

    if delta_pp >= 5:
        context = f"Gjennomsnitt for alle timer: {avg_pct}%"
        return Insight(
            id="peak_hour", category="pattern", stadium=2,
            observation=observation, context=context,
            value=float(hour), trend_is_positive=False,
        )

    return Insight(
        id="peak_hour", category="pattern", stadium=1,
        observation=observation, value=float(hour),
    )


def _insight_best_streak(conn, user_id: str) -> Insight | None:
    """
    Lengste rekke sanger uten et eneste skip (all-time).
    Hvis brukeren er i en aktiv streak på 5+, vises begge tall.
    Stadium 1 normalt, stadium 2 under aktiv streak.
    """
    # All-time best via gaps-and-islands
    streak_row = execute(
        conn,
        """
        WITH numbered AS (
            SELECT
                skipped,
                ROW_NUMBER() OVER (ORDER BY timestamp)
                - ROW_NUMBER() OVER (PARTITION BY skipped ORDER BY timestamp) AS grp
            FROM plays WHERE user_id = %s
        ),
        streaks AS (
            SELECT COUNT(*) AS len FROM numbered WHERE NOT skipped GROUP BY grp
        )
        SELECT COALESCE(MAX(len), 0) FROM streaks
        """,
        (user_id,),
    ).fetchone()
    best = int(streak_row[0]) if streak_row else 0

    if best < 3:
        return None

    # Gjeldende streak: tell ikke-skippede fra nyeste bakover til første skip
    recent = execute(
        conn,
        """
        SELECT skipped FROM plays WHERE user_id = %s
        ORDER BY timestamp DESC LIMIT 100
        """,
        (user_id,),
    ).fetchall()

    current = 0
    for (skipped,) in recent:
        if not skipped:
            current += 1
        else:
            break

    if current >= 5:
        observation = f"Du er i en streak — {current} sanger på rad uten skip"
        context = f"Rekorden din er {best} sanger"
        return Insight(
            id="best_streak", category="streak", stadium=2,
            observation=observation, context=context,
            value=float(current), trend="up", trend_is_positive=True,
        )

    return Insight(
        id="best_streak", category="streak", stadium=1,
        observation=f"Rekorden din er {best} sanger på rad uten skip",
        value=float(best),
    )


def _insight_janitor_status(conn, user_id: str) -> Insight | None:
    """
    Antall ventende Janitor-forslag med kontekstuell handlingsoppfordring.
    Stadium 1 om ingen forslag, stadium 2 med action om mange.
    """
    row = execute(
        conn,
        "SELECT COUNT(*) FROM janitor_suggestions WHERE user_id = %s AND status = 'pending'",
        (user_id,),
    ).fetchone()
    count = int(row[0]) if row else 0

    if count == 0:
        return Insight(
            id="janitor_status", category="janitor", stadium=1,
            observation="Playlist Janitor har ingen ventende forslag",
            value=0.0, trend_is_positive=True,
        )

    observation = f"{count} sang{'er' if count != 1 else ''} venter i Playlist Janitor"

    if count >= 10:
        return Insight(
            id="janitor_status", category="janitor", stadium=2,
            observation=observation,
            context="Spillelistene dine trenger oppmerksomhet",
            action="Gå til Playlist Janitor og gjennomgå forslagene",
            value=float(count), trend_is_positive=False,
        )
    if count >= 3:
        return Insight(
            id="janitor_status", category="janitor", stadium=2,
            observation=observation,
            context="Noen kandidater er klare for gjennomgang",
            value=float(count), trend_is_positive=None,
        )

    return Insight(
        id="janitor_status", category="janitor", stadium=1,
        observation=observation, value=float(count),
    )


def _insight_session_start_pattern(conn, user_id: str) -> Insight | None:
    """
    Sammenligner skip-rate på første sang i en sesjon med resten.
    Krever session_id-data — returnerer None til backfill er fullført.
    Stadium 2 ved moderat avvik, stadium 3 ved stort avvik.
    """
    has_data = execute(
        conn,
        "SELECT 1 FROM plays WHERE user_id = %s AND session_id IS NOT NULL LIMIT 1",
        (user_id,),
    ).fetchone()
    if not has_data:
        return None

    row = execute(
        conn,
        """
        WITH positions AS (
            SELECT
                skipped,
                ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY timestamp) AS pos
            FROM plays
            WHERE user_id = %s AND session_id IS NOT NULL
        )
        SELECT
            AVG(CASE WHEN pos = 1 THEN skipped::INT END)  AS first_rate,
            AVG(CASE WHEN pos > 1 THEN skipped::INT END)  AS rest_rate,
            COUNT(DISTINCT session_id)                     AS sessions
        FROM positions
        """,
        (user_id,),
    ).fetchone()

    if not row or row[0] is None or row[1] is None or int(row[2] or 0) < 10:
        return None

    first_pct = round(float(row[0]) * 100)
    rest_pct = round(float(row[1]) * 100)
    sessions = int(row[2])
    delta = first_pct - rest_pct

    if delta >= 20:
        return Insight(
            id="session_start_pattern", category="session", stadium=3,
            observation=f"Du starter lyttesesjoner utålmodig ({first_pct}% skip på første sang)",
            context=f"Etter første sang faller skip-raten til {rest_pct}%",
            explanation=f"De første sangene i en sesjon skippes langt oftere enn resten",
            action="Vurder å lage spillelister med trygge, kjente sanger som åpning",
            value=float(first_pct), trend_is_positive=False,
        )
    if delta >= 10:
        return Insight(
            id="session_start_pattern", category="session", stadium=2,
            observation=f"Første sang i en sesjon skippes oftere ({first_pct}% vs {rest_pct}%)",
            context=f"Basert på {sessions} lyttesesjoner",
            value=float(first_pct), trend_is_positive=None,
        )

    return None  # Ikke interessant nok å vise


# ---------------------------------------------------------------------------
# Hoved-innsiktsgenerator
# ---------------------------------------------------------------------------

def generate_insights(user_id: str = "default_user") -> list[Insight]:
    """
    Genererer alle tilgjengelige innsikter for brukeren.

    Returnerer en liste av Insight-objekter sortert etter stadium (3→1)
    slik at de mest forklarende innsiktene vises øverst.

    Feil i én generator isoleres slik at resten alltid returneres.
    """
    generators = [
        _insight_weekly_skip_rate,
        _insight_impatient_day,
        _insight_peak_hour,
        _insight_best_streak,
        _insight_janitor_status,
        _insight_session_start_pattern,
    ]

    with pooled_connection() as conn:
        insights: list[Insight] = []
        for gen in generators:
            try:
                result = gen(conn, user_id)
                if result is not None:
                    insights.append(result)
            except Exception as exc:
                logger.warning(
                    "Insight-generator '%s' feilet (ignorerer): %s",
                    gen.__name__, exc,
                )

    # Høyest stadium øverst, deretter stabil sortering på id
    insights.sort(key=lambda i: (-i.stadium, i.id))
    return insights
