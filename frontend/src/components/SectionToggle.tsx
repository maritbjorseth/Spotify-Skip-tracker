import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";

const STORAGE_PREFIX = "vis_";

export const SECTION_IDS = [
  "skipped", "artistChart", "contextChart", "hourChart",
  "weekdayRateChart", "heatmap", "trendChart", "mostCompleted", "playlistJanitor",
] as const;

export type SectionId = typeof SECTION_IDS[number];

// SECTIONS brukes kun for å styre visibilitet — labels hentes fra i18n
export const SECTIONS = SECTION_IDS.map((id) => ({ id }));

export function useSectionVisibility() {
  const [visible, setVisible] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    for (const id of SECTION_IDS) {
      const saved = localStorage.getItem(STORAGE_PREFIX + id);
      initial[id] = saved === null ? true : saved === "1";
    }
    return initial;
  });

  const toggle = (id: string) => {
    setVisible((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  useEffect(() => {
    for (const id of SECTION_IDS) {
      localStorage.setItem(STORAGE_PREFIX + id, visible[id] ? "1" : "0");
    }
  }, [visible]);

  return { visible, toggle };
}

export function SectionToggle({
  visible,
  onToggle,
}: {
  visible: Record<string, boolean>;
  onToggle: (id: string) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      const target = e.target as HTMLElement;
      if (!target.closest("[data-section-toggle]")) setOpen(false);
    }
    document.addEventListener("click", handleClick);
    return () => document.removeEventListener("click", handleClick);
  }, []);

  const checkedCount = SECTION_IDS.filter((id) => visible[id]).length;

  return (
    <div className="relative" data-section-toggle>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-lg border border-[#3a3a3a] bg-[#1c1c1c] px-3 py-2 text-sm text-[#bbb] hover:text-[#eee] hover:border-[#666] hover:bg-[#242424] active:scale-95 transition-all duration-150"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 0 0 2.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 0 0 1.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 0 0-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 0 0-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 0 0-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 0 0-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 0 0 1.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0z" />
        </svg>
        <span>{t("sectionToggle.counter", { count: checkedCount, total: SECTION_IDS.length })}</span>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 flex flex-col gap-1 rounded-xl border border-[#2a2a2a] bg-[#1c1c1c] p-3 shadow-xl z-50 min-w-56">
          {SECTION_IDS.map((id) => (
            <label
              key={id}
              className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-[#ccc] hover:text-[#eee] hover:bg-[#232323] cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                checked={visible[id]}
                onChange={() => onToggle(id)}
                className="accent-[#1db954]"
              />
              {t(`sectionToggle.${id}` as const)}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
