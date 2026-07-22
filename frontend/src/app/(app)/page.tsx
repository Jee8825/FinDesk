"use client";
// Dashboard — "Command center" (wireframe Dashboard A): cash KPIs, the base
// projection, live agent activity, and the three queues that need a human.
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import Link from "next/link";

import {
  Card,
  MonoLabel,
  PageShell,
  Skeleton,
  StatCard,
  stagger,
} from "@/components/ui";
import { api, formatINR, formatINRCompact, type ForecastOut } from "@/lib/api";

function runwayLabel(f?: ForecastOut): string {
  const base = f?.scenarios.base;
  if (!base?.length) return "—";
  const breach = base.find((w) => w.closing_paise < 0);
  if (!breach) return `${f!.horizon_weeks}+ wk`;
  return `${breach.week} wk`;
}

function ProjectionChart({ f }: { f: ForecastOut }) {
  const base = f.scenarios.base ?? [];
  if (!base.length) return null;
  const W = 640;
  const H = 190;
  const PAD = 10;
  const values = base.map((w) => w.closing_paise);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0);
  const span = max - min || 1;
  const x = (i: number) => PAD + (i / (base.length - 1)) * (W - 2 * PAD);
  const y = (v: number) => PAD + (1 - (v - min) / span) * (H - 2 * PAD);
  const line = base.map((w, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(w.closing_paise)}`).join(" ");
  const area = `${line} L${x(base.length - 1)},${H - PAD} L${x(0)},${H - PAD} Z`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 w-full" role="img" aria-label="base-case cash projection">
      <motion.path
        d={area}
        fill="#ffa028"
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.09 }}
        transition={{ duration: 1 }}
      />
      <line x1={PAD} x2={W - PAD} y1={y(0)} y2={y(0)} stroke="rgba(148,163,204,0.35)" strokeDasharray="4 4" strokeWidth="1" />
      <motion.path
        d={line}
        fill="none"
        stroke="#ffa028"
        strokeWidth="2.5"
        strokeLinecap="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1.4, ease: "easeOut" }}
      />
      {base.map((w, i) => (
        <motion.circle
          key={w.week}
          cx={x(i)}
          cy={y(w.closing_paise)}
          r="3"
          fill="#fcf9f2"
          stroke="#ffa028"
          strokeWidth="2"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.08 * i, duration: 0.3 }}
        />
      ))}
    </svg>
  );
}

const RUN_LABELS: Record<string, string> = {
  ping: "Pulse check",
  reconciliation: "Reconciled statement lines",
  anomaly_scan: "Scanned for anomalies",
  collections: "Drafted collection chasers",
  cash_forecast: "Recomputed the cash forecast",
  working_capital: "Ranked working-capital options",
  enforcer_45day: "Advanced 45-day escalations",
};

export default function Dashboard() {
  const forecast = useQuery({ queryKey: ["forecast"], queryFn: () => api.forecast(), retry: false });
  const radar = useQuery({ queryKey: ["radar"], queryFn: () => api.radar() });
  const approvals = useQuery({ queryKey: ["approvals"], queryFn: () => api.approvals() });
  const conflicts = useQuery({ queryKey: ["conflicts"], queryFn: () => api.conflicts() });
  const anomalies = useQuery({ queryKey: ["anomalies"], queryFn: () => api.anomalies() });
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api.listRuns(), refetchInterval: 15_000 });

  const f = forecast.data;
  const recoverable = (anomalies.data ?? [])
    .filter((a) => a.status === "open")
    .reduce((s, a) => s + (a.recoverable_paise ?? 0), 0);
  const loading = forecast.isLoading || radar.isLoading;

  const firstConflict = conflicts.data?.[0];
  const firstAnomaly = anomalies.data?.find((a) => a.status === "open");

  return (
    <PageShell
      title="Dashboard"
      subtitle="Cash position, runway, alerts & live agent activity"
      annotation="composed client-side · SSE agent feed · queue count polls"
    >
      {loading ? (
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : (
        <motion.div className="grid grid-cols-2 gap-4 xl:grid-cols-4" initial="initial" animate="animate" variants={stagger}>
          <StatCard
            label="cash position"
            value={f?.opening_balance_paise ?? 0}
            format={formatINRCompact}
            sub={f ? `opening balance · ${new Date(f.generated_at).toLocaleDateString("en-IN")}` : "run a forecast to compute"}
          />
          <StatCard
            label="runway (base case)"
            value={runwayLabel(f)}
            sub={f ? "till first negative week · recomputed on ledger events" : "—"}
          />
          <StatCard
            label="overdue receivables"
            value={radar.data?.totals.overdue_paise ?? 0}
            format={formatINRCompact}
            tone="accent"
            sub={`${radar.data?.items.filter((i) => i.clock.overdue_days > 0).length ?? 0} invoices past day 45`}
          />
          <StatCard
            label="awaiting your approval"
            value={approvals.data?.length ?? 0}
            sub={
              approvals.data?.length
                ? `${approvals.data.filter((a) => a.action_kind === "send_email").length} chasers · ${approvals.data.filter((a) => a.action_kind === "commit_match").length} commits · ${approvals.data.filter((a) => a.action_kind === "treds_listing").length} TReDS`
                : "queue is clear"
            }
          />
        </motion.div>
      )}

      <div className="mt-5 grid gap-5 xl:grid-cols-[1fr_360px]">
        <Card className="p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-[15px] font-bold text-ink">Cash projection — base case</h2>
            <span className="mono-annot hidden lg:block">◇ backend computes; UI formats (formatINR)</span>
          </div>
          {f ? (
            <>
              <ProjectionChart f={f} />
              <div className="mt-2 flex items-center justify-between">
                <span className="text-xs text-faint">
                  <span className="mr-1 inline-block h-[3px] w-5 rounded bg-accent align-middle" />
                  closing balance / week
                </span>
                <span className="mono-annot">
                  w1 → w{f.horizon_weeks} · recurring outflow ~{formatINRCompact(f.weekly_outflow_paise)}/wk
                </span>
              </div>
            </>
          ) : (
            <div className="flex h-48 items-center justify-center text-sm text-faint">
              No forecast yet —{" "}
              <Link href="/forecast" className="ml-1 font-semibold text-accent">
                run the agent →
              </Link>
            </div>
          )}
        </Card>

        <Card className="flex flex-col p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-[15px] font-bold text-ink">Agent activity</h2>
            <span className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-moss" />
              <span className="mono-label text-moss">live</span>
            </span>
          </div>
          <motion.ul className="mt-4 flex-1 space-y-4" initial="initial" animate="animate" variants={stagger}>
            {(runs.data ?? []).slice(0, 5).map((r) => (
              <motion.li
                key={r.run_id}
                className="flex gap-3 text-[13px]"
                variants={{ initial: { opacity: 0, x: 12 }, animate: { opacity: 1, x: 0 } }}
              >
                <span className="mono-annot mt-0.5 shrink-0">{r.run_id.slice(-4)}</span>
                <span className="text-mute">
                  <span className="font-semibold text-ink">{RUN_LABELS[r.graph] ?? r.graph}</span>
                  {" · "}
                  <span className={r.status === "failed" ? "text-claret" : r.status === "finished" ? "text-moss" : "text-accent"}>
                    {r.status}
                  </span>
                </span>
              </motion.li>
            ))}
            {runs.data?.length === 0 && (
              <li className="text-sm text-faint">No runs yet — import a statement to wake the agent.</li>
            )}
          </motion.ul>
          <Link href="/reconciliation" className="mt-4 inline-flex items-center gap-1 text-[13px] font-bold text-accent">
            View all runs <ArrowRight size={13} />
          </Link>
        </Card>
      </div>

      <motion.div className="mt-5 grid gap-5 lg:grid-cols-3" initial="initial" animate="animate" variants={stagger}>
        <Card hover className={`p-5 ${firstConflict ? "border-accent/50" : ""}`}>
          <MonoLabel className="!text-accent">conflict · a4</MonoLabel>
          <p className="mt-2 text-[15px] font-bold leading-snug text-ink">
            {firstConflict
              ? `${firstConflict.engine_view.counterparty ?? firstConflict.scope_key} — ${firstConflict.claim_kind.replace(/_/g, " ")} disputed`
              : "No open conflicts — beliefs and books agree"}
          </p>
          <Link href="/conflicts" className="mt-3 inline-flex items-center gap-1 text-[13px] font-bold text-accent">
            {firstConflict ? "Resolve (1 tap)" : "Open queue"} <ArrowRight size={13} />
          </Link>
        </Card>
        <Card hover className="p-5">
          <MonoLabel className="!text-moss">recoverable · a6</MonoLabel>
          <p className="mt-2 text-[15px] font-bold leading-snug text-ink">
            {firstAnomaly
              ? `${firstAnomaly.vendor_label} — ${firstAnomaly.kind.replace(/_/g, " ")}${recoverable ? ` · ${formatINR(recoverable)} flagged` : ""}`
              : "No anomalies flagged this cycle"}
          </p>
          <Link href="/anomalies" className="mt-3 inline-flex items-center gap-1 text-[13px] font-bold text-moss">
            Review anomalies <ArrowRight size={13} />
          </Link>
        </Card>
        <Card hover className="p-5">
          <MonoLabel>forecast · b3</MonoLabel>
          <p className="mt-2 text-[15px] font-bold leading-snug text-ink">
            {f?.gap
              ? `Week-${f.gap.week} gap: ${formatINRCompact(f.gap.shortfall_paise)} in the ${f.gap.scenario} band`
              : "No funding gap inside the horizon"}
          </p>
          <Link href="/forecast" className="mt-3 inline-flex items-center gap-1 text-[13px] font-bold text-ink">
            Open forecast <ArrowRight size={13} />
          </Link>
        </Card>
      </motion.div>
    </PageShell>
  );
}
