import type { ReactNode } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  LabelList,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { Artist, Context, HourlyStats, WeekdayStats } from "../types";

// ---------------------------------------------------------------------------
// Delt tema
// ---------------------------------------------------------------------------

const TICK_STYLE = { fill: "#666", fontSize: 11 };

interface TooltipPayload {
  name: string;
  value: number;
  color: string;
  payload: Record<string, number>;
}

function CustomTooltip({
  active,
  payload,
  label,
  suffix = "",
}: {
  active?: boolean;
  payload?: TooltipPayload[];
  label?: string;
  suffix?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-[#333] bg-[#111] px-3 py-2 shadow-xl text-xs">
      <p className="font-semibold text-white mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.value}{suffix}
        </p>
      ))}
    </div>
  );
}

// Tooltip for rate-grafer: viser %-rate + rå skip/avspillinger
function RateTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayload[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0];
  const { skips, plays } = row.payload;
  return (
    <div className="rounded-lg border border-[#333] bg-[#111] px-3 py-2 shadow-xl text-xs">
      <p className="font-semibold text-white mb-1">{label}</p>
      <p style={{ color: row.color }}>{row.value}% skip-rate</p>
      {plays > 0 && (
        <p className="text-[#555] mt-0.5">{skips} skip / {plays} avsp.</p>
      )}
      {plays === 0 && (
        <p className="text-[#444] mt-0.5 italic">Ingen avspillinger</p>
      )}
    </div>
  );
}

