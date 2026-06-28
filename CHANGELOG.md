# Changelog

Alle brukermerkbare og arkitekturmessige endringer dokumenteres her.
Format basert på [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

---

## [0.4.0] — Multi-user / Alpha-klar — 2026-06-28

### Endret (arkitektur)
- **Autentisering:** Spotify OAuth er nå den eneste innloggingsmetoden.
  Passord-innlogging og «åpen modus» (auto-innlogging som eieren) er fjernet.
  Alle brukere må logge inn med sin egen Spotify-konto via `/api/auth/login`.
- **`LoginScreen.tsx`:** Passordskjema erstattet med «Logg inn med Spotify»-knapp.

### Lagt til
- **Multi-user tracking (Steg 1–6):** Systemet er nå fullt multi-tenant.
  - `user_tokens`-tabell med Fernet-kryptert lagring av refresh-tokens per bruker.
  - Session bærer `user_id` fra Spotify OAuth — alle API-svar er isolert per bruker.
  - `now_playing`, `smart_skipper_config` og `auto_skips` er migrert til per-bruker-design.
  - `tracker_manager()` starter én polling-tråd per bruker ved oppstart.
  - Nye brukere får tracker umiddelbart etter OAuth-innlogging via `ensure_tracker_running()`.
  - Bootstrap-migrasjon: SPOTIFY_REFRESH_TOKEN-eieren migreres automatisk til DB.
- **Token-kryptering:** `token_crypto.py` med Fernet (AES-128-CBC + HMAC-SHA256).
  Krever `TOKEN_ENCRYPTION_KEY` i Railway-miljøet.
- **Sikkerhet:** `@require_auth`-dekorator på alle API-ruter, rate limiting på
  innloggingsendepunktet, `user_id`-filter i SmartSkipper.
- **DB-indekser:** 5 indekser på `plays`-tabellen for å unngå fulle tabellskann.
- **Helse-endepunkt:** `/health` for Railway-monitorering.
- **60 s stats-cache:** `compute_stats()` caches per `user_id`.
- **`now_playing` stale-terskel:** Senket fra 60 s til 20 s.
- **Tester:** 103 tester totalt. Nye testfiler:
  `test_auth.py`, `test_now_playing.py`, `test_janitor.py`,
  `test_smart_skipper_config.py`, `test_token_storage.py`,
  `test_tracker_manager.py`, `test_auto_skips.py`.

### Fjernet
- `DASHBOARD_PASSWORD`-støtte og tilhørende passord-innloggingsflyt.
- Åpen modus (auto-autentisering som eier uten innlogging).
- In-process Janitor-scheduler (dupliserte Railway-cron).

---

## [0.3.0] — Steg mot multi-user / Produksjonsklar — 2026-06

### Lagt til
- `user_id`-kolonne i alle kjernetabeller (`plays`, `smart_skipper_config`,
  `janitor_suggestions`, `janitor_removals`, `auto_skips`).
- Musikkcoach-panel med strukturerte Insight-objekter (stadium 1–3).
- Lyttescore (0–100) basert på fullføringsgrad, streak og konsistens.
- Playlist Janitor: foreslår fjerning av konsekvent skippede sanger fra spillelister.
  Støtter angring via `snapshot_id`.
- Smart Skipper: automatisk hopping med dry-run-modus og rate-limiting.
- `session_id`-kolonne i `plays` — grupperer avspillinger i lyttesesjoner.
- `now_playing`-tabell for «Spiller nå»-widget.
- React/TypeScript-frontend med Tailwind CSS og Recharts.
- Ukentlig skip-rate trend-graf, drill-down i kontekst-grafer.
- Heatmap for daglig aktivitet (siste 365 dager).

### Endret
- Migrert fra SQLite til Postgres (Neon serverless).
- Migrert til pakkestruktur (`spotify_skip_tracker/`).
- Deployment: Railway (tracker) + Vercel (dashboard) + Neon (DB).

---

## [0.1.0] — Første versjon — 2025

### Lagt til
- Polling av Spotify `/v1/me/player` hvert 7. sekund.
- Skip-deteksjon: `is_skip(ratio, remaining_ms, shuffle_toggled, context_switched)`.
- Logging til Postgres: `plays`-tabell med URI, tittel, artister, skip-status.
- Flask-dashboard med statistikk.
- «Wrapped»-rapport som HTML.
- CSV-eksport.
- CLI: `setup`, `run`, `track`, `wrapped`, `export`.
