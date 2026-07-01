# UX Backlog — Spotify Skip Tracker

Prioritert etter brukerverdi. Basert på design-audit av hele frontend (juni 2026).

---

## ✅ Ferdig

| # | Endring | Commit |
|---|---|---|
| 1 | Kompakt dashboard — padding, marginer, korthøyder | `9d0ec7e` |
| 2 | ArtistChart: semantiske farger via `skipRateColor()` | `90d5574` |
| 3 | ContextChart: fjern %-akse, reduser høyde og barSize | `d3e2b1b` |
| 4 | Unify skip-rate farge-system — alle badges bruker `skipRateColor()` | `b48cd6f` |
| 5 | StatCardsRow mb-16 → mb-6 (outlier fra kompakt-commit) | `40a437d` |
| 6 | NowPlaying mb-8 → mb-4 på playing-tilstand (fjerner layout-hopp) | `6ba4b60` |
| 7 | Heatmap p-6/mb-8 → p-4/mb-4 (sync med ChartCard) | `c009f0e` |
| 8 | Janitor: erstatt window.confirm() med inline Bekreft/Avbryt | `719c182` |
| 9 | StatCard «Totalt skippet» farge #aaa → #eee | `8f6c130` |
| 10 | Musikkcoach-divider vises kun når score-data er tilgjengelig | `afb9ba2` |
| 11 | Tabellrader py-5 → py-3 (tettere, konsistent med kort) | `50a5853` |
| 12 | NowPlaying skip-rate: 3 nivåer via skipRateColor() | `9532cc9` |
| 13 | ContextChart filter-aktiv: orange → Spotify-grønn | `581a499` |
| 14 | Heatmap: amber/rød for skips, blågrå for 0-skips-dager, skiller ingen-data vs aktiv dag | `ec2beee` |
| 15 | Insights: dynamiske tekster (observation/context/explanation/action) oversettes nå korrekt basert på valgt språk. Backend leser `?lang=`-parameter, frontend sender normalisert språkkode og inkluderer lang i React Query-nøkkelen. | `e96520b` |
| 16 | Login-siden starter nå på nettleserens språk for førstegangsbrukere. La til `load: "languageOnly"` i i18next-konfig slik at `"en-US"` matches mot `"en"` i stedet for å falle tilbake til norsk. | `4bbf9aa` |
| 17 | Heatmap: legende og informasjons-tooltip beskriver nå skip-rate (ikke rått antall). `legendMany` og `headingTooltip` var feilaktig formulert som tellingsspråk selv om fargesystemet er rate-basert. | `04ad138` |
| 18 | Heatmap: `AlgorithmTooltip` erstatter nativ `title`-attributt på ⓘ-ikonet, som ikke vistes konsistent i nettlesere. | `503ee1f` |
| 19 | AlgorithmTooltip: ⓘ-glyfen var ikke visuelt sentrert ved arv av `font-semibold` og `tracking-widest` fra overordnede elementer. Fikset med `font-normal leading-none` og flytting av komponenten ut av `<h2>`. | `171c2eb`, `66efaec` |
| 20 | Janitor: `ON CONFLICT DO NOTHING` erstattet med `DO UPDATE` for `pending`/`rejected`-rader slik at `skip_rate` og `janitor_score` oppdateres ved nye kjøringer. `removed`-rader (brukerdismissed) berøres ikke. | `8661543` |
| 21 | Janitor: `GET /playlists/{id}/tracks` (deprekert av Spotify, returnerer 403) erstattet med `GET /playlists/{id}/items`. Nøkkel per element endret fra `"track"` til `"item"`. | `b2fa9b4` |
| 22 | Insights: `_insight_session_start_pattern` feilet med "column session_id does not exist" fordi `session_id` ble brukt i `PARTITION BY` men ikke inkludert i CTE-ens SELECT-liste. | `55f4790` |
| 23 | Insights: kort bruker nå CSS Grid (1/2/3 kolonner) i stedet for `flex-wrap`. `break-words` lagt til alle tekstelementer. Forhindrer tekstoverflow og sikrer lik korthøyde i samme rad. | `89570d4` |

---

## 🔴 Bugs (gjenstår)

| # | Problem | Status |
|---|---|---|
| 1 | Spotify OAuth henger i Samsung Internet-nettleseren etter autorisasjon. Chrome og 1DM+ fungerer. | ⏳ Ikke undersøkt |
| 4 | Noen sanger viser fortsatt manglende albumcover i stedet for fallback-bildet. | ⏳ Ikke undersøkt |

---

## 🟢 Neste sesjon — prioritert rekkefølge

