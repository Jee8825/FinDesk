"use client";
// Payables Shield — buyer-side §15 clock + 43B(h) tax exposure per MSE bill.
// The radar's mirror: same statutory engine, opposite direction. Suppliers may
// hesitate to enforce; buyers have a hard legal reason to comply.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ShieldAlert, ShieldCheck } from "lucide-react";
import { useState } from "react";

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
import { api, formatINR, formatINRCompact, type PayableItem } from "@/lib/api";

const BAND: Record<string, { label: string; tone: "neutral" | "warn" | "bad" | "good" }> = {
  within: { label: "within window", tone: "good" },
  closing: { label: "closing window", tone: "warn" },
  breached: { label: "breached", tone: "bad" },
};

function BillRow({ item }: { item: PayableItem }) {
  const queryClient = useQueryClient();
  const [verifyOpen, setVerifyOpen] = useState(false);
  const [urn, setUrn] = useState("");
  const verify = useMutation({
    mutationFn: () => api.verifyMsme(item.counterparty_id, urn.trim()),
    onSuccess: () => {
      setVerifyOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["payables"] });
    },
  });
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
        <p className="mt-0.5 flex items-center gap-1.5 font-mono text-xs text-dark-mute">
          {item.bill_number} ·{" "}
          {item.msme_source === "verified" ? (
            <span className="inline-flex items-center gap-1 text-mint">
              <ShieldCheck size={12} /> {item.verified_category} · Udyam-verified
            </span>
          ) : (
            <span>{item.msme_status} · self-declared</span>
          )}
        </p>
        {item.msme_source !== "verified" && (
          <div className="mt-1">
            {verifyOpen ? (
              <span className="inline-flex items-center gap-1.5">
                <input
                  value={urn}
                  onChange={(e) => setUrn(e.target.value)}
                  placeholder="UDYAM-XX-00-0000000"
                  aria-label={`Udyam URN for ${item.vendor}`}
                  className="w-44 rounded border border-dark-line bg-dark-card2 px-1.5 py-0.5 font-mono text-[11px] text-dark-text placeholder:text-dark-mute/60"
                />
                <button
                  onClick={() => urn.trim() && verify.mutate()}
                  disabled={urn.trim().length < 16 || verify.isPending}
                  className="mono-label text-mint disabled:opacity-40"
                >
                  {verify.isPending ? "…" : "verify"}
                </button>
                <button onClick={() => setVerifyOpen(false)} className="mono-label text-dark-mute">
                  ×
                </button>
              </span>
            ) : (
              <button
                onClick={() => setVerifyOpen(true)}
                className="mono-annot text-dark-mute transition-colors hover:text-accent-soft"
              >
                + verify Udyam URN
              </button>
            )}
            {verify.isError && (
              <p className="mono-annot mt-0.5 text-blush">{String(verify.error)}</p>
            )}
          </div>
        )}
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

function DefensePlan() {
  const plan = useQuery({ queryKey: ["payables-plan"], queryFn: () => api.payablesPlan() });
  const d = plan.data;
  if (!d || d.items.length === 0) return null;
  return (
    <Card className="mt-5 px-5 py-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-bold text-dark-text">
          Deduction Defense — pay these first
        </p>
        <p className="mono-annot">
          {formatINRCompact(d.totals.planned_paise)} protects the deduction
          {d.totals.daily_bleed_paise > 0 &&
            ` · §16 bleeding ${formatINR(d.totals.daily_bleed_paise)}/day until paid`}
          {d.cash_basis_paise != null &&
            ` · cash basis ${formatINRCompact(d.cash_basis_paise)} (latest forecast)`}
        </p>
      </div>
      <ol className="mt-3 space-y-2">
        {d.items.map((item, idx) => (
          <li key={item.bill_number} className="flex items-start gap-3 text-sm">
            <span className="mono-label mt-0.5 shrink-0 text-dark-mute">{idx + 1}.</span>
            <div className="min-w-0 flex-1">
              <span className="font-bold text-dark-text">{item.vendor}</span>{" "}
              <span className="font-mono text-xs text-dark-mute">{item.bill_number}</span>
              <p className="mt-0.5 text-xs text-dark-mute">
                {item.why} · act by {item.action_by}
              </p>
            </div>
            <div className="shrink-0 text-right">
              <p className="font-mono text-sm font-semibold text-dark-text">
                {formatINRCompact(item.outstanding_paise)}
              </p>
              <Pill tone={item.affordable_now ? "good" : "warn"}>
                {item.affordable_now ? "affordable now" : "needs inflow"}
              </Pill>
            </div>
          </li>
        ))}
      </ol>
      <p className="mono-annot mt-3">
        ◇ deterministic ranking: closing windows by deadline, breached by daily §16 bleed ·
        advice only — findesk moves no money
      </p>
    </Card>
  );
}

export default function PayablesPage() {
  const payables = useQuery({ queryKey: ["payables"], queryFn: () => api.payables() });
  const p = payables.data;

  // The section number is SERVER-derived per tax year — §43B(h) under the ITA
  // 1961 through FY 2025-26, §37(2)(g) under the ITA 2025 from 1 Apr 2026 — so
  // it is never hardcoded here. Falls back to a neutral phrase before data
  // arrives rather than briefly showing the wrong citation.
  const statute = p?.items?.[0]?.clock?.statute;
  const statuteLabel = statute?.label ?? "MSME disallowance";
  const statuteAct = statute?.act ?? "";

  return (
    <PageShell
      title="Payables Shield"
      surface="dark"
      subtitle={`§15 clock and ${statuteLabel} tax exposure on bills owed to MSE vendors`}
      annotation="GET /payables/compliance · deterministic clock engine"
    >
      <p className="mono-annot mb-5">
        ◇ same statutory engine as the radar, pointed at what we owe · pay inside 45 days or the
        expense deduction defers (income-tax {statuteLabel}
        {statuteAct ? `, ${statuteAct}` : ""})
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
              label={`${statuteLabel} at risk`}
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

          {p.drift_alerts.length > 0 && (
            <Card className="mt-5 border-amber/40 px-5 py-4">
              <p className="flex items-center gap-2 text-sm font-bold text-dark-text">
                <ShieldAlert size={15} className="text-amber" /> Udyam status drift — scope
                changed
              </p>
              <ul className="mt-2 space-y-1">
                {p.drift_alerts.map((d) => (
                  <li key={d.vendor} className="text-xs text-dark-mute">
                    <span className="font-bold text-dark-text">{d.vendor}</span> — tagged{" "}
                    <span className="font-mono">{d.self_declared}</span>, register says{" "}
                    <span className="font-mono">{d.verified}</span> → {d.effect}. Update your
                    vendor master with your CA.
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <DefensePlan />

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
                      {statuteLabel} at risk
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
