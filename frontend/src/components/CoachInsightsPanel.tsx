import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

// ---------------------------------------------------------------------------
// Sirkel-ikoner (SVG, ingen emojier)
// ---------------------------------------------------------------------------

function IconCalendar() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

function IconClock() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function IconList() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <line x1="8" y1="6" x2="21" y2="6" />
      <line x1="8" y1="12" x2="21" y2="12" />
      <line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" />
      <line x1="3" y1="12" x2="3.01" y2="12" />
      <line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Enkelt insight-kort
// ---------------------------------------------------------------------------

function InsightCard({
  icon,
  label,
  value,
  accentColor,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  accentColor: string;
}) {
  return (
    <div className="flex items-start gap-4 rounded-xl border border-[#2a2a2a] bg-[#141414] px-5 py-4 flex-1 min-w-0">
      {/* Sirkel-ikonboks */}
      <div
        className="flex items-center justify-center rounded-full shrink-0"
        style={{
          width: 36,
          height: 36,
          background: `${accentColor}18`,
          color: accentColor,
        }}
      >
        {icon}
      </div>

      {/* Tekst */}
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-widest text-[#555] mb-1">
          {label}
        </p>
        <p className="text-sm text-[#ccc] leading-snug">{value}</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hoved-panel
// ---------------------------------------------------------------------------

export function CoachInsightsPanel() {
  const { data } = useQuery({
    queryKey: ["coachInsights"],
    queryFn: api.coachInsights,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  if (!data) return null;

  const { top_skipped_hour, most_impatient_day, weekday_skip_rate, janitor_pending_count } = data;

  // Kort 1: Utålmodig ukedag
  const dayText =
    most_impatient_day && weekday_skip_rate != null
      ? `${most_impatient_day} er din mest utålmodige dag (${Math.round(weekday_skip_rate * 100)}% skip-rate)`
      : "Ikke nok data ennå";

  // Kort 2: Kritisk tidspunkt
  const hourText =
    top_skipped_hour != null
      ? `Du gjør flest skips rundt kl. ${top_skipped_hour}:00`
      : "Ikke nok data ennå";

  // Kort 3: Janitor-status
  const janitorText =
    janitor_pending_count > 0
      ? `${janitor_pending_count} sang${janitor_pending_count !== 1 ? "er" : ""} venter på å bli ryddet i Playlist Janitor`
      : "Ingen sanger venter i Playlist Janitor";

  return (
    <div className="mb-8">
      <p className="text-xs font-semibold uppercase tracking-widest text-[#444] mb-3">
        Musikkcoach
      </p>
      <div className="flex flex-col sm:flex-row gap-3">
        <InsightCard
          icon={<IconCalendar />}
          label="Utålmodig ukedag"
          value={dayText}
          accentColor="#1db954"
        />
        <InsightCard
          icon={<IconClock />}
          label="Kritisk tidspunkt"
          value={hourText}
          accentColor="#9b59b6"
        />
        <InsightCard
          icon={<IconList />}
          label="Janitor-status"
          value={janitorText}
          accentColor="#4a9eff"
        />
      </div>
    </div>
  );
}
