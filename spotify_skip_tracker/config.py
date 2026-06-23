"""
Konfigurasjon og konstanter for Spotify Skip Tracker.
Alle miljøvariabler og innstillinger samles her.
"""

import os
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
SCOPE = "user-read-currently-playing user-read-playback-state user-modify-playback-state"

# ---------------------------------------------------------------------------
# Tracker-innstillinger
# ---------------------------------------------------------------------------

POLL_SECONDS: int = 7

# Andel av sangen som må ha spilt for at trackbytte IKKE teller som skip
SKIP_THRESHOLD: float = 0.9

# Minste gjenværende tid (ms) for at et tidlig trackbytte teller som skip.
# Forhindrer at naturlige outro-overganger logges som skip.
MIN_REMAINING_MS: int = 30_000
