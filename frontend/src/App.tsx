import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "./api";
import { NowPlaying } from "./components/NowPlaying";
import { StatCardsRow } from "./components/StatCards";
import { SkipHeatmap } from "./components/SkipHeatmap";
import { SkippedTable, MostCompletedTable, AutoSkipPreviewTable } from "./components/Tables";
import { SmartSkipperPanel } from "./components/SmartSkipperPanel";
import { PlaylistJanitorPanel } from "./components/PlaylistJanitorPanel";
import { CoachInsightsPanel } from "./components/CoachInsightsPanel";
import { ListeningScorePanel } from "./components/ListeningScorePanel";
import { LoginScreen } from "./components/LoginScreen";
import { LanguageSelector } from "./components/LanguageSelector";
import { ArtistChart, ContextChart, HourlyChart, WeekdayRateChart } from "./components/Charts";
import { SkipTrendChart } from "./components/SkipTrendChart";
import { useSectionVisibility, SectionToggle } from "./components/SectionToggle";

function SectionDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-4 mb-5 mt-10">
      <div className="h-px flex-1 bg-[#2a2a2a]" />
      <span className="text-sm font-semibold uppercase tracking-widest text-[#888]">{label}</span>
      <div className="h-px flex-1 bg-[#2a2a2a]" />
    </div>
  );
}

