import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import type { JanitorCandidate, JanitorCategory } from "../types";
import { AlgorithmTooltip } from "./AlgorithmTooltip";
import { skipRateColor } from "../theme";

// ---------------------------------------------------------------------------
// Kategori-konfigurasjon (statiske farger, labels hentes via i18n)
// ---------------------------------------------------------------------------

const CATEGORY_CONFIG: Record<
  JanitorCategory,
  { labelKey: string; dot: string; bg: string; fg: string; canRemove: boolean }
> = {
  Remove:    { labelKey: "playlistJanitor.categoryRemove",    dot: "#ef4444", bg: "#ef444418", fg: "#ef4444", canRemove: true  },
  Candidate: { labelKey: "playlistJanitor.categoryCandidate", dot: "#f97316", bg: "#f9731618", fg: "#f97316", canRemove: true  },
  Watchlist: { labelKey: "playlistJanitor.categoryWatchlist", dot: "#eab308", bg: "#eab30818", fg: "#eab308", canRemove: false },
  Keep:      { labelKey: "playlistJanitor.categoryKeep",      dot: "#1db954", bg: "#1db95418", fg: "#1db954", canRemove: false },
};

const TAB_ORDER: JanitorCategory[] = ["Remove", "Candidate", "Watchlist"];

// ---------------------------------------------------------------------------
// Skip-rate badge
// ---------------------------------------------------------------------------

function SkipRateBadge({ rate }: { rate: number }) {
  const { t } = useTranslation();
  const pct = Math.round(rate * 100);
  const fg  = skipRateColor(pct);

  let label: string;
  if (pct >= 50) label = t("playlistJanitor.skipRateHigh");
  else if (pct >= 25) label = t("playlistJanitor.skipRateMedium");
  else label = t("playlistJanitor.skipRateLow");

  return (
    <span
      className="inline-block rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums"
      style={{ background: fg + "22", color: fg }}
      title={`${pct}% — ${label}`}
    >
      {pct}%
    </span>
  );
}

// ---------------------------------------------------------------------------
// Score-bar
// ---------------------------------------------------------------------------

