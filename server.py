"""
Railway-inngang: starter tracker i bakgrunnen og eksponerer Flask-appen
via gunicorn. Holdes separat fra app.py (som er Vercel sin inngang).

Playlist Janitor kjøres via railway.json-cron-tjenesten (daglig kl. 03:00 UTC)
som en separat Railway-service. Den tidligere in-process scheduleren er fjernet
for å unngå dobbelt kjøring.
"""

import logging
import os
import sys
import threading

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("server")

# ---------------------------------------------------------------------------
# Oppstartvalidering — feil som bør fanges opp FØR gunicorn tar over
# ---------------------------------------------------------------------------

def _validate_environment() -> None:
    """
    Sjekker at kritiske miljøvariabler er satt.

    SECRET_KEY: Dersom den mangler, genererer Flask en tilfeldig nøkkel
    ved hver oppstart. Alle aktive dashbordsesjoner (session-cookies)
    invalideres da ved hver Railway-deploy. For en multi-bruker alpha
    er dette uakseptabelt — brukere kastes ut uten varsel.

    Kjøres kun på Railway (RAILWAY_ENVIRONMENT satt) slik at lokal
    utvikling ikke hindres.
    """
    is_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT"))

    if is_railway and not os.environ.get("SECRET_KEY"):
        logger.critical(
            "KRITISK: SECRET_KEY er ikke satt som miljøvariabel på Railway. "
            "Flask genererer en tilfeldig nøkkel ved hver omstart, noe som "
            "ugyldiggjør alle aktive brukersesjoner ved hver deploy. "
            "Sett SECRET_KEY til en fast tilfeldig streng i Railway-prosjektets "
            "Variables-fane: python3 -c \"import secrets; print(secrets.token_hex(32))\""
        )
        # Advarer, men avslutter ikke — appen fungerer, sesjoner er bare kortlevde.

    if is_railway and not os.environ.get("TOKEN_ENCRYPTION_KEY"):
        logger.warning(
            "ADVARSEL: TOKEN_ENCRYPTION_KEY er ikke satt. Refresh-tokens lagres "
            "i klartekst i databasen. Generer en nøkkel og sett den i Railway: "
            "python3 -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )

    missing = [
        var for var in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET",
                        "SPOTIFY_REFRESH_TOKEN", "DATABASE_URL")
        if not os.environ.get(var)
    ]
    if missing:
        logger.critical(
            "KRITISK: Følgende påkrevde miljøvariabler mangler: %s. "
            "Appen vil sannsynligvis feile ved oppstart.",
            ", ".join(missing),
        )


_validate_environment()

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

logger.info("server.py: oppretter Flask-app…")
app = create_flask_app()
logger.info("server.py: klar")
