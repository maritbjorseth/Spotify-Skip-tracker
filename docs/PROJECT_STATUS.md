# Project Status

Spotify Skip Tracker er klar for offentlig lansering.

## Gjeldende fokus

- Feilrettinger
- Testing
- Lansering

Unngå feature creep.

---

# Release Checklist

## 1. Kritiske feil

### Bugs

| Oppgave | Prioritet | Status |
|---|---|---|
| ~~Fjern `print(">>> API NOW CALLED <<<")` i `web.py`~~ | 🔴 Må gjøres | Fikset |
| ~~Senk STEP 1–8-logger i `tracker.py` til `DEBUG`~~ | 🔴 Må gjøres | Fikset |
| ~~Lukk DB-tilkobling i `tracker.py` ved token-feil og 403-exit~~ | 🔴 Må gjøres | Fikset |
| ~~Fjern død `passwordLogin`-funksjon i `api.ts:42–47`~~ | 🟡 Bør gjøres | Fikset |

### Sikkerhet

| Oppgave | Prioritet | Status |
|---|---|---|
| Bekreft at `SECRET_KEY` er satt i Railway (ikke tilfeldig per restart) | 🔴 Må gjøres | Ukjent |
| Bekreft at `TOKEN_ENCRYPTION_KEY` er satt i Railway | 🔴 Må gjøres | Ukjent |
| ~~Fjern `localhost` fra CORS-origins i produksjon (`web.py:112`)~~ | 🟡 Bør gjøres | Fikset |

### API-feil

| Oppgave | Prioritet | Status |
|---|---|---|
| `janitor.py:run_janitor()` bruker single-user-legitimasjon — ikke multi-user | 🟢 Kan vente | Åpen |

---

## 2. Funksjonell testing

| Oppgave | Prioritet | Status |
|---|---|---|
| Innlogging → dashboard → utlogging (full flyt) | 🔴 Må gjøres | Ukjent |
| Avbrutt OAuth-innlogging viser feilmelding | 🔴 Må gjøres | Ukjent |
| Statistikk er filtrert på innlogget bruker | 🔴 Må gjøres | Ukjent |
| Ny bruker uten data ser en fornuftig tom-tilstand | 🔴 Må gjøres | Ukjent |
| Playlist Janitor fjerner sang fra Spotify | 🔴 Må gjøres | Ukjent |
| Smart Skipper skipper sang under avspilling | 🔴 Må gjøres | Ukjent |
| Demo-modus eksponerer ingen ekte brukerdata | 🔴 Må gjøres | Ukjent |
| Datofilter (7d / 30d / all time) gir riktige tall | 🟡 Bør gjøres | Ukjent |
| Lyttescore og Musikkcoach vises med data | 🟡 Bør gjøres | Ukjent |
| Session overlever F5 (ikke kastet ut ved refresh) | 🟡 Bør gjøres | Ukjent |
| Brukeren kan logge inn igjen umiddelbart etter utlogging | 🟡 Bør gjøres | Ukjent |

---

## 3. UI/UX

| Oppgave | Prioritet | Status |
|---|---|---|
| ~~`onError`-handler i Janitor-mutation (`PlaylistJanitorPanel`)~~ | 🟡 Bør gjøres | Fikset |
| ~~`onError`-handler i SmartSkipper config-mutation~~ | 🟡 Bør gjøres | Fikset |
| React `ErrorBoundary` i `main.tsx` | 🟡 Bør gjøres | Åpen |
| Loading state i `CoachInsightsPanel` og `ListeningScorePanel` | 🟡 Bør gjøres | Åpen |
| Felles konstant for Railway-URL (`api.ts` + `LoginScreen.tsx`) | 🟡 Bør gjøres | Åpen |
| Mobilvisning: tabeller, heatmap, knapper | 🟡 Bør gjøres | Ukjent |
| Hardkodede strenger i Recharts-tooltips (`Charts.tsx`) | 🟢 Kan vente | Åpen |
| Hardkodede strenger i `Tables.tsx:448` og `PlaylistJanitorPanel` | 🟢 Kan vente | Åpen |

---

## 4. Produksjon

### Railway / miljøvariabler

| Oppgave | Prioritet | Status |
|---|---|---|
| `SECRET_KEY` satt som fast verdi | 🔴 Må gjøres | Ukjent |
| `TOKEN_ENCRYPTION_KEY` satt | 🔴 Må gjøres | Ukjent |
| `SPOTIFY_CLIENT_ID` og `SPOTIFY_CLIENT_SECRET` satt | 🔴 Må gjøres | Ukjent |
| `REDIRECT_URI_WEB` registrert i Spotify Developer Dashboard | 🔴 Må gjøres | Ukjent |
| `DATABASE_URL` peker på Railway PostgreSQL | 🔴 Må gjøres | Ukjent |
| `FRONTEND_URL` peker på korrekt Vercel-URL | 🔴 Må gjøres | Ukjent |
| `RAILWAY_ENVIRONMENT` settes automatisk av Railway — ingen handling nødvendig | 🟢 Kan vente | OK |
| Gunicorn kjøres med `--workers 1` (se `railway.toml`) | 🔴 Må gjøres | OK |

### Spotify

| Oppgave | Prioritet | Status |
|---|---|---|
| App er ikke i "Development Mode" (maks 25 brukere ellers) | 🔴 Må gjøres | Ukjent |
| Scopes i Developer Dashboard matcher `SPOTIFY_SCOPES` i `config.py` | 🔴 Må gjøres | Ukjent |

### Vercel / frontend

| Oppgave | Prioritet | Status |
|---|---|---|
| `npm run build` kjørt og `frontend/dist/` committet etter siste endring | 🔴 Må gjøres | Ukjent |

### Logging

| Oppgave | Prioritet | Status |
|---|---|---|
| ~~`print(">>> API NOW CALLED <<<")` fjernet~~ | 🔴 Må gjøres | Fikset |
| ~~STEP 1–8-logger i `tracker.py` senket til `DEBUG`~~ | 🔴 Må gjøres | Fikset |
| Railway log-nivå satt til `WARNING` i produksjon | 🟡 Bør gjøres | Ukjent |

### Database

| Oppgave | Prioritet | Status |
|---|---|---|
| `init_db()` kjøres og alle migreringer passerer | 🔴 Må gjøres | Ukjent |
| Flask kjøres med `DEBUG=False` | 🔴 Må gjøres | Ukjent |

---

## 5. Etter lansering (v1.1 / v2.0)

| Oppgave | Versjon |
|---|---|
| Rate limiting på API-endepunkter | v1.1 |
| `_oauth_states`-settet med TTL (unngå minnelekkasje) | v1.1 |
| Fikse pre-eksisterende testfeil (`test_stale_updated_at`) | v1.1 |
| Testdekning for `insights.py`, `stats.py`, janitor-ruter | v1.1 |
| Fjern ubrukte React-komponenter (`MostPlayedTable` m.fl.) | v1.1 |
| `requirements.txt`-lockfile | v1.1 |
| Cursor-lukking i `database.py:execute()` | v1.1 |
| `janitor.py:run_janitor()` multi-user-støtte | v2.0 |
