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
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>
          {p.value}{suffix}
        </p>
      ))}
    </div>
  );
}

function ChartCard({ title, color, children }: { title: string; color: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-[#2a2a2a] bg-[#181818] p-6">
      <h2 className="text-sm font-semibold uppercase tracking-widest mb-5" style={{ color }}>
        {title}
      </h2>
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

  const chartHeight = Math.max(300, data.length * 40);

  return (
    <ChartCard title="Mest skippede artister" color="#ff6b35">
      <div style={{ height: chartHeight + 80 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 20, right: 40, bottom: 20, left: 180 }}>
            <XAxis hide />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 16, fill: "#d0d0d0" }}
              axisLine={false}
              tickLine={false}
              width={180}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "#ffffff08" }} />
            <Bar dataKey="skip" radius={[0, 4, 4, 0]}>
              {data.map((_, i) => (
                <Cell
                  key={i}
                  fill={`hsl(${20 + i * 6}, 90%, ${65 - i * 2}%)`}
                />
              ))}
              <LabelList dataKey="skip" position="right" style={{ fill: "#fff", fontSize: 15 }} />
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

  return (
    <ChartCard title="Høyest skip-rate per spilleliste/album" color="#ff6b35">
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} layout="vertical" margin={{ left: 0, right: 16 }}>
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
          <Bar dataKey="rate" radius={[0, 4, 4, 0]}>
            {data.map((d, i) => (
              <Cell
                key={i}
                fill={d.rate >= 50 ? "#ff6b35" : "#1db954"}
                fillOpacity={0.85 - i * 0.05}
              />
            ))}
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

  return (
    <ChartCard title="Skip etter tidspunkt på døgnet" color="#9b59b6">
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ left: -16, right: 8 }}>
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

  return (
    <ChartCard title="Skip etter ukedag" color="#9b59b6">
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ left: -16, right: 8 }}>
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
    </ChartCard>
  );
}
