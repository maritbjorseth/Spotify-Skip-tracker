import { useQuery } from "@tanstack/react-query";
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

export function SmartSkipperPanel() {
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
          {!data.config.enabled && (
            <p className="mt-3 text-xs text-[#888]">
              {t("smartSkipper.enableHint")}{" "}
              <code className="rounded bg-[#1c1c1c] px-1.5 py-0.5 text-[#888]">
                python3 -m spotify_skip_tracker smart-skipper enable
              </code>
            </p>
          )}
          {data.config.enabled && data.config.dry_run && (
            <p className="mt-3 text-xs text-[#888]">
              {t("smartSkipper.dryRunHint")}{" "}
              <code className="rounded bg-[#1c1c1c] px-1.5 py-0.5 text-[#888]">
                python3 -m spotify_skip_tracker smart-skipper dry-run off
              </code>
            </p>
          )}
          <h3 className="text-xs font-semibold text-[#888] uppercase tracking-wider mt-6 mb-3">
            {t("smartSkipper.historyHeading")}
          </h3>
          <HistoryTable rows={data.history} />
        </>
      )}
    </section>
  );
}
