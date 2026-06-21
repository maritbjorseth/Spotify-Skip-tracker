# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Single-file Python script (`spotify_skip_tracker.py`) that polls the Spotify Web API's "currently playing" endpoint to detect skips across all of a user's devices, stores plays in a local SQLite database, and serves a Flask dashboard plus a static "wrapped" report. There is no test suite, build system, or linter configured — it's a personal utility script.

## Commands

```bash
# Install dependencies (no requirements.txt — install directly)
pip install requests flask

# One-time OAuth login (requires a Spotify Developer app, see module docstring)
python spotify_skip_tracker.py setup --client-id YOUR_ID --client-secret YOUR_SECRET

# Run the tracker + dashboard (http://localhost:5000)
python spotify_skip_tracker.py run

# Generate a static "wrapped" HTML report from logged data
python spotify_skip_tracker.py wrapped
```

There are no automated tests. Verify changes by running `run` and checking the dashboard, or by inspecting the SQLite DB directly:

```bash
sqlite3 ~/.spotify_skip_tracker/data.db "select * from plays order by id desc limit 5;"
```

## Architecture

All state lives under `~/.spotify_skip_tracker/` (outside the repo): `credentials.json` (OAuth tokens), `data.db` (SQLite), `wrapped.html` (generated report).

The script has three entry points (`main()` dispatches via argparse subcommands) sharing one module:

- **`setup`** (`run_setup`) — one-time OAuth code flow. Spins up a throwaway `HTTPServer`/`_CallbackHandler` on `127.0.0.1:8888` to catch the redirect, exchanges the code for tokens, writes `credentials.json`.
- **`run`** (`run_tracker`) — starts `polling_loop()` in a background daemon thread and runs the Flask app (`create_flask_app`) in the foreground on port 5000.
  - `polling_loop()` hits `/v1/me/player/currently-playing` every `POLL_SECONDS` (7s). Skip detection works by tracking the *previous* track's last-seen `progress_ms`/`duration_ms`: when the URI changes, if the previous track's completion ratio is below `SKIP_THRESHOLD` (0.9) *and* more than `MIN_REMAINING_MS` (30s) was left, it's logged as a skip (`log_play`). This means a skip is only recorded for the prior track, one poll cycle late — by design, since you can't know a track was skipped until something else starts playing.
  - `get_access_token()` transparently refreshes the OAuth token (mutates and persists `creds` via `save_creds`) when it's within 30s of expiry.
  - Playlist/album context names are resolved lazily and cached in the `contexts` table (`get_context_name`) to avoid repeated API calls.
- **`wrapped`** (`run_wrapped`) — runs `build_wrapped_data()` (a set of one-off aggregate SQL queries) through `build_wrapped_html()` to produce a static HTML report, written to disk and opened in the browser. Independent of the Flask app.

The dashboard (`DASHBOARD_HTML`, a big inline template string in `create_flask_app`) is a single static page that polls `/api/stats` (backed by `compute_stats()`) every 10s and renders entirely client-side with vanilla JS + Chart.js — there's no server-side templating or separate frontend build.

`compute_stats()` and `build_wrapped_data()` independently re-derive overlapping aggregates (skip counts/rates per track, artist, context) via separate SQL queries against the `plays` table — there's no shared aggregation layer, so changes to skip/play semantics need to be applied in both places.

## Database schema

- `plays`: one row per finished track (uri, title, album, artists, context_uri, skipped, progress_ratio, timestamp). Append-only.
- `contexts`: cache of playlist/album URI → display name.

## Notes for changes

- User-facing strings (CLI help text, setup prompts, dashboard UI) are in Norwegian; keep new user-facing text consistent with that.
- The OAuth redirect URI (`http://127.0.0.1:8888/callback`) and scopes (`SCOPE`) must match what's registered in the Spotify Developer dashboard for the app — changing `SCOPE` requires re-running `setup`.
