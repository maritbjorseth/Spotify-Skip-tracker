import React, { useState, useMemo, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { Track, Artist, AutoSkipCandidate } from "../types";
import { skipRateColor } from "../theme";
import { api } from "../api";

// ---------------------------------------------------------------------------
// Hjelpefunksjoner
// ---------------------------------------------------------------------------

function SkipBadge({ rate }: { rate: number }) {
  const { t } = useTranslation();
  const pct = Math.round(rate * 100);
  const fg  = skipRateColor(pct);

  let label: string;
  if (rate < 0.25) label = t("tables.skipRateLow");
  else if (rate < 0.5) label = t("tables.skipRateMedium");
  else label = t("tables.skipRateHigh");

  return (
    <span
      className="inline-block rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums"
      style={{ background: fg + "22", color: fg }}
      title={`${pct}% — ${label}`}
    >
      {pct}%
    </span>
  );
}

// Inline-stil-beholder garanterer 56×56 px uavhengig av CSS-cascade og
// Tailwinds preflight (img,video { height: auto }). Beholderen kan ikke
// overstyres av eksternt CSS uten !important, og overflow:hidden klipper
// eventuell overflow fra bildet inni.
const THUMB_SIZE = 56;
const thumbBoxStyle: React.CSSProperties = {
  width: THUMB_SIZE,
  height: THUMB_SIZE,
  minWidth: THUMB_SIZE,
  minHeight: THUMB_SIZE,
  flexShrink: 0,
  overflow: 'hidden',
  borderRadius: '0.375rem',
  display: 'block',
  backgroundColor: '#2a2a2a',
};
const thumbImgStyle: React.CSSProperties = {
  width: '100%',
  height: '100%',
  objectFit: 'cover',
  display: 'block',
};

function AlbumThumb({ url, title, uri }: { url: string | null; title: string | null; uri?: string | null }) {
  const { t } = useTranslation();

  // Bygg Spotify-lenke fra track-URI (spotify:track:ID → open.spotify.com/track/ID)
  const spotifyHref =
    uri?.startsWith("spotify:track:")
      ? `https://open.spotify.com/track/${uri.split(":")[2]}`
      : null;

  const inner = url ? (
    <div style={thumbBoxStyle}>
      <img src={url} alt={title ?? ""} loading="lazy" style={thumbImgStyle} />
    </div>
  ) : (
    <div style={thumbBoxStyle} className="flex items-center justify-center">
      <svg className="h-5 w-5 text-[#555]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 19V6l12-3v13M9 19a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm12-3a3 3 0 1 1-6 0 3 3 0 0 1 6 0ZM9 7l12-3" />
      </svg>
    </div>
  );

  if (spotifyHref) {
    return (
      <a
        href={spotifyHref}
        target="_blank"
        rel="noopener noreferrer"
        title={t("tables.openInSpotify", { title: title ?? "—" })}
        className="block hover:scale-105 transition-transform duration-150"
      >
        {inner}
      </a>
    );
  }
  return inner;
}

function Pagination({
  page,
  total,
  pageSize,
  onPage,
}: {
  page: number;
  total: number;
  pageSize: number;
  onPage: (p: number) => void;
}) {
  const { t } = useTranslation();
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center justify-center gap-3 mt-4">
      <button
        disabled={page <= 1}
        onClick={() => onPage(page - 1)}
        className="rounded-lg border border-[#2a2a2a] bg-[#1c1c1c] px-3 py-1.5 text-sm text-[#ccc] disabled:opacity-30 disabled:cursor-default enabled:hover:border-[#444] enabled:cursor-pointer transition-colors"
      >
        {t("tables.pagination.prev")}
      </button>
      <span className="text-sm text-[#888]">
        {t("tables.pagination.info", { page, totalPages, total })}
      </span>
      <button
        disabled={page >= totalPages}
        onClick={() => onPage(page + 1)}
        className="rounded-lg border border-[#2a2a2a] bg-[#1c1c1c] px-3 py-1.5 text-sm text-[#ccc] disabled:opacity-30 disabled:cursor-default enabled:hover:border-[#444] enabled:cursor-pointer transition-colors"
      >
        {t("tables.pagination.next")}
      </button>
    </div>
  );
}

