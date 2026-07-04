# Spotify Skip Tracker

**First time installing?**
- 📖 [INSTALLATION.md](INSTALLATION.md) — full step-by-step guide with screenshots
- 🤖 [AI_INSTALL.md](AI_INSTALL.md) — use ChatGPT, Claude, or Gemini as an installation assistant

---

> An honest mirror for your listening habits. Automatically tracks every Spotify play across all your devices, detects skips, and surfaces patterns over time — which songs you always skip, which playlists trigger the most skipping, and when during the day you're most impatient.

![Dashboard screenshot](docs/screenshots/Dashboard.png)

---

## Features

### Core Tracking
- **Cross-device skip detection** — polls the Spotify Web API every 7 seconds and detects skips retroactively when the next track starts
- **Accurate skip logic** — a track is only counted as skipped if less than 90% was played, more than 30 seconds remained, and the skip was not caused by a shuffle toggle or playlist switch
- **Multi-user support** — one independent tracking thread per Spotify account; each user's data is fully isolated
- **Persistent tracking** — runs continuously on Railway, survives token expiration and brief network failures

### Dashboard
- **Now Playing** — live widget showing the current track with album art and historical skip rate; served from a 30-second cache with a direct Spotify API fallback
- **Statistics overview** — total plays, total skips, overall skip rate, and longest listening streak
- **Charts** — skip rate by hour of day, by day of week, by artist, and by context (playlist / album)
- **Weekly skip trend** — rolling 7-day skip rate over the last 12 weeks
- **Activity heatmap** — skip rate per day for the last 365 days
- **Top tables** — most-skipped songs, most-completed songs, and most-active listening contexts
- **Listening score** — a 0–100 score derived from completion rate, streak consistency, and session depth

### Intelligence
- **Music Coach** — structured insights about your listening patterns (session timing, skip streaks, context behaviour)
- **Smart Skipper** — automatically skips songs on Spotify when their personal skip rate exceeds a configurable threshold; includes dry-run mode and per-context exclusions
- **Playlist Janitor** — analyses your playlists and surfaces consistently-skipped tracks as removal candidates; supports undo via Spotify snapshot IDs

### Utilities
- **"Wrapped" report** — generates a static HTML summary for any month/year
- **CSV export** — exports all logged plays to a spreadsheet-compatible file
- **Album art backfill** — retroactively fetches missing artwork for historical plays
- **Demo mode** — serves the dashboard with static fixture data for public demos without exposing real listening history

### Internationalisation
- Full i18n via `i18next`; ships with **Norwegian Bokmål** (default) and **English**
- Language preference persisted in `localStorage`; new languages require only a JSON translation file

---

## Tech Stack

### Backend
| Layer | Technology |
|---|---|
| Language | Python 3.12+ |
| Web framework | Flask 3 + Flask-CORS |
| WSGI server | Gunicorn |
| Database driver | psycopg2-binary |
| HTTP client | requests |
| Token encryption | cryptography (Fernet / AES-128-CBC + HMAC-SHA256) |
| Environment | python-dotenv |

### Frontend
| Layer | Technology |
|---|---|
| Framework | React 19 |
| Language | TypeScript 6 |
| Styling | Tailwind CSS 4 |
| Build tool | Vite 8 |
| Data fetching | TanStack React Query 5 |
| Charts | Recharts 3 |
| Animations | Framer Motion 12 |
| Icons | Lucide React |
| i18n | i18next + react-i18next + browser-languagedetector |

