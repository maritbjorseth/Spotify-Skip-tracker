"""
Spotify Skip Tracker — pakke-inngang.

Eksporterer create_flask_app slik at Vercel sin app.py kan importere
den på samme måte som før:

    from spotify_skip_tracker import create_flask_app
"""

from .web import create_flask_app

__all__ = ["create_flask_app"]
