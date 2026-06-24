import { useState } from "react";
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
    const ratePct = Math.round(a.skip_rate * 100);
    return {
      name: a.artists.includes(",") ? first + " m.fl." : first,
      skip: a.skip_count,
      label: `${a.skip_count} skips (${ratePct}%)`,
    };
  });

  const chartHeight = Math.max(300, data.length * 56);

  return (
    <ChartCard title="Mest skippede artister" subtitle="Artister du har lavest tålmodighet for." color="#ff6b35">
      <div style={{ height: chartHeight + 80 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            barCategoryGap="35%"
            margin={{ top: 20, right: 120, bottom: 20, left: 20 }}
          >
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="name" hide />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "#ffffff08" }} />
            <Bar dataKey="skip" radius={[0, 4, 4, 0]} barSize={24}>
              {data.map((_, i) => (
                <Cell
                  key={i}
                  fill={`hsl(${20 + i * 6}, 90%, ${65 - i * 2}%)`}
                />
              ))}
              {/* Artistnavn rendres rett over sin søyle */}
              <LabelList
                dataKey="name"
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                content={({ x, y, value }: any) => {
                  const text = String(value ?? "");
                  const display = text.length > 24 ? text.slice(0, 23) + "…" : text;
                  return (
                    <text
                      x={Number(x) + 6}
                      y={Number(y) - 5}
                      fill="#d0d0d0"
                      fontSize={12}
                      fontWeight={500}
                      textAnchor="start"
                    >
                      {display}
                    </text>
                  );
                }}
              />
              {/* Skip-teller til høyre for søylen */}
              <LabelList
                dataKey="label"
                position="right"
                style={{ fill: "#aaa", fontSize: 13, fontWeight: 500 }}
              />
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

type ContextFilter = "playlist" | "album" | "all";

const FILTER_BUTTONS: { id: ContextFilter; label: string }[] = [
  { id: "playlist", label: "Spillelister" },
  { id: "album",    label: "Album" },
  { id: "all",      label: "Alle" },
];

export function ContextChart({
  contexts,
  playlistContexts = [],
  albumContexts = [],
}: {
  contexts: Context[];
  playlistContexts?: string[];
  albumContexts?: string[];
}) {
  const [filter, setFilter] = useState<ContextFilter>("playlist");

  const playlistSet = new Set(playlistContexts);
  const albumSet    = new Set(albumContexts);

  const filtered = contexts.filter((c) => {
    if (filter === "all")      return true;
    if (filter === "playlist") return playlistSet.has(c.context_name);
    if (filter === "album")    return albumSet.has(c.context_name);
    return true;
  });

  const data = filtered.slice(0, 8).map((c) => ({
    name: c.context_name,
    rate: Math.round(c.skip_rate * 100),
    skips: c.skip_count,
    plays: c.play_count,
    label: `${Math.round(c.skip_rate * 100)}%`,
  }));

  const chartHeight = Math.max(200, data.length * 40);

  return (
    <ChartCard title="Høyest skip-rate per spilleliste/album" color="#ff6b35">
      {/* Filter-bryterrekke */}
      <div className="flex gap-1 mb-4">
        {FILTER_BUTTONS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setFilter(id)}
            className={[
              "rounded-md border px-3 py-1 text-xs font-medium transition-all duration-150",
              filter === id
                ? "border-[#ff6b35] bg-[#ff6b3520] text-[#ff6b35]"
                : "border-[#2e2e2e] bg-[#1c1c1c] text-[#666] hover:border-[#555] hover:text-[#aaa]",
            ].join(" ")}
          >
            {label}
          </button>
        ))}
      </div>

      {data.length === 0 ? (
        <div className="flex items-center justify-center h-[120px] text-xs text-[#444] italic">
          Ingen data for dette filteret ennå.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 120, bottom: 4, left: 8 }}>
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
              tick={{ fontSize: 13, fill: "#d0d0d0", textAnchor: "start" }}
              axisLine={false}
              tickLine={false}
              width={140}
              dx={-132}
              tickFormatter={(v: string) => v.length > 18 ? v.slice(0, 17) + "…" : v}
            />
            <Tooltip content={<CustomTooltip suffix="%" />} cursor={{ fill: "#ffffff08" }} />
            <Bar dataKey="rate" radius={[0, 4, 4, 0]} barSize={20}>
              {data.map((d, i) => (
                <Cell
                  key={i}
                  fill={d.rate > 25 ? "#e11d48" : "#1db954"}
                  fillOpacity={0.85 - i * 0.04}
                />
              ))}
              <LabelList
                dataKey="label"
                position="right"
                style={{ fill: "#aaa", fontSize: 13, fontWeight: 500 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
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

  const peakHour = totalSkips > 0
    ? data.reduce((best, d) => (d.skip > best.skip ? d : best), data[0])
    : null;
  const peakLabel = peakHour && peakHour.skip > 0
    ? `Du gjør flest skips rundt kl. ${peakHour.hour.split(":")[0]}–${String(Number(peakHour.hour.split(":")[0]) + 2).padStart(2, "0")}`
    : undefined;

  return (
    <ChartCard title="Skips etter tidspunkt på døgnet" subtitle={peakLabel} color="#9b59b6">
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

const DAY_FULL = ["Mandager", "Tirsdager", "Onsdager", "Torsdager", "Fredager", "Lørdager", "Søndager"];

export function WeekdayRateChart({ weekday }: { weekday: WeekdayStats[] }) {
  const data = weekday.map((w, i) => ({
    day: DAYS[i],
    dayFull: DAY_FULL[i],
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

  const daysWithData = data.filter((d) => d.plays > 0);
  const peakDay = daysWithData.length > 0
    ? daysWithData.reduce((best, d) => (d.rate > best.rate ? d : best), daysWithData[0])
    : null;
  const subtitle = peakDay && peakDay.rate > 0
    ? `${peakDay.dayFull} er din mest utålmodige dag (${peakDay.rate}% skip-rate)`
    : undefined;

  return (
    <ChartCard title="Skip-rate per ukedag" subtitle={subtitle} color="#1db954">
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
    </ChartCard>
  );
}
