import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { Insight } from "../types";
import { api } from "../api";
import { AlgorithmTooltip } from "./AlgorithmTooltip";

function InsightIcon({ category }: { category: Insight["category"] }) {
  const props = {
    width: 18, height: 18, viewBox: "0 0 24 24",
    fill: "none", stroke: "currentColor",
    strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const,
  };
  if (category === "skip_rate") return <svg {...props}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>;
  if (category === "streak") return <svg {...props}><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" /></svg>;
  if (category === "session") return <svg {...props}><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>;
  if (category === "janitor") return <svg {...props}><line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" /><line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" /></svg>;
  return <svg {...props}><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>;
}

function accentColor(insight: Insight): string {
  if (insight.trend_is_positive === true) return "#1db954";
  if (insight.trend_is_positive === false) return "#ef4444";
  if (insight.category === "streak") return "#f59e0b";
  if (insight.category === "session") return "#9b59b6";
  if (insight.category === "janitor") return "#4a9eff";
  return "#6b7280";
}

function contextColor(insight: Insight): string {
  if (insight.trend_is_positive === true) return "#1db954";
  if (insight.trend_is_positive === false) return "#ef4444";
  return "#f59e0b";
}

function InsightCard({ insight }: { insight: Insight }) {
  const { t } = useTranslation();
  const color = accentColor(insight);

  return (
    <div className="flex items-start gap-4 rounded-xl border border-[#2a2a2a] bg-[#141414] px-5 py-4 min-w-0">
      <div
        className="flex items-center justify-center rounded-full shrink-0 mt-0.5"
        style={{ width: 36, height: 36, background: `${color}18`, color }}
      >
        <InsightIcon category={insight.category} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium uppercase tracking-widest text-[#777] mb-1 break-words">
          {t(`coachInsights.categories.${insight.category}` as const)}
        </p>
        <p className="text-sm text-[#ccc] leading-snug break-words">{insight.observation}</p>
        {insight.context && (
          <p className="text-xs mt-1 leading-snug font-medium break-words" style={{ color: contextColor(insight) }}>
            {insight.context}
          </p>
        )}
        {insight.explanation && (
          <p className="text-xs text-[#888] mt-1 leading-snug italic break-words">{insight.explanation}</p>
        )}
        {insight.action && (
          <p className="text-xs text-[#4a9eff] mt-2 leading-snug break-words">→ {insight.action}</p>
        )}
      </div>
    </div>
  );
}

export function CoachInsightsPanel() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language?.startsWith("en") ? "en" : "nb";
  const { data: insights } = useQuery({
    queryKey: ["coachInsights", lang],
    queryFn: () => api.coachInsights(lang),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  if (!insights || insights.length === 0) return null;

  return (
    <div className="mb-8">
      <div className="flex items-center gap-2 mb-3">
        <p className="text-xs font-semibold uppercase tracking-widest text-[#777]">
          {t("coachInsights.label")}
        </p>
        <AlgorithmTooltip text={t("coachInsights.explanation")} color="#6b7280" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
        {insights.map((insight) => (
          <InsightCard key={insight.id} insight={insight} />
        ))}
      </div>
    </div>
  );
}
