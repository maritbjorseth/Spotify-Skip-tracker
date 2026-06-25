import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { AlgorithmTooltip } from "./AlgorithmTooltip";

const SCORE_EXPLANATION =
  "Lytte-scoren viser hvor stor andel av musikken du faktisk hører ferdig, beregnet over de siste 30 dagene. " +
  "En score på 80 eller høyere betyr at du sjelden skipper. " +
  "Scoren oppdateres automatisk etter hvert som du lytter — " +
  "det er ingen «riktig» verdi, men en pekepinn på ditt nåværende lyttemønster.";

// ---------------------------------------------------------------------------
// Hjelpefunksjoner
// ---------------------------------------------------------------------------

function scoreColor(score: number): string {
  if (score > 80) return "#1db954";   // grønn
  if (score >= 50) return "#f59e0b";  // gul
  return "#ef4444";                   // rød
}

function scoreMessage(score: number): string {
  if (score >= 90) return "Fantastisk — du er en ekstremt tålmodig og dedikert lytter.";
  if (score >= 80) return "Veldig bra! Du hører musikken din til ende nesten alltid.";
  if (score >= 65) return "Ganske bra, men du skipper mer enn gjennomsnittet enkelte dager.";
  if (score >= 50) return "Du er midt på treet — litt kaotisk, men det finnes dager du er tålmodig.";
  if (score >= 35) return "Du skipper mye om dagen. Kanskje på tide med en Janitor-opprydding?";
  return "Høy skip-rate og lav konsistens — spillelistene dine kan trenge et grundig Janitor-gjennomgang.";
}

function scoreLabel(score: number): string {
  if (score > 80) return "Tålmodig lytter";
  if (score >= 50) return "Aktiv lytter";
  return "Utålmodig lytter";
}

// ---------------------------------------------------------------------------
// Sirkel-ikoner
// ---------------------------------------------------------------------------

function IconMusic() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 18V5l12-2v13" />
      <circle cx="6" cy="18" r="3" />
      <circle cx="18" cy="16" r="3" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Horisontal progress-bar
// ---------------------------------------------------------------------------

function ScoreBar({ score, color }: { score: number; color: string }) {
  return (
    <div className="w-full h-2 rounded-full bg-[#2a2a2a] overflow-hidden mt-4">
      <div
        className="h-full rounded-full transition-all duration-700"
        style={{
          width: `${score}%`,
          background: `linear-gradient(90deg, ${color}99, ${color})`,
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hoved-komponent
// ---------------------------------------------------------------------------

export function ListeningScorePanel() {
  const { data } = useQuery({
    queryKey: ["listeningScore"],
    queryFn: api.listeningScore,
    refetchInterval: 120_000,
    staleTime: 60_000,
  });

  if (!data) return null;

  const { score } = data;
  const color = scoreColor(score);

  return (
    <div className="rounded-xl border border-[#2a2a2a] bg-[#141414] px-6 py-5 mb-4">
      {/* Topp-rad: ikon + etikett + stor score */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className="flex items-center justify-center rounded-full shrink-0"
            style={{ width: 36, height: 36, background: `${color}18`, color }}
          >
            <IconMusic />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <p className="text-xs font-medium uppercase tracking-widest text-[#555]">
                Lytte-score
              </p>
              <AlgorithmTooltip text={SCORE_EXPLANATION} color={color} />
            </div>
            <p className="text-xs text-[#444] mt-0.5">{scoreLabel(score)}</p>
          </div>
        </div>

        {/* Score-tall */}
        <div className="text-right">
          <span
            className="text-4xl font-bold tabular-nums leading-none"
            style={{ color }}
          >
            {score}
          </span>
          <span className="text-lg text-[#444] font-normal ml-0.5">/100</span>
        </div>
      </div>

      {/* Progress-bar */}
      <ScoreBar score={score} color={color} />

      {/* Motiverende melding */}
      <p className="text-xs text-[#666] mt-3 leading-relaxed">
        {scoreMessage(score)}
      </p>
    </div>
  );
}
