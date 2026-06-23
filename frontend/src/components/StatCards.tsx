import { useEffect, useRef } from "react";
import { motion, useMotionValue, useTransform, animate } from "framer-motion";

// ---------------------------------------------------------------------------
// Animert teller
// ---------------------------------------------------------------------------

function AnimatedNumber({
  value,
  format,
}: {
  value: number;
  format: (n: number) => string;
}) {
  const mv = useMotionValue(0);
  const display = useTransform(mv, (v) => format(Math.round(v)));
  const prevRef = useRef(0);

  useEffect(() => {
    const ctrl = animate(prevRef.current, value, {
      duration: 1.2,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => mv.set(v),
    });
    prevRef.current = value;
    return () => ctrl.stop();
  }, [value, mv]);

  return <motion.span>{display}</motion.span>;
}

// ---------------------------------------------------------------------------
// Enkelt KPI-kort
// ---------------------------------------------------------------------------

interface StatCardProps {
  label: string;
  value: number;
  format?: (n: number) => string;
  color?: string;
  icon: string;
}

export function StatCard({ label, value, format, color = "#1db954", icon }: StatCardProps) {
  const fmt = format ?? ((n: number) => n.toLocaleString("nb-NO"));

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className="flex-1 min-w-40 rounded-xl border border-[#2a2a2a] bg-[#181818] p-5"
    >
      {/* Øverste rad: etikett til venstre, ikon til høyre */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-medium uppercase tracking-wider text-[#666]">
          {label}
        </span>
        <span className="text-2xl leading-none">{icon}</span>
      </div>

      {/* Stor verdi */}
      <div className="text-3xl font-bold tabular-nums" style={{ color }}>
        <AnimatedNumber value={value} format={fmt} />
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Rad med alle fire KPI-kortene
// ---------------------------------------------------------------------------

export function StatCardsRow({
  totalSkips,
  totalPlays,
  uniqueTracks,
}: {
  totalSkips: number;
  totalPlays: number;
  uniqueTracks: number;
}) {
  const skipRate = totalPlays > 0 ? Math.round((totalSkips / totalPlays) * 100) : 0;
  const rateColor = skipRate >= 50 ? "#ff6b35" : "#1db954";

  return (
    <div className="flex gap-4 flex-wrap mb-10">
      <StatCard icon="⏩" label="Totalt skippet" value={totalSkips} color="#ff6b35" />
      <StatCard icon="📈" label="Skip-rate" value={skipRate} format={(n) => `${n}%`} color={rateColor} />
      <StatCard icon="🎵" label="Avspillinger logget" value={totalPlays} color="#1db954" />
      <StatCard icon="🎶" label="Unike sanger skippet" value={uniqueTracks} color="#4a9eff" />
    </div>
  );
}
