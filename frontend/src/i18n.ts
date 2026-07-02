/**
 * i18n-konfigurasjon for Spotify Skip Tracker.
 *
 * Bruker react-i18next med i18next-browser-languagedetector for automatisk
 * lagring av språkvalg i localStorage ('i18nextLng').
 *
 * Støttede språk:
 *   nb — Norsk bokmål (standardspråk)
 *   en — English
 *
 * Legg til et nytt språk ved å:
 *   1. Opprette src/locales/<kode>.json med alle oversettelsesnøkler.
 *   2. Importere filen nedenfor og legge den til i `resources`.
 *   3. Legge til en knapp i LanguageSelector.tsx.
 */

import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import nb from "./locales/nb.json";
import en from "./locales/en.json";

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      nb: { translation: nb },
      en: { translation: en },
    },

    // Standardspråk: norsk.
    // Brukes dersom detektoren ikke finner et lagret valg.
    fallbackLng: "nb",

    // Strip region from locale codes (e.g. "en-US" → "en") so that
    // navigator detection matches the available resource keys.
    load: "languageOnly",

    // Deteksjonskonfigurasjon: sjekk localStorage først, deretter
    // nettleserens Accept-Language. Aldri gå til server eller querystring.
    //
    // Key versjonert til "i18nextLng_v2" for å nullstille stale "nb"-verdier
    // som ble cachet av den gamle deteksjonen (før load:"languageOnly" ble lagt
    // til). Brukere som besøkte siden før denne endringen vil nå bli re-detektert
    // fra nettleserens Accept-Language i stedet for å bli låst til norsk.
    detection: {
      order: ["localStorage", "navigator"],
      lookupLocalStorage: "i18nextLng_v2",
      caches: ["localStorage"],
    },

    interpolation: {
      // React escaper allerede XSS — ikke gjør det dobbelt
      escapeValue: false,
    },
  });

export default i18n;
