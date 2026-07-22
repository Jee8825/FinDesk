"use client";
// Forecast — "Band chart" (wireframe Forecast A, dark signature surface B3):
// scenario bands (downside / base / upside), gap attribution, suggested cover.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { RefreshCw } from "lucide-react";
import Link from "next/link";

import {
  Bar,
  Card,
  EmptyState,
  ErrorNote,
  MonoLabel,
  PageShell,
  PrimaryBtn,
  Skeleton,
} from "@/components/ui";
import { ForecastTerrain } from "@/components/ForecastTerrain";
import { api, formatINR, formatINRCompact, type ForecastOut, type ForecastWeek } from "@/lib/api";

const W = 720;
const H = 260;
const PAD = 14;

function BandsChart({ f }: { f: ForecastOut }) {
  const base = f.scenarios.base ?? [];
  const up = f.scenarios.upside ?? [];
  const down = f.scenarios.downside ?? [];
  if (!base.length) return null;

  const all = [...base, ...up, ...down].map((w) => w.closing_paise);
  const min = Math.min(...all, 0);
  const max = Math.max(...all, 0);
  const span = max - min || 1;
  const n = f.horizon_weeks;
  const x = (week: number) => PAD + (week / (n - 1)) * (W - 2 * PAD);
  const y = (v: number) => PAD + (1 - (v - min) / span) * (H - 2 * PAD);
  const path = (weeks: ForecastWeek[]) =>
    weeks.map((w, i) => `${i === 0 ? "M" : "L"}${x(w.week)},${y(w.closing_paise)}`).join(" ");
  const band =
    up.length && down.length
      ? `${path(up)} ${[...down].reverse().map((w) => `L${x(w.week)},${y(w.closing_paise)}`).join(" ")} Z`
      : "";

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-4 w-full" role="img" aria-label="13-week cash projection with scenario bands">
      {f.gap && (
        <>
          <line
            x1={x(f.gap.week)}
            x2={x(f.gap.week)}
            y1={PAD}
            y2={H - PAD}
            stroke="#ff6e66"
            strokeWidth="1"
            strokeDasharray="4 4"
          />
          <text x={x(f.gap.week)} y={PAD + 2} textAnchor="middle" fontSize="10" fill="#ff6e66" fontFamily="var(--font-plex-mono)">
            W{f.gap.week} GAP {formatINRCompact(f.gap.shortfall_paise)}
          </text>
        </>
      )}
      <line x1={PAD} x2={W - PAD} y1={y(0)} y2={y(0)} stroke="rgba(148,163,204,0.3)" strokeDasharray="4 4" strokeWidth="1" />
      <text x={PAD + 2} y={y(0) - 5} fontSize="9" fill="#6c7490" fontFamily="var(--font-plex-mono)">₹0</text>
      {band && (
        <motion.path d={band} fill="#ffa028" initial={{ opacity: 0 }} animate={{ opacity: 0.13 }} transition={{ duration: 1.2 }} />
      )}
      <motion.path
        d={path(up)}
        fill="none"
        stroke="#2dd4bf"
        strokeWidth="1.5"
        strokeDasharray="5 4"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1.4, ease: "easeOut" }}
      />
      <motion.path
        d={path(down)}
        fill="none"
        stroke="#a78bfa"
        strokeWidth="1.5"
        strokeDasharray="5 4"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1.4, ease: "easeOut", delay: 0.15 }}
      />
      <motion.path
        d={path(base)}
        fill="none"
        stroke="#ffa028"
        strokeWidth="2.5"
        strokeLinecap="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1.6, ease: "easeOut" }}
      />
      {base.map((w, i) => (
        <motion.circle
          key={w.week}
          cx={x(w.week)}
          cy={y(w.closing_paise)}
          r="3"
          fill="#101527"
          stroke="#ffa028"
          strokeWidth="2"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.06 * i, duration: 0.25 }}
        />
      ))}
      {f.gap && (
        <motion.circle
          cx={x(f.gap.week)}
          cy={y(Math.min(...(down.length ? down : base).map((w) => w.closing_paise)))}
          r="5"
          fill="#ff6e66"
          initial={{ scale: 0 }}
          animate={{ scale: [0, 1.4, 1] }}
          transition={{ delay: 1.2, duration: 0.5 }}
        />
      )}
    </svg>
  );
}

