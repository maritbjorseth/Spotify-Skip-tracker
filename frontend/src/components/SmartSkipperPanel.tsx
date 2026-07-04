import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import type { AutoSkipHistoryEntry, SmartSkipperConfig } from "../types";
import { AlgorithmTooltip } from "./AlgorithmTooltip";

function StatusBadge({ config }: { config: SmartSkipperConfig }) {
  const { t } = useTranslation();
  let label: string;
  let bg: string;
  let fg: string;
  let dot: string;

  if (!config.enabled) {
    label = t("smartSkipper.statusDisabled");
    bg = "#ef444422"; fg = "#ef4444"; dot = "#ef4444";
  } else if (config.dry_run) {
    label = t("smartSkipper.statusDryRun");
    bg = "#f9731622"; fg = "#f97316"; dot = "#f97316";
  } else {
    label = t("smartSkipper.statusActive");
    bg = "#1db95422"; fg = "#1db954"; dot = "#1db954";
  }

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold" style={{ background: bg, color: fg }}>
      <span className="inline-block rounded-full" style={{ width: 7, height: 7, background: dot, flexShrink: 0 }} />
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Toggle-rad
// ---------------------------------------------------------------------------

function ToggleRow({
  checked,
  onChange,
  disabled,
  label,
  description,
  accent,
}: {
  checked: boolean;
  onChange: (val: boolean) => void;
  disabled: boolean;
  label: string;
  description: string;
  accent: string;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-3.5 border-b border-[#222] last:border-b-0">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-[#ddd] leading-snug">{label}</p>
        <p className="text-xs text-[#666] mt-0.5 leading-snug">{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className="flex-shrink-0 relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-40 disabled:cursor-not-allowed"
        style={{
          background: checked ? accent : "#2a2a2a",
          outlineColor: accent,
        }}
      >
        <span
          className="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform duration-200"
          style={{ transform: checked ? "translateX(1.375rem)" : "translateX(0.25rem)" }}
        />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Kontroll-panel (toggles)
// ---------------------------------------------------------------------------

function ConfigControls({
  config,
  isDemo,
}: {
  config: SmartSkipperConfig;
  isDemo: boolean;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [configError, setConfigError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: api.updateSmartSkipperConfig,
    onSuccess: (updated) => {
      setConfigError(null);
      // Oppdater cachen direkte med returverdien fra PATCH
      queryClient.setQueryData<{ config: SmartSkipperConfig; history: AutoSkipHistoryEntry[] }>(
        ["smartSkipper"],
        (old) => old ? { ...old, config: updated } : old,
      );
    },
    onError: () => {
      setConfigError(t("smartSkipper.configError"));
    },
  });

  const saving = mutation.isPending;
  const disabled = isDemo || saving;

  return (
    <div className="rounded-xl border border-[#2a2a2a] bg-[#1c1c1c] px-4 mb-6">
      {configError && (
        <p className="text-xs text-red-400 pt-3 pb-1">{configError}</p>
      )}
      {isDemo && (
        <p className="text-xs text-[#555] pt-3 pb-1">{t("smartSkipper.toggleDemoDisabled")}</p>
      )}
      <ToggleRow
        checked={config.enabled}
        onChange={(val) => mutation.mutate({ enabled: val })}
        disabled={disabled}
        label={saving ? t("smartSkipper.toggleSaving") : t("smartSkipper.toggleEnable")}
        description={t("smartSkipper.toggleEnableDesc")}
        accent="#1db954"
      />
      {config.enabled && (
        <ToggleRow
          checked={config.dry_run}
          onChange={(val) => mutation.mutate({ dry_run: val })}
          disabled={disabled}
          label={t("smartSkipper.toggleDryRun")}
          description={t("smartSkipper.toggleDryRunDesc")}
          accent="#f97316"
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Historikk-tabell
// ---------------------------------------------------------------------------

function HistoryTable({ rows }: { rows: AutoSkipHistoryEntry[] }) {
  const { t, i18n } = useTranslation();
  if (rows.length === 0) {
    return <p className="text-sm italic text-[#888] py-6 text-center">{t("smartSkipper.historyEmpty")}</p>;
  }

  return (
    <div className="overflow-hidden rounded-xl border border-[#2a2a2a] bg-[#1c1c1c]">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px]">
          <thead className="bg-[#161616]">
            <tr>
              {(["title","artist","skipRate","timestamp","mode"] as const).map((col) => (
                <th key={col} className={`px-4 py-3 text-xs font-semibold text-[#888] uppercase tracking-wider ${col === "title" || col === "artist" ? "text-left" : "text-right"}`}>
                  {t(`smartSkipper.columns.${col}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const isDryRun = r.reason?.startsWith("[DRY RUN]") ?? false;
              const ts = r.timestamp
                ? new Date(r.timestamp).toLocaleString(i18n.language, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })
                : "—";
              return (
                <tr key={i} className="border-t border-[#2a2a2a] hover:bg-white/[0.03] transition-colors">
                  <td className="px-4 py-4 text-sm font-medium max-w-[180px] truncate" title={r.title ?? undefined}>{r.title ?? "—"}</td>
                  <td className="px-4 py-4 text-sm text-[#999] max-w-[140px] truncate" title={r.artists ?? undefined}>{r.artists ?? "—"}</td>
                  <td className="px-4 py-4 text-right">
                    <span className="text-sm font-semibold text-[#f97316] tabular-nums">
                      {r.skip_rate != null ? `${Math.round(r.skip_rate * 100)}%` : "—"}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-sm text-[#888] text-right tabular-nums whitespace-nowrap">{ts}</td>
                  <td className="px-4 py-4 text-right">
                    <span
                      className="rounded-full px-2 py-0.5 text-xs font-medium"
                      style={isDryRun ? { background: "#2a2a2a", color: "#888" } : { background: "#1db95422", color: "#1db954" }}
                    >
                      {isDryRun ? t("smartSkipper.modeDryRun") : t("smartSkipper.modeReal")}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hoved-panel
// ---------------------------------------------------------------------------

export function SmartSkipperPanel({ isDemo = false }: { isDemo?: boolean }) {
  const { t } = useTranslation();
  const { data, isLoading, error } = useQuery({
    queryKey: ["smartSkipper"],
    queryFn: api.smartSkipper,
    refetchInterval: 15_000,
    staleTime: 10_000,
  });

  return (
    <section className="mb-8">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-[#f97316]">{t("smartSkipper.heading")}</h2>
            <AlgorithmTooltip text={t("smartSkipper.explanation")} color="#f97316" />
          </div>
          <p className="text-xs text-[#888] mt-0.5">{t("smartSkipper.subtitle")}</p>
        </div>
        {data?.config && <StatusBadge config={data.config} />}
      </div>

      {isLoading && <p className="text-sm text-[#888] py-4">{t("smartSkipper.loading")}</p>}
      {error && (
        <div className="rounded-xl border border-red-900/40 bg-red-900/10 p-4 text-red-400 text-sm">
          {t("smartSkipper.error")}
        </div>
      )}

      {data && (
        <>
          <ConfigControls config={data.config} isDemo={isDemo} />
          <h3 className="text-xs font-semibold text-[#888] uppercase tracking-wider mt-6 mb-3">
            {t("smartSkipper.historyHeading")}
          </h3>
          <HistoryTable rows={data.history} />
        </>
      )}
    </section>
  );
}
