# Implementeringsplan — Public Demo og Open Source

Opprettet: 2026-06-29  
Branch: `feature/i18n-complete` (nåværende arbeidsgren)  
Status-nøkkel: `[ ]` ikke startet · `[~]` påbegynt · `[x]` fullført

---

## Status

**Prosjektfase:**
- ☑ i18n ferdig
- ☑ Produksjon deployet
- ☑ Demo-data generert
- ☑ Public Demo backend (steg 2 av 6)
- ☐ Public Demo frontend
- ☐ Open Source-klargjøring
- ☐ README

---

## Kontekst

Spotify Skip Tracker endrer retning til et **open source self-hosting-prosjekt**.  
Den hostede versjonen (Vercel + Railway) skal fungere som en **read-only offentlig demo**.

Nøkkelarkitektur:
- **Vercel** — serverer kun statisk React-build (`frontend/dist/`)
- **Railway** — kjører all Flask/API-logikk
- **Neon** — delt Postgres-database
- `api.ts` bruker Railway-URL direkte i produksjon, relative URL-er lokalt

---

## Prioritet 1 — Public Demo (steg 1–10)

### Teknisk arkitektur

**Backend:**
- `demo_data.json` — statisk JSON med realistiske data; lastes i minnet ved Flask-oppstart
- `/api/auth/demo` — setter `session['user_id'] = '_demo_'` og `session['is_demo'] = True`; ingen DB-tilgang; redirecter til `FRONTEND_URL`
- Alle read-endepunkter: én tidlig `if session.get("is_demo"): return demo_data[...]`-sjekk
- `/api/janitor/remove` (eneste write): returnerer `403` umiddelbart i demo-modus
- `DEMO_MODE`-env-flagg (Railway) — demo-endepunktet er deaktivert med mindre flagget er satt

**Frontend:**
- `AuthStatus`-typen utvides med `is_demo: boolean`
- «View Demo»-knapp i `LoginScreen.tsx` navigerer til `BASE + "/api/auth/demo"`
- Ikke-avvisbart demo-banner øverst i `App.tsx` ved `is_demo === true`
- Fjern-knappen i `PlaylistJanitorPanel.tsx` skjules/deaktiveres i demo-modus

**Isolasjonsgarantier:**
- Null DB-tilgang i demo-modus (alle reads returnerer fra JSON i minnet)
- Null Spotify API-kall i demo-modus
- Kun én write-blokkering nødvendig (`/api/janitor/remove`)
- Fullstendig isolert fra produksjonsdata

---

### Steg 1 — Generer `demo_data.json`

**Status:** `[☑]`  
**Fil:** `spotify_skip_tracker/demo_data.json` (ny)  
**Beskrivelse:**  
Opprett et statisk JSON-datasett med realistiske verdier som speiler eksakt hva hvert API-endepunkt returnerer. Strukturen:

```
{
  "stats":               { ...identisk med /api/stats-respons... },
  "now":                 { ...identisk med /api/now-respons... },
  "smart_skipper":       { "config": {...}, "history": [...] },
  "score":               { "score": 72 },
  "insights":            [ ...liste med Insight-objekter... ],
  "janitor_suggestions": [ ...liste med JanitorCandidate-objekter... ]
}
```

Datasettet skal inkludere:
- ~1 000 avspillinger fordelt over ~6 måneder
- 20–30 unike artister, 15–20 spillelister/album
- Varierende skip-rater (noen høye, noen lave) for å demonstrere alle grenser
- En «now playing»-sang (statisk, `is_playing: false` — ingen live-indikator)
- 3–5 Smart Skipper audit-historikk-rader
- 4–6 Playlist Janitor-kandidater i ulike kategorier
- 2–3 musikkcoach-innsikter

**Avhengigheter:** Ingen  
**Neste steg:** Steg 2

---

### Steg 2 — Backend: demo-infrastruktur i `web.py` og `config.py`

**Status:** `[x]`  
**Filer:** `web.py`, `config.py`  
**Beskrivelse:**

`config.py`:
- Legg til `DEMO_MODE: bool = os.environ.get("DEMO_MODE", "false").lower() == "true"`

`web.py`:
- Last `demo_data.json` ved modulnivå inn i `_DEMO_DATA: dict | None`
- Legg til intern helper: `def _is_demo() -> bool: return bool(session.get("is_demo"))`
- Nytt endepunkt:
  ```
  GET /api/auth/demo
    - Returnerer 404 dersom DEMO_MODE ikke er True
    - Setter session['user_id'] = '_demo_', session['is_demo'] = True
    - Returnerer redirect(FRONTEND_URL)
    - Ingen DB-tilgang, ingen Spotify-kall
  ```
- Utvid `GET /api/auth/status` til å inkludere `"is_demo": _is_demo()` i responsen

**Avhengigheter:** Steg 1  
**Neste steg:** Steg 3

---

### Steg 3 — Backend: demo-sjekk i stats, now, smart-skipper

