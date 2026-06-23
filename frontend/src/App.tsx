import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "./api";
import { NowPlaying } from "./components/NowPlaying";
import { StatCardsRow } from "./components/StatCards";
import { SkipHeatmap } from "./components/SkipHeatmap";
import { SkippedTable, MostPlayedTable, MostCompletedTable, TopArtistsTable } from "./components/Tables";
import { ArtistChart, ContextChart, HourlyChart, WeekdayChart, HourlyRateChart, WeekdayRateChart } from "./components/Charts";
import { useSectionVisibility, SectionToggle } from "./components/SectionToggle";

function SectionDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-4 mb-8 mt-16">
      <div className="h-px flex-1 bg-[#2a2a2a]" />
      <span className="text-sm font-semibold uppercase tracking-widest text-[#666]">{label}</span>
      <div className="h-px flex-1 bg-[#2a2a2a]" />
    </div>
  );
}

export default function App() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["stats"],
    queryFn: api.stats,
    refetchInterval: 10_000,
    staleTime: 5_000,
  });

  const { visible, toggle } = useSectionVisibility();

  const hasGraphs = ["artistChart", "contextChart", "hourChart", "weekdayChart", "hourRateChart", "weekdayRateChart"].some((id) => visible[id]);
  const hasMore = ["mostPlayed", "mostCompleted", "topArtists"].some((id) => visible[id]);

  return (
    <div className="min-h-screen bg-[#0d0d0d] text-[#eee]">
      <div className="max-w-6xl mx-auto px-6 py-10">

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="mb-8 flex items-start justify-between"
        >
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-[#1db954]">
              Skip Stats
            </h1>
            <p className="text-sm text-[#555] mt-1">
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
          <SectionToggle visible={visible} onToggle={toggle} />
        </motion.div>

        {/* Spiller nå */}
        <NowPlaying />

        {/* Lasting / feil */}
        {isLoading && (
          <div className="flex items-center justify-center py-24 text-[#555] text-sm">
            Laster statistikk…
          </div>
        )}
        {error && (
          <div className="rounded-xl border border-red-900/40 bg-red-900/10 p-6 text-red-400 text-sm">
            Kunne ikke laste data. Sjekk at Flask-serveren kjører.
          </div>
        )}

        {data && (
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
              <div className="mb-6">
                <SkipHeatmap daily={data.daily} />
              </div>
            )}

            {/* Mest skippede sanger */}
            {visible.skipped && (
              <div className="mb-6">
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
              {(visible.artistChart || visible.contextChart || visible.hourChart || visible.weekdayChart || visible.hourRateChart || visible.weekdayRateChart) && (
                <motion.div
                  key="graphs"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-10"
                >
                  {visible.artistChart && <ArtistChart artists={data.top_artists} />}
                  {visible.contextChart && <ContextChart contexts={data.top_contexts} />}
                  {visible.hourChart && <HourlyChart hourly={data.hourly} />}
                  {visible.weekdayChart && <WeekdayChart weekday={data.weekday} />}
                  {visible.hourRateChart && <HourlyRateChart hourly={data.hourly} />}
                  {visible.weekdayRateChart && <WeekdayRateChart weekday={data.weekday} />}
                </motion.div>
              )}
            </AnimatePresence>

            {hasMore && <SectionDivider label="Mer statistikk" />}

            {/* Nedre tabeller — to kolonner */}
            <AnimatePresence mode="sync">
              {(visible.mostPlayed || visible.mostCompleted) && (
                <motion.div
                  key="tables"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-10"
                >
                  {visible.mostPlayed && <MostPlayedTable tracks={data.most_played} />}
                  {visible.mostCompleted && <MostCompletedTable tracks={data.most_completed} />}
                </motion.div>
              )}
            </AnimatePresence>

            {visible.topArtists && <TopArtistsTable artists={data.top_listened_artists} />}
          </motion.div>
        )}
      </div>
    </div>
  );
}