function ScoreBar({ score, category }: { score: number; category: JanitorCategory }) {
  const pct = Math.round(score * 100);
  const color = CATEGORY_CONFIG[category].dot;
  return (
    <div className="flex items-center gap-2 justify-end">
      <div className="w-14 h-1.5 rounded-full bg-[#2a2a2a] overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span
        className="text-xs font-semibold tabular-nums w-8 text-right"
        style={{ color }}
      >
        {score.toFixed(2)}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Confidence-merkelapp
// ---------------------------------------------------------------------------

function ConfidenceBadge({ label }: { label: string }) {
  return (
    <span className="inline-block rounded px-1.5 py-0.5 text-[10px] font-medium bg-[#232323] text-[#666] leading-none whitespace-nowrap">
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Enkelt spor-rad
// ---------------------------------------------------------------------------

function TrackRow({
  candidate,
  onRemove,
  isRemoving,
  isDemo,
}: {
  candidate: JanitorCandidate;
  onRemove: (playlistId: string, trackUri: string) => void;
  isRemoving: boolean;
  isDemo: boolean;
}) {
  const { t } = useTranslation();
  const cfg = CATEGORY_CONFIG[candidate.category];
  const [confirming, setConfirming] = useState(false);

  const handleRemoveClick = useCallback(() => setConfirming(true), []);
  const handleCancel      = useCallback(() => setConfirming(false), []);
  const handleConfirm     = useCallback(() => {
    setConfirming(false);
    onRemove(candidate.playlist_id, candidate.uri);
  }, [candidate.playlist_id, candidate.uri, onRemove]);

  return (
    <div className="flex items-center gap-3 px-4 py-3.5 border-b border-[#1e1e1e] last:border-b-0 hover:bg-white/[0.02] transition-colors">
      {/* Tittel + artist + confidence */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <p
            className="text-sm font-medium text-[#ddd] truncate"
            title={candidate.title}
          >
            {candidate.title || "—"}
          </p>
          <ConfidenceBadge label={candidate.confidence_level} />
        </div>
        <p
          className="text-xs text-[#888] truncate mt-0.5"
          title={candidate.artists}
        >
          {candidate.artists || "—"}
        </p>
      </div>

      {/* Skip-rate */}
      <div className="flex-shrink-0 hidden sm:block">
        <SkipRateBadge rate={candidate.skip_rate} />
      </div>

      {/* Score-bar */}
      <div className="flex-shrink-0 w-24 hidden md:block">
        <ScoreBar score={candidate.janitor_score} category={candidate.category} />
      </div>

      {/* Fjern-knapp — kun for Remove og Candidate; skjult i demo-modus */}
      {cfg.canRemove ? (
        isDemo ? (
          <span
            className="flex-shrink-0 text-xs text-[#555] w-[72px] text-right"
            title={t("playlistJanitor.demoDisabled")}
          >
            {t("playlistJanitor.demoDisabled")}
          </span>
        ) : confirming ? (
          /* Inline bekreftelse — erstatter window.confirm() */
          <div className="flex-shrink-0 flex items-center gap-1.5">
            <button
              type="button"
              onClick={handleConfirm}
              disabled={isRemoving}
              className="rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-all duration-150
                border border-red-700/70 bg-red-900/25 text-red-300
                hover:bg-red-900/40 active:scale-95 disabled:opacity-40"
            >
              {isRemoving ? "…" : t("playlistJanitor.confirm")}
            </button>
            <button
              type="button"
              onClick={handleCancel}
              className="rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-all duration-150
                border border-[#333] bg-[#1c1c1c] text-[#888]
                hover:border-[#555] hover:text-[#bbb] active:scale-95"
            >
              {t("playlistJanitor.cancel")}
            </button>
          </div>
        ) : (
          <button
            type="button"
            disabled={isRemoving}
            onClick={handleRemoveClick}
            className="flex-shrink-0 flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all duration-150
              border border-red-900/50 bg-red-900/10 text-red-400
              hover:bg-red-900/25 hover:border-red-700/70 hover:text-red-300
              active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
            {isRemoving ? "…" : t("playlistJanitor.remove")}
          </button>
        )
      ) : (
        <div className="flex-shrink-0 w-[72px]" />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Spilleliste-gruppe innen en fane
// ---------------------------------------------------------------------------

function PlaylistGroup({
  name,
  candidates,
  onRemove,
  removingUri,
  isDemo,
}: {
  name: string;
  candidates: JanitorCandidate[];
  onRemove: (playlistId: string, trackUri: string) => void;
  removingUri: string | null;
  isDemo: boolean;
}) {
  return (
    <div className="mb-2 last:mb-0">
      <div className="flex items-center gap-2 px-4 py-2 bg-[#161616] border-b border-[#252525]">
        <svg className="h-3.5 w-3.5 text-[#666] flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"
          />
        </svg>
        <span className="text-xs font-semibold text-[#777] uppercase tracking-wider truncate">
          {name}
        </span>
        <span className="ml-auto text-xs text-[#777] flex-shrink-0">
          {candidates.length}
        </span>
      </div>
      {candidates.map((c) => (
        <TrackRow
          key={c.uri + c.playlist_id}
          candidate={c}
          onRemove={onRemove}
          isRemoving={removingUri === c.uri}
          isDemo={isDemo}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Fane-innhold
// ---------------------------------------------------------------------------

function TabContent({
  candidates,
  onRemove,
  removingUri,
  isDemo,
}: {
  candidates: JanitorCandidate[];
  onRemove: (playlistId: string, trackUri: string) => void;
  removingUri: string | null;
  isDemo: boolean;
}) {
  const { t } = useTranslation();

  if (candidates.length === 0) {
    return (
      <div className="py-10 text-center">
        <p className="text-sm text-[#777]">{t("playlistJanitor.tabEmpty")}</p>
      </div>
    );
  }

  // Grupper per spilleliste
  const grouped = new Map<string, JanitorCandidate[]>();
  for (const c of candidates) {
    const key = c.playlist_name || c.playlist_id;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(c);
  }

  return (
    <div>
      {/* Kolonne-header */}
      <div className="hidden md:flex items-center gap-3 px-4 py-2.5 bg-[#111] border-b border-[#252525]">
        <span className="flex-1 text-xs font-semibold text-[#888] uppercase tracking-wider">{t("playlistJanitor.columns.songArtist")}</span>
        <span className="flex-shrink-0 w-12 text-xs font-semibold text-[#888] uppercase tracking-wider text-center hidden sm:block">{t("playlistJanitor.columns.skipPct")}</span>
        <span className="flex-shrink-0 w-24 text-xs font-semibold text-[#888] uppercase tracking-wider text-right">{t("playlistJanitor.columns.score")}</span>
        <span className="flex-shrink-0 w-[72px]" />
      </div>
      {[...grouped.entries()].map(([name, cands]) => (
        <PlaylistGroup
          key={name}
          name={name}
          candidates={cands}
          onRemove={onRemove}
          removingUri={removingUri}
          isDemo={isDemo}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hoved-panel
// ---------------------------------------------------------------------------

export function PlaylistJanitorPanel({ isDemo = false }: { isDemo?: boolean }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<JanitorCategory>("Remove");

  const { data, isLoading, isError, dataUpdatedAt } = useQuery({
    queryKey: ["janitorCandidates"],
    queryFn: api.janitorCandidates,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const mutation = useMutation({
    mutationFn: ({ playlistId, trackUri }: { playlistId: string; trackUri: string }) =>
      api.removeJanitorCandidate(playlistId, trackUri),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["janitorCandidates"] });
    },
  });

  const byCategory = TAB_ORDER.reduce<Record<string, JanitorCandidate[]>>(
    (acc, cat) => {
      acc[cat] = (data ?? [])
        .filter((c) => c.category === cat)
        .sort((a, b) => b.janitor_score - a.janitor_score);
      return acc;
    },
    { Remove: [], Candidate: [], Watchlist: [] },
  );

  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString(i18n.language === "en" ? "en-GB" : "nb-NO", { hour: "2-digit", minute: "2-digit" })
    : null;

  const removingUri = mutation.isPending ? (mutation.variables?.trackUri ?? null) : null;

  return (
    <section className="mb-8">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-[#a78bfa]">{t("playlistJanitor.heading")}</h2>
            <AlgorithmTooltip text={t("playlistJanitor.explanation")} color="#a78bfa" />
          </div>
          <p className="text-xs text-[#888] mt-0.5">
            {t("playlistJanitor.subtitle")}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-[#888]">
              {t("playlistJanitor.lastUpdated", { time: lastUpdated })}
            </span>
          )}
          {data && data.length > 0 && (
            <span
              className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold"
              style={{ background: "#ef444418", color: "#ef4444" }}
            >
              <span className="inline-block rounded-full" style={{ width: 7, height: 7, background: "#ef4444" }} />
              {t("playlistJanitor.actionable", { n: byCategory.Remove.length + byCategory.Candidate.length })}
            </span>
          )}
        </div>
      </div>

      {/* Laster */}
      {isLoading && (
        <p className="text-sm text-[#888] py-6 text-center">{t("playlistJanitor.loading")}</p>
      )}

      {/* Feil */}
      {isError && (
        <div className="rounded-xl border border-red-900/40 bg-red-900/10 p-4 text-red-400 text-sm">
          {t("playlistJanitor.error")}&nbsp;
          <code className="rounded bg-[#1c1c1c] px-1.5 py-0.5 text-[#888]">
            python3 -m spotify_skip_tracker janitor
          </code>
        </div>
      )}

      {/* Tom tilstand */}
      {data && data.length === 0 && (
        <div className="rounded-xl border border-[#2a2a2a] bg-[#161616] p-8 text-center">
          <svg className="h-8 w-8 mx-auto mb-3 text-[#333]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm text-[#888]">{t("playlistJanitor.emptyHeading")}</p>
          <p className="text-xs text-[#777] mt-1">
            {t("playlistJanitor.emptyCLIHint")}{" "}
            <code className="rounded bg-[#1c1c1c] px-1.5 py-0.5 text-[#888]">
              python3 -m spotify_skip_tracker janitor
            </code>
          </p>
        </div>
      )}

      {/* Fane-visning */}
      {data && data.length > 0 && (
        <div className="rounded-xl border border-[#2a2a2a] bg-[#1c1c1c] overflow-hidden">
          {/* Fane-rad */}
          <div className="flex border-b border-[#2a2a2a] overflow-x-auto">
            {TAB_ORDER.map((cat) => {
              const cfg = CATEGORY_CONFIG[cat];
              const count = byCategory[cat].length;
              const isActive = activeTab === cat;
              return (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setActiveTab(cat)}
                  className="flex items-center gap-2 px-4 py-3 text-xs font-semibold whitespace-nowrap transition-colors flex-shrink-0"
                  style={{
                    color: isActive ? cfg.fg : "#888",
                    borderBottom: isActive ? `2px solid ${cfg.dot}` : "2px solid transparent",
                    background: isActive ? cfg.bg : "transparent",
                  }}
                >
                  <svg width="8" height="8" viewBox="0 0 8 8" fill="none" aria-hidden="true" className="flex-shrink-0">
                    <circle cx="4" cy="4" r="4" fill={cfg.dot} />
                  </svg>
                  <span>{t(cfg.labelKey as Parameters<typeof t>[0])}</span>
                  {count > 0 && (
                    <span
                      className="rounded-full px-1.5 py-0.5 text-[10px] font-bold tabular-nums"
                      style={{
                        background: isActive ? cfg.dot + "33" : "#2a2a2a",
                        color: isActive ? cfg.fg : "#888",
                      }}
                    >
                      {count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Fane-innhold */}
          <TabContent
            candidates={byCategory[activeTab]}
            onRemove={(playlistId, trackUri) => mutation.mutate({ playlistId, trackUri })}
            removingUri={removingUri}
            isDemo={isDemo}
          />
        </div>
      )}
    </section>
  );
}