export default function ForecastPage() {
  const queryClient = useQueryClient();
  const forecast = useQuery({ queryKey: ["forecast"], queryFn: () => api.forecast(), retry: false });
  const refresh = useMutation({
    mutationFn: () => api.startRunByGraph("cash_forecast"),
    onSuccess: () => setTimeout(() => queryClient.invalidateQueries({ queryKey: ["forecast"] }), 6000),
  });

  const f = forecast.data;
  const gapTotal = f?.gap ? f.gap.delayed_inflows.reduce((s, d) => s + d.amount_paise, 0) : 0;

  return (
    <PageShell
      title="Forecast"
      surface="dark"
      subtitle="13-week scenario bands, gap attribution, click-through to invoices"
      annotation="GET /forecast · recomputed on ledger events"
      actions={
        <PrimaryBtn onClick={() => refresh.mutate()} disabled={refresh.isPending}>
          <RefreshCw size={14} className={refresh.isPending ? "animate-spin" : ""} />
          {refresh.isPending ? "Recomputing…" : "Recompute"}
        </PrimaryBtn>
      }
    >
      <p className="mono-annot mb-5">
        ◇ signature surface b3 · scenario bands (downside / base / upside) · recomputed on every
        ledger event
      </p>

      {forecast.isLoading && <Skeleton className="h-96" />}
      {forecast.isError && (
        <EmptyState hint="POST /agent/runs {cash_forecast}">
          No forecast yet — hit Recompute to run the agent.
        </EmptyState>
      )}

      {f && (
        <div className="grid items-start gap-5 xl:grid-cols-[1fr_340px]">
          <Card className="p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-[15px] font-bold text-dark-text">13-week cash projection</h2>
              <div className="flex items-center gap-4 font-mono text-[11px]">
                <span className="text-mint">● upside</span>
                <span className="text-accent-soft">● base</span>
                <span className="text-blush">● downside</span>
              </div>
            </div>
            <ForecastTerrain f={f} fallback={<BandsChart f={f} />} />
            <div className="mt-2 flex items-center justify-between">
              <span className="mono-annot">
                opening {formatINRCompact(f.opening_balance_paise)} · recurring outflow ~
                {formatINRCompact(f.weekly_outflow_paise)}/wk
              </span>
              <span className="mono-annot">
                {f.scenarios.base?.[0]?.week_start} → w{f.horizon_weeks}
              </span>
            </div>
            <div className="mt-5 border-t border-dark-line pt-4">
              <MonoLabel>what the agent concluded</MonoLabel>
              <ul className="mt-2 space-y-1.5 text-[13.5px] leading-relaxed text-dark-text/90">
                {f.narrative.map((line, i) => (
                  <motion.li
                    key={i}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.15 * i }}
                  >
                    • {line}
                  </motion.li>
                ))}
              </ul>
            </div>
          </Card>

          <div className="space-y-5">
            <Card className={`p-6 ${f.gap ? "border-blush/30" : ""}`}>
              <MonoLabel className={f.gap ? "!text-blush" : "!text-mint"}>
                {f.gap ? `gap attribution · w${f.gap.week}` : "no gap in horizon"}
              </MonoLabel>
              {f.gap ? (
                <div className="mt-4 space-y-4">
                  {f.gap.delayed_inflows.map((d) => (
                    <div key={d.invoice_number}>
                      <div className="flex items-center justify-between text-[13px]">
                        <span className="font-semibold text-dark-text">
                          {d.client} <span className="font-mono text-xs text-dark-mute">{d.invoice_number}</span>
                        </span>
                        <span className="font-mono font-semibold text-dark-text">
                          {gapTotal ? Math.round((d.amount_paise / gapTotal) * 100) : 0}%
                        </span>
                      </div>
                      <Bar className="mt-1.5" pct={gapTotal ? (d.amount_paise / gapTotal) * 100 : 0} tone="bad" />
                      <p className="mono-annot mt-1">
                        {formatINR(d.amount_paise)} · expected {d.expected}
                      </p>
                    </div>
                  ))}
                  <p className="mono-annot">◇ each driver links to its invoice — click-through to source</p>
                </div>
              ) : (
                <p className="mt-3 text-sm leading-relaxed text-dark-text/90">
                  All three bands stay positive across the horizon. The runway holds even in the
                  downside case.
                </p>
              )}
            </Card>

            <Card className="p-6">
              <MonoLabel className="!text-accent-soft">suggested cover</MonoLabel>
              <p className="mt-3 text-sm leading-relaxed text-dark-text/90">
                {f.gap
                  ? `Working-capital options are prepared to close the ${formatINRCompact(f.gap.shortfall_paise)} gap with headroom.`
                  : "Working-capital options stay ranked and costed — ready if a gap opens."}
              </p>
              <Link href="/actions">
                <motion.span
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.97 }}
                  className="mt-4 inline-flex w-full items-center justify-center rounded-lg bg-accent px-4 py-2.5 text-sm font-bold text-[#1a1204] shadow-[0_10px_24px_-10px_rgba(255,160,40,0.7)] transition-colors hover:bg-accent-soft"
                >
                  See WC actions →
                </motion.span>
              </Link>
            </Card>
          </div>
        </div>
      )}
    </PageShell>
  );
}
