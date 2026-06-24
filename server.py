"""
Railway-inngang: starter tracker i bakgrunnen og eksponerer Flask-appen
via gunicorn. Holdes separat fra app.py (som er Vercel sin inngang).

Inneholder også en in-process janitor-scheduler som kjører daglig kl. 03:00 UTC.
Dette komplementerer railway.json-cron-tjenesten og sikrer at jobben kjøres
selv om Railway-cron-tjenesten ikke er satt opp som separat service.
"""

import logging
import sys
import threading
import time
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("server")

# ---------------------------------------------------------------------------
# Janitor-scheduler — kjøres som daemon-tråd
# ---------------------------------------------------------------------------

_JANITOR_HOUR_UTC = 3      # kl. 03:00 UTC
_JANITOR_MIN_PLAYS = 2
_JANITOR_MIN_SCORE = 0.50
_JANITOR_POLL_INTERVAL = 60  # sjekk hvert minutt


def _janitor_scheduler() -> None:
    """
    Bakgrunnstråd som kjører Playlist Janitor én gang per dag kl. 03:00 UTC.
    Sover 10 minutter etter kjøring for å unngå dobbelkjøring innen samme time.
    """
    logger.info("janitor-scheduler: startet (kjører daglig kl. %02d:00 UTC)", _JANITOR_HOUR_UTC)
    _last_run_date: str | None = None

    while True:
        try:
            now = datetime.now(tz=timezone.utc)
            today = now.strftime("%Y-%m-%d")

            if now.hour == _JANITOR_HOUR_UTC and _last_run_date != today:
                _last_run_date = today
                logger.info(
                    "janitor-scheduler: trigger kl. %s UTC — starter Playlist Janitor",
                    now.strftime("%H:%M:%S"),
                )
                try:
                    from spotify_skip_tracker.janitor import run_janitor
                    result = run_janitor(
                        min_plays=_JANITOR_MIN_PLAYS,
                        min_score=_JANITOR_MIN_SCORE,
                        dry_run=False,
                    )
                    logger.info(
                        "janitor-scheduler: ferdig — %d spillelister analysert, "
                        "%d kandidater funnet og lagret",
                        result["playlists_analysed"],
                        result["total_candidates"],
                    )
                except Exception as exc:
                    logger.error("janitor-scheduler: kjøring feilet — %s", exc, exc_info=True)

                # Sov 10 min etter kjøring for å unngå gjentatt trigger i samme time
                time.sleep(600)
                continue

        except Exception as exc:
            logger.error("janitor-scheduler: uventet feil i schedulerløkke — %s", exc)

        time.sleep(_JANITOR_POLL_INTERVAL)


# ---------------------------------------------------------------------------
# Oppstart
# ---------------------------------------------------------------------------

logger.info("server.py: importerer moduler…")
from spotify_skip_tracker.database import connect, init_db
from spotify_skip_tracker.tracker import polling_loop
from spotify_skip_tracker.web import create_flask_app

logger.info("server.py: kobler til database…")
try:
    _conn = connect()
    init_db(_conn)
    _conn.close()
    logger.info("server.py: database OK")
except Exception as exc:
    logger.error("server.py: DB-feil ved oppstart: %s", exc)

logger.info("server.py: starter tracker…")
try:
    _t = threading.Thread(target=polling_loop, daemon=True)
    _t.start()
    logger.info("server.py: tracker startet")
except Exception as exc:
    logger.error("server.py: tracker feil: %s", exc)

logger.info("server.py: starter janitor-scheduler…")
try:
    _js = threading.Thread(target=_janitor_scheduler, daemon=True, name="janitor-scheduler")
    _js.start()
    logger.info("server.py: janitor-scheduler startet")
except Exception as exc:
    logger.error("server.py: janitor-scheduler feil: %s", exc)

logger.info("server.py: oppretter Flask-app…")
app = create_flask_app()
logger.info("server.py: klar")
