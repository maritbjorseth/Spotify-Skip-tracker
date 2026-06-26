import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
import { ArtistChart, ContextChart, HourlyChart, WeekdayRateChart } from "./components/Charts";
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
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="rounded-xl border border-[#2a2a2a] bg-[#141414] px-8 py-12 text-center max-w-lg mx-auto mt-8"
    >
      {/* Ikon */}
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
        Trackeren er klar
      </h2>
      <p className="text-sm text-[#888] leading-relaxed mb-6">
        Ingen avspillinger er logget ennå. Sett på musikk i Spotify — trackeren
        registrerer automatisk hva du hører på og hva du hopper over.
        Data vises her etter første lyttesesjon.
      </p>

      <div className="flex flex-col gap-3 text-left">
        <div className="flex items-start gap-3 rounded-lg bg-[#1c1c1c] px-4 py-3">
          <span className="text-[#1db954] font-bold text-sm mt-0.5 shrink-0">1</span>
          <p className="text-xs text-[#888] leading-relaxed">
            Spill en sang i Spotify — på hvilken som helst enhet.
          </p>
        </div>
        <div className="flex items-start gap-3 rounded-lg bg-[#1c1c1c] px-4 py-3">
          <span className="text-[#1db954] font-bold text-sm mt-0.5 shrink-0">2</span>
          <p className="text-xs text-[#888] leading-relaxed">
            Hopp over sangen før den er ferdig — trackeren oppdager skipet automatisk.
          </p>
        </div>
        <div className="flex items-start gap-3 rounded-lg bg-[#1c1c1c] px-4 py-3">
          <span className="text-[#1db954] font-bold text-sm mt-0.5 shrink-0">3</span>
          <p className="text-xs text-[#888] leading-relaxed">
            Kom tilbake hit etter noen sanger — statistikken oppdateres i sanntid.
          </p>
        </div>
      </div>
    </motion.div>
  );
}

function LogoutButton({ onLogout }: { onLogout: () => void }) {
  return (
    <button
      onClick={onLogout}
      className="rounded-lg border border-[#2a2a2a] bg-[#181818] px-3 py-1.5 text-xs text-[#666] transition-all duration-150 hover:border-[#444] hover:text-[#aaa]"
    >
      Logg ut
    </button>
  );
}

export default function App() {
  const queryClient = useQueryClient();

  // Auth-sjekk — kjøres alltid, uavhengig av annen data
  const { data: authData, isLoading: authLoading } = useQuery({
    queryKey: ["authStatus"],
    queryFn: api.authStatus,
    retry: 1,
    staleTime: 5 * 60_000,    // re-bruk cached svar i 5 min
    refetchInterval: 10 * 60_000, // sjekk på nytt hvert 10. min
  });

  const logoutMutation = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      // Ugyldiggjør auth-cachen → App viser LoginScreen umiddelbart
      queryClient.invalidateQueries({ queryKey: ["authStatus"] });
    },
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ["stats"],
    queryFn: api.stats,
    refetchInterval: 10_000,
    staleTime: 5_000,
    // Ikke hent stats-data før vi vet at brukeren er autentisert
    enabled: authData?.authenticated === true,
  });

  const { visible, toggle } = useSectionVisibility();

  const hasGraphs = ["artistChart", "contextChart", "hourChart", "weekdayRateChart"].some((id) => visible[id]);
  const hasMore = visible.mostCompleted;

  // Viser ingenting mens vi venter på auth-svar (unngår blink av LoginScreen)
  if (authLoading) {
    return (
      <div className="min-h-screen bg-[#0d0d0d] flex items-center justify-center">
        <div className="w-5 h-5 rounded-full border-2 border-[#1db954] border-t-transparent animate-spin" />
      </div>
    );
  }

  // Ikke autentisert → vis login-skjerm
  if (!authData?.authenticated) {
    return <LoginScreen />;
  }

  return (
    <div className="min-h-screen bg-[#0d0d0d] text-[#eee]">
      <div className="max-w-6xl mx-auto px-6 py-6">

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="mb-5 flex items-start justify-between"
        >
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-[#1db954]">
              Skip Stats
            </h1>
            <p className="text-sm text-[#888] mt-1">
              Hva skipper du egentlig?
            </p>
            <span className="text-xs text-neutral-500 mt-1 block">
              Sist oppdatert:{" "}
              {new Date().toLocaleDateString("nb-NO", {
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <LogoutButton onLogout={() => logoutMutation.mutate()} />
            <SectionToggle visible={visible} onToggle={toggle} />
          </div>
        </motion.div>

        {/* Spiller nå */}
        <NowPlaying />

        {/* Lasting / feil */}
        {isLoading && (
          <div className="flex items-center justify-center py-24 text-[#888] text-sm">
            Laster statistikk…
          </div>
        )}
        {error && (
          <div className="rounded-xl border border-red-900/40 bg-red-900/10 p-6 text-red-400 text-sm">
            Kunne ikke laste data. Sjekk at Flask-serveren kjører.
          </div>
        )}

        {data && data.total_plays === 0 && <EmptyDashboard />}

        {data && data.total_plays > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4, delay: 0.1 }}
          >
            {/* Oppsummering */}
            <StatCardsRow
              totalSkips={data.total_skips}
              totalPlays={data.total_plays}
              uniqueTracks={data.unique_tracks}
            />

            {/* Heatmap */}
            {visible.heatmap && (
              <div className="mb-4">
                <SkipHeatmap daily={data.daily} />
              </div>
            )}

            {/* Mest skippede sanger */}
            {visible.skipped && (
              <div className="mb-4">
                <SkippedTable
                tracks={data.tracks}
                playlistContexts={data.playlist_contexts ?? data.contexts ?? []}
                albumContexts={data.album_contexts ?? []}
              />
              </div>
            )}

            {hasGraphs && <SectionDivider label="Grafer" />}

            {/* Graf-grid */}
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
                    />
                  )}
                  {visible.hourChart && <HourlyChart hourly={data.hourly} />}
                  {visible.weekdayRateChart && <WeekdayRateChart weekday={data.weekday} />}
                </motion.div>
              )}
            </AnimatePresence>

            {hasMore && <SectionDivider label="Mer statistikk" />}

            {visible.mostCompleted && (
              <div className="mb-6">
                <MostCompletedTable tracks={data.most_completed} />
              </div>
            )}

            {/* Musikkcoach — lyttescore + innsiktskort */}
            <SectionDivider label="Musikkcoach" />
            <ListeningScorePanel />
            <CoachInsightsPanel />

            {/* Smart Skipper — kontrollpanel + forhåndsvisning */}
            <SectionDivider label="Smart Skipper" />
            <SmartSkipperPanel />
            <AutoSkipPreviewTable
              candidates={data.auto_skip_candidates ?? []}
              threshold={data.smart_skipper_threshold ?? 0.85}
            />

            {/* Playlist Janitor */}
            {visible.playlistJanitor && (
              <>
                <SectionDivider label="Playlist Janitor" />
                <PlaylistJanitorPanel />
              </>
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
}
