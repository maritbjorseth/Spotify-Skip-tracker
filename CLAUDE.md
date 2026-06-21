# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Single-file Python script (`spotify_skip_tracker.py`) that polls the Spotify Web API's "currently playing" endpoint to detect skips across all of a user's devices, stores plays in a shared Postgres database (Neon), and serves a Flask dashboard. There is no test suite, build system, or linter configured — it's a personal utility script.

## Deployment architecture

- **Railway** runs `python3 spotify_skip_tracker.py track` continuously 24/7 via `railway.toml`. It polls Spotify and writes to the database. No dashboard here.
- **Vercel** hosts the read-only dashboard at `spotify-skip-tracker.vercel.app` via `app.py`. It only reads from the database.
- **Neon** (managed Postgres) is the shared database, connected via the `DATABASE_URL` environment variable set on both Railway and Vercel.
- Credentials (`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REFRESH_TOKEN`, `DATABASE_URL`) are environment variables on Railway/Vercel. Locally they live in `.env.local` (not in git).

## Commands

```bash
# Install dependencies
pip install requests flask psycopg2-binary python-dotenv

# One-time OAuth login (requires a Spotify Developer app, see module docstring)
python spotify_skip_tracker.py setup --client-id YOUR_ID --client-secret YOUR_SECRET

# Run the tracker + dashboard locally (http://localhost:5000) — useful for testing
python spotify_skip_tracker.py run

# Run tracking only (no dashboard) — what Railway runs
python spotify_skip_tracker.py track

# Generate a static "wrapped" HTML report from logged data
python spotify_skip_tracker.py wrapped

# Export all logged plays to CSV
python spotify_skip_tracker.py export --output skips.csv
```

There are no automated tests. Verify changes by running `run` locally and checking the dashboard, or by querying the Neon database directly.

## Architecture

All local OAuth state lives under `~/.spotify_skip_tracker/`: `credentials.json` (OAuth tokens), `wrapped.html` (generated report). In cloud deployments credentials come from environment variables instead.

The script has five entry points (`main()` dispatches via argparse subcommands):

- **`setup`** (`run_setup`) — one-time OAuth code flow. Spins up a throwaway `HTTPServer`/`_CallbackHandler` on `127.0.0.1:8888` to catch the redirect, exchanges the code for tokens, writes `credentials.json`.
- **`run`** (`run_tracker`) — starts `polling_loop()` in a background daemon thread and runs the Flask app (`create_flask_app`) in the foreground on port 5000.
- **`track`** (`run_track_only`) — tracking only, no Flask app. This is what Railway runs.
  - `polling_loop()` hits `/v1/me/player` every `POLL_SECONDS` (7s). Skip detection works by tracking the *previous* track's last-seen `progress_ms`/`duration_ms`: when the URI changes, if the previous track's completion ratio is below `SKIP_THRESHOLD` (0.9) *and* more than `MIN_REMAINING_MS` (30s) was left, it's logged as a skip (`log_play`). This means a skip is only recorded for the prior track, one poll cycle late — by design, since you can't know a track was skipped until something else starts playing.
  - If the DB connection drops (e.g. Neon idle timeout), `polling_loop()` catches the `psycopg2.Error`, closes the old connection, reconnects, and continues — losing at most one data point rather than crashing.
  - `get_access_token()` transparently refreshes the OAuth token when it's within 30s of expiry.
  - Playlist/album context names are resolved lazily and cached in the `contexts` table (`get_context_name`) to avoid repeated API calls.
- **`wrapped`** (`run_wrapped`) — runs `build_wrapped_data()` through `build_wrapped_html()` to produce a static HTML report, written to disk and opened in the browser.
- **`export`** (`run_export`) — dumps all plays to a CSV file.

The dashboard (`DASHBOARD_HTML`) is a single static page that polls `/api/stats` (backed by `compute_stats()`) every 10s and renders entirely client-side with vanilla JS + Chart.js.

`compute_stats()` and `build_wrapped_data()` independently re-derive overlapping aggregates via separate SQL queries — there's no shared aggregation layer, so changes to skip/play semantics need to be applied in both places.

All three functions that open DB connections (`compute_stats`, `build_wrapped_data`, `run_export`) use `try/finally` to ensure the connection is always closed, even if an error occurs mid-query.

## Database schema

- `plays`: one row per finished track (uri, title, album, artists, context_uri, skipped, progress_ratio, timestamp). Append-only.
- `contexts`: cache of playlist/album URI → display name.

All queries must be Postgres-compatible (stricter `GROUP BY`/`HAVING` rules than SQLite, use `%s` placeholders — handled automatically by `db_execute()`).

## Notes for changes

- User-facing strings (CLI help text, setup prompts, dashboard UI) are in Norwegian; keep new user-facing text consistent with that.
- The OAuth redirect URI (`http://127.0.0.1:8888/callback`) and scopes (`SCOPE`) must match what's registered in the Spotify Developer dashboard — changing `SCOPE` requires re-running `setup`.
- `compute_stats()` and `build_wrapped_data()` share no code but cover overlapping logic — update both when changing aggregation behavior.
