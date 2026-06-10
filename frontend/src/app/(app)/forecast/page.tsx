"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, formatINR, type ForecastOut, type ForecastWeek } from "@/lib/api";

const W = 640;
const H = 220;
const PAD = 8;

function BandsChart({ f }: { f: ForecastOut }) {
  const scenarios = ["upside", "base", "downside"] as const;
  const all = scenarios.flatMap((s) => f.scenarios[s] ?? []);
  if (!all.length) return null;
  const values = all.map((w) => w.closing_paise);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0);
  const span = max - min || 1;
  const n = f.horizon_weeks;

  const x = (week: number) => PAD + (week / (n - 1)) * (W - 2 * PAD);
  const y = (v: number) => PAD + (1 - (v - min) / span) * (H - 2 * PAD);
  const path = (weeks: ForecastWeek[]) =>
    weeks.map((w, i) => `${i === 0 ? "M" : "L"}${x(w.week)},${y(w.closing_paise)}`).join(" ");

  const up = f.scenarios.upside ?? [];
  const down = f.scenarios.downside ?? [];
  const band =
    up.length && down.length
      ? `${path(up)} ${[...down].reverse().map((w) => `L${x(w.week)},${y(w.closing_paise)}`).join(" ")} Z`
      : "";

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-2 w-full" role="img" aria-label="cash forecast bands">
      {/* zero line */}
      <line x1={PAD} x2={W - PAD} y1={y(0)} y2={y(0)} stroke="#dc2626" strokeDasharray="4 4" strokeWidth="1" />
      {band && <path d={band} fill="#0e6e74" opacity="0.12" />}
      <path d={path(f.scenarios.base ?? [])} fill="none" stroke="#0e6e74" strokeWidth="2.5" />
      <path d={path(up)} fill="none" stroke="#0e6e74" strokeWidth="1" opacity="0.4" />
      <path d={path(down)} fill="none" stroke="#b45309" strokeWidth="1.5" opacity="0.7" />
      {f.gap && (
        <circle
          cx={x(f.gap.week)}
          cy={y(-(f.gap.shortfall_paise))}
          r="5"
          fill="#dc2626"
        />
      )}
      <text x={PAD} y={y(0) - 4} fontSize="10" fill="#dc2626">
        ₹0
      </text>
    </svg>
  );
}

export default function ForecastPage() {
  const queryClient = useQueryClient();
  const forecast = useQuery({
    queryKey: ["forecast"],
    queryFn: () => api.forecast(),
    retry: false,
  });
  const refresh = useMutation({
    mutationFn: () => api.startRunByGraph("cash_forecast"),
    onSuccess: () =>
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["forecast"] }), 6000),
  });

  const f = forecast.data;

  return (
    <div className="max-w-4xl">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Cash forecast</h1>
          <p className="mt-1 text-sm text-slate-500">
            13 weeks ahead, as bands — not point estimates. Inflows land when each client
            actually pays, from memory.
          </p>
        </div>
        <button
          onClick={() => refresh.mutate()}
          disabled={refresh.isPending}
          className="rounded-md bg-teal-brand px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {refresh.isPending ? "Recomputing…" : "Recompute"}
        </button>
      </div>

      {forecast.isLoading && <div className="mt-6 h-56 animate-pulse rounded-xl bg-slate-100" />}
      {forecast.isError && (
        <div className="mt-6 rounded-xl border border-dashed bg-white p-10 text-center text-sm text-slate-500">
          No forecast yet — hit Recompute to run the agent.
        </div>
      )}

      {f && (
        <>
          {f.gap && (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4">
              <p className="text-sm font-semibold text-red-700">
                ⚠ {f.gap.scenario} scenario goes {formatINR(f.gap.shortfall_paise)} negative in
                week {f.gap.week + 1} (w/c {f.gap.week_start})
              </p>
              {f.gap.delayed_inflows[0] && (
                <p className="mt-1 text-sm text-red-600">
                  Largest lever: {f.gap.delayed_inflows[0].client}&apos;s{" "}
                  {f.gap.delayed_inflows[0].invoice_number} (
                  {formatINR(f.gap.delayed_inflows[0].amount_paise)}), expected{" "}
                  {f.gap.delayed_inflows[0].expected}.
                </p>
              )}
            </div>
          )}

          <section className="mt-4 rounded-xl border bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>
                opening {formatINR(f.opening_balance_paise)} · recurring outflow ~
                {formatINR(f.weekly_outflow_paise)}/week
              </span>
              <span>
                <span className="mr-3 border-b-2 border-teal-brand pb-0.5">base</span>
                <span className="mr-3 text-amber-700">downside</span>
                <span className="text-slate-400">band = upside↔downside</span>
              </span>
            </div>
            <BandsChart f={f} />
          </section>

          <section className="mt-4 rounded-xl border bg-white p-5 shadow-sm">
            <h2 className="text-sm font-medium text-slate-700">What the agent concluded</h2>
            <ul className="mt-2 space-y-1 text-sm text-slate-600">
              {f.narrative.map((line, i) => (
                <li key={i}>• {line}</li>
              ))}
            </ul>
          </section>

          <section className="mt-4 rounded-xl border bg-white p-5 shadow-sm">
            <h2 className="text-sm font-medium text-slate-700">
              Recurring outflows the projection assumes
            </h2>
            <table className="mt-2 w-full text-sm">
              <tbody className="divide-y">
                {f.outflow_basis.map((o) => (
                  <tr key={o.vendor}>
                    <td className="py-1 text-slate-600">{o.vendor.replace(/-/g, " ")}</td>
                    <td className="py-1 text-right font-mono">
                      {formatINR(o.monthly_paise)}/mo
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}
