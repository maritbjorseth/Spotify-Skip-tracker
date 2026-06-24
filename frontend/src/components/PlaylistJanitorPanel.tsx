import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { JanitorCandidate, JanitorCategory } from "../types";

// ---------------------------------------------------------------------------
// Kategori-konfigurasjon
// ---------------------------------------------------------------------------

const CATEGORY_CONFIG: Record<
  JanitorCategory,
  { label: string; dot: string; bg: string; fg: string; canRemove: boolean }
> = {
  Remove:    { label: "Fjern",     dot: "#ef4444", bg: "#ef444418", fg: "#ef4444", canRemove: true  },
  Candidate: { label: "Kandidat",  dot: "#f97316", bg: "#f9731618", fg: "#f97316", canRemove: true  },
  Watchlist: { label: "Overvåkes", dot: "#eab308", bg: "#eab30818", fg: "#eab308", canRemove: false },
  Keep:      { label: "Behold",    dot: "#1db954", bg: "#1db95418", fg: "#1db954", canRemove: false },
};

const TAB_ORDER: JanitorCategory[] = ["Remove", "Candidate", "Watchlist"];

// ---------------------------------------------------------------------------
// Skip-rate badge
// ---------------------------------------------------------------------------

function SkipRateBadge({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100);
  let bg: string;
  let fg: string;
  if (pct >= 90)      { bg = "#ef444422"; fg = "#ef4444"; }
  else if (pct >= 75) { bg = "#f9731622"; fg = "#f97316"; }
  else if (pct >= 60) { bg = "#eab30822"; fg = "#eab308"; }
  else                { bg = "#1db95422"; fg = "#1db954"; }
  return (
    <span
      className="inline-block rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums"
      style={{ background: bg, color: fg }}
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
}: {
  candidate: JanitorCandidate;
  onRemove: (playlistId: string, trackUri: string) => void;
  isRemoving: boolean;
}) {
  const cfg = CATEGORY_CONFIG[candidate.category];

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
          className="text-xs text-[#666] truncate mt-0.5"
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

      {/* Fjern-knapp — kun for Remove og Candidate */}
      {cfg.canRemove ? (
        <button
          type="button"
          disabled={isRemoving}
          onClick={() => {
            if (window.confirm("Fjerne sangen permanent fra spillelisten?")) {
              onRemove(candidate.playlist_id, candidate.uri);
            }
          }}
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
          {isRemoving ? "…" : "Fjern"}
        </button>
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
}: {
  name: string;
  candidates: JanitorCandidate[];
  onRemove: (playlistId: string, trackUri: string) => void;
  removingUri: string | null;
}) {
  return (
    <div className="mb-2 last:mb-0">
      <div className="flex items-center gap-2 px-4 py-2 bg-[#161616] border-b border-[#252525]">
        <svg className="h-3.5 w-3.5 text-[#444] flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"
          />
        </svg>
        <span className="text-xs font-semibold text-[#777] uppercase tracking-wider truncate">
          {name}
        </span>
        <span className="ml-auto text-xs text-[#444] flex-shrink-0">
          {candidates.length}
        </span>
      </div>
      {candidates.map((c) => (
        <TrackRow
          key={c.uri + c.playlist_id}
          candidate={c}
          onRemove={onRemove}
          isRemoving={removingUri === c.uri}
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
}: {
  candidates: JanitorCandidate[];
  onRemove: (playlistId: string, trackUri: string) => void;
  removingUri: string | null;
}) {
  if (candidates.length === 0) {
    return (
      <div className="py-10 text-center">
        <p className="text-sm text-[#444]">Ingen sanger i denne kategorien.</p>
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
        <span className="flex-1 text-xs font-semibold text-[#444] uppercase tracking-wider">Sang / artist</span>
        <span className="flex-shrink-0 w-12 text-xs font-semibold text-[#444] uppercase tracking-wider text-center hidden sm:block">Skip%</span>
        <span className="flex-shrink-0 w-24 text-xs font-semibold text-[#444] uppercase tracking-wider text-right">Score</span>
        <span className="flex-shrink-0 w-[72px]" />
      </div>
      {[...grouped.entries()].map(([name, cands]) => (
        <PlaylistGroup
          key={name}
          name={name}
          candidates={cands}
          onRemove={onRemove}
          removingUri={removingUri}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hoved-panel
// ---------------------------------------------------------------------------

export function PlaylistJanitorPanel() {
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
    ? new Date(dataUpdatedAt).toLocaleTimeString("nb-NO", { hour: "2-digit", minute: "2-digit" })
    : null;

  const removingUri = mutation.isPending ? (mutation.variables?.trackUri ?? null) : null;

  return (
    <section className="mb-8">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="text-base font-semibold text-[#a78bfa]">Playlist Janitor</h2>
          <p className="text-xs text-[#555] mt-0.5">
            Sanger du konsekvent hopper over — kategorisert etter risiko.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && <span className="text-xs text-[#555]">Oppdatert {lastUpdated}</span>}
          {data && data.length > 0 && (
            <span
              className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold"
              style={{ background: "#ef444418", color: "#ef4444" }}
            >
              <span className="inline-block rounded-full" style={{ width: 7, height: 7, background: "#ef4444" }} />
              {byCategory.Remove.length + byCategory.Candidate.length} handlingsklare
            </span>
          )}
        </div>
      </div>

      {/* Laster */}
      {isLoading && (
        <p className="text-sm text-[#555] py-6 text-center">Analyserer spillelister…</p>
      )}

      {/* Feil */}
      {isError && (
        <div className="rounded-xl border border-red-900/40 bg-red-900/10 p-4 text-red-400 text-sm">
          Kunne ikke hente Playlist Janitor-data. Kjør analysen via CLI:&nbsp;
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
          <p className="text-sm text-[#555]">Ingen kandidater funnet.</p>
          <p className="text-xs text-[#444] mt-1">
            Kjør{" "}
            <code className="rounded bg-[#1c1c1c] px-1.5 py-0.5 text-[#888]">
              python3 -m spotify_skip_tracker janitor
            </code>{" "}
            for å analysere spillelistene dine.
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
                    color: isActive ? cfg.fg : "#555",
                    borderBottom: isActive ? `2px solid ${cfg.dot}` : "2px solid transparent",
                    background: isActive ? cfg.bg : "transparent",
                  }}
                >
                  <svg width="8" height="8" viewBox="0 0 8 8" fill="none" aria-hidden="true" className="flex-shrink-0">
                    <circle cx="4" cy="4" r="4" fill={cfg.dot} />
                  </svg>
                  <span>{cfg.label}</span>
                  {count > 0 && (
                    <span
                      className="rounded-full px-1.5 py-0.5 text-[10px] font-bold tabular-nums"
                      style={{
                        background: isActive ? cfg.dot + "33" : "#2a2a2a",
                        color: isActive ? cfg.fg : "#555",
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
            category={activeTab}
            candidates={byCategory[activeTab]}
            onRemove={(playlistId, trackUri) => mutation.mutate({ playlistId, trackUri })}
            removingUri={removingUri}
          />
        </div>
      )}
    </section>
  );
}
