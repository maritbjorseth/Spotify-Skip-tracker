import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { Track, Artist } from "../types";

// ---------------------------------------------------------------------------
// Hjelpefunksjoner
// ---------------------------------------------------------------------------

function SkipBadge({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100);
  const high = rate >= 0.5;
  return (
    <span
      className="inline-block rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums"
      style={{
        background: high ? "#ff6b3522" : "#1db95422",
        color: high ? "#ff6b35" : "#1db954",
      }}
    >
      {pct}%
    </span>
  );
}

function AlbumThumb({ url, title }: { url: string | null; title: string | null }) {
  if (!url)
    return (
      <div className="flex aspect-square size-12 items-center justify-center rounded-md bg-[#2a2a2a] flex-shrink-0">
        <svg className="h-5 w-5 text-[#555]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 19V6l12-3v13M9 19a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm12-3a3 3 0 1 1-6 0 3 3 0 0 1 6 0ZM9 7l12-3" />
        </svg>
      </div>
    );
  return (
    <img
      src={url}
      alt={title ?? ""}
      loading="lazy"
      className="aspect-square size-12 rounded-md object-cover flex-shrink-0"
    />
  );
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
  contexts,
}: {
  tracks: Track[];
  contexts: string[];
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
      const av = a[sortKey] ?? "";
      const bv = b[sortKey] ?? "";
      return av < bv ? -sortDir : av > bv ? sortDir : 0;
    });
    return rows;
  }, [tracks, ctx, search, sortKey, sortDir]);

  const page_rows = filtered.slice((page - 1) * PAGE, page * PAGE);

  function sort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === 1 ? -1 : 1));
    else { setSortKey(key); setSortDir(-1); }
    setPage(1);
  }

  function Th({ k, label }: { k: SortKey; label: string }) {
    const active = sortKey === k;
    return (
      <th
        onClick={() => sort(k)}
        className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider cursor-pointer select-none hover:text-[#999] transition-colors"
      >
        {label}
        {active && <span className="ml-1 text-[#1db954]">{sortDir === -1 ? "↓" : "↑"}</span>}
      </th>
    );
  }

  return (
    <section className="mb-10">
      <h2 className="mb-3 text-base font-semibold text-[#ff6b35]">Mest skippede sanger</h2>

      <div className="mb-4 flex flex-wrap gap-3">
        <select
          value={ctx}
          onChange={(e) => { setCtx(e.target.value); setPage(1); }}
          className="rounded-lg border border-[#2a2a2a] bg-[#1c1c1c] px-3 py-2 text-sm text-[#eee] focus:outline-none focus:border-[#444]"
        >
          <option value="">Alle spillelister/album</option>
          {contexts.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <input
          type="text"
          placeholder="Søk etter tittel eller artist…"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="rounded-lg border border-[#2a2a2a] bg-[#1c1c1c] px-3 py-2 text-sm text-[#eee] placeholder-[#555] focus:outline-none focus:border-[#444] min-w-56"
        />
      </div>

      <div className="overflow-hidden rounded-xl border border-[#2a2a2a] bg-[#1c1c1c]">
        <table className="w-full">
          <thead className="bg-[#161616]">
            <tr>
              <th className="px-4 py-3" />
              <Th k="title" label="Tittel" />
              <Th k="artists" label="Artist" />
              <Th k="context_name" label="Spilleliste/album" />
              <Th k="skip_count" label="Skip" />
              <Th k="play_count" label="Spilt" />
              <Th k="skip_rate" label="Skip-rate" />
            </tr>
          </thead>
          <tbody>
            <AnimatePresence mode="sync">
              {page_rows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-sm italic text-[#555]">
                    Ingen data ennå
                  </td>
                </tr>
              ) : (
                page_rows.map((t, i) => (
                  <motion.tr
                    key={t.uri + i}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.15, delay: i * 0.02 }}
                    className="border-t border-[#2a2a2a] hover:bg-[#232323] transition-colors"
                  >
                    <td className="px-4 py-2.5">
                      <AlbumThumb url={t.image_url} title={t.title} />
                    </td>
                    <td className="px-4 py-2.5 text-sm font-medium" title={t.title ?? undefined}>
                      {t.title ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 text-sm text-[#999]" title={t.artists ?? undefined}>
                      {t.artists ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 text-sm text-[#777]" title={t.context_name ?? undefined}>
                      {t.context_name ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <span className="text-sm font-bold text-[#ff6b35]">{t.skip_count}</span>
                    </td>
                    <td className="px-4 py-2.5 text-sm text-[#999] text-center">
                      {t.play_count}
                    </td>
                    <td className="px-4 py-2.5">
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
  const rows = tracks.slice((page - 1) * PAGE, page * PAGE);

  return (
    <section>
      <h2 className="mb-3 text-base font-semibold text-[#4a9eff]">Mest spilt totalt</h2>
      <div className="overflow-hidden rounded-xl border border-[#2a2a2a] bg-[#1c1c1c]">
        <table className="w-full">
          <thead className="bg-[#161616]">
            <tr>
              <th className="px-4 py-3" />
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider">Tittel</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider">Artist</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider">Spilt</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider">Skip-rate</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t, i) => (
              <tr key={t.uri + i} className="border-t border-[#2a2a2a] hover:bg-[#232323] transition-colors">
                <td className="px-4 py-2.5"><AlbumThumb url={t.image_url} title={t.title} /></td>
                <td className="px-4 py-2.5 text-sm font-medium" title={t.title ?? undefined}>{t.title ?? "—"}</td>
                <td className="px-4 py-2.5 text-sm text-[#999]" title={t.artists ?? undefined}>{t.artists ?? "—"}</td>
                <td className="px-4 py-2.5 text-sm text-[#4a9eff] font-semibold">{t.play_count}</td>
                <td className="px-4 py-2.5"><SkipBadge rate={t.skip_rate} /></td>
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
      <h2 className="mb-3 text-base font-semibold text-[#1db954]">Sanger du nesten aldri skipper</h2>
      <div className="overflow-hidden rounded-xl border border-[#2a2a2a] bg-[#1c1c1c]">
        <table className="w-full">
          <thead className="bg-[#161616]">
            <tr>
              <th className="px-4 py-3" />
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider">Tittel</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider">Artist</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider">Spilt</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider">Skip-rate</th>
            </tr>
          </thead>
          <tbody>
            {tracks.map((t, i) => (
              <tr key={t.uri + i} className="border-t border-[#2a2a2a] hover:bg-[#232323] transition-colors">
                <td className="px-4 py-2.5"><AlbumThumb url={t.image_url} title={t.title} /></td>
                <td className="px-4 py-2.5 text-sm font-medium" title={t.title ?? undefined}>{t.title ?? "—"}</td>
                <td className="px-4 py-2.5 text-sm text-[#999]" title={t.artists ?? undefined}>{t.artists ?? "—"}</td>
                <td className="px-4 py-2.5 text-sm text-[#1db954] font-semibold">{t.play_count}</td>
                <td className="px-4 py-2.5"><SkipBadge rate={t.skip_rate} /></td>
              </tr>
            ))}
            {tracks.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-sm italic text-[#555]">Ingen data ennå</td></tr>
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
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider">Artist</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider">Totalt spilt</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#666] uppercase tracking-wider">Skip-rate</th>
            </tr>
          </thead>
          <tbody>
            {artists.map((a, i) => (
              <tr key={i} className="border-t border-[#2a2a2a] hover:bg-[#232323] transition-colors">
                <td className="px-4 py-2.5 text-sm font-medium">{a.artists}</td>
                <td className="px-4 py-2.5 text-sm text-[#4a9eff] font-semibold">{a.play_count}</td>
                <td className="px-4 py-2.5"><SkipBadge rate={a.skip_rate} /></td>
              </tr>
            ))}
            {artists.length === 0 && (
              <tr><td colSpan={3} className="px-4 py-8 text-center text-sm italic text-[#555]">Ingen data ennå</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
