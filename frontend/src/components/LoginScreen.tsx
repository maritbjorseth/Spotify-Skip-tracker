/**
 * LoginScreen — passordvegg for dashbordet.
 *
 * Vises når auth/status returnerer authenticated=false.
 * Sender passordet til /api/auth/password. Flask setter en signert
 * sesjonscookie (HttpOnly, Secure, SameSite=None) slik at cookien
 * følger med på alle påfølgende kall fra Vercel → Railway.
 * Ved suksess ugyldiggjøres ["authStatus"]-cachen og App.tsx viser
 * dashbordet umiddelbart uten sideinnlasting.
 */

import { useState, useRef, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";

// ---------------------------------------------------------------------------
// Ikon
// ---------------------------------------------------------------------------

function MusicIcon() {
  return (
    <svg
      width="32"
      height="32"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M9 18V5l12-2v13" />
      <circle cx="6" cy="18" r="3" />
      <circle cx="18" cy="16" r="3" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Hoved-komponent
// ---------------------------------------------------------------------------

export function LoginScreen() {
  const queryClient = useQueryClient();
  const [password, setPassword] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // Fokuser passordfeltet automatisk ved innlasting
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const loginMutation = useMutation({
    mutationFn: (pw: string) => api.passwordLogin(pw),
    onSuccess: () => {
      // Ugyldiggjør auth-cachen → App.tsx re-fetcher og viser dashbordet
      queryClient.invalidateQueries({ queryKey: ["authStatus"] });
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password && !loginMutation.isPending) {
      loginMutation.mutate(password);
    }
  }

  const isWrongPassword =
    loginMutation.isError ||
    (loginMutation.isSuccess === false && loginMutation.error != null);

  return (
    <div className="min-h-screen bg-[#0d0d0d] flex items-center justify-center px-6">
      <div className="w-full max-w-sm">

        {/* Logo + tittel */}
        <div className="text-center mb-10">
          <div
            className="inline-flex items-center justify-center rounded-2xl mb-5"
            style={{ width: 64, height: 64, background: "#1db95420", color: "#1db954" }}
          >
            <MusicIcon />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Spotify Skip Tracker
            <span className="text-[#1db954]"> & Coach</span>
          </h1>
          <p className="text-sm text-[#555] mt-2">
            Skriv inn tilgangspassordet for å se dashbordet.
          </p>
        </div>

        {/* Passordskjema */}
        <form onSubmit={handleSubmit} noValidate>
          <div className="mb-3">
            <input
              ref={inputRef}
              type="password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                // Nullstill feilmelding når brukeren begynner å skrive igjen
                if (loginMutation.isError) loginMutation.reset();
              }}
              placeholder="Passord"
              autoComplete="current-password"
              className="w-full rounded-xl px-4 py-3 text-sm text-[#eee] placeholder-[#444] outline-none transition-all duration-150"
              style={{
                background: "#141414",
                border: loginMutation.isError
                  ? "1px solid #ef444466"
                  : "1px solid #2a2a2a",
              }}
            />
          </div>

          {/* Feilmelding */}
          {loginMutation.isError && (
            <p className="text-xs text-red-400 mb-3 pl-1">
              Feil passord. Prøv igjen.
            </p>
          )}

          <button
            type="submit"
            disabled={!password || loginMutation.isPending}
            className="w-full rounded-xl py-3 text-sm font-semibold transition-all duration-150"
            style={{
              background:
                !password || loginMutation.isPending ? "#158a3e" : "#1db954",
              color: "#000",
              opacity: !password || loginMutation.isPending ? 0.6 : 1,
              cursor:
                !password || loginMutation.isPending ? "not-allowed" : "pointer",
            }}
          >
            {loginMutation.isPending ? "Logger inn…" : "Logg inn"}
          </button>
        </form>

        <p className="text-center text-xs text-[#333] mt-8">
          Spotify Skip Tracker & Coach · Personlig dashbord
        </p>
      </div>
    </div>
  );
}
