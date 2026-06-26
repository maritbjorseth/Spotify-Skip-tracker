import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../api";

function formatMs(ms: number): string {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function NowPlaying() {
  const { data, error } = useQuery({
    queryKey: ["now"],
    queryFn: api.nowPlaying,
    refetchInterval: 5000,
    staleTime: 0,
  });

  // Lokal progress som tikker fremover hvert sekund mellom polls
  const [localProgress, setLocalProgress] = useState(0);
  useEffect(() => {
    if (!data?.is_playing) return;
    setLocalProgress(data.progress_ms);
    const id = setInterval(() => {
      setLocalProgress((p) => Math.min(p + 1000, data.duration_ms));
    }, 1000);
    return () => clearInterval(id);
  }, [data?.progress_ms, data?.is_playing, data?.duration_ms]);

  return (
    <AnimatePresence mode="wait">
      {error && (
        <motion.div
          key="offline"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="mb-4 rounded-lg border border-[#2a2a2a] px-4 py-2 text-xs text-[#888]"
        >
          Kan ikke nå serveren — viser sist kjente data.
        </motion.div>
      )}
      {data && !data.is_playing && !error && (
        <motion.div
          key="idle"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="mb-4 flex items-center gap-2 rounded-lg border border-[#2a2a2a] px-4 py-2 text-xs text-[#888]"
        >
          <svg className="h-3.5 w-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 19V6l12-3v13M9 19a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm12-3a3 3 0 1 1-6 0 3 3 0 0 1 6 0ZM9 7l12-3" />
          </svg>
          Spill musikk i Spotify for å se hva som spilles nå.
        </motion.div>
      )}
      {data?.is_playing ? (
        <motion.div
          key="playing"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.3 }}
          className="flex items-center gap-4 rounded-xl border border-[#2a2a2a] bg-[#181818] p-4 mb-4"
        >
          {/* Albumcover med pulserende ring */}
          <div className="relative flex-shrink-0">
            {data.image_url ? (
              <img
                src={data.image_url}
                alt={data.album ?? ""}
                className="size-16 aspect-square rounded-md object-cover shadow-lg"
              />
            ) : (
              <div className="flex size-16 items-center justify-center rounded-md bg-[#2a2a2a]">
                <svg className="h-8 w-8 text-[#555]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 19V6l12-3v13M9 19a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm12-3a3 3 0 1 1-6 0 3 3 0 0 1 6 0ZM9 7l12-3" />
                </svg>
              </div>
            )}
            {/* Pulserende grønn ring */}
            <motion.span
              className="absolute -inset-1 rounded-lg border-2 border-[#1db954]"
              animate={{ opacity: [0.6, 0.15, 0.6] }}
              transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
            />
          </div>

          {/* Sporinfo og fremgangslinje */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              {/* Pulserende grønn prikk */}
              <motion.span
                className="inline-block h-2 w-2 rounded-full bg-[#1db954] flex-shrink-0"
                animate={{ scale: [1, 1.4, 1] }}
                transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
              />
              <span className="text-xs font-medium text-[#1db954] uppercase tracking-widest">
                Spiller nå
              </span>
              {data.skip_rate !== null && (
                <span
                  className="ml-auto text-xs font-medium px-2 py-0.5 rounded-full"
                  style={{
                    background: data.skip_rate >= 0.5 ? "#ff6b3520" : "#1db95420",
                    color: data.skip_rate >= 0.5 ? "#ff6b35" : "#1db954",
                  }}
                  title={
                    data.skip_rate >= 0.5
                      ? "Du hopper vanligvis over denne sangen"
                      : "Du hører vanligvis denne sangen ferdig"
                  }
                >
                  {Math.round(data.skip_rate * 100)}% skip-rate
                </span>
              )}
            </div>

            <p className="text-base font-semibold truncate leading-tight">
              {data.title ?? "Ukjent spor"}
            </p>
            <p className="text-sm text-[#999] truncate">{data.artists ?? ""}</p>

            {/* Fremgangslinje */}
            <div className="mt-2 flex items-center gap-2">
              <span className="text-xs text-[#888] tabular-nums w-9 text-right">
                {formatMs(localProgress)}
              </span>
              <div className="flex-1 h-1 rounded-full bg-[#2a2a2a] overflow-hidden">
                <motion.div
                  className="h-full rounded-full bg-[#1db954]"
                  initial={false}
                  animate={{
                    width: `${Math.min(100, (localProgress / data.duration_ms) * 100)}%`,
                  }}
                  transition={{ duration: 0.9, ease: "linear" }}
                />
              </div>
              <span className="text-xs text-[#888] tabular-nums w-9">
                {formatMs(data.duration_ms)}
              </span>
            </div>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