function ChartCard({ title, subtitle, color, children }: { title: string; subtitle?: string; color: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-[#2a2a2a] bg-[#181818] p-6">
      <h2 className="text-sm font-semibold uppercase tracking-widest" style={{ color }}>
        {title}
      </h2>
      {subtitle && (
        <p className="text-xs text-[#555] mt-1 mb-5">{subtitle}</p>
      )}
      {!subtitle && <div className="mb-5" />}
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mest skippede artister
// ---------------------------------------------------------------------------

export function ArtistChart({ artists }: { artists: Artist[] }) {
  const data = artists.map((a) => {
    const first = a.artists.split(",")[0].trim();
    return {
      name: a.artists.includes(",") ? first + " m.fl." : first,
      skip: a.skip_count,
    };
  });

  const chartHeight = Math.max(300, data.length * 44);

  return (
    <ChartCard title="Mest skippede artister" subtitle="Artister du har lavest tålmodighet for." color="#ff6b35">
      <div style={{ height: chartHeight + 80 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 20, right: 28, bottom: 20, left: 180 }}>
            <XAxis type="number" allowDecimals={false} tick={TICK_STYLE} axisLine={false} tickLine={false} />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 16, fill: "#d0d0d0" }}
              axisLine={false}
              tickLine={false}
              width={180}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "#ffffff08" }} />
            <Bar dataKey="skip" radius={[0, 4, 4, 0]} barSize={22}>
              {data.map((_, i) => (
                <Cell
                  key={i}
                  fill={`hsl(${20 + i * 6}, 90%, ${65 - i * 2}%)`}
                />
              ))}
              <LabelList dataKey="skip" position="right" style={{ fill: "#fff", fontSize: 16, fontWeight: 600 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}

// ---------------------------------------------------------------------------
// Høyest skip-rate per spilleliste/album
// ---------------------------------------------------------------------------

export function ContextChart({ contexts }: { contexts: Context[] }) {
  const data = contexts.slice(0, 8).map((c) => ({
    name: c.context_name,
    rate: Math.round(c.skip_rate * 100),
  }));

  const chartHeight = Math.max(200, data.length * 40);

  return (
    <ChartCard title="Høyest skip-rate per spilleliste/album" color="#ff6b35">
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart data={data} layout="vertical" margin={{ left: 0, right: 48 }}>
          <XAxis
            type="number"
            domain={[0, 100]}
            tick={TICK_STYLE}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => `${v}%`}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={TICK_STYLE}
            axisLine={false}
            tickLine={false}
            width={110}
            tickFormatter={(v: string) => v.length > 15 ? v.slice(0, 14) + "…" : v}
          />
          <Tooltip content={<CustomTooltip suffix="%" />} cursor={{ fill: "#ffffff08" }} />
          <Bar dataKey="rate" radius={[0, 4, 4, 0]} barSize={20}>
            {data.map((d, i) => (
              <Cell
                key={i}
                fill={d.rate >= 50 ? "#ff6b35" : "#1db954"}
                fillOpacity={0.85 - i * 0.05}
              />
            ))}
            <LabelList
              dataKey="rate"
              position="right"
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={(v: any) => v != null ? `${v}%` : ""}
              style={{ fill: "#aaa", fontSize: 13, fontWeight: 600 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// ---------------------------------------------------------------------------
// Skip per time på døgnet
// ---------------------------------------------------------------------------

export function HourlyChart({ hourly }: { hourly: HourlyStats[] }) {
  const data = hourly.map((h, i) => ({
    hour: `${i}:00`,
    skip: h.skips,
    plays: h.plays,
  }));

  const max = Math.max(...data.map((d) => d.skip), 1);
  const totalSkips = data.reduce((s, d) => s + d.skip, 0);

  return (
    <ChartCard title="Skip-antall etter tidspunkt på døgnet" color="#9b59b6">
      {totalSkips === 0 ? (
        <div className="flex items-center justify-center h-[200px] text-xs text-[#444] italic">
          Ingen data ennå – tracker samler data i sanntid.
        </div>
      ) : (
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ left: -16, right: 4 }} barCategoryGap="12%">
          <XAxis
            dataKey="hour"
            tick={TICK_STYLE}
            axisLine={false}
            tickLine={false}
            interval={3}
            tickFormatter={(v: string) => v.split(":")[0]}
          />
          <YAxis tick={TICK_STYLE} axisLine={false} tickLine={false} />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "#ffffff08" }} />
          <Bar dataKey="skip" name="Skip" radius={[3, 3, 0, 0]}>
            {data.map((d, i) => (
              <Cell
                key={i}
                fill={`hsl(280, 60%, ${35 + (d.skip / max) * 30}%)`}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      )}
    </ChartCard>
  );
}

// ---------------------------------------------------------------------------
// Skip per ukedag
// ---------------------------------------------------------------------------

const DAYS = ["Man", "Tir", "Ons", "Tor", "Fre", "Lør", "Søn"];

export function WeekdayChart({ weekday }: { weekday: WeekdayStats[] }) {
  const data = weekday.map((w, i) => ({
    day: DAYS[i],
    skip: w.skips,
    plays: w.plays,
  }));

  const max = Math.max(...data.map((d) => d.skip), 1);
  const totalSkips = data.reduce((s, d) => s + d.skip, 0);

  return (
    <ChartCard title="Skip-antall etter ukedag" color="#9b59b6">
      {totalSkips === 0 ? (
        <div className="flex items-center justify-center h-[200px] text-xs text-[#444] italic">
          Ingen data ennå – tracker samler data i sanntid.
        </div>
      ) : (
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ left: -16, right: 4 }} barCategoryGap="18%">
          <XAxis dataKey="day" tick={TICK_STYLE} axisLine={false} tickLine={false} />
          <YAxis tick={TICK_STYLE} axisLine={false} tickLine={false} />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "#ffffff08" }} />
          <Bar dataKey="skip" name="Skip" radius={[3, 3, 0, 0]}>
            {data.map((d, i) => (
              <Cell
                key={i}
                fill={`hsl(280, 60%, ${30 + (d.skip / max) * 35}%)`}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      )}
    </ChartCard>
  );
}

// ---------------------------------------------------------------------------
// Skip-RATE per time på døgnet (prosent, ikke antall)
// ---------------------------------------------------------------------------

export function HourlyRateChart({ hourly }: { hourly: HourlyStats[] }) {
  const data = hourly.map((h, i) => ({
    hour: `${i}:00`,
    rate: h.plays > 0 ? Math.round((h.skips / h.plays) * 100) : 0,
    skips: h.skips,
    plays: h.plays,
  }));

  // Farger: lav rate → grønn, høy rate → oransje (matching ContextChart-logikk)
  function barColor(rate: number, plays: number): string {
    if (plays === 0) return "#2a2a2a";
    if (rate < 25) return `hsl(140, 60%, ${28 + rate * 0.4}%)`;
    if (rate < 50) return `hsl(${140 - (rate - 25) * 3.6}, 65%, 38%)`;
    return `hsl(${25 - (rate - 50) * 0.2}, 85%, 48%)`;
  }

  return (
    <ChartCard title="Skip-rate per time på døgnet" color="#4a9eff">
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ left: -4, right: 4 }} barCategoryGap="12%">
          <XAxis
            dataKey="hour"
            tick={TICK_STYLE}
            axisLine={false}
            tickLine={false}
            interval={3}
            tickFormatter={(v: string) => v.split(":")[0]}
          />
          <YAxis
            tick={TICK_STYLE}
            axisLine={false}
            tickLine={false}
            domain={[0, 100]}
            tickFormatter={(v: number) => `${v}%`}
            width={34}
          />
          <Tooltip content={<RateTooltip />} cursor={{ fill: "#ffffff08" }} />
          <Bar dataKey="rate" name="Skip-rate" radius={[3, 3, 0, 0]}>
            {data.map((d, i) => (
              <Cell
                key={i}
                fill={barColor(d.rate, d.plays)}
                fillOpacity={d.plays === 0 ? 0.35 : 0.9}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// ---------------------------------------------------------------------------
// Skip-RATE per ukedag (prosent, ikke antall)
// ---------------------------------------------------------------------------

export function WeekdayRateChart({ weekday }: { weekday: WeekdayStats[] }) {
  const data = weekday.map((w, i) => ({
    day: DAYS[i],
    rate: w.plays > 0 ? Math.round((w.skips / w.plays) * 100) : 0,
    skips: w.skips,
    plays: w.plays,
  }));

  function barColor(rate: number, plays: number): string {
    if (plays === 0) return "#2a2a2a";
    if (rate < 25) return `hsl(140, 60%, ${28 + rate * 0.4}%)`;
    if (rate < 50) return `hsl(${140 - (rate - 25) * 3.6}, 65%, 38%)`;
    return `hsl(${25 - (rate - 50) * 0.2}, 85%, 48%)`;
  }

  // Beregn gjennomsnittlig skip-rate (kun dager med data)
  const daysWithData = data.filter((d) => d.plays > 0);
  const avgRate =
    daysWithData.length > 0
      ? Math.round(daysWithData.reduce((s, d) => s + d.rate, 0) / daysWithData.length)
      : null;

  return (
    <ChartCard title="Skip-rate per ukedag" color="#4a9eff">
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ left: -4, right: 4 }} barCategoryGap="18%">
          <XAxis dataKey="day" tick={TICK_STYLE} axisLine={false} tickLine={false} />
          <YAxis
            tick={TICK_STYLE}
            axisLine={false}
            tickLine={false}
            domain={[0, 100]}
            tickFormatter={(v: number) => `${v}%`}
            width={34}
          />
          <Tooltip content={<RateTooltip />} cursor={{ fill: "#ffffff08" }} />
          <Bar dataKey="rate" name="Skip-rate" radius={[3, 3, 0, 0]}>
            {data.map((d, i) => (
              <Cell
                key={i}
                fill={barColor(d.rate, d.plays)}
                fillOpacity={d.plays === 0 ? 0.35 : 0.9}
              />
            ))}
            <LabelList
              dataKey="rate"
              position="top"
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={(v: any) => (v > 0 ? `${v}%` : "")}
              style={{ fill: "#777", fontSize: 12, fontWeight: 600 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {avgRate !== null && (
        <p className="mt-2 text-right text-xs text-[#555]">
          Snitt: <span className="text-[#777] font-medium">{avgRate}%</span>
        </p>
      )}
    </ChartCard>
  );
}
