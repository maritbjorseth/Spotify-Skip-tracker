/**
 * SkipTrendChart
 *
 * Viser ukentlig skip-rate (%) de siste 16 ukene basert på den eksisterende
 * `daily`-dataen som allerede hentes av /api/stats.  Ingen nye API-kall.
 *
 * Grafen inneholder:
 *  - Fylt areal  — ukentlig skip-rate (rå, nøytral blå)
 *  - Linje       — 4-ukers glidende gjennomsnitt (amber, tydelig trend)
 *  - Referanselinje — totalsnitt over alle viste uker (stiplet)
 *  - Trend-badge — "↓ Ned Xpp" / "→ Stabil" / "↑ Opp Xpp" vs. forrige 4 uker
 */

import { useMemo } from "react";
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";
import type { DailyStats } from "../types";
import { C, skipRateColor } from "../theme";

// ---------------------------------------------------------------------------
// Konstanter
// ---------------------------------------------------------------------------

const WEEKS_TO_SHOW = 16;
const TICK_STYLE = { fill: "#888", fontSize: 11 };

// ---------------------------------------------------------------------------
// Databehandling
// ---------------------------------------------------------------------------

/** Returnerer "YYYY-MM-DD" for mandagen i uken som inneholder dateStr. */
function getMondayKey(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  const dow = d.getDay(); // 0 = søndag, 1 = mandag, …, 6 = lørdag
  const diff = dow === 0 ? -6 : 1 - dow;
  d.setDate(d.getDate() + diff);
  return d.toISOString().slice(0, 10);
}

/** Formater "YYYY-MM-DD" → "24. jun" (norsk kortformat). */
function fmtWeekLabel(mondayKey: string): string {
  return new Date(mondayKey + "T12:00:00").toLocaleDateString("nb-NO", {
    day: "numeric",
    month: "short",
  });
}

interface WeekPoint {
  weekKey: string; // "YYYY-MM-DD" (mandag)
  label: string;   // "24. jun"
  skips: number;
  plays: number;
  rate: number;    // 0–100 (ukentlig skip-rate i prosent)
  avg4: number;    // 4-ukers glidende gjennomsnitt (0–100)
}

/**
 * Grupperer daglige stats etter uke, beregner skip-rate per uke og
 * et 4-ukers glidende gjennomsnitt.  Returnerer de siste WEEKS_TO_SHOW ukene.
 */
function buildWeeklyData(daily: Record<string, DailyStats>): WeekPoint[] {
  // Steg 1: summer skips og avspillinger per uke
  const map = new Map<string, { skips: number; plays: number }>();
  for (const [dateStr, { skips, plays }] of Object.entries(daily)) {
    const key = getMondayKey(dateStr);
    const prev = map.get(key) ?? { skips: 0, plays: 0 };
    map.set(key, { skips: prev.skips + skips, plays: prev.plays + plays });
  }

  // Steg 2: sorter, filtrer uker uten aktivitet, behold siste N uker
  const sorted = [...map.entries()]
    .filter(([, v]) => v.plays > 0)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-WEEKS_TO_SHOW);

  // Steg 3: beregn rate + 4-ukers glidende gjennomsnitt
  return sorted.map(([weekKey, { skips, plays }], i, arr) => {
    const rate = Math.round((skips / plays) * 100);

    const window = arr.slice(Math.max(0, i - 3), i + 1);
    const avg4 = Math.round(
      (window.reduce((s, [, v]) => s + (v.plays > 0 ? v.skips / v.plays : 0), 0) /
        window.length) * 100,
    );

    return { weekKey, label: fmtWeekLabel(weekKey), skips, plays, rate, avg4 };
  });
}

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

function TrendTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: WeekPoint }>;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg border border-[#333] bg-[#111] px-3 py-2 shadow-xl text-xs">
      <p className="font-semibold text-white mb-1">Uke f.o.m. {d.label}</p>
      <p style={{ color: skipRateColor(d.rate, d.plays) }}>{d.rate}% skip-rate</p>
      <p className="text-[#888] mt-0.5">
        {d.skips} skip / {d.plays} avspillinger
      </p>
      <p className="mt-0.5" style={{ color: C.amber }}>
        {d.avg4}% snitt (4 uker)
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Trend-badge
// ---------------------------------------------------------------------------

/**
 * Sammenligner siste 4 uker mot de forrige 4.
 * Returnerer null hvis det ikke finnes minst 8 uker med data.
 */
function computeTrend(
  weeks: WeekPoint[],
): { label: string; color: string } | null {
  if (weeks.length < 8) return null;

  const sumRate = (slice: WeekPoint[]) => {
    const s = slice.reduce((a, w) => a + w.skips, 0);
    const p = slice.reduce((a, w) => a + w.plays, 0);
    return p > 0 ? (s / p) * 100 : 0;
  };

  const last4 = sumRate(weeks.slice(-4));
  const prev4 = sumRate(weeks.slice(-8, -4));
  const delta = Math.round(last4 - prev4);

  if (Math.abs(delta) < 2) return { label: "→ Stabil", color: C.neutral };
  if (delta < 0)
    return { label: `↓ Ned ${Math.abs(delta)}pp`, color: C.green };
  return { label: `↑ Opp ${delta}pp`, color: C.red };
}

// ---------------------------------------------------------------------------
// Hoved­komponent
// ---------------------------------------------------------------------------

export function SkipTrendChart({
  daily,
}: {
  daily: Record<string, DailyStats>;
}) {
  const weeks = useMemo(() => buildWeeklyData(daily), [daily]);
  const trend = useMemo(() => computeTrend(weeks), [weeks]);

  if (weeks.length < 3) {
    return (
      <div className="rounded-xl border border-[#2a2a2a] bg-[#181818] p-4 mb-4">
        <h2 className="text-sm font-semibold uppercase tracking-widest text-[#888] mb-3">
          Skip-rate over tid
        </h2>
        <div className="flex items-center justify-center h-[100px] text-xs text-[#777] italic">
          Trenger minst 3 ukers data for å vise trenden.
        </div>
      </div>
    );
  }

  // Referanselinje: totalsnitt over alle viste uker
  const totalSkips = weeks.reduce((s, w) => s + w.skips, 0);
  const totalPlays = weeks.reduce((s, w) => s + w.plays, 0);
  const overallRate = Math.round((totalSkips / totalPlays) * 100);

  // Vis annenhver X-akse-label når det er mange uker
  const xInterval = weeks.length > 10 ? 1 : 0;

  return (
    <div className="rounded-xl border border-[#2a2a2a] bg-[#181818] p-4 mb-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold uppercase tracking-widest text-[#888] flex items-center gap-1.5">
          Skip-rate over tid
          <span
            title="Ukentlig skip-rate de siste 16 ukene. Stiplet linje = totalsnitt. Amber linje = 4-ukers glidende gjennomsnitt."
            className="text-[#666] hover:text-[#999] cursor-help transition-colors text-[10px] font-normal normal-case tracking-normal"
          >
            ⓘ
          </span>
        </h2>

        {trend && (
          <span
            className="text-xs font-medium px-2 py-0.5 rounded-full border"
            style={{
              color: trend.color,
              borderColor: trend.color + "40",
              background: trend.color + "12",
            }}
          >
            {trend.label} siste 4 uker
          </span>
        )}
      </div>

      {/* Graf */}
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart
          data={weeks}
          margin={{ top: 4, right: 8, bottom: 0, left: -4 }}
        >
          <CartesianGrid stroke="#1e1e1e" vertical={false} />
          <XAxis
            dataKey="label"
            tick={TICK_STYLE}
            axisLine={false}
            tickLine={false}
            interval={xInterval}
          />
          <YAxis
            domain={[0, 100]}
            tickFormatter={(v: number) => `${v}%`}
            tick={TICK_STYLE}
            axisLine={false}
            tickLine={false}
            width={34}
          />
          <Tooltip content={<TrendTooltip />} cursor={{ fill: "#ffffff06", stroke: "none" }} />

          {/* Totalsnitt-referanselinje */}
          <ReferenceLine
            y={overallRate}
            stroke="#3a3a3a"
            strokeDasharray="4 4"
            label={{
              value: `snitt ${overallRate}%`,
              position: "insideTopRight",
              fill: "#555",
              fontSize: 10,
            }}
          />

          {/* Ukentlig skip-rate — fylt areal */}
          <Area
            type="monotone"
            dataKey="rate"
            name="Ukentlig rate"
            stroke={C.neutral}
            strokeWidth={1.5}
            fill={C.neutral}
            fillOpacity={0.12}
            dot={{ fill: C.neutral, r: 3, strokeWidth: 0 }}
            activeDot={{ r: 5, fill: C.neutral, strokeWidth: 0 }}
          />

          {/* 4-ukers glidende gjennomsnitt — overlappende linje */}
          <Line
            type="monotone"
            dataKey="avg4"
            name="4-ukers snitt"
            stroke={C.amber}
            strokeWidth={2}
            dot={false}
            activeDot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Forklaring */}
      <div className="flex items-center gap-4 mt-3 text-[#888] text-[11px]">
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block w-3 h-0.5 rounded"
            style={{ background: C.neutral }}
          />
          Ukentlig skip-rate
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block w-3 h-0.5 rounded"
            style={{ background: C.amber }}
          />
          4-ukers snitt
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-4 border-t border-dashed border-[#3a3a3a]" />
          Totalsnitt
        </span>
      </div>
    </div>
  );
}
