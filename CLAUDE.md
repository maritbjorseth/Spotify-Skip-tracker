# CLAUDE.md

Denne filen gir veiledning til Claude Code når det jobbes med koden i dette repoet.

## Oversikt

Python-pakke (`spotify_skip_tracker/`) som poller Spotify Web APIets
«currently playing»-endepunkt for å oppdage skip på tvers av alle enheter,
lagrer avspillinger i en delt Postgres-database (Neon), og serverer et
Flask-dashboard. Ingen testoppsett utover pytest.

## Deployment-arkitektur

- **Railway** kjører `python3 -m spotify_skip_tracker track` kontinuerlig 24/7 via `railway.toml`.
  Den poller Spotify og skriver til databasen. Ingen dashboard her.
- **Vercel** hoster det skrivebeskyttede dashbordet via `app.py`. Leser kun fra databasen.
- **Neon** (managed Postgres) er den delte databasen, koblet til via `DATABASE_URL`.
- Legitimasjon (`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REFRESH_TOKEN`, `DATABASE_URL`)
  er miljøvariabler på Railway/Vercel. Lokalt ligger de i `.env.local` (ikke i git).

## Pakkestruktur

```
spotify_skip_tracker/
├── __init__.py       eksporterer create_flask_app (for Vercel-kompatibilitet)
├── __main__.py       CLI-inngang (argparse); kjøres via python -m spotify_skip_tracker
├── config.py         konstanter og env-innlasting
├── database.py       tilkoblingspool, init_db, migrasjoner
├── spotify_api.py    OAuth-flyt, token-oppdatering, kontekstnavn-cache
├── tracker.py        is_skip() (ren funksjon), polling_loop, log_play
├── stats.py          compute_stats() → JSON for /api/stats
├── wrapped.py        build_wrapped_data, build_wrapped_html, run_wrapped
├── export.py         CSV-eksport
├── web.py            create_flask_app(), Flask-ruter
└── dashboard.html    dashbord-HTML (separat fil, lastes av web.py)

tests/
├── test_tracker.py   14 tester for is_skip() (ingen DB nødvendig)
└── test_stats.py     DB-tester for compute_stats (krever DATABASE_URL)
```

## Kommandoer

```bash
# Installer avhengigheter
pip install requests flask psycopg2-binary python-dotenv

# Engangs-innlogging (krever en Spotify Developer-app, se modulens docstring)
python3 -m spotify_skip_tracker setup --client-id DIN_ID --client-secret DIN_SECRET

# Kjør tracker + dashboard lokalt (http://localhost:5000)
python3 -m spotify_skip_tracker run

# Kjør kun tracking (ingen dashboard) — det Railway kjører
python3 -m spotify_skip_tracker track

# Generer en statisk "Wrapped"-rapport (valgfritt: filtrer på måned/år)
python3 -m spotify_skip_tracker wrapped
python3 -m spotify_skip_tracker wrapped --month 6 --year 2026

# Eksporter alle loggede avspillinger til CSV
python3 -m spotify_skip_tracker export --output skips.csv

# Kjør tester (skip-deteksjon krever ikke DB)
pytest tests/test_tracker.py -v

# Kjør DB-tester (krever DATABASE_URL)
DATABASE_URL=... pytest tests/test_stats.py -v
```

## Arkitektur

### Skip-deteksjon (`tracker.py`)

`is_skip(ratio, remaining_ms, shuffle_toggled, context_switched) → bool`
er en ren funksjon uten bivirkninger. Skip-logikken er:
- `ratio < SKIP_THRESHOLD (0.9)` — sporet ble forlatt før 90 % ble spilt
- `remaining_ms >= MIN_REMAINING_MS (30 000)` — minst 30 s gjenstod
- `not shuffle_toggled` — shuffle-bytte regnes ikke som skip
- `not context_switched` — kontekstbytte regnes ikke som skip

Et skip kan bare oppdages retroaktivt: når neste spor starter, sjekker vi
det *forrige* sporets fremgang.

### Databaselag (`database.py`)

- `connect()` — direkte tilkobling (brukes av tracker-loopen og CLI)
- `pooled_connection()` — kontekstbehandler over `ThreadedConnectionPool` (brukes av stats/web)
- `init_db(conn)` — oppretter tabeller + kjører migrasjoner ved oppstart
- Migrasjoner: konverterer `timestamp TEXT → TIMESTAMPTZ`, legger til `image_url`

### Statistikk (`stats.py`)

`compute_stats()` bruker connection-poolen og henter all statistikk i
separate SQL-spørringer. Hourly/weekday-aggregering gjøres i SQL med
`EXTRACT(HOUR/ISODOW FROM timestamp AT TIME ZONE 'Europe/Oslo')`.

### Dashboard (`web.py` + `dashboard.html`)

`dashboard.html` er en separat fil som leses inn av `web.py` ved import.
Dashbordet bruker `esc()`-funksjonen i JavaScript for å forhindre XSS,
og viser albumcover fra `image_url`-kolonnen i `plays`-tabellen.

## Databaseskjema

```sql
plays (
  id             SERIAL PRIMARY KEY,
  uri            TEXT NOT NULL,
  title          TEXT,
  album          TEXT,
  artists        TEXT,
  context_uri    TEXT,
  skipped        BOOLEAN NOT NULL,
  progress_ratio REAL,
  timestamp      TIMESTAMPTZ NOT NULL,
  image_url      TEXT
)

contexts (
  uri  TEXT PRIMARY KEY,
  name TEXT
)
```

Alle spørringer bruker psycopg2-stil (`%s`-plassholdere) direkte.

## Notater for endringer

- Brukervendte tekster (CLI, dashboard, meldinger) er på norsk — hold nye tekster konsistente.
- OAuth redirect-URI (`http://127.0.0.1:8888/callback`) og `SCOPE` må stemme overens med
  hva som er registrert i Spotify Developer Dashboard. Endring av `SCOPE` krever ny `setup`.
- `compute_stats()` og `build_wrapped_data()` dekker overlappende logikk i separate spørringer.
  Endre begge ved endring av aggregeringslogikk.
- `app.py` (Vercel) og `railway.toml` er allerede oppdatert til å bruke den nye pakkestrukturen.