| Prioritet | Oppgave | Referanse |
|-----------|---------|-----------|
| 1 | **Bug #4**: Undersøk og fiks manglende albumcover-fallback. Enkel synlig feil for alle brukere. | `plays.image_url`, frontend fallback-logikk |
| 2 | **Forbedring #10**: Laste-tilstander (skeleton/spinner) for Score og Insights. Panelene vises ingenting mens data hentes — gir inntrykk av tom app. | `ListeningScorePanel.tsx`, `CoachInsightsPanel.tsx` |
| 3 | **Forbedring #19**: Opprett offentlig GitHub-repository med Issues aktivert. To testere har etterspurt dette. | GitHub |
| 4 | **Forbedring #21**: Tydeliggjør på login-siden at autentisering skjer via Spotifys offisielle OAuth. Øker tillit for nye brukere (ref. tester-feedback). | `LoginScreen.tsx` |
| 5 | **Bug #1**: Undersøk Spotify OAuth-heng i Samsung Internet. Krev reproduksjon/logg før kodeendring. | `spotify_api.py`, OAuth-callback |
| 6 | **Forbedring #9**: Felles `<EmptyState>`-komponent. Reduserer duplisering og gir konsistent tom-tilstand-UX. | `Tables.tsx`, `SmartSkipperPanel.tsx` |

---

## 🟡 Senere

Viktige forbedringer, men ikke blokkerende for lansering.

| # | Endring | Fil(er) |
|---|---|---|
| ~~6~~ | ~~Unified seksjonstittel: felles `<SectionHeading>`-komponent~~ | Utsatt — ikke stor nok brukerverdi |
| ~~7~~ | ~~StatCard "Totalt skippet": grå verdi (#aaa) → hvit~~ | ✅ Ferdig (#9) |
| ~~8~~ | ~~Betingede SectionDividers for Musikkcoach/Smart Skipper~~ | ✅ Ferdig (#10) |
| 20 | Demo login skal være tydelig synlig i produksjon. Verifiser Vercel-miljøkonfig. | `LoginScreen.tsx` |

---

## ⚪ Lav prioritet

Audit-funn med minimal brukersynlig effekt.

| # | Endring | Fil(er) |
|---|---|---|
| 17 | Focus-stiler for keyboard-navigasjon (a11y) | `index.css`, alle komponenter |
| 18 | @theme token-adopsjon (erstatt hardkodede hex) | Alle komponenter |
| 19 | AlgorithmTooltip: overflow-fix nær høyre viewport-kant | `AlgorithmTooltip.tsx` |
| 20 | StatCards ikonfarger: Tailwind-klasser → hex | `StatCards.tsx:197` |
| 21 | ⓘ-tegn → inline SVG overalt | `StatCards.tsx` |
| 22 | aria-label på alle Recharts-grafer | `Charts.tsx` |
| 23 | "Vis passord"-knapp i LoginScreen | `LoginScreen.tsx` |
| 24 | Paginering: "(47)" → "(47 sanger)" | `Tables.tsx:120` |
| 25 | SectionToggle: "Vis alle / Skjul alle" hurtigknapper | `SectionToggle.tsx` |
| 26 | Side-tittel og meta-beskrivelse for offentlig side | `index.html` |
| 27 | Tilbake-til-topp-knapp for lang dashboard | `App.tsx` |
| 28 | Kopier-til-utklippstavle på CLI-kommandoer | `SmartSkipperPanel.tsx`, `PlaylistJanitorPanel.tsx` |
| 29 | Overflatefarger: tydeliggjør `#141414`/`#181818`/`#1c1c1c`-hierarki | `index.css` |

### Spotify API-kompatibilitet (post-nov 2024)

Spotify endret tilgangspolitikk for en rekke endepunkter i 2024–2025. `GET /playlists/{id}/tracks` er nå deprekert og erstattet av `GET /playlists/{id}/items` (fikset i #21 over). Følgende bør verifiseres ved behov:

- `GET /audio-features` — sannsynligvis blokkert uten quota extension
- `GET /recommendations` — sannsynligvis blokkert uten quota extension
- `GET /artists/{id}/related-artists` — sannsynligvis blokkert uten quota extension

---

## 💬 Tester feedback log

Historikk over tilbakemeldinger fra eksterne testere.

| Dato | Kilde | Tilbakemelding | Referanse |
|------|-------|----------------|-----------|
| 2026-06-29 | Reddit – ricki17 | Login page initially appeared in Norwegian, which made the site seem suspicious before Spotify login. | ✅ Ferdig #16 |
| 2026-07-01 | Reddit – InevitableBand6043 | Insights remain in Norwegian even when English is selected. Asked whether there is a GitHub repository for reporting bugs. | ✅ Ferdig #15, Gjenstår #19 |
| 2026-07-01 | Reddit – Musichead2468 | Requested a public GitHub repository for bug reporting and confirmed that Insights still appear in Norwegian when English is selected. | ✅ Ferdig #15, Gjenstår #19 |
