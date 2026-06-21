#!/usr/bin/env python3
"""
Spotify Skip Tracker
=====================
Tracks how often you skip tracks on Spotify, ACROSS ALL DEVICES (phone,
desktop, web player, smart speakers) - because it talks to your Spotify
*account* via the official Web API, not to a single app installation.

How it works
------------
Spotify's public Web API exposes what is "currently playing" on your account,
regardless of which device is playing it. This script polls that endpoint
every few seconds. When the playing track changes, it checks how far the
previous track got (progress / duration). If it changed before ~95%
completion, it's logged as a skip. Everything is stored locally in a SQLite
database, and a small dashboard at http://localhost:5000 shows the stats.

IMPORTANT LIMITATION: this can only see what happens *while the script is
running*. Leave it running on a machine that's usually on (this Mac, your
desktop PC) to catch as much as possible. It cannot retroactively see skips
that happened before you started it, or while it wasn't running.

------------------------------------------------------------------------
SETUP (one-time)
------------------------------------------------------------------------
1. Go to https://developer.spotify.com/dashboard and log in with your normal
   Spotify account. Click "Create app".
     - App name / description: anything, e.g. "Skip Tracker"
     - Redirect URI: http://127.0.0.1:8888/callback
     - Tick "Web API" under "Which API/SDKs are you planning to use?"
   Save, open the app, click "Settings" and copy the "Client ID" and
   "Client secret".

2. Install dependencies (Python 3.9+):
     pip install requests flask

3. Run the one-time login (replace with your own values):
     python spotify_skip_tracker.py setup --client-id YOUR_ID --client-secret YOUR_SECRET

   This opens your browser, you log in/approve, and your login is saved
   locally to ~/.spotify_skip_tracker/credentials.json (stored only on this
   computer, never sent anywhere else).

------------------------------------------------------------------------
RUNNING
------------------------------------------------------------------------
    python spotify_skip_tracker.py run

Then open http://localhost:5000 in your browser. Leave the terminal window
running in the background while you listen to music on any device.
"""

import argparse
import csv
import json
import os
import sys
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import psycopg2
import requests
from dotenv import load_dotenv

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_SCRIPT_DIR, ".env.local"))
load_dotenv(os.path.join(_SCRIPT_DIR, ".env"))

DATABASE_URL = os.environ.get("DATABASE_URL")

APP_DIR = os.path.join(os.path.expanduser("~"), ".spotify_skip_tracker")
CREDS_PATH = os.path.join(APP_DIR, "credentials.json")
WRAPPED_PATH = os.path.join(APP_DIR, "wrapped.html")
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "user-read-currently-playing user-read-playback-state"
POLL_SECONDS = 7
SKIP_THRESHOLD = 0.9  # if track changes before this fraction played, count as skip
MIN_REMAINING_MS = 30000  # if less than this is left when the track changes, it's an outro, not a skip


def ensure_app_dir():
    os.makedirs(APP_DIR, exist_ok=True)


class _CursorProxy:
    """Mimics sqlite3's conn.execute(...).fetchall() chaining for psycopg2."""

    def __init__(self, cursor):
        self._cursor = cursor

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchone(self):
        return self._cursor.fetchone()

    def __iter__(self):
        return iter(self._cursor)


def get_db_connection():
    # some platforms bundle an older libpq that rejects the "channel_binding"
    # param Neon adds to its connection strings - sslmode=require already
    # covers encryption, so it's safe to drop
    dsn = DATABASE_URL
    if dsn:
        parts = urllib.parse.urlsplit(dsn)
        query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if k != "channel_binding"]
        dsn = urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))
    return psycopg2.connect(dsn)


def db_execute(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql.replace("?", "%s"), params)
    return _CursorProxy(cur)


def init_db():
    conn = get_db_connection()
    db_execute(
        conn,
        """
        CREATE TABLE IF NOT EXISTS plays (
            id SERIAL PRIMARY KEY,
            uri TEXT NOT NULL,
            title TEXT,
            album TEXT,
            artists TEXT,
            context_uri TEXT,
            skipped INTEGER NOT NULL,
            progress_ratio REAL,
            timestamp TEXT NOT NULL
        )
        """,
    )
    db_execute(
        conn,
        """
        CREATE TABLE IF NOT EXISTS contexts (
            uri TEXT PRIMARY KEY,
            name TEXT
        )
        """,
    )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# OAuth setup
# ---------------------------------------------------------------------------

_auth_code = {}


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            _auth_code["code"] = params["code"][0]
            msg = b"<html><body><h2>Innlogging OK! Du kan lukke denne fanen og g\xc3\xa5 tilbake til terminalen.</h2></body></html>"
        else:
            msg = b"<html><body><h2>Noe gikk feil. Se terminalen for detaljer.</h2></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(msg)

    def log_message(self, format, *args):
        pass  # silence default request logging


