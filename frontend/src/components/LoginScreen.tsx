/**
 * LoginScreen — vises når backenden ikke har et gyldig Spotify-token.
 *
 * "Koble til med Spotify"-knappen starter web-OAuth-flyten ved å sende
 * nettleseren til /api/auth/login på Railway-backenden.
 */

import { useState } from "react";

// ---------------------------------------------------------------------------
// Samme BASE-logikk som i api.ts — peker på Railway i produksjon
// ---------------------------------------------------------------------------

const API_BASE =
  window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? ""
    : "https://spotify-skip-tracker-production.up.railway.app";

// ---------------------------------------------------------------------------
// Spotify-logo SVG (offisiell form, ingen emojier)
// ---------------------------------------------------------------------------

function SpotifyIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.441 17.307a.75.75 0 0 1-1.031.25c-2.824-1.726-6.378-2.116-10.564-1.159a.75.75 0 0 1-.334-1.463c4.579-1.046 8.507-.596 11.678 1.341a.75.75 0 0 1 .251 1.031zm1.452-3.23a.937.937 0 0 1-1.288.308c-3.232-1.986-8.158-2.563-11.983-1.402a.938.938 0 0 1-.54-1.794c4.368-1.315 9.79-.678 13.503 1.6a.937.937 0 0 1 .308 1.288zm.125-3.363C15.26 8.6 8.898 8.393 5.265 9.483a1.124 1.124 0 1 1-.652-2.152c4.218-1.278 11.233-1.031 15.666 1.617a1.124 1.124 0 0 1-1.261 1.866z" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Feature-liste
// ---------------------------------------------------------------------------

const FEATURES = [
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    ),
    text: "Sporer og analyserer alle skips på tvers av enheter i sanntid",
  },
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3" />
        <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83" />
      </svg>
    ),
    text: "Smart Skipper hopper automatisk over sanger du konsekvent skipper",
  },
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 6h18M3 12h18M3 18h18" />
        <circle cx="7" cy="6" r="1" fill="currentColor" />
        <circle cx="7" cy="12" r="1" fill="currentColor" />
        <circle cx="7" cy="18" r="1" fill="currentColor" />
      </svg>
    ),
    text: "Playlist Janitor renser spillelistene dine for sanger du aldri hører",
  },
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 18V5l12-2v13" />
        <circle cx="6" cy="18" r="3" />
        <circle cx="18" cy="16" r="3" />
      </svg>
    ),
    text: "Lytte-score og Musikkcoach gir deg innsikt i lyttevanene dine",
  },
];

// ---------------------------------------------------------------------------
// Hoved-komponent
// ---------------------------------------------------------------------------

export function LoginScreen() {
  const [loading, setLoading] = useState(false);

  function handleLogin() {
    setLoading(true);
    window.location.href = `${API_BASE}/api/auth/login`;
  }

  return (
    <div className="min-h-screen bg-[#0d0d0d] text-[#eee] flex items-center justify-center px-6">
      <div className="max-w-md w-full">

        {/* Logo / tittel */}
        <div className="mb-10 text-center">
          <div
            className="inline-flex items-center justify-center rounded-2xl mb-6"
            style={{ width: 72, height: 72, background: "#1db95422" }}
          >
            <svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="#1db954" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18V5l12-2v13" />
              <circle cx="6" cy="18" r="3" />
              <circle cx="18" cy="16" r="3" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-3">
            Spotify Skip Tracker
            <span className="text-[#1db954]"> & Coach</span>
          </h1>
          <p className="text-[#888] text-sm leading-relaxed">
            Ta kontroll over lyttevanene dine. Analyser skips,
            automatiser hopping, og rens spillelistene dine — alt
            drevet av dine egne Spotify-data.
          </p>
        </div>

        {/* Feature-liste */}
        <div className="rounded-xl border border-[#1e1e1e] bg-[#141414] p-5 mb-6 space-y-4">
          {FEATURES.map((f, i) => (
            <div key={i} className="flex items-start gap-3">
              <span className="text-[#1db954] mt-0.5 shrink-0">{f.icon}</span>
              <span className="text-sm text-[#aaa] leading-snug">{f.text}</span>
            </div>
          ))}
        </div>

        {/* Koble til-knapp */}
        <button
          onClick={handleLogin}
          disabled={loading}
          className="w-full flex items-center justify-center gap-3 rounded-xl py-4 px-6 text-sm font-semibold transition-all duration-150"
          style={{
            background: loading ? "#158a3e" : "#1db954",
            color: "#000",
            opacity: loading ? 0.8 : 1,
            cursor: loading ? "wait" : "pointer",
          }}
        >
          <SpotifyIcon />
          {loading ? "Kobler til…" : "Koble til med Spotify"}
        </button>

        <p className="text-center text-xs text-[#444] mt-5 leading-relaxed">
          Appen leser avspillingsdata og kan hoppe over sanger på dine vegne
          dersom Smart Skipper er aktivert. Ingen data deles med tredjeparter.
        </p>
      </div>
    </div>
  );
}
