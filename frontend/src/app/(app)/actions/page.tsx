"use client";
// WC Actions — "Ranked cards" (wireframe WC Actions A, dark surface B4):
// costed, ranked working-capital options. Drafts only — never auto-executed.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { RefreshCw } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import {
  Card,
  EmptyState,
  ErrorNote,
  MonoLabel,
  PageShell,
  Pill,
  PrimaryBtn,
  Skeleton,
  stagger,
} from "@/components/ui";
import { api, formatINR, formatINRCompact, type WcAction } from "@/lib/api";

function HeroAction({ action }: { action: WcAction }) {
  const queryClient = useQueryClient();
  const requestApproval = useMutation({
    mutationFn: () => api.requestWcAction(action.id),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["wc-actions"] }),
  });
  const q = action.detail.quote;
  const isTreds = action.kind === "treds";

  const stats: [string, string][] = isTreds && q
    ? [
        ["raises", formatINRCompact(action.unlock_paise)],
        ["rate", `${(q.discount_rate_bps_annual / 100).toFixed(1)}%`],
        ["cost", formatINRCompact(action.cost_paise)],
        ["settles", `T+1 · ${q.tenor_days}d tenor`],
      ]
    : [
        ["unlocks", formatINRCompact(action.unlock_paise)],
        ["overdue", `${action.detail.days_overdue ?? "—"} days`],
        ["cost", formatINRCompact(action.cost_paise)],
        ["path", "collections"],
      ];

  return (
    <Card className="border-mint/20 p-7">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-mint/40 font-mono text-sm font-bold text-mint">
            {action.rank}
          </span>
          <div>
            <h2 className="text-xl font-bold tracking-[-0.01em] text-dark-text">
              {isTreds
                ? `Discount ${formatINRCompact(action.unlock_paise)} receivable on TReDS`
                : `Accelerate collection — ${action.client}`}
            </h2>
            <p className="mt-1 text-sm text-dark-mute">
              {action.client} · {action.invoice_number}
              {isTreds
                ? ` · recommended · lowest cost of capital`
                : ` · ${action.detail.note ?? "chase before it ages further"}`}
            </p>
          </div>
        </div>
        <Pill tone="good">best fit</Pill>
      </div>

      <motion.div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4" initial="initial" animate="animate" variants={stagger}>
        {stats.map(([label, value]) => (
          <motion.div
            key={label}
            variants={{ initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 } }}
            className="rounded-xl border border-dark-line bg-dark-card2 p-4"
          >
            <MonoLabel>{label}</MonoLabel>
            <div className={`mt-1.5 font-mono text-lg font-bold ${label === "raises" || label === "unlocks" ? "text-mint" : "text-dark-text"}`}>
              {value}
            </div>
          </motion.div>
        ))}
      </motion.div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        {action.status === "proposed" &&
          (isTreds ? (
            <PrimaryBtn onClick={() => requestApproval.mutate()} disabled={requestApproval.isPending}>
              Draft → Approvals
            </PrimaryBtn>
          ) : (
            <Link
              href="/receivables"
              className="inline-flex items-center justify-center rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-[var(--accent-contrast)] shadow-[0_10px_24px_-10px_rgba(255,160,40,0.7)] transition-colors hover:bg-accent-soft"
            >
              Open radar →
            </Link>
          ))}
        {action.status === "approval_requested" && (
          <Link href="/approvals">
            <Pill tone="warn" className="!px-3 !py-1.5 !text-xs">awaiting approval →</Pill>
          </Link>
        )}
        {action.status === "executed" && <Pill tone="good" className="!px-3 !py-1.5 !text-xs">listed ✓</Pill>}
        <span className="mono-annot ml-auto hidden lg:block">
          ◇ POST /wc-actions/:id/request → /approvals · drafts only, never auto-executed
        </span>
      </div>
      {requestApproval.isError && (
        <ErrorNote>
          {requestApproval.error instanceof Error ? requestApproval.error.message : "request failed"}
        </ErrorNote>
      )}
    </Card>
  );
}

