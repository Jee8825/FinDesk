"use client";
// Daily CFO Brief — the morning front page. Composes what already exists
// (forecast, radar, approvals, conflicts, anomalies, runs) into one
// readable digest: where cash stands, what needs you, who owes you, what
// the agent did while you were away. IST at the presentation edge.
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import Link from "next/link";

import {
  AnimatedNumber,
  Card,
  MonoLabel,
  PageShell,
  Pill,
  Skeleton,
  stagger,
} from "@/components/ui";
import { motion } from "framer-motion";
import { api, formatINR, formatINRCompact } from "@/lib/api";

const RUN_VERBS: Record<string, string> = {
  anomaly_scan: "Scanned for anomalies",
  cash_forecast: "Recomputed the cash forecast",
  reconciliation: "Reconciled statement lines",
  collections: "Drafted collection chases",
  working_capital: "Ranked working-capital options",
  enforcer: "Checked 45-day escalations",
  ping: "Health check",
};

function istGreeting(): { greeting: string; dateLine: string } {
  const now = new Date();
  const hour = Number(
    new Intl.DateTimeFormat("en-IN", {
      hour: "numeric",
      hour12: false,
      timeZone: "Asia/Kolkata",
    }).format(now),
  );
  const greeting = hour < 5 ? "Working late" : hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const dateLine = new Intl.DateTimeFormat("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone: "Asia/Kolkata",
  }).format(now);
  return { greeting, dateLine };
}

