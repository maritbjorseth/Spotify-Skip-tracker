"""
Railway-inngang: starter tracker i bakgrunnen og eksponerer Flask-appen
via gunicorn. Holdes separat fra app.py (som er Vercel sin inngang).
"""

import threading

from spotify_skip_tracker.database import connect, init_db
from spotify_skip_tracker.tracker import polling_loop
from spotify_skip_tracker.web import create_flask_app

# Initialiser database (oppretter tabeller og migrasjoner)
_conn = connect()
init_db(_conn)
_conn.close()

# Start tracker i bakgrunnstråd
_t = threading.Thread(target=polling_loop, daemon=True)
_t.start()

# Flask-app som gunicorn importerer
app = create_flask_app()
