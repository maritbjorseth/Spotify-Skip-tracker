import type { StatsResponse, NowPlayingResponse, SmartSkipperResponse, JanitorCandidate, CoachInsights, ListeningScore, AuthStatus } from "./types";

const BASE =
  window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? ""
    : "https://spotify-skip-tracker-production.up.railway.app";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  stats:             () => fetchJson<StatsResponse>("/api/stats"),
  nowPlaying:        () => fetchJson<NowPlayingResponse>("/api/now"),
  smartSkipper:      () => fetchJson<SmartSkipperResponse>("/api/smart-skipper"),
  janitorCandidates: () => fetchJson<JanitorCandidate[]>("/api/janitor/suggestions"),
  removeJanitorCandidate: (playlistId: string, trackUri: string) =>
    fetchJson<{ success: boolean }>("/api/janitor/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ playlist_id: playlistId, track_uri: trackUri }),
    }),
  coachInsights:   () => fetchJson<CoachInsights>("/api/coach/insights"),
  listeningScore:  () => fetchJson<ListeningScore>("/api/stats/score"),
  authStatus:      () => fetchJson<AuthStatus>("/api/auth/status"),
  logout:          () => fetchJson<{ success: boolean }>("/api/auth/logout", { method: "POST" }),
};
