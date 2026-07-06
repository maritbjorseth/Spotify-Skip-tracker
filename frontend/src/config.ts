/**
 * API-basadresse.
 *
 * Frontend og backend serveres alltid fra samme origin:
 *   - Lokal utvikling: Vite-proxyen videresender /api/* til Flask (port 5000).
 *   - Produksjon (Railway): Flask/Gunicorn serverer både frontend/dist og /api/*.
 *
 * Relativ adressering ("") fungerer derfor i begge miljøer, og ingen
 * cross-origin-oppsett (CORS, SameSite=None-cookies) er nødvendig.
 */
export const API_BASE = "";
