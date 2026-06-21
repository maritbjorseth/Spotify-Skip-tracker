import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import type { DailyStats } from "../types";

const CELL = 11;
const GAP = 2;
const STEP = CELL + GAP;
const WEEKS = 53;

const MONTH_NAMES = [
  "jan", "feb", "mar", "apr", "mai", "jun",
  "jul", "aug", "sep", "okt", "nov", "des",
];
const DAY_LABELS = ["", "man", "", "ons", "", "fre", ""];

function getColor(skips: number, maxSkips: number): string {
  if (skips === 0) return "#1a1a1a";
  const t = Math.min(1, skips / Math.max(maxSkips * 0.6, 1));
  // Gradient: mørkegrønn → lys oransje for høye skip-tall
  if (t < 0.33) return "#1a3d25";
  if (t < 0.66) return "#1db954";
  if (t < 0.85) return "#e07b3a";
  return "#ff6b35";
}

interface Props {
  daily: Record<string, DailyStats>;
}

export function SkipHeatmap({ daily }: Props) {
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    date: string;
    skips: number;
    plays: number;
  } | null>(null);

  const { cells, monthLabels, maxSkips } = useMemo(() => {
    // Bygg et grid bakover fra i dag, 53 uker
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // Start fra mandag i første uke
    const startDay = new Date(today);
    startDay.setDate(today.getDate() - WEEKS * 7 + 1);
    // Juster til nærmeste mandag
    const dow = startDay.getDay(); // 0 = søndag
    const toMonday = dow === 0 ? -6 : 1 - dow;
    startDay.setDate(startDay.getDate() + toMonday);

    const cells: Array<{
      date: string;
      skips: number;
      plays: number;
      col: number;
      row: number;
    }> = [];

    let maxSkips = 1;
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
        if (stats.skips > maxSkips) maxSkips = stats.skips;

        cells.push({ date: key, skips: stats.skips, plays: stats.plays, col: w, row: d });

        const m = date.getMonth();
        if (m !== lastMonth && d === 0) {
          monthPos.push({ month: m, col: w });
          lastMonth = m;
        }
      }
    }

    return { cells, monthLabels: monthPos, maxSkips };
  }, [daily]);

  const width = WEEKS * STEP;
  const height = 7 * STEP;

  return (
    <div className="rounded-xl border border-[#2a2a2a] bg-[#181818] p-6 mb-8">
      <h2 className="text-sm font-semibold text-[#999] uppercase tracking-widest mb-4">
        Skip-aktivitet siste år
      </h2>

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
                className="text-[#555] text-right pr-1 w-6"
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
                  className="absolute text-[#555]"
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
                  fill={getColor(c.skips, maxSkips)}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: (c.col * 7 + c.row) * 0.0005 }}
                  className="cursor-pointer"
                  onMouseEnter={(e) => {
                    const rect = (e.target as SVGRectElement)
                      .closest("svg")!
                      .getBoundingClientRect();
                    setTooltip({
                      x: rect.left + c.col * STEP,
                      y: rect.top + c.row * STEP,
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

          {/* Tooltip */}
          {tooltip && (
            <div
              className="fixed z-50 pointer-events-none rounded-lg border border-[#333] bg-[#111] px-3 py-2 shadow-xl text-xs"
              style={{ left: tooltip.x + 8, top: tooltip.y - 4 }}
            >
              <div className="font-semibold text-white mb-0.5">{tooltip.date}</div>
              <div className="text-[#ff6b35]">{tooltip.skips} skip</div>
              <div className="text-[#999]">{tooltip.plays} avspillinger</div>
            </div>
          )}
        </div>
      </div>

      {/* Fargelegende */}
      <div className="flex items-center gap-2 mt-4 text-[#555] text-xs">
        <span>Færre</span>
        {["#1a1a1a", "#1a3d25", "#1db954", "#e07b3a", "#ff6b35"].map((c) => (
          <div key={c} className="w-3 h-3 rounded-sm" style={{ background: c }} />
        ))}
        <span>Flere skip</span>
      </div>
    </div>
  );
}
