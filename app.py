"""Vercel entry point: hosts only the read-only dashboard, backed by the
shared Postgres database. The actual tracking (polling Spotify, writing
plays) keeps running locally on a machine that's usually on, via the
`run` command - see spotify_skip_tracker.py.
"""

from spotify_skip_tracker import create_flask_app

app = create_flask_app()
