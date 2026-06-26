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

---

## 🟢 Neste

Alle punkter gjennomført. Se ✅ Ferdig.

---

## 🟡 Senere

Viktige forbedringer, men ikke blokkerende for lansering.

| # | Endring | Fil(er) |
|---|---|---|
| ~~6~~ | ~~Unified seksjonstittel: felles `<SectionHeading>`-komponent~~ | Utsatt — ikke stor nok brukerverdi |
| ~~7~~ | ~~StatCard "Totalt skippet": grå verdi (#aaa) → hvit~~ | ✅ Ferdig (#9) |
| ~~8~~ | ~~Betingede SectionDividers for Musikkcoach/Smart Skipper~~ | ✅ Ferdig (#10) |
| 9 | Felles `<EmptyState>`-komponent for alle tomtilstander | `Tables.tsx`, `SmartSkipperPanel.tsx` |
| 10 | Laste-tilstander: skeleton/spinner for Score og Insights | `ListeningScorePanel.tsx`, `CoachInsightsPanel.tsx` |
| 11 | Heatmap: semantisk riktig fargeskala (mer skips = rød, ikke grønn) | `SkipHeatmap.tsx:16` |
| 12 | Heatmap: skill mellom "0 skips" og "ingen data"-celler | `SkipHeatmap.tsx` |
| ~~13~~ | ~~Tabellrader: `py-5` → `py-3`~~ | ✅ Ferdig (#11) |
| ~~14~~ | ~~NowPlaying skip-rate: 2 nivåer → 3~~ | ✅ Ferdig (#12) |
| ~~15~~ | ~~ContextChart filter-aktiv: orange → Spotify-grønn~~ | ✅ Ferdig (#13) |
| 16 | Unify tooltip: alle bruker `AlgorithmTooltip` eller `title` | `StatCards.tsx`, `SkipHeatmap.tsx` |

---

## ⚪ Lav prioritet

Audit-funn med minimal brukersynlig effekt.

| # | Endring | Fil(er) |
|---|---|---|
| 17 | Focus-stiler for keyboard-navigasjon (a11y) | `index.css`, alle komponenter |
| 18 | @theme token-adopsjon (erstatt hardkodede hex) | Alle komponenter |
| 19 | AlgorithmTooltip: overflow-fix nær høyre viewport-kant | `AlgorithmTooltip.tsx` |
| 20 | StatCards ikonfarger: Tailwind-klasser → hex | `StatCards.tsx:197` |
| 21 | ⓘ-tegn → inline SVG overalt | `StatCards.tsx`, `SkipHeatmap.tsx` |
| 22 | aria-label på alle Recharts-grafer | `Charts.tsx` |
| 23 | "Vis passord"-knapp i LoginScreen | `LoginScreen.tsx` |
| 24 | Paginering: "(47)" → "(47 sanger)" | `Tables.tsx:120` |
| 25 | SectionToggle: "Vis alle / Skjul alle" hurtigknapper | `SectionToggle.tsx` |
| 26 | Side-tittel og meta-beskrivelse for offentlig side | `index.html` |
| 27 | Tilbake-til-topp-knapp for lang dashboard | `App.tsx` |
| 28 | Kopier-til-utklippstavle på CLI-kommandoer | `SmartSkipperPanel.tsx`, `PlaylistJanitorPanel.tsx` |
| 29 | Overflatefarger: tydeliggjør `#141414`/`#181818`/`#1c1c1c`-hierarki | `index.css` |
