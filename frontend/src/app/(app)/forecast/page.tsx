"use client";
// Forecast — "Band chart" (wireframe Forecast A, dark signature surface B3):
// scenario bands (downside / base / upside), gap attribution, suggested cover.
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { FlaskConical, RefreshCw } from "lucide-react";
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
import { useEffect, useState } from "react";

const W = 720;
const H = 260;
const PAD = 14;

function BandsChart({ f, whatif }: { f: ForecastOut; whatif?: ForecastWeek[] }) {
  const base = f.scenarios.base ?? [];
  const up = f.scenarios.upside ?? [];
  const down = f.scenarios.downside ?? [];
  const ghost = whatif ?? [];
  if (!base.length) return null;

  const all = [...base, ...up, ...down, ...ghost].map((w) => w.closing_paise);
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
      {whatif && whatif.length > 1 && (
        <path
          d={path(whatif)}
          fill="none"
          stroke="#edf1fa"
          strokeWidth="2"
          strokeDasharray="7 5"
          opacity={0.85}
        />
      )}
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


function SandboxCard({
  onWhatif,
}: {
  onWhatif: (weeks: ForecastWeek[] | undefined) => void;
}) {
  const [delay, setDelay] = useState(0);
  const [haircut, setHaircut] = useState(0);
  const [extra, setExtra] = useState(0);
  const dirty = delay !== 0 || haircut !== 0 || extra !== 0;

  const [debounced, setDebounced] = useState({ delay, haircut, extra });
  useEffect(() => {
    const t = setTimeout(() => setDebounced({ delay, haircut, extra }), 300);
    return () => clearTimeout(t);
  }, [delay, haircut, extra]);

  const q = useQuery({
    queryKey: ["whatif", debounced],
    queryFn: () =>
      api.whatif({
        collection_delay_days: debounced.delay,
        inflow_haircut_bps: debounced.haircut * 100,
        extra_monthly_outflow_paise: debounced.extra * 100_000 * 100,
      }),
    enabled: debounced.delay !== 0 || debounced.haircut !== 0 || debounced.extra !== 0,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });

  useEffect(() => {
    onWhatif(dirty ? q.data?.weeks : undefined);
  }, [dirty, q.data, onWhatif]);

  const delta = q.data?.end_delta_paise ?? 0;

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <MonoLabel className="flex items-center gap-1.5">
          <FlaskConical size={12} className="text-accent" /> scenario sandbox
        </MonoLabel>
        {dirty && (
          <button
            onClick={() => {
              setDelay(0);
              setHaircut(0);
              setExtra(0);
            }}
            className="mono-label text-faint hover:text-mute"
          >
            reset
          </button>
        )}
      </div>
      <p className="mono-annot mt-1.5">◇ server computes — POST /forecast/whatif · UI only renders</p>

      <div className="mt-4 space-y-4">
        <label className="block">
          <div className="flex justify-between text-xs">
            <span className="text-mute">Clients pay later</span>
            <span className="tnum font-mono font-semibold text-ink">+{delay}d</span>
          </div>
          <input
            type="range"
            min={0}
            max={60}
            step={7}
            value={delay}
            onChange={(e) => setDelay(Number(e.target.value))}
            className="mt-1.5 w-full accent-[#ffa028]"
            aria-label="collection delay days"
          />
        </label>
        <label className="block">
          <div className="flex justify-between text-xs">
            <span className="text-mute">Inflows that slip away</span>
            <span className="tnum font-mono font-semibold text-ink">{haircut}%</span>
          </div>
          <input
            type="range"
            min={0}
            max={50}
            step={5}
            value={haircut}
            onChange={(e) => setHaircut(Number(e.target.value))}
            className="mt-1.5 w-full accent-[#ffa028]"
            aria-label="inflow haircut percent"
          />
        </label>
        <label className="block">
          <div className="flex justify-between text-xs">
            <span className="text-mute">New monthly burn (hire, rent…)</span>
            <span className="tnum font-mono font-semibold text-ink">₹{extra}L/mo</span>
          </div>
          <input
            type="range"
            min={0}
            max={20}
            step={1}
            value={extra}
            onChange={(e) => setExtra(Number(e.target.value))}
            className="mt-1.5 w-full accent-[#ffa028]"
            aria-label="extra monthly outflow lakh"
          />
        </label>
      </div>

      {dirty && q.data && (
        <div className="mt-4 border-t border-line2 pt-3 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-mute">Horizon ends</span>
            <span className={`tnum font-mono font-semibold ${delta < 0 ? "text-blush" : "text-mint"}`}>
              {delta >= 0 ? "+" : "−"}{formatINRCompact(Math.abs(delta))}
            </span>
          </div>
          <div className="mt-1.5 flex items-center justify-between">
            <span className="text-mute">Funding gap</span>
            {q.data.gap ? (
              <span className="font-mono text-xs font-semibold text-blush">
                week {q.data.gap.week} · short {formatINRCompact(q.data.gap.shortfall_paise)}
              </span>
            ) : (
              <span className="font-mono text-xs font-semibold text-mint">none in horizon</span>
            )}
          </div>
          {q.data.pushed_out_paise > 0 && (
            <div className="mono-annot mt-1.5">
              ◇ {formatINRCompact(q.data.pushed_out_paise)} pushed past the horizon
            </div>
          )}
          <div className="mono-annot mt-1.5">◇ white dashed line on the chart is this scenario</div>
        </div>
      )}
    </Card>
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
  const [whatifWeeks, setWhatifWeeks] = useState<ForecastWeek[] | undefined>(undefined);
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
            <ForecastTerrain f={f} whatif={whatifWeeks} fallback={<BandsChart f={f} whatif={whatifWeeks} />} />
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
            <SandboxCard onWhatif={setWhatifWeeks} />
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