function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) return null;
  const W = 220;
  const H = 44;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const d = points
    .map(
      (p, i) =>
        `${i === 0 ? "M" : "L"}${(i / (points.length - 1)) * W},${H - 4 - ((p - min) / span) * (H - 8)}`,
    )
    .join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="13-week base case sparkline">
      <path d={d} fill="none" stroke="var(--chart-base)" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export default function BriefPage() {
  const forecast = useQuery({ queryKey: ["forecast"], queryFn: () => api.forecast(), retry: false });
  const radar = useQuery({ queryKey: ["radar"], queryFn: () => api.radar() });
  const approvals = useQuery({ queryKey: ["approvals"], queryFn: () => api.approvals() });
  const conflicts = useQuery({ queryKey: ["conflicts"], queryFn: () => api.conflicts() });
  const anomalies = useQuery({ queryKey: ["anomalies"], queryFn: () => api.anomalies("open") });
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api.listRuns() });

  const { greeting, dateLine } = istGreeting();
  const f = forecast.data;
  const base = f?.scenarios.base ?? [];
  const overdueItems = (radar.data?.items ?? [])
    .filter((i) => i.clock.overdue_days > 0)
    .sort((a, b) => b.clock.overdue_days - a.clock.overdue_days);
  const needsYou =
    (approvals.data?.length ?? 0) + (conflicts.data?.length ?? 0) + (anomalies.data?.length ?? 0);
  const recentRuns = (runs.data ?? []).slice(0, 5);
  const loading = forecast.isLoading || radar.isLoading;

  return (
    <PageShell
      title="Daily Brief"
      chip="front page"
      subtitle={`${greeting} — ${dateLine}. Here's where your cash stands.`}
      annotation="composed client-side from live queues"
    >
      {loading ? (
        <div className="grid gap-4 md:grid-cols-3">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
      ) : (
        <motion.div initial="initial" animate="animate" variants={stagger} className="space-y-5">
          {/* ---- the numbers that matter this morning ------------------ */}
          <div className="grid gap-4 md:grid-cols-3">
            <Card className="px-5 py-4">
              <MonoLabel>cash on hand</MonoLabel>
              <div className="tnum mt-2 font-mono text-[26px] font-semibold text-ink">
                {f ? (
                  <AnimatedNumber value={f.opening_balance_paise} format={formatINRCompact} />
                ) : (
                  "—"
                )}
              </div>
              <div className="mt-2">{base.length > 0 && <Sparkline points={base.map((w) => w.closing_paise)} />}</div>
              <div className="mono-annot mt-1">base case · 13 weeks ahead</div>
            </Card>
            <Card className="px-5 py-4">
              <MonoLabel>overdue receivables</MonoLabel>
              <div className="tnum mt-2 font-mono text-[26px] font-semibold text-accent">
                {radar.data ? (
                  <AnimatedNumber value={radar.data.totals.overdue_paise} format={formatINRCompact} />
                ) : (
                  "—"
                )}
              </div>
              <div className="mt-2 text-xs text-faint">
                {overdueItems.length} invoices past day 45 ·{" "}
                <span className="text-blush">
                  {formatINRCompact(radar.data?.totals.accrued_interest_paise ?? 0)} interest accrued
                </span>
              </div>
              <div className="mono-annot mt-1">MSME Act · 3× RBI bank rate</div>
            </Card>
            <Card className="px-5 py-4">
              <MonoLabel>waiting on you</MonoLabel>
              <div className="tnum mt-2 font-mono text-[26px] font-semibold text-ink">{needsYou}</div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {(approvals.data?.length ?? 0) > 0 && (
                  <Pill tone="warn">{approvals.data!.length} approvals</Pill>
                )}
                {(conflicts.data?.length ?? 0) > 0 && (
                  <Pill tone="memory">{conflicts.data!.length} conflicts</Pill>
                )}
                {(anomalies.data?.length ?? 0) > 0 && (
                  <Pill tone="bad">{anomalies.data!.length} anomalies</Pill>
                )}
                {needsYou === 0 && <Pill tone="good">queue clear</Pill>}
              </div>
              <Link
                href="/approvals"
                className="mt-3 inline-flex items-center gap-1 text-xs font-bold text-accent transition-transform hover:translate-x-0.5"
              >
                Open approvals <ArrowRight size={12} />
              </Link>
            </Card>
          </div>

          {/* ---- who owes you ------------------------------------------ */}
          <Card className="px-5 py-4">
            <div className="flex items-center justify-between">
              <MonoLabel>who owes you — chase these first</MonoLabel>
              <Link href="/receivables" className="mono-label text-accent hover:underline">
                full radar →
              </Link>
            </div>
            {overdueItems.length === 0 ? (
              <p className="mt-3 text-sm text-mute">Nobody is past day 45. Rare air — enjoy it.</p>
            ) : (
              <ul className="mt-3 divide-y divide-line2">
                {overdueItems.slice(0, 3).map((i) => (
                  <li key={i.invoice_id} className="flex items-center justify-between gap-3 py-2.5">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-ink">{i.client}</div>
                      <div className="mono-annot">
                        {i.invoice_number} · {i.clock.overdue_days}d overdue
                        {i.avg_days_late !== null && ` · usually pays ${Math.round(i.avg_days_late)}d late`}
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="tnum font-mono text-sm font-semibold text-ink">
                        {formatINR(i.amount_paise)}
                      </div>
                      <Pill tone={i.clock.escalation_level === "none" ? "neutral" : "bad"}>
                        {i.clock.escalation_level === "none" ? "watch" : i.clock.escalation_level}
                      </Pill>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            {/* ---- what the agent did ---------------------------------- */}
            <Card className="px-5 py-4">
              <MonoLabel>while you were away</MonoLabel>
              {recentRuns.length === 0 ? (
                <p className="mt-3 text-sm text-mute">No runs yet — import a statement to wake the agent.</p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {recentRuns.map((r) => (
                    <li key={r.run_id} className="flex items-center gap-2.5 text-sm">
                      <span
                        className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                          r.status === "succeeded" ? "bg-moss" : r.status === "failed" ? "bg-claret" : "bg-accent"
                        }`}
                      />
                      <span className="text-mute">{RUN_VERBS[r.graph] ?? r.graph}</span>
                      <span className="mono-label ml-auto text-faint">{r.status}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            {/* ---- what the agent concluded ---------------------------- */}
            <Card className="px-5 py-4">
              <MonoLabel>what the agent concluded</MonoLabel>
              {(f?.narrative?.length ?? 0) === 0 ? (
                <p className="mt-3 text-sm text-mute">No forecast narrative yet — recompute from Forecast.</p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {f!.narrative.slice(0, 4).map((line, i) => (
                    <li key={i} className="flex gap-2 text-sm leading-relaxed text-mute">
                      <span className="text-accent">◇</span>
                      {line}
                    </li>
                  ))}
                </ul>
              )}
              <Link
                href="/forecast"
                className="mt-3 inline-flex items-center gap-1 text-xs font-bold text-accent transition-transform hover:translate-x-0.5"
              >
                Open the terrain <ArrowRight size={12} />
              </Link>
            </Card>
          </div>
        </motion.div>
      )}
    </PageShell>
  );
}
