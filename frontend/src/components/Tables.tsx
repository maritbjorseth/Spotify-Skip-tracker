import React, { useState, useMemo, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { Track, Artist } from "../types";

// ---------------------------------------------------------------------------
// Hjelpefunksjoner
// ---------------------------------------------------------------------------

function skipBadgeColor(rate: number): { bg: string; fg: string } {
  if (rate < 0.1)  return { bg: "#1db95422", fg: "#1db954" };
  if (rate < 0.3)  return { bg: "#8bc34a22", fg: "#8bc34a" };
  if (rate < 0.5)  return { bg: "#ffc10722", fg: "#ffc107" };
  if (rate < 0.8)  return { bg: "#ff6b3522", fg: "#ff6b35" };
  return             { bg: "#ef444422", fg: "#ef4444" };
}

function SkipBadge({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100);
  const { bg, fg } = skipBadgeColor(rate);
  return (
    <span
      className="inline-block rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums"
      style={{ background: bg, color: fg }}
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
        title={`Åpne «${title ?? "sang"}» i Spotify`}
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
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center justify-center gap-3 mt-4">
      <button
        disabled={page <= 1}
        onClick={() => onPage(page - 1)}
        className="rounded-lg border border-[#2a2a2a] bg-[#1c1c1c] px-3 py-1.5 text-sm text-[#ccc] disabled:opacity-30 enabled:hover:border-[#444] transition-colors"
      >
        ← Forrige
      </button>
      <span className="text-sm text-[#666]">
        Side {page} av {totalPages} ({total})
      </span>
      <button
        disabled={page >= totalPages}
        onClick={() => onPage(page + 1)}
        className="rounded-lg border border-[#2a2a2a] bg-[#1c1c1c] px-3 py-1.5 text-sm text-[#ccc] disabled:opacity-30 enabled:hover:border-[#444] transition-colors"
      >
        Neste →
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
        className={`px-4 py-3 ${align === "right" ? "text-right" : "text-left"} text-xs font-semibold text-[#666] uppercase tracking-wider cursor-pointer select-none hover:text-[#999] transition-colors`}
      >
        {label}
        {active && <span className="ml-1 text-[#1db954]">{sortDir === -1 ? "↓" : "↑"}</span>}
      </th>
    );
  }

  return (
    <section className="mb-10">
      <h2 className="mb-3 text-base font-semibold text-[#ff6b35]">Mest skippede sanger</h2>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        {/* Venstre: spillelistefiler + søk */}
        <div className="flex flex-wrap gap-3">
          <select
            value={albumContexts.includes(ctx) ? "" : ctx}
            onChange={(e) => { setCtx(e.target.value); setPage(1); }}
            className="rounded-lg border border-[#2a2a2a] bg-[#1c1c1c] px-3 py-2 text-sm text-[#eee] focus:outline-none focus:border-[#444]"
          >
            <option value="">Alle spillelister</option>
            {playlistContexts.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <input
            type="text"
            placeholder="Søk etter tittel eller artist…"
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
            <option value="">Alle album</option>
            {albumContexts.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-[#2a2a2a] bg-[#1c1c1c]">
        <table className="w-full">
          <thead className="bg-[#161616]">
            <tr>
              <th className="px-3 py-3 text-right text-xs font-semibold text-[#444] uppercase tracking-wider w-10">#</th>
              <th className="px-4 py-3" />
              <Th k="title" label="Tittel" />
              <Th k="artists" label="Artist" />
              <Th k="context_name" label="Spilleliste/album" />
              <Th k="skip_count" label="Skip" align="right" />
              <Th k="play_count" label="Spilt" align="right" />
              <Th k="skip_rate" label="Skip-rate" align="right" />
            </tr>
          </thead>
          <tbody>
            <AnimatePresence mode="sync">
              {page_rows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-sm italic text-[#555]">
                    Ingen data ennå
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
                    <td className="px-3 py-5 text-right text-xs text-[#444] tabular-nums w-10">
                      {(page - 1) * PAGE + i + 1}
                    </td>
                    <td className="px-4 py-5 w-14">
                      <AlbumThumb url={t.image_url} title={t.title} uri={t.uri} />
                    </td>
                    <td className="px-4 py-5 text-sm font-medium" title={t.title ?? undefined}>
                      {t.title ?? "—"}
                    </td>
                    <td className="px-4 py-5 text-sm text-[#999]" title={t.artists ?? undefined}>
                      {t.artists ?? "—"}
                    </td>
                    <td className="px-4 py-5 text-sm text-[#777]" title={t.context_name ?? undefined}>
                      {t.context_name ?? "—"}
                    </td>
                    <td className="px-4 py-5 text-right">
                      <span className="text-sm font-bold text-[#ff6b35]">{t.skip_count}</span>
                    </td>
                    <td className="px-4 py-5 text-sm text-[#999] text-right">
                      {t.play_count}
                    </td>
                    <td className="px-4 py-5 text-right">
                      <SkipBadge rate={t.skip_rate} />
                    </td>
                  </motion.tr>
                ))
              )}
            </AnimatePresence>
          </tbody>
        </table>
      </div>
      <Pagination page={page} total={filtered.length} pageSize={PAGE} onPage={setPage} />
    </section>
  );
}

// ---------------------------------------------------------------------------
// Mest spilte sanger
// ---------------------------------------------------------------------------

export function MostPlayedTable({ tracks }: { tracks: Track[] }) {
  const [page, setPage] = useState(1);
  useEffect(() => { setPage(1); }, [tracks]);
  const rows = tracks.slice((page - 1) * PAGE, page * PAGE);

  return (
    <section>
      <h2 className="mb-3 text-base font-semibold text-[#4a9eff]">Mest spilt totalt</h2>
      <div className="overflow-hidden rounded-xl border border-[#2a2a2a] bg-[#1c1c1c]">
        <table className="w-full">
          <thead className="bg-[#161616]">
            <tr>
              <th className="px-3 py-3 text-right text-xs font-semibold text-[#444] uppercase tracking-wider w-10">#</th>
              <th className="px-4 py-3" />
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider">Tittel</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider">Artist</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-[#666] uppercase tracking-wider">Spilt</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-[#666] uppercase tracking-wider">Skip-rate</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t, i) => (
              <tr key={t.uri} className="border-t border-[#2a2a2a] hover:bg-white/[0.04] transition-colors duration-150">
                <td className="px-3 py-5 text-right text-xs text-[#444] tabular-nums w-10">
                  {(page - 1) * PAGE + i + 1}
                </td>
                <td className="px-4 py-5 w-14"><AlbumThumb url={t.image_url} title={t.title} uri={t.uri} /></td>
                <td className="px-4 py-5 text-sm font-medium" title={t.title ?? undefined}>{t.title ?? "—"}</td>
                <td className="px-4 py-5 text-sm text-[#999]" title={t.artists ?? undefined}>{t.artists ?? "—"}</td>
                <td className="px-4 py-5 text-sm text-[#4a9eff] font-semibold text-right">{t.play_count}</td>
                <td className="px-4 py-5 text-right"><SkipBadge rate={t.skip_rate} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={page} total={tracks.length} pageSize={PAGE} onPage={setPage} />
    </section>
  );
}

// ---------------------------------------------------------------------------
// Nesten aldri skippet
// ---------------------------------------------------------------------------

export function MostCompletedTable({ tracks }: { tracks: Track[] }) {
  return (
    <section>
      <h2 className="mb-1 text-base font-semibold text-[#1db954]">Sanger du nesten aldri skipper</h2>
      <p className="text-xs text-[#555] mb-3">Låter du som regel lytter til helt ferdig.</p>
      <div className="overflow-hidden rounded-xl border border-[#2a2a2a] bg-[#1c1c1c]">
        <table className="w-full">
          <thead className="bg-[#161616]">
            <tr>
              <th className="px-3 py-3 text-right text-xs font-semibold text-[#444] uppercase tracking-wider w-10">#</th>
              <th className="px-4 py-3" />
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider">Tittel</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider">Artist</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-[#666] uppercase tracking-wider">Spilt</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-[#666] uppercase tracking-wider">Skip-rate</th>
            </tr>
          </thead>
          <tbody>
            {tracks.map((t, i) => (
              <tr key={t.uri} className="border-t border-[#2a2a2a] hover:bg-white/[0.04] transition-colors duration-150">
                <td className="px-3 py-5 text-right text-xs text-[#444] tabular-nums w-10">{i + 1}</td>
                <td className="px-4 py-5 w-14"><AlbumThumb url={t.image_url} title={t.title} uri={t.uri} /></td>
                <td className="px-4 py-5 text-sm font-medium" title={t.title ?? undefined}>{t.title ?? "—"}</td>
                <td className="px-4 py-5 text-sm text-[#999]" title={t.artists ?? undefined}>{t.artists ?? "—"}</td>
                <td className="px-4 py-5 text-sm text-[#1db954] font-semibold text-right">{t.play_count}</td>
                <td className="px-4 py-5 text-right"><SkipBadge rate={t.skip_rate} /></td>
              </tr>
            ))}
            {tracks.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-sm italic text-[#555]">Ingen data ennå</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Mest hørte artister
// ---------------------------------------------------------------------------

export function TopArtistsTable({ artists }: { artists: Artist[] }) {
  return (
    <section>
      <h2 className="mb-3 text-base font-semibold text-[#4a9eff]">Artister du hører mest på</h2>
      <div className="overflow-hidden rounded-xl border border-[#2a2a2a] bg-[#1c1c1c]">
        <table className="w-full">
          <thead className="bg-[#161616]">
            <tr>
              <th className="px-3 py-3 text-right text-xs font-semibold text-[#444] uppercase tracking-wider w-10">#</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider">Artist</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-[#666] uppercase tracking-wider">Totalt spilt</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-[#666] uppercase tracking-wider">Skip-rate</th>
            </tr>
          </thead>
          <tbody>
            {artists.map((a, i) => (
              <tr key={a.artists} className="border-t border-[#2a2a2a] hover:bg-white/[0.04] transition-colors duration-150">
                <td className="px-3 py-5 text-right text-xs text-[#444] tabular-nums w-10">{i + 1}</td>
                <td className="px-4 py-5 text-sm font-medium">{a.artists}</td>
                <td className="px-4 py-5 text-sm text-[#4a9eff] font-semibold text-right">{a.play_count}</td>
                <td className="px-4 py-5 text-right"><SkipBadge rate={a.skip_rate} /></td>
              </tr>
            ))}
            {artists.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-sm italic text-[#555]">Ingen data ennå</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