def run_setup(client_id, client_secret):
    ensure_app_dir()
    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
        }
    )
    print("Åpner nettleseren for innlogging...")
    print(f"Hvis den ikke åpner selv, gå til denne URL-en manuelt:\n{auth_url}\n")

    server = HTTPServer(("127.0.0.1", 8888), _CallbackHandler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    webbrowser.open(auth_url)

    timeout = time.time() + 120
    while "code" not in _auth_code and time.time() < timeout:
        time.sleep(0.5)

    if "code" not in _auth_code:
        print("Tidsavbrudd - ingen innlogging mottatt. Prøv igjen.")
        sys.exit(1)

    code = _auth_code["code"]
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    resp.raise_for_status()
    token_data = resp.json()

    creds = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": token_data["refresh_token"],
        "access_token": token_data["access_token"],
        "expires_at": time.time() + token_data["expires_in"],
    }
    with open(CREDS_PATH, "w") as f:
        json.dump(creds, f, indent=2)

    print(f"Innlogging lagret i {CREDS_PATH}.")
    print("Du kan nå kjøre: python spotify_skip_tracker.py run")


# ---------------------------------------------------------------------------
# Token handling
# ---------------------------------------------------------------------------

def load_creds():
    # cloud deployments (no local credentials.json) configure these via env vars instead
    if os.environ.get("SPOTIFY_REFRESH_TOKEN"):
        return {
            "client_id": os.environ["SPOTIFY_CLIENT_ID"],
            "client_secret": os.environ["SPOTIFY_CLIENT_SECRET"],
            "refresh_token": os.environ["SPOTIFY_REFRESH_TOKEN"],
            "access_token": "",
            "expires_at": 0,
        }
    if not os.path.exists(CREDS_PATH):
        print("Ingen innlogging funnet. Kjør 'setup' først (se -h for hjelp).")
        sys.exit(1)
    with open(CREDS_PATH) as f:
        return json.load(f)


def save_creds(creds):
    # cloud deployments have no local file to persist to (and don't need one - the
    # refresh token doesn't rotate, so re-reading it from the env var on restart is fine)
    if os.environ.get("SPOTIFY_REFRESH_TOKEN"):
        return
    with open(CREDS_PATH, "w") as f:
        json.dump(creds, f, indent=2)


def get_access_token(creds):
    if creds["expires_at"] > time.time() + 30:
        return creds["access_token"]

    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": creds["refresh_token"],
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
        },
    )
    resp.raise_for_status()
    token_data = resp.json()
    creds["access_token"] = token_data["access_token"]
    creds["expires_at"] = time.time() + token_data["expires_in"]
    if "refresh_token" in token_data:
        creds["refresh_token"] = token_data["refresh_token"]
    save_creds(creds)
    return creds["access_token"]


# ---------------------------------------------------------------------------
# Context (playlist/album) name caching
# ---------------------------------------------------------------------------

def get_context_name(conn, token, context_uri):
    if not context_uri:
        return None
    row = db_execute(conn, "SELECT name FROM contexts WHERE uri = ?", (context_uri,)).fetchone()
    if row:
        return row[0]

    try:
        parts = context_uri.split(":")
        kind, id_ = parts[1], parts[2]
        if kind not in ("playlist", "album"):
            return None
        url = f"https://api.spotify.com/v1/{kind}s/{id_}"
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if resp.status_code != 200:
            return None
        name = resp.json().get("name")
        db_execute(
            conn,
            "INSERT INTO contexts (uri, name) VALUES (?, ?) ON CONFLICT (uri) DO UPDATE SET name = EXCLUDED.name",
            (context_uri, name),
        )
        conn.commit()
        return name
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Polling loop
# ---------------------------------------------------------------------------

