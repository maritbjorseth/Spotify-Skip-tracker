import type { StatsResponse, NowPlayingResponse } from "./types";

const BASE = "";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  stats: () => fetchJson<StatsResponse>("/api/stats"),
  nowPlaying: () => fetchJson<NowPlayingResponse>("/api/now"),
};
