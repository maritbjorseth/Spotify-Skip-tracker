/**
 * AlgorithmTooltip — gjenbrukbar forklaringsknapp for AI-drevne funksjoner.
 *
 * Plasser ved siden av en paneltittel. Klikk åpner en liten popover med
 * en brukerorientert forklaring av hvordan funksjonen fungerer.
 *
 * Lukkes automatisk ved klikk utenfor.
 */

import { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Info } from "lucide-react";

interface Props {
  text: string;
  color?: string;
}

export function AlgorithmTooltip({ text, color = "#555" }: Props) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleOutsideClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, [open]);

  const label = t("algorithmTooltip.label");

  return (
    <div ref={containerRef} className="relative inline-flex items-center">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={label}
        title={label}
        className="flex items-center justify-center rounded-full transition-all duration-150 select-none"
        style={{
          width: 20, height: 20,
          color: open ? color : "#444",
          background: open ? `${color}20` : "transparent",
          border: `1px solid ${open ? `${color}50` : "#2e2e2e"}`,
        }}
      >
        <Info size={11} strokeWidth={1.8} />
      </button>

      {open && (
        <div role="tooltip" className="absolute left-0 top-7 z-50 w-72 rounded-xl border border-[#2a2a2a] bg-[#191919] p-4 shadow-2xl">
          <div className="absolute -top-[5px] left-2.5 h-2.5 w-2.5 rotate-45 border-l border-t border-[#2a2a2a] bg-[#191919]" />
          <p className="text-xs text-[#aaa] leading-relaxed relative">{text}</p>
        </div>
      )}
    </div>
  );
}
