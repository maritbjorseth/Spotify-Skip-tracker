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
import { C, skipRateColor } from "../theme";

// ---------------------------------------------------------------------------
// Delt tema
// ---------------------------------------------------------------------------

const TICK_STYLE = { fill: "#888", fontSize: 11 };

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
        <p className="text-[#888] mt-0.5">{skips} skip / {plays} avsp.</p>
      )}
      {plays === 0 && (
        <p className="text-[#777] mt-0.5 italic">Ingen avspillinger</p>
      )}
    </div>
  );
}

function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-[#2a2a2a] bg-[#181818] p-4">
      <h2 className="text-sm font-semibold uppercase tracking-widest text-[#888]">
        {title}
      </h2>
      {subtitle && (
        <p className="text-xs text-[#888] mt-1 mb-3">{subtitle}</p>
      )}
      {!subtitle && <div className="mb-3" />}
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mest skippede artister
// ---------------------------------------------------------------------------

export function ArtistChart({ artists }: { artists: Artist[] }) {
  // Sort DESC (høyest skip-rate først = data[0]).
  // Recharts layout="vertical" rendrer data[0] øverst som standard — ingen reversed nødvendig.
  const data = [...artists]
    .sort((a, b) =>
      b.skip_rate - a.skip_rate ||          // 1. skip-rate DESC
      b.skip_count - a.skip_count ||        // 2. antall skips DESC
      a.artists.localeCompare(b.artists, "nb") // 3. artistnavn A–Å
    )
    .map((a) => {
      const first = a.artists.split(",")[0].trim();
      const ratePct = Math.round(a.skip_rate * 100);
      return {
        name: a.artists.includes(",") ? first + " m.fl." : first,
        skips: a.skip_count,
        rate: ratePct,
        plays: a.play_count,
        label: `${ratePct}% (${a.skip_count} skip)`,
      };
    });

  const chartHeight = Math.max(240, data.length * 48);

  return (
    <ChartCard title="Høyest skip-rate per artist" subtitle="Rangert etter skip-rate (min. 5 avspillinger).">
      <div style={{ height: chartHeight + 64 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            barCategoryGap="35%"
            margin={{ top: 16, right: 112, bottom: 16, left: 16 }}
          >
            <XAxis type="number" domain={[0, 100]} hide />
            <YAxis type="category" dataKey="name" hide />
            <Tooltip content={<RateTooltip />} cursor={{ fill: "#ffffff08" }} />
            <Bar dataKey="rate" radius={[0, 4, 4, 0]} barSize={22}>
              {data.map((d, i) => (
                <Cell
                  key={i}
                  fill={skipRateColor(d.rate, d.plays)}
                  fillOpacity={0.9 - i * 0.04}
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
              {/* Skip-rate til høyre for søylen */}
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

  const chartHeight = Math.max(160, data.length * 34);

  return (
    <ChartCard title="Høyest skip-rate per spilleliste/album">
      {/* Filter-bryterrekke */}
      <div className="flex gap-1 mb-4">
        {FILTER_BUTTONS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setFilter(id)}
            className={[
              "rounded-md border px-3 py-1 text-xs font-medium transition-all duration-150",
              filter === id
                ? "border-[#1db954] bg-[#1db95420] text-[#1db954]"
                : "border-[#2e2e2e] bg-[#1c1c1c] text-[#666] hover:border-[#555] hover:text-[#aaa]",
            ].join(" ")}
          >
            {label}
          </button>
        ))}
      </div>

      {data.length === 0 ? (
        <div className="flex items-center justify-center h-[120px] text-xs text-[#777] italic">
          Ingen data for dette filteret ennå.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 100, bottom: 0, left: 8 }}>
            <XAxis type="number" domain={[0, 100]} hide />
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
            <Bar dataKey="rate" radius={[0, 4, 4, 0]} barSize={18}>
              {data.map((d, i) => (
                <Cell
                  key={i}
                  fill={skipRateColor(d.rate, d.plays)}
                  fillOpacity={0.9 - i * 0.04}
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

  const totalSkips = data.reduce((s, d) => s + d.skip, 0);

  return (
    <ChartCard title="Skips etter tidspunkt på døgnet">
      {totalSkips === 0 ? (
        <div className="flex items-center justify-center h-[200px] text-xs text-[#777] italic">
          Ingen data ennå – tracker samler data i sanntid.
        </div>
      ) : (
      <ResponsiveContainer width="100%" height={180}>
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
            {data.map((_, i) => (
              <Cell key={i} fill={C.neutral} fillOpacity={0.85} />
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

  const totalSkips = data.reduce((s, d) => s + d.skip, 0);

  return (
    <ChartCard title="Skip-antall etter ukedag">
      {totalSkips === 0 ? (
        <div className="flex items-center justify-center h-[200px] text-xs text-[#777] italic">
          Ingen data ennå – tracker samler data i sanntid.
        </div>
      ) : (
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ left: -16, right: 4 }} barCategoryGap="18%">
          <XAxis dataKey="day" tick={TICK_STYLE} axisLine={false} tickLine={false} />
          <YAxis tick={TICK_STYLE} axisLine={false} tickLine={false} />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "#ffffff08" }} />
          <Bar dataKey="skip" name="Skip" radius={[3, 3, 0, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill={C.neutral} fillOpacity={0.85} />
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

  return (
    <ChartCard title="Skip-rate per time på døgnet">
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
                fill={skipRateColor(d.rate, d.plays)}
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

  return (
    <ChartCard title="Skip-rate per ukedag">
      <ResponsiveContainer width="100%" height={200}>
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
                fill={skipRateColor(d.rate, d.plays)}
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
