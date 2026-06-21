import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { api } from "./api";
import { NowPlaying } from "./components/NowPlaying";
import { StatCardsRow } from "./components/StatCards";
import { SkipHeatmap } from "./components/SkipHeatmap";
import { SkippedTable, MostPlayedTable, MostCompletedTable, TopArtistsTable } from "./components/Tables";
import { ArtistChart, ContextChart, HourlyChart, WeekdayChart } from "./components/Charts";

function SectionDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-4 mb-6 mt-12">
      <div className="h-px flex-1 bg-[#2a2a2a]" />
      <span className="text-xs font-semibold uppercase tracking-widest text-[#555]">{label}</span>
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

  return (
    <div className="min-h-screen bg-[#0d0d0d] text-[#eee]">
      <div className="max-w-6xl mx-auto px-6 py-10">

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="mb-8"
        >
          <h1 className="text-3xl font-bold tracking-tight text-[#1db954]">
            Skip Stats
          </h1>
          <p className="text-sm text-[#555] mt-1">
            Hva skipper du egentlig?
          </p>
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
            <SkipHeatmap daily={data.daily} />

            {/* Mest skippede sanger */}
            <SkippedTable tracks={data.tracks} contexts={data.contexts} />

            <SectionDivider label="Grafer" />

            {/* Graf-grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-10">
              <ArtistChart artists={data.top_artists} />
              <ContextChart contexts={data.top_contexts} />
              <HourlyChart hourly={data.hourly} />
              <WeekdayChart weekday={data.weekday} />
            </div>

            <SectionDivider label="Mer statistikk" />

            {/* Nedre tabeller — to kolonner */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-10">
              <MostPlayedTable tracks={data.most_played} />
              <MostCompletedTable tracks={data.most_completed} />
            </div>

            <TopArtistsTable artists={data.top_listened_artists} />
          </motion.div>
        )}
      </div>
    </div>
  );
}
