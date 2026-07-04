import type { ReactNode } from "react";
import { useEffect, useRef } from "react";
import { motion, useMotionValue, useTransform, animate } from "framer-motion";
import { useTranslation } from "react-i18next";
import { Info } from "lucide-react";
import { skipRateColor } from "../theme";

// ---------------------------------------------------------------------------
// Inline SVG-ikoner – tynne streker, strokeWidth 1.5, ingen fill
// ---------------------------------------------------------------------------

function IconSkipForward({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {/* Fremre trekant */}
      <polygon points="5 4 15 12 5 20 5 4" />
      {/* Loddrett strek (slutten av sporet) */}
      <line x1="19" y1="5" x2="19" y2="19" />
    </svg>
  );
}

function IconTrendingUp({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
      <polyline points="16 7 22 7 22 13" />
    </svg>
  );
}

function IconMusicNote({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {/* Strek ned + bue øverst */}
      <path d="M9 18V5l12-2v13" />
      {/* Notehodet */}
      <circle cx="6" cy="18" r="3" />
      <circle cx="18" cy="16" r="3" />
    </svg>
  );
}

function IconDisc({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {/* Ytre sirkel */}
      <circle cx="12" cy="12" r="10" />
      {/* Indre hull */}
      <circle cx="12" cy="12" r="3" />
      {/* To dekorative buer for vinyl-riller */}
      <path d="M12 2a10 10 0 0 1 7.07 2.93" strokeOpacity={0.35} />
      <path d="M2 12a10 10 0 0 1 2.93-7.07" strokeOpacity={0.35} />
    </svg>
  );
}

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
  icon: ReactNode;
  tooltip?: string;
}

export function StatCard({ label, value, format, color = "#1db954", icon, tooltip }: StatCardProps) {
  const { i18n } = useTranslation();
  const fmt = format ?? ((n: number) => n.toLocaleString(i18n.language));

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className="flex-1 min-w-40 rounded-xl border border-[#2a2a2a] bg-[#181818] p-5"
    >
      {/* Øverste rad: etikett til venstre, ikon til høyre */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-medium uppercase tracking-wider text-[#888] flex items-center gap-1">
          {label}
          {tooltip && (
            <span
              title={tooltip}
              className="inline-flex items-center text-[#666] hover:text-[#999] cursor-help transition-colors"
            >
              <Info size={11} strokeWidth={1.8} />
            </span>
          )}
        </span>
        {icon}
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
  const { t } = useTranslation();
  const skipRate = totalPlays > 0 ? Math.round((totalSkips / totalPlays) * 100) : 0;
  const rateColor = skipRateColor(skipRate, totalPlays);

  return (
    <div className="flex gap-4 flex-wrap mb-6">
      <StatCard
        icon={<IconSkipForward className="w-5 h-5 text-[#6b7280]" />}
        label={t("statCards.totalSkipped")}
        value={totalSkips}
        color="#eeeeee"
        tooltip={t("statCards.totalSkippedTooltip")}
      />
      <StatCard
        icon={<span style={{ color: rateColor }}><IconTrendingUp className="w-5 h-5" /></span>}
        label={t("statCards.skipRate")}
        value={skipRate}
        format={(n) => `${n}%`}
        color={rateColor}
        tooltip={t("statCards.skipRateTooltip")}
      />
      <StatCard
        icon={<IconMusicNote className="w-5 h-5 text-green-500/70" />}
        label={t("statCards.playsLogged")}
        value={totalPlays}
        color="#1db954"
        tooltip={t("statCards.playsLoggedTooltip")}
      />
      <StatCard
        icon={<IconDisc className="w-5 h-5 text-blue-500/70" />}
        label={t("statCards.uniqueSkipped")}
        value={uniqueTracks}
        color="#4a9eff"
        tooltip={t("statCards.uniqueSkippedTooltip")}
      />
    </div>
  );
}