function CompactAction({ action, deltaVsTop }: { action: WcAction; deltaVsTop: number }) {
  return (
    <motion.div
      variants={{ initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 } }}
      whileHover={{ y: -2 }}
      className="flex items-center justify-between gap-4 rounded-2xl border border-dark-line bg-dark-card px-6 py-5 shadow-card-dark"
    >
      <div className="flex items-center gap-4">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-dark-line font-mono text-sm font-bold text-dark-mute">
          {action.rank}
        </span>
        <div>
          <p className="text-[15px] font-bold text-dark-text">
            {action.kind === "treds"
              ? `Discount ${action.invoice_number} on TReDS`
              : `Collect ${action.invoice_number} from ${action.client}`}
          </p>
          <p className="mt-0.5 text-xs text-dark-mute">
            unlocks {formatINR(action.unlock_paise)} · cost {formatINR(action.cost_paise)}
            {action.detail.days_overdue != null && ` · ${action.detail.days_overdue}d overdue`}
            {action.detail.predicted_payment && ` · else pays ~${action.detail.predicted_payment}`}
          </p>
        </div>
      </div>
      <span className="whitespace-nowrap font-mono text-sm text-dark-mute">
        {action.status === "proposed"
          ? deltaVsTop > 0
            ? `+${formatINRCompact(deltaVsTop)} vs #1`
            : "alt"
          : action.status.replace(/_/g, " ")}
      </span>
    </motion.div>
  );
}

export default function ActionsPage() {
  const queryClient = useQueryClient();
  const [running, setRunning] = useState(false);
  const actions = useQuery({ queryKey: ["wc-actions"], queryFn: () => api.wcActions() });

  async function recompute() {
    setRunning(true);
    try {
      await api.startRunByGraph("working_capital");
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["wc-actions"] });
        setRunning(false);
      }, 6000);
    } catch {
      setRunning(false);
    }
  }

  const list = [...(actions.data ?? [])].sort((a, b) => a.rank - b.rank);
  const [top, ...rest] = list;
  const unlockable = list
    .filter((a) => a.status === "proposed")
    .reduce((s, a) => s + a.unlock_paise, 0);

  return (
    <PageShell
      title="WC Actions"
      surface="dark"
      subtitle="Costed, ranked working-capital options — drafts only, never auto-executed"
      annotation="GET /wc-actions · POST /wc-actions/:id/request → /approvals"
      actions={
        <PrimaryBtn onClick={recompute} disabled={running}>
          <RefreshCw size={14} className={running ? "animate-spin" : ""} />
          {running ? "Computing…" : "Recompute options"}
        </PrimaryBtn>
      }
    >
      <p className="mono-annot mb-5">
        ◇ b4 · costed, ranked options{unlockable > 0 && ` · ${formatINRCompact(unlockable)} unlockable`} ·
        drafts only — never auto-executed
      </p>

      {actions.isLoading && (
        <>
          <Skeleton className="h-72" />
          <Skeleton className="mt-4 h-24" />
        </>
      )}
      {actions.isError && <ErrorNote>Could not load options.</ErrorNote>}
      {actions.data && list.length === 0 && (
        <EmptyState hint="POST /agent/runs {working_capital}">
          No options yet — hit Recompute to run the agent.
        </EmptyState>
      )}

      {top && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
          <HeroAction action={top} />
        </motion.div>
      )}
      {rest.length > 0 && (
        <motion.div className="mt-4 space-y-3" initial="initial" animate="animate" variants={stagger}>
          {rest.map((a) => (
            <CompactAction key={a.id} action={a} deltaVsTop={a.cost_paise - (top?.cost_paise ?? 0)} />
          ))}
        </motion.div>
      )}
    </PageShell>
  );
}
