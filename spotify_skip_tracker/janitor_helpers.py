"""
Hjelpefunksjoner for Spotify API-kall knyttet til Playlist Janitor.

Håndterer henting av spillelister og spor fra Spotify Web API,
inkludert paginering og filtrering av ikke-musikk-innhold.
"""

import logging

import requests

logger = logging.getLogger(__name__)

_BASE = "https://api.spotify.com/v1"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def get_all_my_playlists(token: str) -> list[dict]:
    """
    Henter alle spillelister brukeren selv eier.

    Gjør først et kall til /me for å hente brukerens Spotify-ID,
    deretter paginerer gjennom /me/playlists og filtrerer ut
    spillelister eid av andre.

    Returnerer en liste med dicts:
        { "id": str, "name": str, "total_tracks": int, "uri": str }
    """
    # Hent brukerens egen Spotify-ID
    try:
        me_resp = requests.get(
            f"{_BASE}/me",
            headers=_headers(token),
            timeout=10,
        )
        me_resp.raise_for_status()
        user_id: str = me_resp.json()["id"]
    except requests.RequestException as exc:
        logger.error("Kunne ikke hente bruker-ID fra Spotify: %s", exc)
        return []

    playlists: list[dict] = []
    url: str | None = f"{_BASE}/me/playlists?limit=50"

    while url:
        try:
            resp = requests.get(url, headers=_headers(token), timeout=10)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Feil ved henting av spillelister: %s", exc)
            break

        data = resp.json()

        for pl in data.get("items") or []:
            if not pl:
                continue
            if pl.get("owner", {}).get("id") == user_id:
                playlists.append({
                    "id": pl["id"],
                    "name": pl.get("name", ""),
                    "total_tracks": (pl.get("tracks") or {}).get("total", 0),
                    "uri": pl.get("uri", ""),
                })

        url = data.get("next")

    logger.info("Fant %d spilleliste(r) eid av brukeren.", len(playlists))
    return playlists


def get_playlist_tracks(token: str, playlist_id: str) -> list[dict]:
    """
    Henter alle musikk-spor i en spilleliste.

    Paginerer automatisk gjennom alle sider og filtrerer bort
    podkast-episoder, lokale filer og andre ikke-track-elementer.

    Returnerer en liste med dicts:
        { "uri": str, "name": str, "artists": str }
    der "artists" er en kommaseparert streng av artistnavn.
    """
    tracks: list[dict] = []
    url: str | None = f"{_BASE}/playlists/{playlist_id}/tracks?limit=100"

    while url:
        try:
            resp = requests.get(url, headers=_headers(token), timeout=10)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error(
                "Feil ved henting av spor for spilleliste %s: %s",
                playlist_id, exc,
            )
            break

        data = resp.json()

        for item in data.get("items") or []:
            track = (item or {}).get("track")
            if not track:
                continue
            if track.get("type") != "track":
                # Hopp over podkaster, lokale filer o.l.
                continue
            if not track.get("uri"):
                continue

            artists = ", ".join(
                a.get("name", "") for a in (track.get("artists") or [])
            )
            tracks.append({
                "uri": track["uri"],
                "name": track.get("name", ""),
                "artists": artists,
            })

        url = data.get("next")

    logger.info(
        "Hentet %d musikkspor fra spilleliste %s.", len(tracks), playlist_id
    )
    return tracks
