import type { StatsResponse, NowPlayingResponse, SmartSkipperResponse, JanitorCandidate, Insight, ListeningScore, AuthStatus } from "./types";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  // Alle kall bruker relativ adressering — frontend og backend deler alltid
  // samme origin (Vite-proxy lokalt, Flask/Gunicorn på Railway).
  // credentials: 'include' sikrer at session-cookien følger med på alle kall.
  const res = await fetch(path, {
    credentials: "include",
    ...init,
  });
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
  coachInsights:   (lang: string) => fetchJson<Insight[]>(`/api/coach/insights?lang=${lang}`),
  listeningScore:  () => fetchJson<ListeningScore>("/api/stats/score"),
  updateSmartSkipperConfig: (patch: { enabled?: boolean; dry_run?: boolean }) =>
    fetchJson<import("./types").SmartSkipperConfig>("/api/smart-skipper/config", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }),
  authStatus:      () => fetchJson<AuthStatus>("/api/auth/status"),
  logout:          () => fetchJson<{ success: boolean }>("/api/auth/logout", { method: "POST" }),
};