### Infrastructure
| Service | Role |
|---|---|
| [Railway](https://railway.app) | Runs the tracker process 24/7; hosts the Flask API |
| [Vercel](https://vercel.com) | Hosts the static React frontend |
| [Neon](https://neon.tech) | Managed serverless Postgres (shared database) |

---

## Architecture

```
┌─────────────────────────────────────┐     ┌──────────────────────┐
│             Railway                 │     │        Vercel        │
│                                     │     │                      │
│  ┌─────────────────────────────┐    │     │  ┌────────────────┐  │
│  │  tracker thread (per user)  │    │     │  │  React SPA     │  │
│  │  polls /v1/me/player @ 7s   │    │     │  │  (static build)│  │
│  │  writes → now_playing       │    │     │  └───────┬────────┘  │
│  │  writes → plays             │    │     │          │ fetch      │
│  └──────────────┬──────────────┘    │     └──────────┼───────────┘
│                 │ psycopg2          │                │
│  ┌──────────────▼──────────────┐    │     ┌──────────▼───────────┐
│  │  Flask API  (Gunicorn)      │◄───┼─────┤  /api/now            │
│  │  /api/now, /api/stats, …    │    │     │  /api/stats          │
│  └──────────────┬──────────────┘    │     │  /api/auth/*         │
└─────────────────┼───────────────────┘     └──────────┬───────────┘
                  │                                     │
                  ▼                                     │
         ┌────────────────┐                            │
         │  Neon Postgres │◄───────────────────────────┘
         │                │      pooled reads
         │  plays         │
         │  now_playing   │
         │  user_tokens   │
         │  contexts      │
         └────────────────┘
```

### Skip Detection

Skip detection is retroactive: the tracker learns that a song was skipped only when the *next* track starts. At that point it evaluates the previous track:

```python
def is_skip(ratio, remaining_ms, shuffle_toggled, context_switched) -> bool:
    return (
        ratio < 0.9           # less than 90% played
        and remaining_ms >= 30_000  # more than 30 seconds remained
        and not shuffle_toggled     # not a shuffle-induced skip
        and not context_switched    # not a playlist/context change
    )
```

### Database Schema

```sql
plays              -- every completed or skipped track
now_playing        -- current track per user (updated every poll)
user_tokens        -- encrypted Spotify refresh tokens per user
contexts           -- cached playlist/album display names
auto_skips         -- Smart Skipper audit log
smart_skipper_config -- per-user Smart Skipper settings
janitor_suggestions  -- Playlist Janitor removal candidates
janitor_removals     -- confirmed Playlist Janitor removals (with undo support)
```

---

## Installation

> **New to Railway, Neon, Vercel, or Spotify APIs?**  
> See [INSTALLATION.md](INSTALLATION.md) for a step-by-step guide that explains every command, what you should see at each stage, and how to fix common errors.  
> If you want an AI assistant to guide you through the process, see [AI_INSTALL.md](AI_INSTALL.md).

### Prerequisites

- Python 3.12+
- Node.js 20+ (for the frontend)
- A **Spotify Premium** account — required to create a Web API app in the Spotify Developer Dashboard
- A [Spotify Developer App](https://developer.spotify.com/dashboard) — two redirect URIs must be registered:
  - `http://127.0.0.1:8888/callback` — used by the one-time CLI `setup` command
  - `http://127.0.0.1:5000/api/auth/callback` — used by the web-based login at `/api/auth/login`
- A Postgres database (local or [Neon](https://neon.tech))

### Backend

```bash
# Clone the repository
git clone https://github.com/your-username/spotify-skip-tracker.git
cd spotify-skip-tracker

# Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows

# Install Python dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.local.example .env.local
# Edit .env.local — see Environment Variables below

# Authenticate with Spotify (one-time, opens a browser window)
# Note: client-id and client-secret are passed directly here because the
# setup command runs before the main server and does not read .env.local.
# The values you set in .env.local are used by the `run` command.
python3 -m spotify_skip_tracker setup \
  --client-id YOUR_CLIENT_ID \
  --client-secret YOUR_CLIENT_SECRET
# Credentials are saved to ~/.spotify_skip_tracker/credentials.json

# Run tracker + API server locally (http://localhost:5000)
# DATABASE_URL must be set in .env.local before running this command.
python3 -m spotify_skip_tracker run
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # starts Vite dev server at http://localhost:5173
```

If everything is working, navigate to `http://localhost:5173`. You should see the login screen. Log in with your Spotify account to start the tracker and open the dashboard.

---

## Environment Variables

### Backend (`.env.local` for local development; Railway environment variables in production)

| Variable | When required | Description |
|---|---|---|
| `DATABASE_URL` | **Before `run`** | Postgres connection string (e.g. `postgresql://user:pass@host/db?sslmode=require`). Not needed for the `setup` command. |
| `SPOTIFY_CLIENT_ID` | **Yes** | From your Spotify Developer App. |
| `SPOTIFY_CLIENT_SECRET` | **Yes** | From your Spotify Developer App. |
| `TOKEN_ENCRYPTION_KEY` | Recommended | Fernet key for encrypting refresh tokens at rest. Generate with: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `SECRET_KEY` | Recommended | Flask session signing key. Auto-generated if not set, but a new value on every restart invalidates all active sessions. Set a stable value in production. |
| `REDIRECT_URI_WEB` | **Local + prod** | Spotify OAuth callback URL for web-based login. Local: `http://127.0.0.1:5000/api/auth/callback`. Production: `https://your-railway-app.up.railway.app/api/auth/callback`. Must be registered in your Spotify Developer App. |
| `FRONTEND_URL` | **Local + prod** | URL of the frontend — used for CORS and post-login redirect. Local: `http://localhost:5173`. Production: your Vercel URL. |
| `SPOTIFY_REFRESH_TOKEN` | Legacy | Only needed for single-user / legacy mode. Multi-user setups authenticate via the web OAuth flow instead. |
| `SPOTIFY_USER_ID` | Optional | Your Spotify user ID. Used by the bootstrap migration to backfill historical plays tagged `default_user`. |
| `DEMO_MODE` | Optional | Set to `true` to enable the `/api/auth/demo` endpoint for public demos. |

### Frontend

No `frontend/.env.local` file is needed for local development. The Vite dev server proxies all `/api` requests to `http://127.0.0.1:5000` automatically via `vite.config.ts`.

For production (Vercel), the API URL is resolved automatically based on the hostname. No environment variable configuration is required in Vercel beyond what is set in the Vercel dashboard.

| Variable | When required | Description |
|---|---|---|
| `VITE_IS_PUBLIC_DEMO` | Optional | Set to `true` when hosting a public demo. Displays an informational notice on the login page explaining that "Log in with Spotify" is unavailable and that the data is constructed sample data. Leave unset for all self-hosted installations. |

---

## Development

### Running locally

```bash
# Terminal 1 — Python API + tracker (http://localhost:5000)
python3 -m spotify_skip_tracker run

# Terminal 2 — Vite dev server with HMR (http://localhost:5173)
cd frontend && npm run dev
```

The React dev server proxies API requests to `localhost:5000` via the Vite config. Use the Vite dev server for all frontend verification — do not rely on Flask's static file serving during development.

### CLI reference

```bash
# One-time Spotify authentication
python3 -m spotify_skip_tracker setup --client-id ID --client-secret SECRET

# Start tracker + dashboard locally
python3 -m spotify_skip_tracker run

# Start tracker only (no dashboard) — used by Railway
python3 -m spotify_skip_tracker track

# Generate a "Wrapped"-style HTML report
python3 -m spotify_skip_tracker wrapped
python3 -m spotify_skip_tracker wrapped --month 6 --year 2026

# Export all plays to CSV
python3 -m spotify_skip_tracker export --output plays.csv

# Backfill missing album art for historical plays
python3 -m spotify_skip_tracker backfill

# Smart Skipper management
python3 -m spotify_skip_tracker smart-skipper status
python3 -m spotify_skip_tracker smart-skipper enable
python3 -m spotify_skip_tracker smart-skipper threshold 0.80

# Playlist Janitor (dry-run by default)
python3 -m spotify_skip_tracker janitor
python3 -m spotify_skip_tracker janitor --playlist "Favourites" --min-score 0.70 --no-dry-run
```

### Running tests

```bash
# Skip detection unit tests (no database required)
pytest tests/test_tracker.py -v

# Database integration tests (requires DATABASE_URL)
DATABASE_URL=postgresql://... pytest tests/test_stats.py -v

# All tests
DATABASE_URL=postgresql://... pytest -v
```

### Code structure

```
spotify_skip_tracker/
├── __init__.py        # exports create_flask_app (Vercel entrypoint)
├── __main__.py        # CLI entrypoint (argparse)
├── config.py          # all constants and environment variable loading
├── database.py        # connection pool, init_db, schema migrations
├── spotify_api.py     # OAuth flow, token refresh, context name cache
├── tracker.py         # is_skip() logic, polling_loop, _upsert_now_playing
├── stats.py           # compute_stats() → JSON for /api/stats
├── insights.py        # generate_insights() — Music Coach analysis
├── smart_skipper.py   # SmartSkipper class — evaluate() and auto-skip logic
├── janitor.py         # Playlist Janitor — candidate scoring and removal
├── token_crypto.py    # Fernet-based encrypt/decrypt for refresh tokens
├── wrapped.py         # build_wrapped_data, build_wrapped_html, run_wrapped
├── export.py          # CSV export
├── web.py             # create_flask_app(), all Flask routes
└── dashboard.html     # legacy dashboard fallback (loaded by web.py)

frontend/src/
├── components/
│   ├── NowPlaying.tsx
│   ├── StatCards.tsx
│   ├── Charts.tsx
│   ├── SkipTrendChart.tsx
│   ├── SkipHeatmap.tsx
│   ├── Tables.tsx
│   ├── ListeningScorePanel.tsx
│   ├── CoachInsightsPanel.tsx
│   ├── SmartSkipperPanel.tsx
│   ├── PlaylistJanitorPanel.tsx
│   └── LanguageSelector.tsx
├── locales/
│   ├── nb.json        # Norwegian Bokmål (default)
│   └── en.json        # English
├── api.ts             # React Query hooks and API client
├── types.ts           # TypeScript interfaces
└── i18n.ts            # i18next initialisation

tests/
├── test_tracker.py    # 14 unit tests for is_skip() — no DB required
└── test_stats.py      # integration tests for compute_stats()
```

---

## Deployment

This project uses a split deployment model: the tracking process runs on Railway, the frontend is served by Vercel, and both share a single Neon Postgres database.

### Neon (Database)

1. Create a project at [neon.tech](https://neon.tech)
2. Copy the connection string — it will be used as `DATABASE_URL` on both Railway and Vercel
3. The schema is created automatically on first startup via `init_db()`; no manual migration step is needed

### Railway (Tracker + API)

1. Create a new Railway project and connect your repository
2. Railway will use `railway.toml` automatically:
   ```toml
   [deploy]
   startCommand = "gunicorn server:app --bind 0.0.0.0:$PORT --timeout 120 --workers 1"
   restartPolicyType = "ALWAYS"
   ```
3. Set the following environment variables in Railway:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | Your Neon connection string |
   | `SPOTIFY_CLIENT_ID` | From Spotify Developer Dashboard |
   | `SPOTIFY_CLIENT_SECRET` | From Spotify Developer Dashboard |
   | `TOKEN_ENCRYPTION_KEY` | Generated Fernet key |
   | `SECRET_KEY` | A stable random string |
   | `REDIRECT_URI_WEB` | `https://<your-railway-domain>/api/auth/callback` |
   | `FRONTEND_URL` | Your Vercel deployment URL |

4. Add `https://<your-railway-domain>/api/auth/callback` to your Spotify app's redirect URIs

### Vercel (Frontend)

1. Create a new Vercel project and connect your repository
2. Vercel will use `vercel.json` automatically:
   ```json
   {
     "buildCommand": "cd frontend && npm install && npm run build",
     "outputDirectory": "frontend/dist",
     "rewrites": [{ "source": "/:path*", "destination": "/index.html" }]
   }
   ```

### First login after deployment

Navigate to `https://<your-railway-domain>/api/auth/login` to complete the Spotify OAuth flow. This stores your encrypted refresh token in the database and starts the tracking thread. Subsequent visits use the React frontend on Vercel.

---


## Screenshots

| Dashboard | Grafer | Mest skippede sanger |
|---|---|---|
| ![Dashboard](docs/screenshots/Dashboard.png) | ![Grafer](docs/screenshots/Grafer.png) | ![Mest skippede sanger](docs/screenshots/Mest-skippede-sanger.png) |

| Smart Skipper | Playlist Janitor | Musikk Coach |
|---|---|---|
| ![Smart Skipper](docs/screenshots/Smart-Skipper.png) | ![Playlist Janitor](docs/screenshots/Playlist-Janitor.png) | ![Musikk Coach](docs/screenshots/Musikk-Coach.png) |

---

## Roadmap

The project is feature-complete in its core tracking and dashboard functionality. Current focus is stability, UX polish, and testing.

**In progress / next up**
- Missing album art fallback for tracks with no cover image
- Loading skeletons for the Listening Score and Music Coach panels
- Public GitHub repository with Issues enabled
- Clarified OAuth trust indicators on the login screen

**Known issues**
- Spotify OAuth flow hangs in Samsung Internet (not yet investigated)

**Not planned**
- Additional music streaming services
- Social / sharing features
- Monetisation

See [`UX_BACKLOG.md`](UX_BACKLOG.md) for the full prioritised backlog.

---

## Contributing

Contributions are welcome. Please open an issue before submitting a pull request so the change can be discussed first.

**Guidelines**
- One logical change per pull request
- All user-facing text must use `i18next` translation keys — no hardcoded strings
- New backend functionality should include tests where feasible
- Run `pytest tests/test_tracker.py -v` before submitting; it requires no database and must pass cleanly
- Follow the existing code style: Norwegian comments in internal code, English in public-facing documentation

**Development setup** — see the [Development](#development) section above.

---

## License

[MIT](LICENSE)

---

## Acknowledgements

- [Spotify Web API](https://developer.spotify.com/documentation/web-api) — the source of all playback data
- [Neon](https://neon.tech) — serverless Postgres that makes the split Railway/Vercel architecture practical
- [Recharts](https://recharts.org) — composable chart library used throughout the dashboard