**Status:** `[☑]`  
**Fil:** `web.py`  
**Beskrivelse:**  
Legg til tidlig demo-return øverst i funksjonslegemene for:
- `GET /api/stats` → returnerer `_DEMO_DATA["stats"]`
- `GET /api/now` → returnerer `_DEMO_DATA["now"]`
- `GET /api/smart-skipper` → returnerer `_DEMO_DATA["smart_skipper"]`

Mønsteret er identisk i alle tre:
```python
if _is_demo():
    return jsonify(_DEMO_DATA["<nøkkel>"])
```
Plasseres etter `@require_auth`-sjekken, men før alle DB-kall.

**Avhengigheter:** Steg 2  
**Neste steg:** Steg 4

---

### Steg 4 — Backend: demo-sjekk i score, insights, janitor/suggestions

**Status:** `[☑]`  
**Fil:** `web.py`  
**Beskrivelse:**  
Samme mønster som steg 3 for:
- `GET /api/stats/score` → returnerer `_DEMO_DATA["score"]`
- `GET /api/coach/insights` → returnerer `_DEMO_DATA["insights"]`
- `GET /api/janitor/suggestions` → returnerer `_DEMO_DATA["janitor_suggestions"]`

**Avhengigheter:** Steg 3  
**Neste steg:** Steg 5

---

### Steg 5 — Backend: blokker skriving i demo-modus

**Status:** `[☑]`  
**Fil:** `web.py`  
**Beskrivelse:**  
`POST /api/janitor/remove` er det eneste endepunktet som faktisk skriver data (til DB og Spotify). Legg til øverst i funksjonslegemet:
```python
if _is_demo():
    return jsonify({"error": "Ikke tilgjengelig i demo-modus"}), 403
```

Verifiser at ingen andre endepunkter skriver data i demo-kontekst.

**Avhengigheter:** Steg 4  
**Neste steg:** Steg 6

---

### Steg 6 — Backend: `DEMO_MODE`-env-flagg

**Status:** `[☑]`  
**Filer:** `web.py`, `config.py`  
**Beskrivelse:**  
`/api/auth/demo` skal returnere `404` med en tydelig melding dersom `DEMO_MODE` ikke er satt til `true` i Railway-miljøet. Dette forhindrer at selvhostede installasjoner utilsiktet eksponerer et åpent innloggingspunkt.

Sett `DEMO_MODE=true` i Railway-variablene for den hostede instansen.  
Standard for alle andre er `DEMO_MODE=false` (ingen endring nødvendig).

**Avhengigheter:** Steg 5  
**Neste steg:** Steg 7

---

### Steg 7 — Frontend: oppdater `AuthStatus`-typen

**Status:** `[ ]`  
**Fil:** `frontend/src/types.ts`  
**Beskrivelse:**  
Utvid `AuthStatus`-interfacet med `is_demo: boolean`. Dette er den eneste type-endringen og påvirker alle komponenter som leser `authData`.

**Avhengigheter:** Steg 6  
**Neste steg:** Steg 8

---

### Steg 8 — Frontend: «View Demo»-knapp i `LoginScreen.tsx`

**Status:** `[ ]`  
**Fil:** `frontend/src/components/LoginScreen.tsx`  
**Beskrivelse:**  
Legg til en sekundær knapp under «Logg inn med Spotify» som navigerer til `BASE + "/api/auth/demo"`.

Knappen skal:
- Visuelt skille seg fra primærknappen (tonet ned — ikke grønn)
- Ha tekst på begge språk via i18n-nøkler: `login.demoButton` (nb: «Utforsk demo», en: «Explore demo»)
- Legge til i18n-nøklene i `locales/nb.json` og `locales/en.json`

Siden `/api/auth/demo` returnerer en redirect, brukes `window.location.href = BASE + "/api/auth/demo"` eller en vanlig `<a>`-lenke.

**Avhengigheter:** Steg 7  
**Neste steg:** Steg 9

---

### Steg 9 — Frontend: demo-banner i `App.tsx`

**Status:** `[ ]`  
**Fil:** `frontend/src/App.tsx`  
**Beskrivelse:**  
Vis et ikke-avvisbart informasjonsbanner øverst i dashbordet når `authData?.is_demo === true`.

Banneret skal forklare:
- At dette er en demo med eksempeldata
- At ingen endringer lagres
- Lenke til GitHub-repoet for å self-hoste

i18n-nøkler: `demo.banner`, `demo.bannerLink` (nb og en).

**Avhengigheter:** Steg 8  
**Neste steg:** Steg 10

---

### Steg 10 — Frontend: deaktiver Fjern-knapp i demo-modus

**Status:** `[ ]`  
**Fil:** `frontend/src/components/PlaylistJanitorPanel.tsx`  
**Beskrivelse:**  
`PlaylistJanitorPanel` henter janitor-data og viser en «Fjern»-knapp per sang. I demo-modus:
- Skjul eller deaktiver «Fjern»-knappen
- Vis en tooltip/tekst som forklarer at fjerning ikke er tilgjengelig i demo