function EmptyDashboard() {
  const { t } = useTranslation();
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="rounded-xl border border-[#2a2a2a] bg-[#141414] px-8 py-12 text-center max-w-lg mx-auto mt-8"
    >
      <div
        className="inline-flex items-center justify-center rounded-full mb-6"
        style={{ width: 56, height: 56, background: "#1db95418", color: "#1db954" }}
      >
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M9 18V5l12-2v13" />
          <circle cx="6" cy="18" r="3" />
          <circle cx="18" cy="16" r="3" />
        </svg>
      </div>

      <h2 className="text-lg font-semibold text-[#eee] mb-2">
        {t("app.empty.heading")}
      </h2>
      <p className="text-sm text-[#888] leading-relaxed mb-6">
        {t("app.empty.description")}
      </p>

      <div className="flex flex-col gap-3 text-left">
        {([1, 2, 3] as const).map((n) => (
          <div key={n} className="flex items-start gap-3 rounded-lg bg-[#1c1c1c] px-4 py-3">
            <span className="text-[#1db954] font-bold text-sm mt-0.5 shrink-0">{n}</span>
            <p className="text-xs text-[#888] leading-relaxed">
              {t(`app.empty.step${n}` as const)}
            </p>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

function LogoutButton({ onLogout }: { onLogout: () => void }) {
  const { t } = useTranslation();
  return (
    <button
      onClick={onLogout}
      className="rounded-lg border border-[#2a2a2a] bg-[#181818] px-3 py-1.5 text-xs text-[#666] transition-all duration-150 hover:border-[#444] hover:text-[#aaa]"
    >
      {t("app.logout")}
    </button>
  );
}

export default function App() {
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  const { data: authData, isLoading: authLoading } = useQuery({
    queryKey: ["authStatus"],
    queryFn: api.authStatus,
    retry: 1,
    staleTime: 5 * 60_000,
    refetchInterval: 10 * 60_000,
  });

  const logoutMutation = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["authStatus"] });
    },
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ["stats"],
    queryFn: api.stats,
    refetchInterval: 10_000,
    staleTime: 5_000,
    enabled: authData?.authenticated === true,
  });

  const { data: scoreData } = useQuery({
    queryKey: ["listeningScore"],
    queryFn: api.listeningScore,
    staleTime: 60_000,
    enabled: authData?.authenticated === true,
  });

  const { visible, toggle } = useSectionVisibility();
  const hasGraphs = ["artistChart", "contextChart", "hourChart", "weekdayRateChart"].some((id) => visible[id]);
  const hasMore = visible.mostCompleted;

  if (authLoading) {
    return (
      <div className="min-h-screen bg-[#0d0d0d] flex items-center justify-center">
        <div className="w-5 h-5 rounded-full border-2 border-[#1db954] border-t-transparent animate-spin" />
      </div>
    );
  }

  if (!authData?.authenticated) {
    return <LoginScreen />;
  }

  return (
    <div className="min-h-screen bg-[#0d0d0d] text-[#eee]">
      <div className="max-w-6xl mx-auto px-6 py-6">

        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="mb-5 flex items-start justify-between"
        >
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-[#1db954]">
              {t("app.header.title")}
            </h1>
            <p className="text-sm text-[#888] mt-1">
              {t("app.header.subtitle")}
            </p>
            <span className="text-xs text-neutral-500 mt-1 block">
              {t("app.header.lastUpdated")}{" "}
              {new Date().toLocaleDateString(undefined, {
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <LanguageSelector />
            <LogoutButton onLogout={() => logoutMutation.mutate()} />
            <SectionToggle visible={visible} onToggle={toggle} />
          </div>
        </motion.div>

        <NowPlaying />

        {isLoading && (
          <div className="flex items-center justify-center py-24 text-[#888] text-sm">
            {t("app.loading")}
          </div>
        )}
        {error && (
          <div className="rounded-xl border border-red-900/40 bg-red-900/10 p-6 text-red-400 text-sm">
            {t("app.error")}
          </div>
        )}

        {data && data.total_plays === 0 && <EmptyDashboard />}

        {data && data.total_plays > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4, delay: 0.1 }}
          >
            <StatCardsRow
              totalSkips={data.total_skips}
              totalPlays={data.total_plays}
              uniqueTracks={data.unique_tracks}
            />

            {visible.heatmap && (
              <div className="mb-4">
                <SkipHeatmap daily={data.daily} />
              </div>
            )}

            {visible.trendChart && (
              <SkipTrendChart daily={data.daily} />
            )}

            {visible.skipped && (
              <div className="mb-4">
                <SkippedTable
                  tracks={data.tracks}
                  playlistContexts={data.playlist_contexts ?? data.contexts ?? []}
                  albumContexts={data.album_contexts ?? []}
                />
              </div>
            )}

            {hasGraphs && <SectionDivider label={t("app.sections.charts")} />}

            <AnimatePresence mode="sync">
              {(visible.artistChart || visible.contextChart || visible.hourChart || visible.weekdayRateChart) && (
                <motion.div
                  key="graphs"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6"
                >
                  {visible.artistChart && <ArtistChart artists={data.top_artists} />}
                  {visible.contextChart && (
                    <ContextChart
                      contexts={data.top_contexts}
                      playlistContexts={data.playlist_contexts ?? []}
                      albumContexts={data.album_contexts ?? []}
                      tracks={data.tracks}
                    />
                  )}
                  {visible.hourChart && <HourlyChart hourly={data.hourly} />}
                  {visible.weekdayRateChart && <WeekdayRateChart weekday={data.weekday} />}
                </motion.div>
              )}
            </AnimatePresence>

            {hasMore && <SectionDivider label={t("app.sections.more")} />}

            {visible.mostCompleted && (
              <div className="mb-6">
                <MostCompletedTable tracks={data.most_completed} />
              </div>
            )}

            {scoreData && (
              <>
                <SectionDivider label={t("app.sections.coach")} />
                <ListeningScorePanel />
                <CoachInsightsPanel />
              </>
            )}

            <SectionDivider label={t("app.sections.smartSkipper")} />
            <SmartSkipperPanel />
            <AutoSkipPreviewTable
              candidates={data.auto_skip_candidates ?? []}
              threshold={data.smart_skipper_threshold ?? 0.85}
            />

            {visible.playlistJanitor && (
              <>
                <SectionDivider label={t("app.sections.janitor")} />
                <PlaylistJanitorPanel />
              </>
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
}