const PAGE = 15;

// ---------------------------------------------------------------------------
// Mest skippede sanger
// ---------------------------------------------------------------------------

type SortKey = "skip_count" | "play_count" | "skip_rate" | "title" | "artists" | "context_name";

export function SkippedTable({
  tracks,
  playlistContexts = [],
  albumContexts = [],
}: {
  tracks: Track[];
  playlistContexts?: string[];
  albumContexts?: string[];
}) {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [ctx, setCtx] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("skip_count");
  const [sortDir, setSortDir] = useState<1 | -1>(-1);

  const filtered = useMemo(() => {
    let rows = tracks;
    if (ctx) rows = rows.filter((t) => t.context_name === ctx);
    if (search) {
      const q = search.toLowerCase();
      rows = rows.filter(
        (t) =>
          (t.title ?? "").toLowerCase().includes(q) ||
          (t.artists ?? "").toLowerCase().includes(q),
      );
    }
    rows = [...rows].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return sortDir;
      if (bv == null) return -sortDir;
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * sortDir;
      return String(av) < String(bv) ? -sortDir : String(av) > String(bv) ? sortDir : 0;
    });
    return rows;
  }, [tracks, ctx, search, sortKey, sortDir]);

  const page_rows = filtered.slice((page - 1) * PAGE, page * PAGE);

  function sort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === 1 ? -1 : 1));
    else { setSortKey(key); setSortDir(-1); }
    setPage(1);
  }

  function Th({ k, label, align = "left" }: { k: SortKey; label: string; align?: "left" | "right" }) {
    const active = sortKey === k;
    return (
      <th
        onClick={() => sort(k)}
        className={`px-4 py-3 ${align === "right" ? "text-right" : "text-left"} text-xs font-semibold text-[#888] uppercase tracking-wider cursor-pointer select-none hover:text-[#bbb] transition-colors`}
      >
        {label}
        {active && <span className="ml-1 text-[#1db954]">{sortDir === -1 ? "↓" : "↑"}</span>}
      </th>
    );
  }

  return (
    <section className="mb-10">
      <h2 className="mb-3 text-base font-semibold text-[#ff6b35]">
        {t("tables.skipped.heading")}
      </h2>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        {/* Venstre: spillelistefiler + søk */}
        <div className="flex flex-wrap gap-3">
          <select
            value={albumContexts.includes(ctx) ? "" : ctx}
            onChange={(e) => { setCtx(e.target.value); setPage(1); }}
            className="rounded-lg border border-[#2a2a2a] bg-[#1c1c1c] px-3 py-2 text-sm text-[#eee] focus:outline-none focus:border-[#444]"
          >
            <option value="">{t("tables.filters.allPlaylists")}</option>
            {playlistContexts.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <input
            type="text"
            placeholder={t("tables.filters.searchPlaceholder")}
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="rounded-lg border border-[#2a2a2a] bg-[#1c1c1c] px-3 py-2 text-sm text-[#eee] placeholder-[#555] focus:outline-none focus:border-[#444] min-w-56"
          />
        </div>

        {/* Høyre: albumfilter (kun synlig hvis det finnes album) */}
        {albumContexts.length > 0 && (
          <select
            value={albumContexts.includes(ctx) ? ctx : ""}
            onChange={(e) => { setCtx(e.target.value); setPage(1); }}
            className="rounded-lg border border-[#2a2a2a] bg-[#1c1c1c] px-3 py-2 text-sm text-[#eee] focus:outline-none focus:border-[#444]"
          >
            <option value="">{t("tables.filters.allAlbums")}</option>
            {albumContexts.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-[#2a2a2a] bg-[#1c1c1c]">
        <div className="overflow-x-auto">
        <table className="w-full min-w-[640px]">
          <thead className="bg-[#161616]">
            <tr>
              <th className="px-3 py-3 text-right text-xs font-semibold text-[#444] uppercase tracking-wider w-10">#</th>
              <th className="px-4 py-3" />
              <Th k="title" label={t("tables.columns.title")} />
              <Th k="artists" label={t("tables.columns.artist")} />
              <Th k="context_name" label={t("tables.columns.context")} />
              <Th k="skip_count" label={t("tables.columns.skips")} align="right" />
              <Th k="play_count" label={t("tables.columns.plays")} align="right" />
              <Th k="skip_rate" label={t("tables.columns.skipRate")} align="right" />
            </tr>
          </thead>
          <tbody>
            <AnimatePresence mode="sync">
              {page_rows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-sm italic text-[#888]">
                    {t("tables.noData")}
                  </td>
                </tr>
              ) : (
                page_rows.map((t, i) => (
                  <motion.tr
                    key={t.uri + (t.context_name ?? "")}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.15, delay: i * 0.02 }}
                    className="border-t border-[#2a2a2a] hover:bg-white/[0.04] transition-colors duration-150"
                  >
                    <td className="px-3 py-3 text-right text-xs text-[#444] tabular-nums w-10">
                      {(page - 1) * PAGE + i + 1}
                    </td>
                    <td className="px-4 py-3 w-14">
                      <AlbumThumb url={t.image_url} title={t.title} uri={t.uri} />
                    </td>
                    <td className="px-4 py-3 text-sm font-medium" title={t.title ?? undefined}>
                      {t.title ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-sm text-[#999]" title={t.artists ?? undefined}>
                      {t.artists ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-sm text-[#777]" title={t.context_name ?? undefined}>
                      {t.context_name ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-sm font-bold text-[#ff6b35] tabular-nums">{t.skip_count}</span>
                    </td>
                    <td className="px-4 py-3 text-sm text-[#999] text-right tabular-nums">
                      {t.play_count}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <SkipBadge rate={t.skip_rate} />
                    </td>
                  </motion.tr>
                ))
              )}
            </AnimatePresence>
          </tbody>
        </table>
        </div>
      </div>
      <Pagination page={page} total={filtered.length} pageSize={PAGE} onPage={setPage} />
    </section>
  );
}

// ---------------------------------------------------------------------------
// Mest spilte sanger
// ---------------------------------------------------------------------------

export function MostPlayedTable({ tracks }: { tracks: Track[] }) {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  useEffect(() => { setPage(1); }, [tracks]);
  const rows = tracks.slice((page - 1) * PAGE, page * PAGE);

  return (
    <section>
      <h2 className="mb-3 text-base font-semibold text-[#4a9eff]">
        {t("tables.mostPlayed.heading")}
      </h2>
      <div className="overflow-hidden rounded-xl border border-[#2a2a2a] bg-[#1c1c1c]">
        <div className="overflow-x-auto">
        <table className="w-full min-w-[560px]">
          <thead className="bg-[#161616]">
            <tr>
              <th className="px-3 py-3 text-right text-xs font-semibold text-[#777] uppercase tracking-wider w-10">#</th>
              <th className="px-4 py-3" />
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#888] uppercase tracking-wider">{t("tables.columns.title")}</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#888] uppercase tracking-wider">{t("tables.columns.artist")}</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-[#888] uppercase tracking-wider">{t("tables.columns.plays")}</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-[#888] uppercase tracking-wider">{t("tables.columns.skipRate")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t, i) => (
              <tr key={t.uri} className="border-t border-[#2a2a2a] hover:bg-white/[0.04] transition-colors duration-150">
                <td className="px-3 py-3 text-right text-xs text-[#777] tabular-nums w-10">
                  {(page - 1) * PAGE + i + 1}
                </td>
                <td className="px-4 py-3 w-14"><AlbumThumb url={t.image_url} title={t.title} uri={t.uri} /></td>
                <td className="px-4 py-3 text-sm font-medium" title={t.title ?? undefined}>{t.title ?? "—"}</td>
                <td className="px-4 py-3 text-sm text-[#999]" title={t.artists ?? undefined}>{t.artists ?? "—"}</td>
                <td className="px-4 py-3 text-sm text-[#4a9eff] font-semibold text-right tabular-nums">{t.play_count}</td>
                <td className="px-4 py-3 text-right"><SkipBadge rate={t.skip_rate} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>
      <Pagination page={page} total={tracks.length} pageSize={PAGE} onPage={setPage} />
    </section>
  );
}

// ---------------------------------------------------------------------------
// Nesten aldri skippet
// ---------------------------------------------------------------------------

export function MostCompletedTable({ tracks }: { tracks: Track[] }) {
  const { t } = useTranslation();
  return (
    <section>
      <h2 className="mb-1 text-base font-semibold text-[#1db954]">
        {t("tables.mostCompleted.heading")}
      </h2>
      <p className="text-xs text-[#888] mb-3">{t("tables.mostCompleted.subtitle")}</p>
      <div className="overflow-hidden rounded-xl border border-[#2a2a2a] bg-[#1c1c1c]">
        <div className="overflow-x-auto">
        <table className="w-full min-w-[560px]">
          <thead className="bg-[#161616]">
            <tr>
              <th className="px-3 py-3 text-right text-xs font-semibold text-[#777] uppercase tracking-wider w-10">#</th>
              <th className="px-4 py-3" />
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#888] uppercase tracking-wider">{t("tables.columns.title")}</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#888] uppercase tracking-wider">{t("tables.columns.artist")}</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-[#888] uppercase tracking-wider">{t("tables.columns.plays")}</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-[#888] uppercase tracking-wider">{t("tables.columns.skipRate")}</th>
            </tr>
          </thead>
          <tbody>
            {tracks.map((t, i) => (
              <tr key={t.uri} className="border-t border-[#2a2a2a] hover:bg-white/[0.04] transition-colors duration-150">
                <td className="px-3 py-3 text-right text-xs text-[#777] tabular-nums w-10">{i + 1}</td>
                <td className="px-4 py-3 w-14"><AlbumThumb url={t.image_url} title={t.title} uri={t.uri} /></td>
                <td className="px-4 py-3 text-sm font-medium" title={t.title ?? undefined}>{t.title ?? "—"}</td>
                <td className="px-4 py-3 text-sm text-[#999]" title={t.artists ?? undefined}>{t.artists ?? "—"}</td>
                <td className="px-4 py-3 text-sm text-[#1db954] font-semibold text-right tabular-nums">{t.play_count}</td>
                <td className="px-4 py-3 text-right"><SkipBadge rate={t.skip_rate} /></td>
              </tr>
            ))}
            {tracks.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-sm italic text-[#888]">{t("tables.noData")}</td></tr>
            )}
          </tbody>
        </table>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Smart Skipper — forhåndsvisning av kandidater (dry-run)
// ---------------------------------------------------------------------------

export function AutoSkipPreviewTable({
  candidates,
  threshold,
}: {
  candidates: AutoSkipCandidate[];
  threshold: number;
}) {
  const { t } = useTranslation();
  const pct = Math.round(threshold * 100);
  const { data: skipperData } = useQuery({
    queryKey: ["smartSkipper"],
    queryFn: api.smartSkipper,
    staleTime: 10_000,
  });
  const isEnabled = skipperData?.config?.enabled ?? false;
  const isDryRun = skipperData?.config?.dry_run ?? true;

  return (
    <section className="mb-10">
      <h2 className="mb-1 text-base font-semibold flex items-center gap-2" style={{ color: "#f97316" }}>
        <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true" className="flex-shrink-0 opacity-80">
          <circle cx="7.5" cy="7.5" r="6.5" stroke="#f97316" strokeWidth="1.25" />
          <path d="M7.5 5v.5M7.5 7v3" stroke="#f97316" strokeWidth="1.25" strokeLinecap="round" />
        </svg>
        {t("tables.autoSkip.heading")}
      </h2>
      <p className="text-xs text-[#888] mb-4">
        {t("tables.autoSkip.subtitle")}
      </p>
      <div className="overflow-hidden rounded-xl border border-[#2a2a2a] bg-[#1c1c1c]">
        <div className="overflow-x-auto">
        <table className="w-full min-w-[500px]">
          <thead className="bg-[#161616]">
            <tr>
              <th className="px-3 py-3 text-right text-xs font-semibold text-[#777] uppercase tracking-wider w-10">#</th>
              <th className="px-4 py-3 w-14" />
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#888] uppercase tracking-wider">{t("tables.columns.title")}</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#888] uppercase tracking-wider">{t("tables.columns.artist")}</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-[#888] uppercase tracking-wider">{t("tables.columns.skipRate")}</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-[#888] uppercase tracking-wider">Status</th>
            </tr>
          </thead>
          <tbody>
            {candidates.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-sm italic text-[#888]">
                  {t("tables.autoSkip.empty", { pct })}
                </td>
              </tr>
            ) : (
              candidates.map((c, i) => (
                <tr
                  key={c.uri}
                  className="border-t border-[#2a2a2a] hover:bg-white/[0.04] transition-colors duration-150"
                >
                  <td className="px-3 py-3 text-right text-xs text-[#777] tabular-nums w-10">
                    {i + 1}
                  </td>
                  <td className="px-4 py-3 w-14">
                    <AlbumThumb url={c.image_url} title={c.title} uri={c.uri} />
                  </td>
                  <td className="px-4 py-3 text-sm font-medium" title={c.title ?? undefined}>
                    {c.title ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-sm text-[#999]" title={c.artists ?? undefined}>
                    {c.artists ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <SkipBadge rate={c.skip_rate} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    {!isEnabled ? (
                      <span
                        className="inline-block rounded-md px-3 py-1 text-xs font-medium"
                        style={{
                          background: "#2a2a2a",
                          color: "#555",
                          border: "1px solid #333",
                        }}
                        title={t("tables.autoSkip.disabledTooltip")}
                      >
                        {t("tables.autoSkip.disabledButton")}
                      </span>
                    ) : isDryRun ? (
                      <span
                        className="inline-block rounded-md px-3 py-1 text-xs font-medium"
                        style={{
                          background: "#f9731622",
                          color: "#f97316",
                          border: "1px solid #f9731644",
                        }}
                        title={t("tables.autoSkip.dryRunTooltip")}
                      >
                        {t("tables.autoSkip.dryRunButton")}
                      </span>
                    ) : (
                      <span
                        className="inline-block rounded-md px-3 py-1 text-xs font-medium"
                        style={{
                          background: "#1db95422",
                          color: "#1db954",
                          border: "1px solid #1db95444",
                        }}
                        title={t("tables.autoSkip.activeTooltip")}
                      >
                        {t("tables.autoSkip.activeButton")}
                      </span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Mest hørte artister
// ---------------------------------------------------------------------------

export function TopArtistsTable({ artists }: { artists: Artist[] }) {
  const { t } = useTranslation();
  return (
    <section>
      <h2 className="mb-3 text-base font-semibold text-[#4a9eff]">
        {t("tables.topArtists.heading")}
      </h2>
      <div className="overflow-hidden rounded-xl border border-[#2a2a2a] bg-[#1c1c1c]">
        <div className="overflow-x-auto">
        <table className="w-full min-w-[400px]">
          <thead className="bg-[#161616]">
            <tr>
              <th className="px-3 py-3 text-right text-xs font-semibold text-[#777] uppercase tracking-wider w-10">#</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#888] uppercase tracking-wider">{t("tables.topArtists.columns.artist")}</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-[#888] uppercase tracking-wider">{t("tables.topArtists.columns.plays")}</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-[#888] uppercase tracking-wider">{t("tables.topArtists.columns.skipRate")}</th>
            </tr>
          </thead>
          <tbody>
            {artists.map((a, i) => (
              <tr key={a.artists} className="border-t border-[#2a2a2a] hover:bg-white/[0.04] transition-colors duration-150">
                <td className="px-3 py-3 text-right text-xs text-[#444] tabular-nums w-10">{i + 1}</td>
                <td className="px-4 py-3 text-sm font-medium">{a.artists}</td>
                <td className="px-4 py-3 text-sm text-[#4a9eff] font-semibold text-right tabular-nums">{a.play_count}</td>
                <td className="px-4 py-3 text-right"><SkipBadge rate={a.skip_rate} /></td>
              </tr>
            ))}
            {artists.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-sm italic text-[#888]">{t("tables.noData")}</td></tr>
            )}
          </tbody>
        </table>
        </div>
      </div>
    </section>
  );
}
