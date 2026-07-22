"use client";
// Transactions — "Master table" (wireframe Transactions A): normalized feed,
// server state chips, per-row Why?, inline category correction, imports.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Search, Upload } from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { WhyDrawer } from "@/components/WhyDrawer";
import {
  Card,
  EmptyState,
  ErrorNote,
  GhostBtn,
  PageShell,
  Pill,
  PrimaryBtn,
  Skeleton,
} from "@/components/ui";
import { useRunStream } from "@/hooks/useRunStream";
import { api, formatINR, type ChartAccount, type TxnPage, type WhyRef } from "@/lib/api";

const STATE_TONE: Record<string, "good" | "warn" | "bad" | "neutral"> = {
  matched: "good",
  unmatched: "warn",
};

function CategoryCell({
  txn,
  accounts,
}: {
  txn: TxnPage["items"][number];
  accounts: ChartAccount[];
}) {
  const queryClient = useQueryClient();
  const correct = useMutation({
    mutationFn: (code: string) => api.correctCategory(txn.id, code),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["transactions"] }),
  });

  if (txn.direction !== "dr") return <span className="text-line">—</span>;
  return (
    <span className="inline-flex items-center gap-1.5">
      <select
        value={txn.category_code ?? ""}
        onChange={(e) => e.target.value && correct.mutate(e.target.value)}
        disabled={correct.isPending}
        className={`max-w-36 rounded-lg border bg-white/[0.05] px-1.5 py-0.5 text-xs transition-colors ${
          txn.category_code ? "border-line text-mute" : "border-accent/50 text-accent"
        }`}
        aria-label="expense category"
      >
        <option value="">uncategorized</option>
        {accounts.map((a) => (
          <option key={a.code} value={a.code}>
            {a.name}
          </option>
        ))}
      </select>
      {txn.category_source && (
        <span className="mono-label text-faint" title="who categorized this">
          {txn.category_source}
        </span>
      )}
    </span>
  );
}

