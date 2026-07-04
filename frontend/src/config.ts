/**
 * API-basadressen til Railway-backenden.
 *
 * I lokal utvikling (localhost / 127.0.0.1) brukes relativ adressering
 * slik at Vite-proxyen (eller dev-serveren) håndterer forespørslene.
 * I produksjon (Vercel) peker vi direkte til Railway-tjenesten.
 */
export const API_BASE =
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1"
    ? ""
    : "https://spotify-skip-tracker-production.up.railway.app";
