import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import type { DailyStats } from "../types";
import { AlgorithmTooltip } from "./AlgorithmTooltip";

const CELL = 11;
const GAP = 2;
const STEP = CELL + GAP;
const WEEKS = 53;

// Labels hentes fra i18n — se useTranslation() i komponenten

// plays = 0       →  ingen data registrert (mørkt nøytralt)
// plays > 0, skips = 0  →  aktiv lytting uten skip (grønn)
// skips > 0       →  gul → oransje → rød basert på SKIP-RATE (skips / plays),
//                    ikke absolutt antall skips — konsistent med skipRateColor i theme.ts
function getColor(skips: number, plays: number): string {
  if (plays === 0) return "#1a1a1a";
  if (skips === 0) return "#1db954";
  const rate = skips / plays;          // 0.0 – 1.0
  if (rate <= 0.25) return "#eab308";  // lav skip-rate  — gul    (≤ 25 %)
  if (rate <= 0.50) return "#f97316";  // middels        — oransje (26–50 %)
  if (rate <= 0.75) return "#ef4444";  // høy            — rød    (51–75 %)
  return "#dc2626";                     // svært høy      — mørk rød (> 75 %)
}

interface Props {
  daily: Record<string, DailyStats>;
}

export function SkipHeatmap({ daily }: Props) {
  const { t } = useTranslation();
  const MONTH_NAMES: string[] = t("heatmap.months", { returnObjects: true }) as string[];
  const DAY_LABELS_RAW: string[] = t("heatmap.days", { returnObjects: true }) as string[];
  // Heatmap har 7 rader (man–søn), vi viser label for rad 1, 3, 5 (index 0, 2, 4)
  const DAY_LABELS = ["", DAY_LABELS_RAW[0], "", DAY_LABELS_RAW[1], "", DAY_LABELS_RAW[2], ""];

  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    date: string;
    skips: number;
    plays: number;
  } | null>(null);

  const { cells, monthLabels } = useMemo(() => {
    // Bygg et grid bakover fra i dag, 53 uker.
    //
    // Feil vi fikset: den gamle koden beregnet startDay som
    // "today - 53*7 + 1" og justerte deretter BAKOVER til mandag.
    // Det gjorde at gridet endte på søndagen FØR i dag, slik at
    // de siste dagene (mandag/tirsdag denne uken) aldri ble rendret.
    //
    // Riktig tilnærming: ankre alltid til søndagen i UKENs TIL I DAG,
    // slik at alle dager til og med i dag alltid er synlige.
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // Finn søndagen i nåværende uke (=slutten av gridet)
    const dow = today.getDay(); // 0 = søndag, 1 = mandag …
    const daysToSunday = dow === 0 ? 0 : 7 - dow;
    const endOfWeek = new Date(today);
    endOfWeek.setDate(today.getDate() + daysToSunday);

    // Start er alltid mandagen som åpner gridet: endOfWeek - 53*7 + 1 dag
    // Siden endOfWeek er en søndag, gir dette eksakt en mandag.
    const startDay = new Date(endOfWeek);
    startDay.setDate(endOfWeek.getDate() - WEEKS * 7 + 1);

    const cells: Array<{
      date: string;
      skips: number;
      plays: number;
      col: number;
      row: number;
    }> = [];

    const monthPos: Array<{ month: number; col: number }> = [];
    let lastMonth = -1;

    for (let w = 0; w < WEEKS; w++) {
      for (let d = 0; d < 7; d++) {
        const date = new Date(startDay);
        date.setDate(startDay.getDate() + w * 7 + d);
        if (date > today) continue;

        // Bruk Oslo-tidssone for å matche backend sin DATE(...AT TIME ZONE 'Europe/Oslo')
        const key = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Oslo" }).format(date);
        const stats = daily[key] ?? { skips: 0, plays: 0 };

        cells.push({ date: key, skips: stats.skips, plays: stats.plays, col: w, row: d });

        const m = date.getMonth();
        if (m !== lastMonth && d === 0) {
          monthPos.push({ month: m, col: w });
          lastMonth = m;
        }
      }
    }

    return { cells, monthLabels: monthPos };
  }, [daily]);

  const width = WEEKS * STEP;
  const height = 7 * STEP;

  return (
    <div className="rounded-xl border border-[#2a2a2a] bg-[#181818] p-4 mb-4">
      <div className="flex items-center gap-2 mb-4">
        <h2 className="text-sm font-semibold text-[#999] uppercase tracking-widest">
          {t("heatmap.heading")}
        </h2>
        <AlgorithmTooltip text={t("heatmap.headingTooltip")} color="#666" />
      </div>

      <div className="overflow-x-auto">
        <div className="relative inline-block">
          {/* Ukedags-labels til venstre */}
          <div
            className="absolute left-0 top-0 flex flex-col"
            style={{ gap: GAP, paddingTop: 18 }}
          >
            {DAY_LABELS.map((label, i) => (
              <div
                key={i}
                style={{ height: CELL, lineHeight: `${CELL}px`, fontSize: 9 }}
                className="text-[#888] text-right pr-1 w-6"
              >
                {label}
              </div>
            ))}
          </div>

          <div style={{ marginLeft: 28 }}>
            {/* Måneds-labels */}
            <div className="relative" style={{ height: 16, marginBottom: 2 }}>
              {monthLabels.map(({ month, col }) => (
                <span
                  key={`${month}-${col}`}
                  className="absolute text-[#888]"
                  style={{ left: col * STEP, fontSize: 9, top: 4 }}
                >
                  {MONTH_NAMES[month]}
                </span>
              ))}
            </div>

            {/* SVG-grid */}
            <svg width={width} height={height}>
              {cells.map((c) => (
                <motion.rect
                  key={c.date}
                  x={c.col * STEP}
                  y={c.row * STEP}
                  width={CELL}
                  height={CELL}
                  rx={2}
                  fill={getColor(c.skips, c.plays)}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: (c.col * 7 + c.row) * 0.0005 }}
                  className="cursor-pointer"
                  onMouseMove={(e) => {
                    setTooltip({
                      x: e.clientX,
                      y: e.clientY,
                      date: c.date,
                      skips: c.skips,
                      plays: c.plays,
                    });
                  }}
                  onMouseLeave={() => setTooltip(null)}
                />
              ))}
            </svg>
          </div>

          {/* Tooltip — følger cursoren, flipper til venstre nær høyre kant */}
          {tooltip && (
            <div
              className="fixed z-50 pointer-events-none rounded-lg border border-[#333] bg-[#111] px-3 py-2 shadow-xl text-xs"
              style={{
                left: tooltip.x + 140 > window.innerWidth ? tooltip.x - 144 : tooltip.x + 12,
                top: tooltip.y - 36,
              }}
            >
              <div className="font-semibold text-white mb-0.5">{tooltip.date}</div>
              <div className="text-[#f59e0b]">{t("heatmap.tooltipSkips", { n: tooltip.skips })}</div>
              <div className="text-[#999]">{t("heatmap.tooltipPlays", { n: tooltip.plays })}</div>
            </div>
          )}
        </div>
      </div>

      {/* Fargelegende */}
      <div className="flex items-center gap-2 mt-4 text-[#888] text-xs">
        <span>{t("heatmap.legendNone")}</span>
        {["#1a1a1a", "#1db954", "#eab308", "#f97316", "#ef4444"].map((c) => (
          <div key={c} className="w-3 h-3 rounded-sm" style={{ background: c }} />
        ))}
        <span>{t("heatmap.legendMany")}</span>
      </div>
    </div>
  );
}