export default function BooksPage() {
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const onboardInput = useRef<HTMLInputElement>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("all");
  const [q, setQ] = useState("");
  const [whyRefs, setWhyRefs] = useState<WhyRef[] | null>(null);
  const { done } = useRunStream(runId);

  const txns = useQuery({
    queryKey: ["transactions"],
    queryFn: () => api.transactions(),
    refetchInterval: runId && !done ? 2000 : false,
  });
  const accounts = useQuery({
    queryKey: ["chart-of-accounts"],
    queryFn: () => api.chartOfAccounts(),
    staleTime: 60_000,
  });

  async function onboard(file: File) {
    setError(null);
    setNote(null);
    try {
      const r = await api.onboardInvoices(file);
      setNote(
        `Imported ${r.invoices_created} invoices (${r.source_hint}), ${r.counterparties_created} new clients, ${r.observations_seeded} payment behaviors remembered.`,
      );
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "import failed");
    } finally {
      if (onboardInput.current) onboardInput.current.value = "";
    }
  }

  async function upload(file: File) {
    setError(null);
    setUploading(true);
    try {
      const result = await api.importStatement(file);
      setRunId(result.run_id);
      setNote("Statement queued — the reconciliation agent is on it. Watch it live in Reconciliation.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "upload failed");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  const counts = txns.data?.counts ?? {};
  const chips = [
    { key: "all", label: "All states" },
    { key: "matched", label: `Matched ${counts.matched ?? 0}` },
    { key: "unmatched", label: `Exceptions ${counts.unmatched ?? 0}` },
  ];

  const rows = useMemo(() => {
    let items = txns.data?.items ?? [];
    if (filter !== "all") items = items.filter((t) => t.match_status === filter);
    if (q.trim()) {
      const needle = q.trim().toLowerCase();
      items = items.filter(
        (t) =>
          t.narration.toLowerCase().includes(needle) ||
          (t.counterparty_hint ?? "").toLowerCase().includes(needle) ||
          String(t.amount_paise / 100).includes(needle),
      );
    }
    return items;
  }, [txns.data, filter, q]);

  return (
    <PageShell
      title="Transactions"
      subtitle="Normalized feed, match states, exception list"
      annotation="GET /books/transactions?state= · cursor pagination"
      actions={
        <>
          <input
            ref={onboardInput}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && onboard(e.target.files[0])}
          />
          <GhostBtn onClick={() => onboardInput.current?.click()} title="Tally/Zoho invoice export — seeds payment history into memory">
            Import invoices
          </GhostBtn>
          <input
            ref={fileInput}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
          />
          <PrimaryBtn onClick={() => fileInput.current?.click()} disabled={uploading}>
            <Upload size={14} /> {uploading ? "Uploading…" : "Upload statement"}
          </PrimaryBtn>
        </>
      }
    >
      <div className="flex flex-wrap items-center gap-3">
        <label className="relative">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search narration, vendor, amount…"
            className="w-72 rounded-full border border-line bg-white/[0.05] py-2 pl-8 pr-4 text-[13px] shadow-none outline-none transition-colors placeholder:text-faint focus:border-accent/60"
          />
        </label>
        {chips.map((c) => (
          <motion.button
            key={c.key}
            whileTap={{ scale: 0.95 }}
            onClick={() => setFilter(c.key)}
            className={`rounded-full border px-4 py-1.5 text-[13px] font-semibold transition-colors ${
              filter === c.key
                ? "border-ink bg-ink text-cream"
                : c.key === "unmatched"
                  ? "border-accent/40 bg-white/[0.05] text-accent"
                  : "border-line bg-white/[0.05] text-mute hover:border-faint"
            }`}
          >
            {c.label}
          </motion.button>
        ))}
        <span className="mono-annot ml-auto hidden lg:block">◇ state chips = server filter</span>
      </div>

      {error && <ErrorNote>{error}</ErrorNote>}
      <AnimatePresence>
        {note && (
          <motion.p
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-4 rounded-xl border border-moss/25 bg-moss/10 px-4 py-2.5 text-sm font-medium text-moss"
          >
            {note}
          </motion.p>
        )}
      </AnimatePresence>

      {txns.isLoading && (
        <div className="mt-5 space-y-2">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-12" />
          ))}
        </div>
      )}
      {txns.isError && <ErrorNote>Could not load transactions.</ErrorNote>}
      {txns.data && rows.length === 0 && (
        <div className="mt-5">
          <EmptyState hint="dev fixture: scripts/fixtures/statement_apr2026.csv">
            {q || filter !== "all"
              ? "Nothing matches this filter."
              : "No transactions yet — upload a statement to begin."}
          </EmptyState>
        </div>
      )}

      {rows.length > 0 && (
        <Card className="mt-5 overflow-x-auto !p-0">
          <table className="w-full min-w-[900px] text-sm">
            <thead>
              <tr className="border-b border-line2 text-left">
                {["date", "narration (normalized)", "counterparty", "amount", "match state", ""].map((h, i) => (
                  <th key={i} className={`mono-label px-5 py-3 font-normal text-faint ${h === "amount" ? "text-right" : ""}`}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <motion.tbody initial="initial" animate="animate" variants={{ animate: { transition: { staggerChildren: 0.03 } } }}>
              {rows.map((t) => (
                <motion.tr
                  key={t.id}
                  variants={{ initial: { opacity: 0 }, animate: { opacity: 1 } }}
                  className="border-b border-line2/70 transition-colors last:border-0 hover:bg-white/[0.06]"
                >
                  <td className="whitespace-nowrap px-5 py-3 font-mono text-xs text-faint">
                    {t.value_date.slice(5)}
                  </td>
                  <td className="max-w-md truncate px-5 py-3 font-medium text-ink" title={t.narration}>
                    {t.narration}
                  </td>
                  <td className="px-5 py-3 font-semibold text-mute">{t.counterparty_hint ?? "—"}</td>
                  <td
                    className={`whitespace-nowrap px-5 py-3 text-right font-mono font-semibold ${
                      t.direction === "cr" ? "text-moss" : "text-ink"
                    }`}
                  >
                    {t.direction === "cr" ? "+" : "−"}
                    {formatINR(t.amount_paise)}
                  </td>
                  <td className="px-5 py-3">
                    <Pill tone={STATE_TONE[t.match_status] ?? "neutral"}>{t.match_status}</Pill>
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center justify-end gap-3">
                      <CategoryCell txn={t} accounts={accounts.data ?? []} />
                      <button
                        onClick={() => setWhyRefs([{ kind: "transaction", id: t.id }])}
                        className="whitespace-nowrap text-[13px] font-bold text-accent transition-transform hover:translate-x-0.5"
                      >
                        Why? →
                      </button>
                    </div>
                  </td>
                </motion.tr>
              ))}
            </motion.tbody>
          </table>
        </Card>
      )}
      {txns.data && (
        <p className="mono-annot mt-3">
          showing {rows.length} of {txns.data.items.length} loaded · {counts.matched ?? 0} matched · {counts.unmatched ?? 0} for review
        </p>
      )}

      {whyRefs && <WhyDrawer refs={whyRefs} onClose={() => setWhyRefs(null)} />}
    </PageShell>
  );
}
