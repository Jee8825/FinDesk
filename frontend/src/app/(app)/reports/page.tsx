"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { WhyDrawer } from "@/components/WhyDrawer";
import { api, formatINR, type WhyRef } from "@/lib/api";

const PERIODS = ["2026-04", "2026-05", "2026-06", "2026-07"];

function WhyButton({ refs, onOpen }: { refs: WhyRef[]; onOpen: (refs: WhyRef[]) => void }) {
  if (!refs.length) return null;
  return (
    <button
      onClick={() => onOpen(refs)}
      className="rounded-full border border-teal-brand/40 px-2 py-0.5 text-xs font-medium text-teal-brand hover:bg-teal-brand hover:text-white"
      title="show the evidence trail"
    >
      Why?
    </button>
  );
}

export default function ReportsPage() {
  const [period, setPeriod] = useState("2026-04");
  const [whyRefs, setWhyRefs] = useState<WhyRef[] | null>(null);
  const report = useQuery({
    queryKey: ["month-end", period],
    queryFn: () => api.monthEndReport(period),
  });

  const r = report.data;

  return (
    <div className="max-w-4xl">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Month-end report</h1>
          <p className="mt-1 text-sm text-slate-500">
            Every number can answer “Why?” — down to the statement line and the run that posted
            it.
          </p>
        </div>
        <select
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          className="rounded-md border px-3 py-2 text-sm"
          aria-label="report period"
        >
          {PERIODS.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
      </div>

      {report.isLoading && (
        <div className="mt-6 space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-xl bg-slate-100" />
          ))}
        </div>
      )}
      {report.isError && <p className="mt-6 text-sm text-red-600">Could not build the report.</p>}

      {r && (
        <>
          <section className="mt-6 rounded-xl border bg-white p-5 shadow-sm">
            <h2 className="text-sm font-medium text-slate-700">Summary</h2>
            <ul className="mt-2 space-y-1 text-sm text-slate-600">
              {r.narrative.map((line, i) => (
                <li key={i}>• {line}</li>
              ))}
            </ul>
          </section>

          <section className="mt-4 grid grid-cols-3 gap-3">
            {(
              [
                ["Inflow", r.cash.inflow_paise, "text-emerald-700"],
                ["Outflow", r.cash.outflow_paise, "text-slate-700"],
                ["Net", r.cash.net_paise, r.cash.net_paise >= 0 ? "text-emerald-700" : "text-red-600"],
              ] as const
            ).map(([label, value, cls]) => (
              <div key={label} className="rounded-xl border bg-white p-4 shadow-sm">
                <p className="text-xs uppercase text-slate-400">{label}</p>
                <p className={`mt-1 font-mono text-lg font-semibold ${cls}`}>
                  {formatINR(value)}
                </p>
              </div>
            ))}
          </section>

          <section className="mt-4 rounded-xl border bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium text-slate-700">Spend by category</h2>
              <span className="text-xs text-slate-400">{period}</span>
            </div>
            <table className="mt-3 w-full text-sm">
              <tbody className="divide-y">
                {r.cash.by_category.map((c) => (
                  <tr key={c.category_code}>
                    <td className="py-1.5">{c.category_name}</td>
                    <td className="py-1.5 text-right font-mono">{formatINR(c.amount_paise)}</td>
                    <td className="w-20 py-1.5 text-right text-xs text-slate-400">
                      {c.count} txn{c.count > 1 ? "s" : ""}
                    </td>
                    <td className="w-14 py-1.5 text-right">
                      <WhyButton refs={c.why} onOpen={setWhyRefs} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="mt-4 grid grid-cols-2 gap-3">
            <div className="rounded-xl border bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-medium text-slate-700">Reconciliation</h2>
                <WhyButton refs={r.reconciliation.why} onOpen={setWhyRefs} />
              </div>
              <p className="mt-2 text-sm text-slate-600">
                {r.reconciliation.matched}/{r.reconciliation.transactions} matched
                {r.reconciliation.tds_matches > 0 &&
                  ` (${r.reconciliation.tds_matches} TDS-adjusted)`}
                ; {r.reconciliation.unmatched} for review
              </p>
              <p className="mt-1 font-mono text-sm text-slate-700">
                {formatINR(r.reconciliation.matched_amount_paise)} posted
              </p>
            </div>
            <div className="rounded-xl border bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-medium text-slate-700">Anomalies</h2>
                <WhyButton refs={r.anomalies.why} onOpen={setWhyRefs} />
              </div>
              <p className="mt-2 text-sm text-slate-600">{r.anomalies.open} open</p>
              <p className="mt-1 font-mono text-sm text-emerald-700">
                {formatINR(r.anomalies.recoverable_paise)} recoverable
              </p>
            </div>
          </section>

          <section className="mt-4 rounded-xl border bg-white p-5 shadow-sm">
            <h2 className="text-sm font-medium text-slate-700">
              Receivables aging — {formatINR(r.receivables.overdue_total_paise)} overdue
            </h2>
            {r.receivables.aging.length === 0 && (
              <p className="mt-2 text-sm text-slate-500">Nothing overdue. Rare air.</p>
            )}
            {r.receivables.aging.map((bucket) => (
              <div key={bucket.bucket} className="mt-3">
                <p className="text-xs font-medium uppercase text-slate-400">
                  {bucket.bucket} days · {formatINR(bucket.amount_paise)}
                </p>
                <table className="mt-1 w-full text-sm">
                  <tbody className="divide-y">
                    {bucket.items.map((item) => (
                      <tr key={item.invoice_number}>
                        <td className="py-1">{item.client}</td>
                        <td className="py-1 text-slate-500">{item.invoice_number}</td>
                        <td className="py-1 text-right font-mono">
                          {formatINR(item.amount_paise)}
                        </td>
                        <td className="w-24 py-1 text-right text-xs text-slate-400">
                          {item.days_overdue}d overdue
                        </td>
                        <td className="w-14 py-1 text-right">
                          <WhyButton refs={item.why} onOpen={setWhyRefs} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </section>
        </>
      )}

      {whyRefs && <WhyDrawer refs={whyRefs} onClose={() => setWhyRefs(null)} />}
    </div>
  );
}
