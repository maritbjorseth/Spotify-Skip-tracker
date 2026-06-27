"""
Railway-inngang: starter tracker-manager i bakgrunnen og eksponerer Flask-appen
via gunicorn. Holdes separat fra app.py (som er Vercel sin inngang).

tracker_manager() starter én tracking-tråd per bruker i user_tokens-tabellen.
Nye brukere får tracker via ensure_tracker_running() i auth_callback() (web.py).

Playlist Janitor kjøres via railway.json-cron-tjenesten (daglig kl. 03:00 UTC)
som en separat Railway-service.
"""

import logging
import os
import sys

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
    Sjekker at kritiske miljøvariabler er satt og logger advarsler.

    SECRET_KEY: mangler denne, ugyldiggjøres alle sesjoner ved redeployment.
    TOKEN_ENCRYPTION_KEY: mangler denne, lagres refresh-tokens i klartekst.
    SPOTIFY_REFRESH_TOKEN: valgfri i multi-user-modus (OAuth erstatter den),
        men nødvendig for enkelt-bruker/legacy-modus.

    Kjøres kun på Railway (RAILWAY_ENVIRONMENT satt) slik at lokal
    utvikling ikke hindres av manglende produksjonsvariabler.
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

    if is_railway and not os.environ.get("TOKEN_ENCRYPTION_KEY"):
        logger.warning(
            "ADVARSEL: TOKEN_ENCRYPTION_KEY er ikke satt. Refresh-tokens lagres "
            "i klartekst i databasen. Generer en nøkkel og sett den i Railway: "
            "python3 -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )

    missing_critical = [
        var for var in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "DATABASE_URL")
        if not os.environ.get(var)
    ]
    if missing_critical:
        logger.critical(
            "KRITISK: Følgende påkrevde miljøvariabler mangler: %s. "
            "Appen vil sannsynligvis feile ved oppstart.",
            ", ".join(missing_critical),
        )

    if is_railway and not os.environ.get("SPOTIFY_REFRESH_TOKEN"):
        logger.info(
            "SPOTIFY_REFRESH_TOKEN er ikke satt. I multi-user-modus er dette OK — "
            "brukere autentiserer via /api/auth/login. "
            "For enkelt-bruker/legacy-modus: sett SPOTIFY_REFRESH_TOKEN."
        )


_validate_environment()

# ---------------------------------------------------------------------------
# Oppstart
# ---------------------------------------------------------------------------

logger.info("server.py: importerer moduler…")
from spotify_skip_tracker.database import connect, init_db
from spotify_skip_tracker.tracker import tracker_manager
from spotify_skip_tracker.web import create_flask_app

logger.info("server.py: kobler til database og kjører migrasjoner…")
try:
    _conn = connect()
    init_db(_conn)
    _conn.close()
    logger.info("server.py: database OK")
except Exception as exc:
    logger.error("server.py: DB-feil ved oppstart: %s", exc)

logger.info("server.py: starter tracker-manager…")
try:
    tracker_manager()
    logger.info("server.py: tracker-manager kjørt")
except Exception as exc:
    logger.error("server.py: tracker_manager feilet: %s", exc)

logger.info("server.py: oppretter Flask-app…")
app = create_flask_app()
logger.info("server.py: klar")
