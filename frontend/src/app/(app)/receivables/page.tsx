"use client";

import { useQuery } from "@tanstack/react-query";

import { api, formatINR, type RadarItem } from "@/lib/api";

const RUNG_STYLES: Record<string, string> = {
  none: "bg-slate-100 text-slate-600",
  nudge: "bg-amber-50 text-amber-700",
  reminder: "bg-orange-50 text-orange-700",
  act_letter: "bg-red-50 text-red-700",
  samadhaan_prep: "bg-red-100 text-red-800",
};

const RUNG_LABELS: Record<string, string> = {
  none: "within 45 days",
  nudge: "nudge",
  reminder: "reminder",
  act_letter: "Act letter",
  samadhaan_prep: "Samadhaan prep",
};

function ClockCard({ item }: { item: RadarItem }) {
  const overdue = item.clock.overdue_days > 0;
  return (
    <li className="rounded-xl border bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-ink">
            {item.client}
            <span className="ml-2 text-slate-400">{item.invoice_number}</span>
          </p>
          <p className="mt-1 font-mono text-lg font-semibold text-slate-800">
            {formatINR(item.amount_paise)}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            statutory due {item.clock.statutory_due_date.slice(0, 10)} (MSME Act 45-day)
            {item.predicted_payment_date && (
              <>
                {" · "}
                <span title={`from ${item.behavior_observations} remembered payments`}>
                  likely pays ~{item.predicted_payment_date}
                  {item.avg_days_late != null && ` (runs ${item.avg_days_late}d late)`}
                </span>
              </>
            )}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              RUNG_STYLES[item.clock.escalation_level] ?? RUNG_STYLES.none
            }`}
          >
            {RUNG_LABELS[item.clock.escalation_level] ?? item.clock.escalation_level}
          </span>
          {overdue ? (
            <>
              <p className="mt-2 text-sm font-semibold text-red-600">
                {item.clock.overdue_days} days past statutory due
              </p>
              <p className="mt-1 text-xs text-slate-500">
                interest accrued{" "}
                <span className="font-mono font-medium text-slate-700">
                  {formatINR(item.clock.accrued_interest_paise)}
                </span>{" "}
                @ {item.clock.annual_rate_bps / 100}% p.a.
              </p>
            </>
          ) : (
            <p className="mt-2 text-sm text-emerald-600">on the clock</p>
          )}
        </div>
      </div>
    </li>
  );
}

export default function ReceivablesPage() {
  const radar = useQuery({ queryKey: ["radar"], queryFn: () => api.radar() });
  const r = radar.data;

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-semibold text-ink">Receivables radar</h1>
      <p className="mt-1 text-sm text-slate-500">
        Every open invoice on its 45-day statutory clock, with the interest the MSME Act says
        you&apos;re owed — and when each client will actually pay, from memory.
      </p>

      {r && r.totals.overdue_paise > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-3">
          <div className="rounded-xl border bg-white p-4 shadow-sm">
            <p className="text-xs uppercase text-slate-400">Past statutory due</p>
            <p className="mt-1 font-mono text-lg font-semibold text-red-600">
              {formatINR(r.totals.overdue_paise)}
            </p>
          </div>
          <div className="rounded-xl border bg-white p-4 shadow-sm">
            <p className="text-xs uppercase text-slate-400">Interest legally accrued</p>
            <p className="mt-1 font-mono text-lg font-semibold text-slate-800">
              {formatINR(r.totals.accrued_interest_paise)}
            </p>
          </div>
        </div>
      )}

      {radar.isLoading && (
        <div className="mt-6 space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-28 animate-pulse rounded-xl bg-slate-100" />
          ))}
        </div>
      )}
      {radar.isError && <p className="mt-6 text-sm text-red-600">Could not load the radar.</p>}
      {r && r.items.length === 0 && (
        <div className="mt-6 rounded-xl border border-dashed bg-white p-10 text-center text-sm text-slate-500">
          No open receivables — everything is collected.
        </div>
      )}
      {r && r.items.length > 0 && (
        <ul className="mt-6 space-y-3">
          {r.items.map((item) => (
            <ClockCard key={item.invoice_id} item={item} />
          ))}
        </ul>
      )}

      {r && <p className="mt-6 text-xs text-slate-400">{r.ca_note}</p>}
    </div>
  );
}
