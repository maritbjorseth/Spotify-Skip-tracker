"""Vercel-inngang: serverer kun det skrivebeskyttede dashbordet, lest fra
den delte Postgres-databasen. Selve trackingen (polling av Spotify, skriving
av avspillinger) kjører separat på Railway via 'python -m spotify_skip_tracker track'.
"""

from spotify_skip_tracker import create_flask_app

app = create_flask_app()
