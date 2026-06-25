/**
 * Universelt fargesystem for Spotify Skip Tracker.
 *
 * Tre semantiske farger brukes konsekvent på tvers av alle komponenter:
 *
 *   Grønn  (#1db954)  — bra / lav skip-rate / positiv trend
 *   Amber  (#f59e0b)  — oppmerksomhet / moderat skip-rate
 *   Rød    (#ef4444)  — problem / høy skip-rate / negativ trend
 *
 * Skip-rate-terskler (gyldige overalt — StatCards, Charts, Insights):
 *   ≤ 25 %  →  grønn
 *   26–50 % →  amber
 *   > 50 %  →  rød
 *
 * Tellegrafer (antall skips, ikke rate) bruker NEUTRAL — en nøytral
 * blå-grå som ikke gir semantisk signal om bra/dårlig.
 */

export const C = {
  green:   "#1db954",
  amber:   "#f59e0b",
  red:     "#ef4444",
  neutral: "#5a7fa8",  // tellegrafer og ikke-evaluerende søyler
  empty:   "#2a2a2a",  // ingen data
} as const;

/**
 * Returnerer riktig semantisk farge basert på en skip-rate i prosent (0–100).
 * Bruk `plays` for å vise "ingen data"-fargen når det ikke finnes avspillinger.
 */
export function skipRateColor(ratePct: number, plays = 1): string {
  if (plays === 0) return C.empty;
  if (ratePct <= 25) return C.green;
  if (ratePct <= 50) return C.amber;
  return C.red;
}
