"use client";
// Payables Shield — buyer-side §15 clock + 43B(h) tax exposure per MSE bill.
// The radar's mirror: same statutory engine, opposite direction. Suppliers may
// hesitate to enforce; buyers have a hard legal reason to comply.
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";

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
import { api, formatINRCompact, type PayableItem } from "@/lib/api";

const BAND: Record<string, { label: string; tone: "neutral" | "warn" | "bad" | "good" }> = {
  within: { label: "within window", tone: "good" },
  closing: { label: "closing window", tone: "warn" },
  breached: { label: "breached", tone: "bad" },
};

function BillRow({ item }: { item: PayableItem }) {
  const c = item.clock;
  const breached = c.band === "breached";
  const consumed = breached ? 45 + c.overdue_days : c.day_count;
  const pct = Math.min(100, (consumed / 60) * 100);
  const band = BAND[c.band] ?? BAND.within;

  return (
    <motion.tr
      variants={{ initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 } }}
      className="border-b border-dark-line transition-colors last:border-0 hover:bg-dark-card2/50"
    >
      <td className="px-5 py-4">
        <p className="text-sm font-bold text-dark-text">{item.vendor}</p>
        <p className="mt-0.5 font-mono text-xs text-dark-mute">
          {item.bill_number} · {item.msme_status} enterprise
        </p>
      </td>
      <td className="whitespace-nowrap px-5 py-4 text-right font-mono font-semibold text-dark-text">
        {formatINRCompact(item.outstanding_paise)}
        {item.outstanding_paise < item.amount_paise && (
          <p className="mono-annot mt-0.5">of {formatINRCompact(item.amount_paise)}</p>
        )}
      </td>
      <td
        className={`px-5 py-4 text-right font-mono text-lg font-bold ${breached ? "text-blush" : "text-mint"}`}
      >
        {consumed}
      </td>
      <td className="px-5 py-4">
        <Bar pct={pct} tone={breached ? "bad" : c.days_left <= 7 ? "accent" : "good"} />
        <p className="mono-annot mt-1.5">
          {breached
            ? `+${c.overdue_days} days over · §16 interest accruing against us`
            : `${c.days_left} days to pay within §15`}
        </p>
      </td>
      <td className="whitespace-nowrap px-5 py-4 text-right font-mono text-sm font-semibold text-dark-text">
        {breached ? formatINRCompact(c.interest_owed_paise) : "—"}
      </td>
      <td className="whitespace-nowrap px-5 py-4 text-right font-mono text-sm font-semibold text-dark-text">
        {c.disallowance_risk_paise > 0 ? formatINRCompact(c.disallowance_risk_paise) : "—"}
      </td>
      <td className="px-5 py-4">
        <Pill tone={band.tone}>{band.label}</Pill>
      </td>
    </motion.tr>
  );
}

export default function PayablesPage() {
  const payables = useQuery({ queryKey: ["payables"], queryFn: () => api.payables() });
  const p = payables.data;

  return (
    <PageShell
      title="Payables Shield"
      surface="dark"
      subtitle="§15 clock and 43B(h) tax exposure on bills owed to MSE vendors"
      annotation="GET /payables/compliance · deterministic clock engine"
    >
      <p className="mono-annot mb-5">
        ◇ same statutory engine as the radar, pointed at what we owe · pay inside 45 days or the
        expense deduction defers (income-tax §43B(h))
      </p>

      {payables.isLoading && (
        <>
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
          <Skeleton className="mt-5 h-64" />
        </>
      )}
      {payables.isError && <ErrorNote>Could not load payables compliance.</ErrorNote>}

      {p && (
        <>
          <motion.div
            className="grid grid-cols-2 gap-4 xl:grid-cols-4"
            initial="initial"
            animate="animate"
            variants={stagger}
          >
            <StatCard
              label="open to MSE vendors"
              value={p.totals.open_mse_paise}
              format={formatINRCompact}
            />
            <StatCard
              label="43B(h) at risk"
              value={p.totals.disallowance_risk_paise}
              format={formatINRCompact}
              tone="bad"
              sub="deduction defers if unpaid at FY end"
            />
            <StatCard
              label="closing window"
              value={p.totals.closing_window_paise}
              format={formatINRCompact}
              tone="accent"
              sub="≤7 days left on the §15 clock"
            />
            <StatCard
              label="§16 interest owed"
              value={p.totals.interest_owed_paise}
              format={formatINRCompact}
              tone="accent"
              sub="never deductible — pure cost"
            />
          </motion.div>

          {p.items.length === 0 ? (
            <div className="mt-5">
              <EmptyState>No open bills to registered MSE vendors.</EmptyState>
            </div>
          ) : (
            <Card className="mt-5 overflow-hidden !p-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-dark-line text-left">
                    <th className="mono-label px-5 py-3 font-normal text-dark-mute">
                      vendor · bill
                    </th>
                    <th className="mono-label px-5 py-3 text-right font-normal text-dark-mute">
                      amount
                    </th>
                    <th className="mono-label px-5 py-3 text-right font-normal text-dark-mute">
                      day
                    </th>
                    <th className="mono-label px-5 py-3 font-normal text-dark-mute">
                      statutory clock (45d)
                    </th>
                    <th className="mono-label px-5 py-3 text-right font-normal text-dark-mute">
                      interest owed
                    </th>
                    <th className="mono-label px-5 py-3 text-right font-normal text-dark-mute">
                      43B(h) at risk
                    </th>
                    <th className="mono-label px-5 py-3 font-normal text-dark-mute">band</th>
                  </tr>
                </thead>
                <motion.tbody
                  initial="initial"
                  animate="animate"
                  variants={{ animate: { transition: { staggerChildren: 0.05 } } }}
                >
                  {p.items.map((item) => (
                    <BillRow key={item.bill_id} item={item} />
                  ))}
                </motion.tbody>
              </table>
            </Card>
          )}

          <p className="mono-annot mt-4">
            ◇ {p.non_mse_open_count > 0 ? `${p.non_mse_open_count} open bill(s) to non-MSE vendors excluded · ` : ""}
            clock = bill acceptance + 45d (MSMED Act §15) · interest @ 3× bank rate (§16) ·{" "}
            {p.ca_note}
          </p>
        </>
      )}
    </PageShell>
  );
}
