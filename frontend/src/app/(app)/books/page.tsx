"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { useRunStream } from "@/hooks/useRunStream";
import { api, formatINR, type ChartAccount, type TxnPage } from "@/lib/api";

const STATUS_STYLES: Record<string, string> = {
  matched: "bg-emerald-50 text-emerald-700",
  unmatched: "bg-amber-50 text-amber-700",
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

  if (txn.direction !== "dr") return <span className="text-slate-300">—</span>;
  return (
    <span className="inline-flex items-center gap-1">
      <select
        value={txn.category_code ?? ""}
        onChange={(e) => e.target.value && correct.mutate(e.target.value)}
        disabled={correct.isPending}
        className={`max-w-36 rounded-md border px-1.5 py-0.5 text-xs ${
          txn.category_code ? "border-slate-200 text-slate-700" : "border-amber-300 text-amber-700"
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
        <span className="text-[10px] uppercase text-slate-400" title="who categorized this">
          {txn.category_source}
        </span>
      )}
    </span>
  );
}

export default function BooksPage() {
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const { events, done } = useRunStream(runId);

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

  async function upload(file: File) {
    setError(null);
    setUploading(true);
    try {
      const result = await api.importStatement(file);
      setRunId(result.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "upload failed");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  const counts = txns.data?.counts ?? {};

  return (
    <div className="max-w-4xl">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Books</h1>
          <p className="mt-1 text-sm text-slate-500">
            Upload a bank statement; the reconciliation agent matches it against open invoices.
            Rules-only in Phase 1 — anything ambiguous stays for review.
          </p>
        </div>
        <div>
          <input
            ref={fileInput}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
          />
          <button
            onClick={() => fileInput.current?.click()}
            disabled={uploading}
            className="rounded-md bg-teal-brand px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {uploading ? "Uploading…" : "Upload statement"}
          </button>
        </div>
      </div>

      {error && <p className="mt-4 text-sm text-red-600" role="alert">{error}</p>}

      {runId && (
        <section className="mt-6 rounded-xl border bg-white p-5 shadow-sm">
          <h2 className="text-sm font-medium text-slate-700">
            Reconciliation run {done ? "— complete" : "— live"}
          </h2>
          <ul className="mt-3 space-y-1">
            {events.map((evt, i) => (
              <li key={i} className="flex items-center gap-2 text-sm">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${
                    evt.event.startsWith("run.done")
                      ? "bg-emerald-500"
                      : evt.status === "finished"
                        ? "bg-teal-brand"
                        : evt.status === "failed"
                          ? "bg-red-500"
                          : "bg-amber-400"
                  }`}
                />
                <span className="font-mono text-xs text-slate-500">
                  {evt.name ?? evt.event}
                </span>
                <span className="text-slate-600">{evt.summary ?? ""}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="mt-6">
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <span className="font-medium text-slate-700">Transactions</span>
          <span>{counts.matched ?? 0} matched</span>
          <span>·</span>
          <span>{counts.unmatched ?? 0} for review</span>
        </div>

        {txns.isLoading && (
          <div className="mt-3 space-y-2">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-10 animate-pulse rounded-md bg-slate-100" />
            ))}
          </div>
        )}
        {txns.isError && (
          <p className="mt-3 text-sm text-red-600">Could not load transactions.</p>
        )}
        {txns.data && txns.data.items.length === 0 && (
          <div className="mt-3 rounded-xl border border-dashed bg-white p-10 text-center text-sm text-slate-500">
            No transactions yet — upload a statement to begin.
            <br />
            Dev fixture: <code>scripts/fixtures/statement_apr2026.csv</code>
          </div>
        )}
        {txns.data && txns.data.items.length > 0 && (
          <div className="mt-3 overflow-hidden rounded-xl border bg-white shadow-sm">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Date</th>
                  <th className="px-4 py-2">Narration</th>
                  <th className="px-4 py-2 text-right">Amount</th>
                  <th className="px-4 py-2">Category</th>
                  <th className="px-4 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {txns.data.items.map((t) => (
                  <tr key={t.id}>
                    <td className="px-4 py-2 text-slate-500">{t.value_date}</td>
                    <td className="max-w-md truncate px-4 py-2" title={t.narration}>
                      {t.narration}
                    </td>
                    <td
                      className={`px-4 py-2 text-right font-mono ${
                        t.direction === "cr" ? "text-emerald-700" : "text-slate-700"
                      }`}
                    >
                      {t.direction === "cr" ? "+" : "−"}
                      {formatINR(t.amount_paise)}
                    </td>
                    <td className="px-4 py-2">
                      <CategoryCell txn={t} accounts={accounts.data ?? []} />
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          STATUS_STYLES[t.match_status] ?? "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {t.match_status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
