import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { AutoSkipHistoryEntry, SmartSkipperConfig } from "../types";
import { AlgorithmTooltip } from "./AlgorithmTooltip";

const SMART_SKIPPER_EXPLANATION =
  "Smart Skipper ser på din historiske skip-data og oppdager sanger du nesten alltid hopper over. " +
  "Når en sang har blitt skippet i minst 85 % av avspillingene — og med minst 3 avspillinger som grunnlag — " +
  "venter den noen sekunder og hopper automatisk videre for deg. " +
  "Du bestemmer selv terskel og kan skru funksjonen av og på via CLI.";

// ---------------------------------------------------------------------------
// Status-badge
// ---------------------------------------------------------------------------

function StatusBadge({ config }: { config: SmartSkipperConfig }) {
  let label: string;
  let bg: string;
  let fg: string;
  let dot: string;

  if (!config.enabled) {
    label = "Deaktivert";
    bg = "#ef444422";
    fg = "#ef4444";
    dot = "#ef4444";
  } else if (config.dry_run) {
    label = "Prøvemodus (dry-run)";
    bg = "#f9731622";
    fg = "#f97316";
    dot = "#f97316";
  } else {
    label = "Aktiv";
    bg = "#1db95422";
    fg = "#1db954";
    dot = "#1db954";
  }

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold"
      style={{ background: bg, color: fg }}
    >
      <span
        className="inline-block rounded-full"
        style={{ width: 7, height: 7, background: dot, flexShrink: 0 }}
      />
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Konfigurasjon-grid
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Historikk-tabell
// ---------------------------------------------------------------------------

function HistoryTable({ rows }: { rows: AutoSkipHistoryEntry[] }) {
  if (rows.length === 0) {
    return (
      <p className="text-sm italic text-[#555] py-6 text-center">
        Ingen automatiske hopp registrert ennå.
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-[#2a2a2a] bg-[#1c1c1c]">
      <div className="overflow-x-auto">
      <table className="w-full min-w-[520px]">
        <thead className="bg-[#161616]">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider">
              Tittel
            </th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider">
              Artist
            </th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-[#666] uppercase tracking-wider">
              Skip-rate
            </th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-[#666] uppercase tracking-wider">
              Tidspunkt
            </th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-[#666] uppercase tracking-wider">
              Modus
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const isDryRun = r.reason?.startsWith("[DRY RUN]") ?? false;
            const ts = r.timestamp
              ? new Date(r.timestamp).toLocaleString("nb-NO", {
                  day: "2-digit",
                  month: "2-digit",
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : "—";

            return (
              <tr
                key={i}
                className="border-t border-[#2a2a2a] hover:bg-white/[0.03] transition-colors"
              >
                <td
                  className="px-4 py-4 text-sm font-medium max-w-[180px] truncate"
                  title={r.title ?? undefined}
                >
                  {r.title ?? "—"}
                </td>
                <td
                  className="px-4 py-4 text-sm text-[#999] max-w-[140px] truncate"
                  title={r.artists ?? undefined}
                >
                  {r.artists ?? "—"}
                </td>
                <td className="px-4 py-4 text-right">
                  <span className="text-sm font-semibold text-[#f97316]">
                    {r.skip_rate != null
                      ? `${Math.round(r.skip_rate * 100)}%`
                      : "—"}
                  </span>
                </td>
                <td className="px-4 py-4 text-sm text-[#666] text-right tabular-nums whitespace-nowrap">
                  {ts}
                </td>
                <td className="px-4 py-4 text-right">
                  <span
                    className="rounded-full px-2 py-0.5 text-xs font-medium"
                    style={
                      isDryRun
                        ? { background: "#2a2a2a", color: "#555" }
                        : { background: "#1db95422", color: "#1db954" }
                    }
                  >
                    {isDryRun ? "Dry-run" : "Ekte hopp"}
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

export function SmartSkipperPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["smartSkipper"],
    queryFn: api.smartSkipper,
    refetchInterval: 15_000,
    staleTime: 10_000,
  });

  return (
    <section className="mb-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-[#f97316]">
              Smart Skipper — kontrollpanel
            </h2>
            <AlgorithmTooltip text={SMART_SKIPPER_EXPLANATION} color="#f97316" />
          </div>
          <p className="text-xs text-[#555] mt-0.5">
            Automatisk hopping basert på din historiske skip-data.
          </p>
        </div>
        {data?.config && <StatusBadge config={data.config} />}
      </div>

      {isLoading && (
        <p className="text-sm text-[#555] py-4">Laster Smart Skipper-data…</p>
      )}

      {error && (
        <div className="rounded-xl border border-red-900/40 bg-red-900/10 p-4 text-red-400 text-sm">
          Kunne ikke hente Smart Skipper-status.
        </div>
      )}

      {data && (
        <>
          {/* Aktiveringshjelp */}
          {!data.config.enabled && (
            <p className="mt-3 text-xs text-[#555]">
              Aktiver via CLI:{" "}
              <code className="rounded bg-[#1c1c1c] px-1.5 py-0.5 text-[#888]">
                python3 -m spotify_skip_tracker smart-skipper enable
              </code>
            </p>
          )}
          {data.config.enabled && data.config.dry_run && (
            <p className="mt-3 text-xs text-[#555]">
              Slå av prøvemodus for ekte hopp:{" "}
              <code className="rounded bg-[#1c1c1c] px-1.5 py-0.5 text-[#888]">
                python3 -m spotify_skip_tracker smart-skipper dry-run off
              </code>
            </p>
          )}

          {/* Historikk */}
          <h3 className="text-xs font-semibold text-[#666] uppercase tracking-wider mt-6 mb-3">
            Siste 20 automatiske hopp
          </h3>
          <HistoryTable rows={data.history} />
        </>
      )}
    </section>
  );
}