`is_demo` leses fra `authData` (allerede tilgjengelig i `App.tsx`). Sendes ned som prop eller leses fra en ny context.

i18n-nøkkel: `playlistJanitor.demoDisabled`

**Avhengigheter:** Steg 9  
**Neste steg:** Steg 11

---

## Prioritet 2 — Open Source-klargjøring (steg 11–12)

---

### Steg 11 — Opprett `.env.example`

**Status:** `[ ]`  
**Fil:** `.env.example` (ny)  
**Beskrivelse:**  
Mal for alle miljøvariabler med forklaring, ingen ekte verdier.

Seksjoner:
- **Påkrevd alltid:** `DATABASE_URL`, `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`
- **Påkrevd i produksjon:** `SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`, `REDIRECT_URI_WEB`, `FRONTEND_URL`
- **Valgfri / legacy:** `SPOTIFY_REFRESH_TOKEN`, `SPOTIFY_USER_ID`
- **Railway-spesifikk:** `RAILWAY_ENVIRONMENT` (settes automatisk)
- **Vercel-spesifikk:** `VERCEL` (settes automatisk)
- **Demo:** `DEMO_MODE=false` (sett til `true` på den offentlige Railway-instansen)
- **Lokal dev:** `REDIRECT_URI_WEB=http://127.0.0.1:5000/api/auth/callback`, `FRONTEND_URL=http://localhost:5000`

Tydelige kommentarer om:
- At DEV_BYPASS aktiveres automatisk lokalt når `SPOTIFY_REFRESH_TOKEN` er satt og ingen produksjons-env-var er til stede
- At `TOKEN_ENCRYPTION_KEY` er anbefalt i produksjon for sikker token-lagring
- Hvordan generere `SECRET_KEY` og `TOKEN_ENCRYPTION_KEY`

**Avhengigheter:** Ingen (kan gjøres parallelt med steg 1)  
**Neste steg:** Steg 12

---

### Steg 12 — Opprett root `README.md`

**Status:** `[ ]`  
**Fil:** `README.md` (ny)  
**Beskrivelse:**  
Encompassende README for open source-publikasjon. Seksjoner:

1. **Prosjektbeskrivelse** — hva Spotify Skip Tracker er, screenshot/demo-lenke
2. **Rask start (lokal utvikling)** — forutsetninger, klon, `.env.local`, DB-oppsett, `pip install`, start
3. **Spotify Developer App-oppsett** — steg-for-steg: opprett app, noter Client ID/Secret, legg til redirect URI
4. **Databaseoppsett** — Neon (anbefalt) eller hvilken som helst Postgres; `DATABASE_URL`-format
5. **Self-hosting** — Railway (backend) + Vercel (frontend); environment variables per plattform
6. **Miljøvariabler** — tabell over alle variabler med beskrivelse og eksempelverdi
7. **Demo-modus** — hvordan aktivere den offentlige demoen (`DEMO_MODE=true`)
8. **Arkitektur** — kort oversikt: Railway (tracking + API), Vercel (React SPA), Neon (Postgres)
9. **Kommandolinje** — oversikt over `python -m spotify_skip_tracker`-kommandoene
10. **Lisens** — (avklares med prosjekteier)

**Avhengigheter:** Steg 11  
**Neste steg:** —

---

## Bygg og deploy etter fullføring

```bash
# Bygg frontend etter steg 8–10
cd frontend && npm run build

# Kjør tester
cd .. && python -m pytest tests/test_tracker.py -v

# Commit og push
git add -A
git commit -m "feat: public demo-modus og open source-klargjøring"
git push
```

Railway og Vercel deployer automatisk fra main-branch etter merge.  
Husk å sette `DEMO_MODE=true` i Railway-miljøvariablene for den offentlige instansen.

---

## Filer som berøres

| Fil | Endring | Steg |
|---|---|---|
| `spotify_skip_tracker/demo_data.json` | Ny — statisk demo-datasett | 1 |
| `spotify_skip_tracker/config.py` | `DEMO_MODE`-variabel | 2, 6 |
| `spotify_skip_tracker/web.py` | Demo-endepunkt, helper, sjekker i 7 endepunkter | 2–6 |
| `frontend/src/types.ts` | `is_demo` i `AuthStatus` | 7 |
| `frontend/src/components/LoginScreen.tsx` | «View Demo»-knapp | 8 |
| `frontend/src/locales/nb.json` | i18n-nøkler for demo | 8–10 |
| `frontend/src/locales/en.json` | i18n-nøkler for demo | 8–10 |
| `frontend/src/App.tsx` | Demo-banner | 9 |
| `frontend/src/components/PlaylistJanitorPanel.tsx` | Deaktiver Fjern-knapp | 10 |
| `.env.example` | Ny — mal for selvhosting | 11 |
| `README.md` | Ny — open source-dokumentasjon | 12 |

**Filer som ikke berøres:** `tracker.py`, `stats.py`, `database.py`, `smart_skipper.py`, `insights.py`, `janitor.py`, `spotify_api.py`, og alle andre React-komponenter.
