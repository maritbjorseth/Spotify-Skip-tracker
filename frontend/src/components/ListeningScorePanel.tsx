import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { AlgorithmTooltip } from "./AlgorithmTooltip";

function scoreColor(score: number): string {
  if (score > 80) return "#1db954";
  if (score >= 50) return "#f59e0b";
  return "#ef4444";
}

function IconMusic() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 18V5l12-2v13" />
      <circle cx="6" cy="18" r="3" />
      <circle cx="18" cy="16" r="3" />
    </svg>
  );
}

function ScoreBar({ score, color }: { score: number; color: string }) {
  return (
    <div className="w-full h-2 rounded-full bg-[#2a2a2a] overflow-hidden mt-4">
      <div
        className="h-full rounded-full transition-all duration-700"
        style={{ width: `${score}%`, background: `linear-gradient(90deg, ${color}99, ${color})` }}
      />
    </div>
  );
}

export function ListeningScorePanel() {
  const { t } = useTranslation();
  const { data } = useQuery({
    queryKey: ["listeningScore"],
    queryFn: api.listeningScore,
    refetchInterval: 120_000,
    staleTime: 60_000,
  });

  if (!data) return null;

  const { score } = data;
  const color = scoreColor(score);

  function scoreMessage(s: number): string {
    if (s >= 90) return t("listeningScore.scoreMessage.s90");
    if (s >= 80) return t("listeningScore.scoreMessage.s80");
    if (s >= 65) return t("listeningScore.scoreMessage.s65");
    if (s >= 50) return t("listeningScore.scoreMessage.s50");
    if (s >= 35) return t("listeningScore.scoreMessage.s35");
    return t("listeningScore.scoreMessage.s0");
  }

  function scoreLabel(s: number): string {
    if (s > 80) return t("listeningScore.scoreLabel.patient");
    if (s >= 50) return t("listeningScore.scoreLabel.active");
    return t("listeningScore.scoreLabel.impatient");
  }

  return (
    <div className="rounded-xl border border-[#2a2a2a] bg-[#141414] px-6 py-5 mb-4">
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
              <p className="text-xs font-medium uppercase tracking-widest text-[#888]">
                {t("listeningScore.label")}
              </p>
              <AlgorithmTooltip text={t("listeningScore.explanation")} color={color} />
            </div>
            <p className="text-xs text-[#777] mt-0.5">{scoreLabel(score)}</p>
          </div>
        </div>
        <div className="text-right">
          <span className="text-4xl font-bold tabular-nums leading-none" style={{ color }}>
            {score}
          </span>
          <span className="text-lg text-[#777] font-normal ml-0.5">{t("listeningScore.suffix")}</span>
        </div>
      </div>
      <ScoreBar score={score} color={color} />
      <p className="text-xs text-[#888] mt-3 leading-relaxed">{scoreMessage(score)}</p>
    </div>
  );
}
