import { useState, useEffect } from "react";

const STORAGE_PREFIX = "vis_";

export const SECTIONS = [
  { id: "skipped", label: "Mest skippede sanger" },
  { id: "artistChart", label: "Mest skippede artister" },
  { id: "contextChart", label: "Skip-rate per spilleliste/album" },
  { id: "hourChart", label: "Skip etter tidspunkt" },
  { id: "weekdayChart", label: "Skip etter ukedag" },
  { id: "mostPlayed", label: "Mest spilt totalt" },
  { id: "mostCompleted", label: "Nesten aldri skippet" },
  { id: "topArtists", label: "Mest hørte artister" },
] as const;

export function useSectionVisibility() {
  const [visible, setVisible] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    for (const s of SECTIONS) {
      const saved = localStorage.getItem(STORAGE_PREFIX + s.id);
      initial[s.id] = saved === null ? true : saved === "1";
    }
    return initial;
  });

  const toggle = (id: string) => {
    setVisible((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      return next;
    });
  };

  useEffect(() => {
    for (const s of SECTIONS) {
      localStorage.setItem(STORAGE_PREFIX + s.id, visible[s.id] ? "1" : "0");
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
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      const target = e.target as HTMLElement;
      if (!target.closest("[data-section-toggle]")) setOpen(false);
    }
    document.addEventListener("click", handleClick);
    return () => document.removeEventListener("click", handleClick);
  }, []);

  const checkedCount = SECTIONS.filter((s) => visible[s.id]).length;

  return (
    <div className="relative" data-section-toggle>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-lg border border-[#2a2a2a] bg-[#1c1c1c] px-3 py-2 text-sm text-[#ccc] hover:text-[#eee] hover:border-[#444] transition-colors"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 0 0 2.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 0 0 1.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 0 0-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 0 0-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 0 0-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 0 0-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 0 0 1.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0z" />
        </svg>
        <span>{checkedCount}/{SECTIONS.length} synlige</span>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 flex flex-col gap-1 rounded-xl border border-[#2a2a2a] bg-[#1c1c1c] p-3 shadow-xl z-50 min-w-56">
          {SECTIONS.map((s) => (
            <label
              key={s.id}
              className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-[#ccc] hover:text-[#eee] hover:bg-[#232323] cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                checked={visible[s.id]}
                onChange={() => onToggle(s.id)}
                className="accent-[#1db954]"
              />
              {s.label}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
