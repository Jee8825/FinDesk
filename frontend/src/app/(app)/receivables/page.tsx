"use client";
// 45-Day Radar — "Clock table" (wireframe Radar A, dark signature surface):
// statutory MSME clock per invoice, accrued interest, escalation rung.
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import Link from "next/link";

import {
  Bar,
  Card,
  EmptyState,
  ErrorNote,
  PageShell,
  Pill,
  Skeleton,
  StatCard,
  stagger,
} from "@/components/ui";
import { api, formatINR, formatINRCompact, type RadarItem } from "@/lib/api";

const RUNG: Record<string, { label: string; tone: "neutral" | "warn" | "bad" | "good" }> = {
  none: { label: "within time", tone: "good" },
  nudge: { label: "nudge", tone: "warn" },
  reminder: { label: "reminder", tone: "warn" },
  act_letter: { label: "act letter", tone: "bad" },
  samadhaan_prep: { label: "samadhaan prep", tone: "bad" },
};

function ClockRow({ item }: { item: RadarItem }) {
  const overdue = item.clock.overdue_days > 0;
  // days consumed of the 45-day statutory window (overdue_days counts past it)
  const consumed = overdue ? 45 + item.clock.overdue_days : 45 - daysLeft(item);
  const pct = Math.min(100, (consumed / 60) * 100);
  const rung = RUNG[item.clock.escalation_level] ?? RUNG.none;

  return (
    <motion.tr
      variants={{ initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 } }}
      className="border-b border-dark-line transition-colors last:border-0 hover:bg-dark-card2/50"
    >
      <td className="px-5 py-4">
        <p className="text-sm font-bold text-dark-text">{item.client}</p>
        <p className="mt-0.5 font-mono text-xs text-dark-mute">{item.invoice_number}</p>
      </td>
      <td className="whitespace-nowrap px-5 py-4 text-right font-mono font-semibold text-dark-text">
        {formatINRCompact(item.amount_paise)}
      </td>
      <td className={`px-5 py-4 text-right font-mono text-lg font-bold ${overdue ? "text-blush" : "text-mint"}`}>
        {overdue ? 45 + item.clock.overdue_days : 45 - daysLeft(item)}
      </td>
      <td className="w-72 px-5 py-4">
        <Bar pct={pct} tone={overdue ? "bad" : consumed > 38 ? "accent" : "good"} />
        <p className="mono-annot mt-1.5">
          {overdue
            ? `+${item.clock.overdue_days} days over · interest accruing`
            : `${daysLeft(item)} days to statutory limit`}
          {item.predicted_payment_date &&
            ` · likely pays ~${item.predicted_payment_date}${item.avg_days_late != null ? ` (runs ${item.avg_days_late}d late)` : ""}`}
        </p>
      </td>
      <td className="whitespace-nowrap px-5 py-4 text-right font-mono text-sm font-semibold text-dark-text">
        {overdue ? formatINRCompact(item.clock.accrued_interest_paise) : "—"}
      </td>
      <td className="px-5 py-4">
        <Pill tone={rung.tone}>{rung.label}</Pill>
      </td>
      <td className="px-5 py-4 text-right">
        <Link
          href="/collections"
          className={`whitespace-nowrap text-[13px] font-bold transition-transform hover:translate-x-0.5 ${
            overdue ? "text-blush" : "text-accent-soft"
          }`}
        >
          {overdue ? "Escalate →" : "Chase →"}
        </Link>
      </td>
    </motion.tr>
  );
}

function daysLeft(item: RadarItem): number {
  const due = new Date(item.clock.statutory_due_date).getTime();
  return Math.max(0, Math.ceil((due - Date.now()) / 86_400_000));
}

export default function ReceivablesPage() {
  const radar = useQuery({ queryKey: ["radar"], queryFn: () => api.radar() });
  const r = radar.data;
  const past45 = r?.items.filter((i) => i.clock.overdue_days > 0) ?? [];
  const approaching = r?.items.filter((i) => i.clock.overdue_days === 0 && daysLeft(i) <= 15) ?? [];

  return (
    <PageShell
      title="45-Day Radar"
      surface="dark"
      subtitle="Statutory clock per invoice, accrued interest, escalation rung"
      annotation="GET /receivables/radar · deterministic clock engine"
    >
      <p className="mono-annot mb-5">
        ◇ signature surface · statutory 45-day msme clock per invoice · accrued interest computed
        deterministically
      </p>

      {radar.isLoading && (
        <>
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
          <Skeleton className="mt-5 h-64" />
        </>
      )}
      {radar.isError && <ErrorNote>Could not load the radar.</ErrorNote>}

      {r && (
        <>
          <motion.div className="grid grid-cols-2 gap-4 xl:grid-cols-4" initial="initial" animate="animate" variants={stagger}>
            <StatCard label="overdue total" value={r.totals.overdue_paise} format={formatINRCompact} />
            <StatCard label="past day 45" value={past45.length} tone="bad" sub="interest accruing under MSMED Act" />
            <StatCard label="day 30–45" value={approaching.length} tone="accent" sub="approaching statutory limit" />
            <StatCard
              label="accrued interest"
              value={r.totals.accrued_interest_paise}
              format={formatINRCompact}
              tone="accent"
              sub="@ 3× bank rate on overdue principal"
            />
          </motion.div>

          {r.items.length === 0 ? (
            <div className="mt-5">
              <EmptyState>No open receivables — everything is collected.</EmptyState>
            </div>
          ) : (
            <Card className="mt-5 overflow-hidden !p-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-dark-line text-left">
                    <th className="mono-label px-5 py-3 font-normal text-dark-mute">client · invoice</th>
                    <th className="mono-label px-5 py-3 text-right font-normal text-dark-mute">amount</th>
                    <th className="mono-label px-5 py-3 text-right font-normal text-dark-mute">day</th>
                    <th className="mono-label px-5 py-3 font-normal text-dark-mute">statutory clock (45d)</th>
                    <th className="mono-label px-5 py-3 text-right font-normal text-dark-mute">interest</th>
                    <th className="mono-label px-5 py-3 font-normal text-dark-mute">rung</th>
                    <th className="px-5 py-3" />
                  </tr>
                </thead>
                <motion.tbody initial="initial" animate="animate" variants={{ animate: { transition: { staggerChildren: 0.05 } } }}>
                  {r.items.map((item) => (
                    <ClockRow key={item.invoice_id} item={item} />
                  ))}
                </motion.tbody>
              </table>
            </Card>
          )}

          <p className="mono-annot mt-4">
            ◇ clock = invoice acceptance + 45d (MSMED Act) · interest @ 3× bank rate · engine is
            pure/testable · {r.ca_note}
          </p>
        </>
      )}
    </PageShell>
  );
}
