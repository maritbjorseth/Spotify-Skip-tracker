/**
 * LoginScreen — Spotify OAuth-innlogging.
 *
 * Vises når /api/auth/status returnerer authenticated=false.
 * Brukeren klikker innloggingsknappen, nettleseren navigerer til
 * /api/auth/login på Railway-backenden, Spotify OAuth-flyten kjøres,
 * og brukeren sendes tilbake til frontenden som nå er innlogget.
 */

import { useTranslation } from "react-i18next";
import { API_BASE } from "../config";
import { LanguageSelector } from "./LanguageSelector";

const RAILWAY_BASE = API_BASE;

function SpotifyIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z" />
    </svg>
  );
}

function MusicIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9 18V5l12-2v13" />
      <circle cx="6" cy="18" r="3" />
      <circle cx="18" cy="16" r="3" />
    </svg>
  );
}

export function LoginScreen() {
  const { t } = useTranslation();

  function handleLogin() {
    window.location.href = RAILWAY_BASE + "/api/auth/login";
  }

  function handleDemo() {
    window.location.href = RAILWAY_BASE + "/api/auth/demo";
  }

  return (
    <div className="min-h-screen bg-[#0d0d0d] flex items-center justify-center px-6 relative">
      <div className="absolute top-4 right-4">
        <LanguageSelector />
      </div>
      <div className="w-full max-w-sm">
        <div className="text-center mb-10">
          <div
            className="inline-flex items-center justify-center rounded-2xl mb-5"
            style={{ width: 64, height: 64, background: "#1db95420", color: "#1db954" }}
          >
            <MusicIcon />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            {t("login.title")}
            <span className="text-[#1db954]">{t("login.titleAccent")}</span>
          </h1>
          <p className="text-sm text-[#888] mt-2">{t("login.subtitle")}</p>
        </div>

        <button
          onClick={handleLogin}
          className="w-full flex items-center justify-center gap-3 rounded-xl py-3.5 text-sm font-semibold transition-all duration-150 active:scale-[0.98]"
          style={{ background: "#1db954", color: "#000" }}
        >
          <SpotifyIcon />
          {t("login.loginButton")}
        </button>

        <button
          onClick={handleDemo}
          className="w-full flex items-center justify-center gap-3 rounded-xl py-3.5 text-sm font-semibold transition-all duration-150 active:scale-[0.98] mt-3"
          style={{ background: "#ffffff12", color: "#aaa" }}
        >
          {t("login.demoButton")}
        </button>

        <p className="text-center text-xs text-[#555] mt-8">{t("login.footer")}</p>
      </div>
    </div>
  );
}
