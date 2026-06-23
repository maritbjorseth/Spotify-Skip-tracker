import type { StatsResponse, NowPlayingResponse, SmartSkipperResponse } from "./types";

const BASE =
  window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? ""
    : "https://spotify-skip-tracker-production.up.railway.app";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  stats: () => fetchJson<StatsResponse>("/api/stats"),
  nowPlaying: () => fetchJson<NowPlayingResponse>("/api/now"),
  smartSkipper: () => fetchJson<SmartSkipperResponse>("/api/smart-skipper"),
};
