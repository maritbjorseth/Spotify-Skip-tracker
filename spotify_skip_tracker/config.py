"""
Konfigurasjon og konstanter for Spotify Skip Tracker.
Alle miljøvariabler og innstillinger samles her.
"""

import os
import secrets as _secrets
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).parent.parent
load_dotenv(_REPO_ROOT / ".env.local")
load_dotenv(_REPO_ROOT / ".env")

# ---------------------------------------------------------------------------
# Databasetilkobling
# ---------------------------------------------------------------------------

DATABASE_URL: str | None = os.environ.get("DATABASE_URL")

# ---------------------------------------------------------------------------
# Spotify-legitimasjon (leses fra .env.local / miljøvariabler)
# Fallback til ~/.spotify_skip_tracker/credentials.json håndteres i spotify_api.py
# ---------------------------------------------------------------------------

SPOTIFY_CLIENT_ID: str | None = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET: str | None = os.environ.get("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REFRESH_TOKEN: str | None = os.environ.get("SPOTIFY_REFRESH_TOKEN")

# ---------------------------------------------------------------------------
# Lokale filstier (brukes ikke i cloud-modus)
# ---------------------------------------------------------------------------

APP_DIR = Path.home() / ".spotify_skip_tracker"
CREDS_PATH = APP_DIR / "credentials.json"
WRAPPED_PATH = APP_DIR / "wrapped.html"

# ---------------------------------------------------------------------------
# Spotify OAuth
# ---------------------------------------------------------------------------

REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = (
    "user-read-currently-playing "
    "user-read-playback-state "
    "user-modify-playback-state "
    "playlist-modify-public "
    "playlist-modify-private "
    "playlist-read-private "
    "playlist-read-collaborative "
    "user-read-email"
)

# ---------------------------------------------------------------------------
# Spotify-bruker-ID (for data-migrasjon)
# ---------------------------------------------------------------------------

# Sett SPOTIFY_USER_ID til din faktiske Spotify-ID (f.eks. "ulrikj") i Railway.
# Brukes av bootstrap-migrasjonen i database.py til å flytte historiske
# 'default_user'-rader til riktig ID dersom trackeren ikke har kjørt ennå.
# Ikke strengt nødvendig dersom trackeren allerede har logget minst én
# avspilling med ekte ID — migrasjonen finner den da automatisk.
SPOTIFY_USER_ID: str | None = os.environ.get("SPOTIFY_USER_ID") or None

# ---------------------------------------------------------------------------
# Token-kryptering (multi-user)
# ---------------------------------------------------------------------------

# Fernet-nøkkel for kryptering av refresh-tokens i user_tokens-tabellen.
# Generer med:
#   python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Lagres som miljøvariabel TOKEN_ENCRYPTION_KEY på Railway.
# Uten denne nøkkelen lagres tokens i klartekst (akseptabelt i utvikling,
# ikke i produksjon med ekte brukere).
TOKEN_ENCRYPTION_KEY: str | None = os.environ.get("TOKEN_ENCRYPTION_KEY") or None

# ---------------------------------------------------------------------------
# Dashboard-tilgangskontroll
# ---------------------------------------------------------------------------

# Sett DASHBOARD_PASSWORD i Railway-miljøet for å beskytte dashbordet med passord.
# Hvis variabelen ikke er satt, er dashbordet åpent (praktisk lokalt).
DASHBOARD_PASSWORD: str | None = os.environ.get("DASHBOARD_PASSWORD") or None

# Flask trenger en stabil SECRET_KEY for å signere sesjonscookies.
# Sett SECRET_KEY som en fast tilfeldig streng i Railway — ellers ugyldiggjøres
# alle sesjoner ved hver omstart / ny deploy.
FLASK_SECRET_KEY: str = os.environ.get("SECRET_KEY") or _secrets.token_hex(32)

# ---------------------------------------------------------------------------
# Web OAuth (valgfritt — kun nødvendig for browser-basert innlogging)
# ---------------------------------------------------------------------------

# Callback-URL som er registrert i Spotify Developer Dashboard for web-OAuth.
# Eksempel: https://spotify-skip-tracker-production.up.railway.app/api/auth/callback
REDIRECT_URI_WEB: str | None = os.environ.get("REDIRECT_URI_WEB")

# URL til Vercel-frontenden — hit sendes brukeren etter vellykket innlogging.
FRONTEND_URL: str = os.environ.get("FRONTEND_URL", "https://spotify-skip-tracker.vercel.app")

# ---------------------------------------------------------------------------
# Tracker-innstillinger
# ---------------------------------------------------------------------------

POLL_SECONDS: int = 7

# Antall minutter uten aktivitet før en ny lyttesesjon regnes som startet.
# Brukes av tracker.py (sanntid) og database.py (backfill av historiske data).
SESSION_GAP_MINUTES: int = 30

# Andel av sangen som må ha spilt for at trackbytte IKKE teller som skip
SKIP_THRESHOLD: float = 0.9

# Minste gjenværende tid (ms) for at et tidlig trackbytte teller som skip.
# Forhindrer at naturlige outro-overganger logges som skip.
MIN_REMAINING_MS: int = 30_000

# ---------------------------------------------------------------------------
# Demo-modus
# ---------------------------------------------------------------------------

# Sett DEMO_MODE=true i Railway for å aktivere det åpne demo-innloggingspunktet.
# Alle andre installasjoner beholder standardverdien false.
DEMO_MODE: bool = os.environ.get("DEMO_MODE", "false").lower() == "true"
