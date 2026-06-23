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