def log_play(conn, uri, title, album, artists, context_uri, skipped, ratio):
    db_execute(conn, 
        "INSERT INTO plays (uri, title, album, artists, context_uri, skipped, progress_ratio, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (uri, title, album, artists, context_uri, int(skipped), ratio, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def polling_loop():
    creds = load_creds()
    conn = init_db()

    last_uri = None
    last_progress_ms = 0
    last_duration_ms = 0
    last_title = None
    last_album = None
    last_artists = None
    last_context = None
    last_shuffle_state = None

    print(f"Tracker startet. Poller hvert {POLL_SECONDS}s. Dashboard: http://localhost:5000")

    while True:
        try:
            token = get_access_token(creds)
            resp = requests.get(
                "https://api.spotify.com/v1/me/player",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )

            if resp.status_code == 204 or not resp.content:
                time.sleep(POLL_SECONDS)
                continue
            if resp.status_code != 200:
                time.sleep(POLL_SECONDS)
                continue

            data = resp.json()
            item = data.get("item")
            if not item:
                time.sleep(POLL_SECONDS)
                continue

            uri = item.get("uri")
            duration_ms = item.get("duration_ms") or 1
            progress_ms = data.get("progress_ms") or 0
            title = item.get("name")
            album = (item.get("album") or {}).get("name", "")
            artists = ", ".join(a.get("name", "") for a in item.get("artists", []))
            context = data.get("context") or {}
            context_uri = context.get("uri")
            shuffle_state = data.get("shuffle_state")

            if uri != last_uri:
                if last_uri is not None:
                    ratio = last_progress_ms / last_duration_ms if last_duration_ms else 0
                    remaining_ms = last_duration_ms - last_progress_ms
                    # a shuffle toggle can jump straight to a new track - that's not a real skip
                    shuffle_toggled = last_shuffle_state is not None and shuffle_state != last_shuffle_state
                    # starting a different playlist/album mid-song isn't a real skip either
                    context_switched = last_context is not None and context_uri != last_context
                    skipped = (
                        ratio < SKIP_THRESHOLD
                        and remaining_ms >= MIN_REMAINING_MS
                        and not shuffle_toggled
                        and not context_switched
                    )
                    log_play(conn, last_uri, last_title, last_album, last_artists, last_context, skipped, ratio)
                    if last_context:
                        get_context_name(conn, token, last_context)

                last_uri = uri
                last_title = title
                last_album = album
                last_artists = artists
                last_context = context_uri

            last_progress_ms = progress_ms
            last_duration_ms = duration_ms
            last_shuffle_state = shuffle_state

        except requests.RequestException as e:
            print(f"[tracker] nettverksfeil, prøver igjen: {e}")
        except Exception as e:
            print(f"[tracker] uventet feil: {e}")

        time.sleep(POLL_SECONDS)


# ---------------------------------------------------------------------------
# Web dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!doctype html>
<html lang="no">
<head>
<meta charset="utf-8">
<title>Spotify Skip Stats</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  :root { --green: #1db954; --orange: #ff6b35; --blue: #4a9eff; --purple: #9b59b6; --bg: #0d0d0d; --card: #181818; --card2: #1c1c1c; --border: #2a2a2a; --muted: #999; }
  * { box-sizing: border-box; }
  body { font-family: -apple-system, system-ui, sans-serif; background: var(--bg); color: #eee; margin: 0; padding: 28px; }
  h1 { color: var(--green); margin-top: 0; letter-spacing: -0.5px; }
  h2 { font-size: 1.05em; color: #ddd; margin: 0 0 12px; font-weight: 600; }
  .summary { display: flex; gap: 18px; margin-bottom: 36px; flex-wrap: wrap; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 22px 28px; min-width: 170px; }
  .card .icon { font-size: 1.3em; margin-bottom: 8px; }
  .card .num { font-size: 2.3em; font-weight: bold; color: var(--green); }
  .card .label { font-size: 0.88em; color: var(--muted); margin-top: 2px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 24px; margin-bottom: 36px; }
  .panel { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 18px; }
  .panel canvas { max-height: 260px; }
  .panel h2.accent-orange, .section h2.accent-orange { color: var(--orange); }
  .panel h2.accent-purple, .section h2.accent-purple { color: var(--purple); }
  .panel h2.accent-blue, .section h2.accent-blue { color: var(--blue); }
  .panel h2.accent-green, .section h2.accent-green { color: var(--green); }
  table { width: 100%; border-collapse: collapse; background: var(--card2); border-radius: 10px; overflow: hidden; }
  th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); font-size: 0.92em; }
  th { background: #161616; color: var(--muted); cursor: pointer; user-select: none; font-weight: 600; }
  tr:hover { background: #232323; }
  .skip-count { font-weight: bold; color: var(--orange); text-align: center; }
  select, input { background: var(--card2); color: #eee; border: 1px solid #333; border-radius: 6px; padding: 6px 10px; margin-right: 10px; }
  .controls { margin-bottom: 16px; }
  .section { margin-bottom: 40px; }
  .toggle-box { position: fixed; top: 22px; right: 24px; z-index: 100; }
  .toggle-box summary { display: inline-block; background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 8px 14px; font-size: 0.88em; color: #ccc; cursor: pointer; user-select: none; list-style: none; }
  .toggle-box summary::-webkit-details-marker { display: none; }
  .toggle-box summary:hover { color: #eee; border-color: #444; }
  .toggle-bar { position: absolute; top: 40px; right: 0; display: flex; flex-direction: column; gap: 10px; background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; font-size: 0.88em; width: max-content; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }
  .toggle-bar label { display: flex; align-items: center; gap: 6px; color: #ccc; cursor: pointer; }
  .toggle-bar input { margin: 0; }
  .header-row { display: flex; justify-content: space-between; align-items: flex-start; }
  .empty-row { color: var(--muted); font-style: italic; }
  .pagination { display: flex; align-items: center; gap: 12px; margin-top: 14px; justify-content: center; }
  .pagination button { background: var(--card2); color: #eee; border: 1px solid #333; border-radius: 6px; padding: 6px 14px; cursor: pointer; }
  .pagination button:disabled { opacity: 0.4; cursor: default; }
  .pagination button:not(:disabled):hover { border-color: #555; }
  .pagination span { color: var(--muted); font-size: 0.9em; }
</style>
</head>
<body>
  <div class="header-row">
    <h1>Skip Stats</h1>
    <details class="toggle-box">
      <summary>⚙ Vis/skjul paneler</summary>
      <div class="toggle-bar">
        <label><input type="checkbox" class="vis-toggle" data-target="block-skipped" checked> Mest skippede sanger</label>
        <label><input type="checkbox" class="vis-toggle" data-target="block-artistChart" checked> Mest skippede artister</label>
        <label><input type="checkbox" class="vis-toggle" data-target="block-contextChart" checked> Skip-rate per spilleliste/album</label>
        <label><input type="checkbox" class="vis-toggle" data-target="block-hourChart" checked> Skip etter tidspunkt</label>
        <label><input type="checkbox" class="vis-toggle" data-target="block-weekdayChart" checked> Skip etter ukedag</label>
        <label><input type="checkbox" class="vis-toggle" data-target="block-mostPlayed" checked> Mest spilt totalt</label>
        <label><input type="checkbox" class="vis-toggle" data-target="block-mostCompleted" checked> Nesten aldri skippet</label>
        <label><input type="checkbox" class="vis-toggle" data-target="block-topArtists" checked> Mest hørte artister</label>
      </div>
    </details>
  </div>
  <div class="summary" id="summary"></div>

  <div class="section" id="block-skipped">
    <h2 class="accent-orange">Mest skippede sanger</h2>
    <div class="controls">
      <select id="contextFilter"><option value="">Alle spillelister/album</option></select>
      <input id="search" placeholder="Søk etter tittel/artist...">
    </div>
    <table>
      <thead>
        <tr>
          <th data-key="title">Tittel</th>
          <th data-key="artists">Artist</th>
          <th data-key="context_name">Spilleliste/album</th>
          <th data-key="skip_count">Antall skip</th>
          <th data-key="play_count">Totalt spilt</th>
          <th data-key="skip_rate">Skip-rate</th>
        </tr>
      </thead>
      <tbody id="rows"></tbody>
    </table>
    <div class="pagination" id="pagination"></div>
  </div>

  <div class="grid">
    <div class="panel" id="block-artistChart"><h2 class="accent-orange">Mest skippede artister</h2><canvas id="artistChart"></canvas></div>
    <div class="panel" id="block-contextChart"><h2 class="accent-orange">Høyest skip-rate per spilleliste/album</h2><canvas id="contextChart"></canvas></div>
    <div class="panel" id="block-hourChart"><h2 class="accent-purple">Skip etter tidspunkt på døgnet</h2><canvas id="hourChart"></canvas></div>
    <div class="panel" id="block-weekdayChart"><h2 class="accent-purple">Skip etter ukedag</h2><canvas id="weekdayChart"></canvas></div>
  </div>

  <div class="grid">
    <div class="section" id="block-mostPlayed">
      <h2 class="accent-blue">Mest spilt totalt</h2>
      <table>
        <thead><tr><th>Tittel</th><th>Artist</th><th>Totalt spilt</th><th>Skip-rate</th></tr></thead>
        <tbody id="mostPlayedRows"></tbody>
      </table>
      <div class="pagination" id="mostPlayedPagination"></div>
    </div>
    <div class="section" id="block-mostCompleted">
      <h2 class="accent-green">Sanger du nesten aldri skipper</h2>
      <table>
        <thead><tr><th>Tittel</th><th>Artist</th><th>Totalt spilt</th><th>Skip-rate</th></tr></thead>
        <tbody id="mostCompletedRows"></tbody>
      </table>
    </div>
  </div>

  <div class="section" id="block-topArtists">
    <h2 class="accent-blue">Artister du hører mest på</h2>
    <table>
      <thead><tr><th>Artist</th><th>Totalt spilt</th><th>Skip-rate</th></tr></thead>
      <tbody id="topListenedArtistRows"></tbody>
    </table>
  </div>

<script>
let allData = [];
let sortKey = "skip_count";
let sortDir = -1;
let charts = {};
let currentPage = 1;
const PAGE_SIZE = 15;
let mostPlayedData = [];
let mostPlayedPage = 1;

const HOURS = Array.from({length: 24}, (_, i) => i + ":00");
const WEEKDAYS = ["Man", "Tir", "Ons", "Tor", "Fre", "Lør", "Søn"];

function shortLabel(text) {
  if (!text) return text;
  const first = text.split(",")[0].trim();
  return text.includes(",") ? first + " m.fl." : first;
}

function rateColor(rate) {
  return rate >= 0.5 ? "#ff6b35" : "#1db954";
}

function emptyRow(colspan) {
  return `<tr><td class="empty-row" colspan="${colspan}">Ingen data ennå</td></tr>`;
}

function renderPaginated(rows, page, pageSize, bodyId, paginationId, rowFn, colspan, onPageChange) {
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  if (page > totalPages) page = totalPages;
  const pageRows = rows.slice((page - 1) * pageSize, page * pageSize);

  document.getElementById(bodyId).innerHTML = pageRows.length ? pageRows.map(rowFn).join("") : emptyRow(colspan);

  const pagEl = document.getElementById(paginationId);
  pagEl.innerHTML = rows.length > pageSize ? `
    <button class="prevBtn" ${page <= 1 ? "disabled" : ""}>← Forrige</button>
    <span>Side ${page} av ${totalPages} (${rows.length})</span>
    <button class="nextBtn" ${page >= totalPages ? "disabled" : ""}>Neste →</button>
  ` : "";
  const prevBtn = pagEl.querySelector(".prevBtn");
  const nextBtn = pagEl.querySelector(".nextBtn");
  if (prevBtn) prevBtn.addEventListener("click", () => onPageChange(page - 1));
  if (nextBtn) nextBtn.addEventListener("click", () => onPageChange(page + 1));

  return page;
}

function barChart(canvasId, labels, data, label, color, yMax, horizontal) {
  if (charts[canvasId]) {
    const chart = charts[canvasId];
    chart.data.labels = labels;
    chart.data.datasets[0].data = data;
    chart.data.datasets[0].backgroundColor = color;
    chart.update();
    return;
  }
  const ctx = document.getElementById(canvasId);
  const categoryScale = { ticks: { color: "#999" }, grid: { color: "#2a2a2a" } };
  const valueScale = { ticks: { color: "#999", precision: 0 }, grid: { color: "#2a2a2a" }, beginAtZero: true };
  if (yMax !== undefined) {
    valueScale.max = yMax;
    valueScale.ticks.callback = (v) => v + "%";
  }
  const scales = horizontal ? { x: valueScale, y: categoryScale } : { x: categoryScale, y: valueScale };
  charts[canvasId] = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets: [{ label, data, backgroundColor: color }] },
    options: {
      indexAxis: horizontal ? "y" : "x",
      animation: false,
      plugins: { legend: { display: false } },
      scales
    }
  });
}

async function load() {
  const res = await fetch("/api/stats");
  const data = await res.json();
  allData = data.tracks;

  const skipRate = data.total_plays ? Math.round(100 * data.total_skips / data.total_plays) : 0;
  document.getElementById("summary").innerHTML = `
    <div class="card"><div class="icon">⏭️</div><div class="num">${data.total_skips}</div><div class="label">Totalt skippet</div></div>
    <div class="card"><div class="icon">📊</div><div class="num">${skipRate}%</div><div class="label">Skip-rate</div></div>
    <div class="card"><div class="icon">🎵</div><div class="num">${data.total_plays}</div><div class="label">Sporavspillinger logget</div></div>
    <div class="card"><div class="icon">🎶</div><div class="num">${data.unique_tracks}</div><div class="label">Unike sanger skippet</div></div>
  `;

  const select = document.getElementById("contextFilter");
  const existing = new Set(Array.from(select.options).map(o => o.value));
  data.contexts.forEach(c => {
    if (!existing.has(c)) {
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = c;
      select.appendChild(opt);
    }
  });

  barChart("artistChart", data.top_artists.map(a => shortLabel(a.artists)), data.top_artists.map(a => a.skip_count), "Skip", "#ff6b35");
  barChart("contextChart", data.top_contexts.map(c => c.context_name), data.top_contexts.map(c => Math.round(c.skip_rate * 100)), "Skip-rate %", "#ff6b35", 100);
  barChart("hourChart", HOURS, data.hourly.map(h => h.skips), "Skip", "#9b59b6");
  barChart("weekdayChart", WEEKDAYS, data.weekday.map(w => w.skips), "Skip", "#9b59b6");

  mostPlayedData = data.most_played;
  renderMostPlayed();

  document.getElementById("mostCompletedRows").innerHTML = data.most_completed.length ? data.most_completed.map(t => `
    <tr>
      <td>${t.title || ""}</td>
      <td>${t.artists || ""}</td>
      <td>${t.play_count}</td>
      <td style="color: ${rateColor(t.skip_rate)}">${Math.round(t.skip_rate * 100)}%</td>
    </tr>
  `).join("") : emptyRow(4);

  document.getElementById("topListenedArtistRows").innerHTML = data.top_listened_artists.length ? data.top_listened_artists.map(a => `
    <tr>
      <td>${a.artists || ""}</td>
      <td>${a.play_count}</td>
      <td style="color: ${rateColor(a.skip_rate)}">${Math.round(a.skip_rate * 100)}%</td>
    </tr>
  `).join("") : emptyRow(3);

  render();
}

function renderMostPlayed() {
  mostPlayedPage = renderPaginated(
    mostPlayedData, mostPlayedPage, PAGE_SIZE, "mostPlayedRows", "mostPlayedPagination",
    t => `
      <tr>
        <td>${t.title || ""}</td>
        <td>${t.artists || ""}</td>
        <td>${t.play_count}</td>
        <td style="color: ${rateColor(t.skip_rate)}">${Math.round(t.skip_rate * 100)}%</td>
      </tr>
    `,
    4,
    (newPage) => { mostPlayedPage = newPage; renderMostPlayed(); }
  );
}

function render() {
  const filterCtx = document.getElementById("contextFilter").value;
  const search = document.getElementById("search").value.toLowerCase();

  let rows = allData.filter(t => {
    if (filterCtx && t.context_name !== filterCtx) return false;
    if (search && !((t.title || "") + (t.artists || "")).toLowerCase().includes(search)) return false;
    return true;
  });

  rows.sort((a, b) => (a[sortKey] > b[sortKey] ? 1 : -1) * sortDir);

  currentPage = renderPaginated(
    rows, currentPage, PAGE_SIZE, "rows", "pagination",
    t => `
      <tr>
        <td>${t.title || ""}</td>
        <td>${t.artists || ""}</td>
        <td>${t.context_name || "-"}</td>
        <td class="skip-count">${t.skip_count}</td>
        <td>${t.play_count}</td>
        <td>${Math.round(t.skip_rate * 100)}%</td>
      </tr>
    `,
    6,
    (newPage) => { currentPage = newPage; render(); }
  );
}

document.querySelectorAll("th").forEach(th => {
  th.addEventListener("click", () => {
    const key = th.dataset.key;
    if (sortKey === key) sortDir *= -1; else { sortKey = key; sortDir = -1; }
    currentPage = 1;
    render();
  });
});

document.getElementById("contextFilter").addEventListener("change", () => { currentPage = 1; render(); });
document.getElementById("search").addEventListener("input", () => { currentPage = 1; render(); });

document.querySelectorAll(".vis-toggle").forEach(cb => {
  const target = document.getElementById(cb.dataset.target);
  const saved = localStorage.getItem("vis_" + cb.dataset.target);
  if (saved === "0") {
    cb.checked = false;
    target.style.display = "none";
  }
  cb.addEventListener("change", () => {
    target.style.display = cb.checked ? "" : "none";
    localStorage.setItem("vis_" + cb.dataset.target, cb.checked ? "1" : "0");
    const canvas = target.querySelector("canvas");
    if (cb.checked && canvas && charts[canvas.id]) charts[canvas.id].resize();
  });
});

load();
setInterval(load, 10000);
</script>
</body>
</html>
"""


def compute_stats():
    conn = get_db_connection()

    track_rows = db_execute(conn,
        """
        SELECT p.uri, MAX(p.title) as title, MAX(p.artists) as artists,
               COALESCE(c.name, p.context_uri) as context_name,
               SUM(p.skipped) as skip_count,
               COUNT(*) as play_count
        FROM plays p
        LEFT JOIN contexts c ON c.uri = p.context_uri
        GROUP BY p.uri, context_name
        HAVING SUM(p.skipped) > 0
        ORDER BY skip_count DESC
        """
    ).fetchall()

    tracks = []
    contexts = set()
    for uri, title, artists, context_name, skip_count, play_count in track_rows:
        tracks.append(
            {
                "uri": uri,
                "title": title,
                "artists": artists,
                "context_name": context_name,
                "skip_count": skip_count,
                "play_count": play_count,
                "skip_rate": skip_count / play_count if play_count else 0,
            }
        )
        if context_name:
            contexts.add(context_name)

    artist_rows = db_execute(conn, 
        """
        SELECT artists, SUM(skipped) as skip_count, COUNT(*) as play_count
        FROM plays
        WHERE artists IS NOT NULL AND artists != ''
        GROUP BY artists
        HAVING SUM(skipped) > 0
        ORDER BY skip_count DESC
        LIMIT 10
        """
    ).fetchall()
    top_artists = [
        {
            "artists": artists,
            "skip_count": skip_count,
            "play_count": play_count,
            "skip_rate": skip_count / play_count if play_count else 0,
        }
        for artists, skip_count, play_count in artist_rows
    ]

    listened_artist_rows = db_execute(conn, 
        """
        SELECT artists, SUM(skipped) as skip_count, COUNT(*) as play_count
        FROM plays
        WHERE artists IS NOT NULL AND artists != ''
        GROUP BY artists
        ORDER BY play_count DESC
        LIMIT 10
        """
    ).fetchall()
    top_listened_artists = [
        {
            "artists": artists,
            "skip_count": skip_count,
            "play_count": play_count,
            "skip_rate": skip_count / play_count if play_count else 0,
        }
        for artists, skip_count, play_count in listened_artist_rows
    ]

    context_rows = db_execute(conn, 
        """
        SELECT COALESCE(c.name, p.context_uri) as context_name,
               SUM(p.skipped) as skip_count,
               COUNT(*) as play_count
        FROM plays p
        LEFT JOIN contexts c ON c.uri = p.context_uri
        WHERE p.context_uri IS NOT NULL
        GROUP BY context_name
        HAVING COUNT(*) >= 2
        ORDER BY (CAST(SUM(p.skipped) AS REAL) / COUNT(*)) DESC
        LIMIT 10
        """
    ).fetchall()
    top_contexts = [
        {
            "context_name": context_name,
            "skip_count": skip_count,
            "play_count": play_count,
            "skip_rate": skip_count / play_count if play_count else 0,
        }
        for context_name, skip_count, play_count in context_rows
    ]

    most_played_rows = db_execute(conn, 
        """
        SELECT MAX(title) as title, MAX(artists) as artists, SUM(skipped) as skip_count, COUNT(*) as play_count
        FROM plays
        GROUP BY uri
        ORDER BY play_count DESC
        """
    ).fetchall()
    most_played = [
        {
            "title": title,
            "artists": artists,
            "skip_count": skip_count,
            "play_count": play_count,
            "skip_rate": skip_count / play_count if play_count else 0,
        }
        for title, artists, skip_count, play_count in most_played_rows
    ]

    most_completed_rows = db_execute(conn, 
        """
        SELECT MAX(title) as title, MAX(artists) as artists, SUM(skipped) as skip_count, COUNT(*) as play_count
        FROM plays
        GROUP BY uri
        HAVING COUNT(*) >= 2
        ORDER BY (CAST(SUM(skipped) AS REAL) / COUNT(*)) ASC, play_count DESC
        LIMIT 10
        """
    ).fetchall()
    most_completed = [
        {
            "title": title,
            "artists": artists,
            "skip_count": skip_count,
            "play_count": play_count,
            "skip_rate": skip_count / play_count if play_count else 0,
        }
        for title, artists, skip_count, play_count in most_completed_rows
    ]

    hourly = [{"skips": 0, "plays": 0} for _ in range(24)]
    weekday = [{"skips": 0, "plays": 0} for _ in range(7)]  # 0 = Monday
    for skipped, timestamp in db_execute(conn, "SELECT skipped, timestamp FROM plays"):
        try:
            ts = datetime.fromisoformat(timestamp).astimezone()
        except ValueError:
            continue
        hourly[ts.hour]["plays"] += 1
        hourly[ts.hour]["skips"] += skipped
        weekday[ts.weekday()]["plays"] += 1
        weekday[ts.weekday()]["skips"] += skipped

    total_skips = db_execute(conn, "SELECT COALESCE(SUM(skipped),0) FROM plays").fetchone()[0]
    total_plays = db_execute(conn, "SELECT COUNT(*) FROM plays").fetchone()[0]
    unique_tracks = len(tracks)
    conn.close()

    return {
        "tracks": tracks,
        "contexts": sorted(contexts),
        "top_artists": top_artists,
        "top_listened_artists": top_listened_artists,
        "top_contexts": top_contexts,
        "most_played": most_played,
        "most_completed": most_completed,
        "hourly": hourly,
        "weekday": weekday,
        "total_skips": total_skips,
        "total_plays": total_plays,
        "unique_tracks": unique_tracks,
    }


def create_flask_app():
    from flask import Flask, jsonify, Response

    app = Flask(__name__)

    @app.route("/")
    def index():
        return Response(DASHBOARD_HTML, mimetype="text/html")

    @app.route("/api/stats")
    def stats():
        return jsonify(compute_stats())

    return app


def run_tracker():
    init_db()
    t = threading.Thread(target=polling_loop, daemon=True)
    t.start()

    app = create_flask_app()
    app.run(host="127.0.0.1", port=5000, debug=False)


def run_track_only():
    """Tracking only, no dashboard - for cloud deployments (e.g. Railway) where
    the dashboard is already hosted separately (e.g. on Vercel)."""
    init_db()
    polling_loop()


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def run_export(output_path):
    conn = get_db_connection()
    rows = db_execute(conn,
        """
        SELECT p.timestamp, p.title, p.artists, p.album,
               COALESCE(c.name, p.context_uri) as context_name,
               p.skipped, p.progress_ratio
        FROM plays p
        LEFT JOIN contexts c ON c.uri = p.context_uri
        ORDER BY p.timestamp
        """
    ).fetchall()
    conn.close()

    if not rows:
        print("Ingen data å eksportere ennå. Kjør 'run' og hør på musikk en stund først.")
        sys.exit(1)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "title", "artists", "album", "context", "skipped", "progress_ratio"])
        writer.writerows(rows)

    print(f"Eksporterte {len(rows)} rader til {output_path}")


# ---------------------------------------------------------------------------
# Wrapped report
# ---------------------------------------------------------------------------

def build_wrapped_data():
    conn = get_db_connection()

    total_skips = db_execute(conn, "SELECT COALESCE(SUM(skipped),0) FROM plays").fetchone()[0]
    total_plays = db_execute(conn, "SELECT COUNT(*) FROM plays").fetchone()[0]

    top_track = db_execute(conn,
        """
        SELECT MAX(title) as title, MAX(artists) as artists, SUM(skipped) as skip_count, COUNT(*) as play_count
        FROM plays GROUP BY uri HAVING SUM(skipped) > 0
        ORDER BY skip_count DESC LIMIT 1
        """
    ).fetchone()

    top_listened_artist = db_execute(conn,
        """
        SELECT artists, COUNT(*) as play_count
        FROM plays WHERE artists IS NOT NULL AND artists != ''
        GROUP BY artists ORDER BY play_count DESC LIMIT 1
        """
    ).fetchone()

    most_loyal_artist = db_execute(conn,
        """
        SELECT artists, SUM(skipped) as skip_count, COUNT(*) as play_count
        FROM plays WHERE artists IS NOT NULL AND artists != ''
        GROUP BY artists HAVING COUNT(*) >= 2
        ORDER BY (CAST(SUM(skipped) AS REAL) / COUNT(*)) ASC, play_count DESC LIMIT 1
        """
    ).fetchone()

    top_context = db_execute(conn,
        """
        SELECT COALESCE(c.name, p.context_uri) as context_name, COUNT(*) as play_count
        FROM plays p LEFT JOIN contexts c ON c.uri = p.context_uri
        WHERE p.context_uri IS NOT NULL
        GROUP BY context_name ORDER BY play_count DESC LIMIT 1
        """
    ).fetchone()

    most_completed_track = db_execute(conn,
        """
        SELECT MAX(title) as title, MAX(artists) as artists, COUNT(*) as play_count
        FROM plays GROUP BY uri
        HAVING SUM(skipped) = 0 AND COUNT(*) >= 2
        ORDER BY play_count DESC LIMIT 1
        """
    ).fetchone()

    conn.close()

    return {
        "total_skips": total_skips,
        "total_plays": total_plays,
        "overall_skip_rate": total_skips / total_plays if total_plays else 0,
        "top_track": top_track,
        "top_listened_artist": top_listened_artist,
        "most_loyal_artist": most_loyal_artist,
        "top_context": top_context,
        "most_completed_track": most_completed_track,
    }


WRAPPED_TEMPLATE = """
<!doctype html>
<html lang="no">
<head>
<meta charset="utf-8">
<title>Din Skip Wrapped</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; background: #0d0d0d; color: #eee; margin: 0; padding: 40px 20px; }}
  .wrap {{ max-width: 640px; margin: 0 auto; }}
  h1 {{ color: #1db954; font-size: 2.2em; text-align: center; margin-bottom: 4px; }}
  .subtitle {{ text-align: center; color: #999; margin-bottom: 40px; }}
  .stat {{ background: #181818; border: 1px solid #2a2a2a; border-radius: 14px; padding: 28px; margin-bottom: 18px; text-align: center; }}
  .stat .label {{ color: #999; font-size: 0.95em; margin-bottom: 8px; }}
  .stat .value {{ color: #1db954; font-size: 1.7em; font-weight: bold; }}
  .stat .sub {{ color: #ccc; font-size: 0.95em; margin-top: 4px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Din Skip Wrapped</h1>
  <div class="subtitle">Basert på {total_plays} loggede avspillinger</div>
  {cards}
</div>
</body>
</html>
"""


def _wrapped_card(label, value, sub=None):
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return f'<div class="stat"><div class="label">{label}</div><div class="value">{value}</div>{sub_html}</div>'


def build_wrapped_html(data):
    cards = []

    if data["top_track"]:
        title, artists, skip_count, play_count = data["top_track"]
        cards.append(_wrapped_card("Sangen du skipper mest", f"{title}", f"{artists} - skippet {skip_count} ganger"))

    if data["top_listened_artist"]:
        artists, play_count = data["top_listened_artist"]
        cards.append(_wrapped_card("Artisten du hører mest på", artists, f"{play_count} avspillinger"))

    if data["most_loyal_artist"]:
        artists, skip_count, play_count = data["most_loyal_artist"]
        rate = round(100 * skip_count / play_count) if play_count else 0
        cards.append(_wrapped_card("Din mest trofaste artist", artists, f"kun {rate}% skip-rate over {play_count} avspillinger"))

    if data["top_context"]:
        context_name, play_count = data["top_context"]
        cards.append(_wrapped_card("Spilleliste/album du bruker mest", context_name or "Ukjent", f"{play_count} avspillinger"))

    if data["most_completed_track"]:
        title, artists, play_count = data["most_completed_track"]
        cards.append(_wrapped_card("Sangen du aldri skipper", title, f"{artists} - hørt {play_count} ganger uten et eneste skip"))

    cards.append(
        _wrapped_card(
            "Total skip-rate",
            f"{round(data['overall_skip_rate'] * 100)}%",
            f"{data['total_skips']} skip av {data['total_plays']} avspillinger",
        )
    )

    return WRAPPED_TEMPLATE.format(total_plays=data["total_plays"], cards="\n".join(cards))


def run_wrapped():
    data = build_wrapped_data()
    if data["total_plays"] == 0:
        print("Ingen data logget ennå. Kjør 'run' og hør på musikk en stund først.")
        sys.exit(1)

    html = build_wrapped_html(data)
    ensure_app_dir()
    with open(WRAPPED_PATH, "w") as f:
        f.write(html)

    print(f"Wrapped-rapport generert: {WRAPPED_PATH}")
    webbrowser.open(f"file://{WRAPPED_PATH}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Spotify Skip Tracker - se hvilke sanger du skipper, på tvers av enheter."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    setup_parser = sub.add_parser("setup", help="Engangs-innlogging mot Spotify (kjør denne først)")
    setup_parser.add_argument("--client-id", required=True)
    setup_parser.add_argument("--client-secret", required=True)

    sub.add_parser("run", help="Start tracking + dashboard på http://localhost:5000")
    sub.add_parser("track", help="Start kun tracking, uten dashboard (for skydeploy, f.eks. Railway)")
    sub.add_parser("wrapped", help="Generer en personlig 'wrapped'-rapport som HTML")

    export_parser = sub.add_parser("export", help="Eksporter alle loggede avspillinger til en CSV-fil")
    export_parser.add_argument(
        "--output", default="skips_export.csv",
        help="Filnavn/sti for CSV-filen (standard: skips_export.csv i denne mappen)",
    )

    args = parser.parse_args()

    if args.command == "setup":
        run_setup(args.client_id, args.client_secret)
    elif args.command == "run":
        run_tracker()
    elif args.command == "track":
        run_track_only()
    elif args.command == "wrapped":
        run_wrapped()
    elif args.command == "export":
        run_export(args.output)


if __name__ == "__main__":
    main()
