/**
 * LanguageSelector — kompakt språkvelger for dashbord-headeren.
 *
 * Viser én knapp per støttet språk med flagg og kortnavnet.
 * Aktiv knapp utheves. Valget lagres automatisk i localStorage
 * av i18next-browser-languagedetector (nøkkel: 'i18nextLng').
 *
 * Legg til et nytt språk:
 *   1. Opprett src/locales/<kode>.json
 *   2. Importer og registrer i src/i18n.ts
 *   3. Legg til en ny entry i LANGUAGES nedenfor
 */

import { useTranslation } from "react-i18next";
import ReactCountryFlag from "react-country-flag";

const LANGUAGES = [
  { code: "nb", countryCode: "NO", label: "Norsk" },
  { code: "en", countryCode: "GB", label: "English" },
] as const;

export function LanguageSelector() {
  const { i18n } = useTranslation();
  const current = i18n.language?.startsWith("nb") ? "nb" : i18n.language?.startsWith("en") ? "en" : "nb";

  return (
    <div className="flex items-center gap-1" role="group" aria-label="Language / Språk">
      {LANGUAGES.map(({ code, countryCode, label }) => {
        const isActive = current === code;
        return (
          <button
            key={code}
            onClick={() => i18n.changeLanguage(code)}
            title={label}
            aria-pressed={isActive}
            className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs font-medium transition-all duration-150"
            style={{
              background: isActive ? "#1db95422" : "transparent",
              color: isActive ? "#1db954" : "#555",
              border: isActive ? "1px solid #1db95440" : "1px solid transparent",
              cursor: isActive ? "default" : "pointer",
            }}
          >
            <ReactCountryFlag
              countryCode={countryCode}
              svg
              aria-hidden="true"
              style={{ width: "1.1em", height: "0.85em", borderRadius: "2px" }}
            />
            <span className="hidden sm:inline">{label}</span>
          </button>
        );
      })}
    </div>
  );
}
