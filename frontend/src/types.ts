export interface Track {
  uri: string;
  title: string | null;
  artists: string | null;
  context_name: string | null;
  skip_count: number;
  play_count: number;
  skip_rate: number;
  image_url: string | null;
}

export interface Artist {
  artists: string;
  skip_count: number;
  play_count: number;
  skip_rate: number;
}

export interface Context {
  context_name: string;
  skip_count: number;
  play_count: number;
  skip_rate: number;
}

export interface HourlyStats {
  skips: number;
  plays: number;
}

export interface WeekdayStats {
  skips: number;
  plays: number;
}

export interface DailyStats {
  skips: number;
  plays: number;
}

export interface StatsResponse {
  tracks: Track[];
  contexts: string[];
  playlist_contexts: string[];
  album_contexts: string[];
  top_artists: Artist[];
  top_listened_artists: Artist[];
  top_contexts: Context[];
  most_played: Track[];
  most_completed: Track[];
  hourly: HourlyStats[];   // 24 elementer, indeks = time
  weekday: WeekdayStats[]; // 7 elementer, 0 = mandag
  daily: Record<string, DailyStats>; // "YYYY-MM-DD" → {skips, plays}
  total_skips: number;
  total_plays: number;
  unique_tracks: number;
  auto_skip_candidates: AutoSkipCandidate[];
  smart_skipper_threshold: number;
}

export interface AutoSkipCandidate {
  uri: string;
  title: string | null;
  artists: string | null;
  image_url: string | null;
  skip_count: number;
  play_count: number;
  skip_rate: number;
}

export interface SmartSkipperConfig {
  enabled: boolean;
  threshold: number;
  min_plays: number;
  delay_seconds: number;
  dry_run: boolean;
}

export interface AutoSkipHistoryEntry {
  title: string | null;
  artists: string | null;
  skip_rate: number | null;
  reason: string | null;
  timestamp: string | null;
  undone: boolean;
}

export interface SmartSkipperResponse {
  config: SmartSkipperConfig;
  history: AutoSkipHistoryEntry[];
}

export type JanitorCategory = "Remove" | "Candidate" | "Watchlist" | "Keep";

export interface JanitorCandidate {
  id: number;
  playlist_id: string;
  playlist_name: string;
  uri: string;
  title: string;
  artists: string;
  skip_rate: number;
  janitor_score: number;
  status: string;
  play_count: number;
  confidence_level: string;
  category: JanitorCategory;
  suggested_at: string | null;
}

export interface ListeningScore {
  score: number;
}

export interface AuthStatus {
  authenticated: boolean;
  user_id: string | null;
  is_demo: boolean;
}

/**
 * Strukturert innsiktsobjekt fra /api/coach/insights.
 *
 * Feltene bygger oppå hverandre i stadier:
 *   Stadium 1: kun observation
 *   Stadium 2: observation + context + trend
 *   Stadium 3: alle fire felt
 *
 * Frontenden rendrer kun feltene som er fylt ut.
 */
export interface Insight {
  id: string;
  category: "skip_rate" | "streak" | "session" | "janitor" | "pattern";
  stadium: 1 | 2 | 3;
  observation: string;
  context: string | null;
  explanation: string | null;
  action: string | null;
  value: number | null;
  trend: "up" | "down" | "stable" | null;
  trend_is_positive: boolean | null;
}

export interface NowPlayingResponse {
  is_playing: boolean;
  uri: string | null;
  title: string | null;
  artists: string | null;
  album: string | null;
  image_url: string | null;
  progress_ms: number;
  duration_ms: number;
  skip_rate: number | null;
  updated_at: string | null;
}
