"""
Railway-inngang: starter tracker i bakgrunnen og eksponerer Flask-appen
via gunicorn. Holdes separat fra app.py (som er Vercel sin inngang).
"""

import logging
import sys
import threading

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("server")

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

logger.info("server.py: oppretter Flask-app…")
app = create_flask_app()
logger.info("server.py: klar")
