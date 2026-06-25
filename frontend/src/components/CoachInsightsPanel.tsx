/**
 * CoachInsightsPanel — Musikkcoach-panelet.
 *
 * Rendrer strukturerte Insight-objekter fra /api/coach/insights.
 * Hvert kort viser de feltene som er fylt ut for det gjeldende stadiet:
 *
 *   Stadium 1: kun observation (grå tekst)
 *   Stadium 2: observation + context med trend-farge
 *   Stadium 3: alle fire felt + tydelig handlingsoppfordring
 *
 * Panelet er designet for gradvis oppgradering: når backenden leverer
 * stadium 3 i stedet for 1, vises mer informasjon uten layout-endringer.
 */

import { useQuery } from "@tanstack/react-query";
import type { Insight } from "../types";
import { api } from "../api";
import { AlgorithmTooltip } from "./AlgorithmTooltip";

const COACH_EXPLANATION =
  "Musikkcoach identifiserer mønstre i lyttedataene dine: hvilke sanger du alltid skipper, " +
  "når på dagen du er mest tålmodig, og om spillelistene dine trenger opprydding. " +
  "Innsiktene er basert på din faktiske lyttehistorikk — ikke anbefalingsalgoritmer fra Spotify. " +
  "Jo mer data som samles inn, jo mer presise blir observasjonene.";

// ---------------------------------------------------------------------------
// Ikoner per kategori
// ---------------------------------------------------------------------------

function InsightIcon({ category }: { category: Insight["category"] }) {
  const props = {
    width: 18, height: 18, viewBox: "0 0 24 24",
    fill: "none", stroke: "currentColor",
    strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const,
  };

  if (category === "skip_rate") return (
    <svg {...props}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>
  );
  if (category === "streak") return (
    <svg {...props}>
      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
    </svg>
  );
  if (category === "session") return (
    <svg {...props}>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
  if (category === "janitor") return (
    <svg {...props}>
      <line x1="8" y1="6" x2="21" y2="6" />
      <line x1="8" y1="12" x2="21" y2="12" />
      <line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" />
      <line x1="3" y1="12" x2="3.01" y2="12" />
      <line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  );
  // pattern (default)
  return (
    <svg {...props}>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Farge-hjelpere
// ---------------------------------------------------------------------------

function accentColor(insight: Insight): string {
  if (insight.trend_is_positive === true) return "#1db954";
  if (insight.trend_is_positive === false) return "#ef4444";
  if (insight.category === "streak") return "#f59e0b";
  if (insight.category === "session") return "#9b59b6";
  if (insight.category === "janitor") return "#4a9eff";
  return "#6b7280"; // nøytral grå
}

function contextColor(insight: Insight): string {
  if (insight.trend_is_positive === true) return "#1db954";
  if (insight.trend_is_positive === false) return "#ef4444";
  return "#f59e0b";
}

// ---------------------------------------------------------------------------
// Innsiktskort
// ---------------------------------------------------------------------------

function InsightCard({ insight }: { insight: Insight }) {
  const color = accentColor(insight);

  return (
    <div className="flex items-start gap-4 rounded-xl border border-[#2a2a2a] bg-[#141414] px-5 py-4 flex-1 min-w-0">

      {/* Ikon-sirkel */}
      <div
        className="flex items-center justify-center rounded-full shrink-0 mt-0.5"
        style={{ width: 36, height: 36, background: `${color}18`, color }}
      >
        <InsightIcon category={insight.category} />
      </div>

      {/* Tekstinnhold */}
      <div className="min-w-0 flex-1">

        {/* Kategori-etikett */}
        <p className="text-xs font-medium uppercase tracking-widest text-[#444] mb-1">
          {insight.category === "skip_rate" && "Skip-rate"}
          {insight.category === "streak"    && "Streak"}
          {insight.category === "session"   && "Sesjonsmønster"}
          {insight.category === "janitor"   && "Playlist Janitor"}
          {insight.category === "pattern"   && "Lyttemønster"}
        </p>

        {/* Observasjon — alltid til stede */}
        <p className="text-sm text-[#ccc] leading-snug">{insight.observation}</p>

        {/* Kontekst — stadium 2+ */}
        {insight.context && (
          <p
            className="text-xs mt-1 leading-snug font-medium"
            style={{ color: contextColor(insight) }}
          >
            {insight.context}
          </p>
        )}

        {/* Forklaring — stadium 3 */}
        {insight.explanation && (
          <p className="text-xs text-[#666] mt-1 leading-snug italic">
            {insight.explanation}
          </p>
        )}

        {/* Handling — stadium 3 */}
        {insight.action && (
          <p className="text-xs text-[#4a9eff] mt-2 leading-snug">
            → {insight.action}
          </p>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hoved-panel
// ---------------------------------------------------------------------------

export function CoachInsightsPanel() {
  const { data: insights } = useQuery({
    queryKey: ["coachInsights"],
    queryFn: api.coachInsights,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  if (!insights || insights.length === 0) return null;

  return (
    <div className="mb-8">
      <div className="flex items-center gap-2 mb-3">
        <p className="text-xs font-semibold uppercase tracking-widest text-[#444]">
          Innsikter
        </p>
        <AlgorithmTooltip text={COACH_EXPLANATION} color="#6b7280" />
      </div>
      <div className="flex flex-col sm:flex-row gap-3 flex-wrap">
        {insights.map((insight) => (
          <InsightCard key={insight.id} insight={insight} />
        ))}
      </div>
    </div>
  );
}
