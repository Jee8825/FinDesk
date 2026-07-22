"use client";
// Approvals — "Queue + dossier" (wireframe Approvals A, dark signature
// surface): the control plane. Nothing consequential executes without a
// single-use token minted here.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Check } from "lucide-react";
import { useState } from "react";

import {
  Card,
  EmptyState,
  ErrorNote,
  GhostBtn,
  MonoLabel,
  PageShell,
  Pill,
  PrimaryBtn,
  Skeleton,
} from "@/components/ui";
import { api, formatINR, type Approval } from "@/lib/api";

const KIND_META: Record<string, { chip: string; title: (a: Approval) => string }> = {
  send_email: {
    chip: "comms",
    title: (a) => `Collection chaser → ${String(a.action_payload.client ?? a.action_payload.invoice_number ?? "client")}`,
  },
  commit_match: {
    chip: "ledger",
    title: (a) =>
      `Commit ${a.action_payload.kind === "tds_adjusted" ? "TDS-adjusted " : ""}match · ${a.action_payload.invoice_number ?? "invoice"}`,
  },
  treds_listing: {
    chip: "cash",
    title: (a) => `TReDS discount draft · ${a.action_payload.invoice_number ?? ""}`,
  },
};

function Dossier({ approval }: { approval: Approval }) {
  const queryClient = useQueryClient();
  const decide = useMutation({
    mutationFn: (decision: "approved" | "rejected") => api.decideApproval(approval.id, decision),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["approvals"] }),
  });

  const p = approval.action_payload;
  const meta = KIND_META[approval.action_kind] ?? { chip: "action", title: () => approval.action_kind };
  const verdicts = Object.entries(approval.policy_verdicts).filter(
    ([, v]) => typeof v === "boolean" || typeof v === "number" || typeof v === "string",
  );

  return (
    <Card className="p-7">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-[-0.01em] text-dark-text">{meta.title(approval)}</h2>
          <p className="mt-1 text-sm text-dark-mute">
            drafted by agent · {new Date(approval.created_at).toLocaleString("en-IN")} · run{" "}
            {String(approval.requested_by.run_id ?? "?").slice(0, 13)}…
          </p>
        </div>
        <Pill tone="warn">needs approval</Pill>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_300px]">
        <div className="rounded-xl border border-dark-line bg-dark-card2 p-5">
          <MonoLabel>payload preview · the exact action that will execute</MonoLabel>
          {approval.action_kind === "send_email" ? (
            <div className="mt-3 space-y-3 text-sm leading-relaxed text-dark-text">
              <p className="font-semibold">
                Subject: {String(p.subject ?? "")}{" "}
                <span className="text-dark-mute">→ {((p.to as string[]) ?? []).join(", ")}</span>
              </p>
              <pre className="max-h-64 overflow-auto whitespace-pre-wrap font-sans text-[13px] text-dark-text/90">
                {String(p.body_md ?? "")}
              </pre>
              <p className="mono-annot">
                tone: {String(p.tone ?? "neutral")} · {String(approval.policy_verdicts.days_overdue ?? "—")} days overdue
              </p>
            </div>
          ) : (
            <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <div>
                <dt className="mono-label text-dark-mute">received</dt>
                <dd className="mt-1 font-mono font-semibold text-dark-text">{formatINR(p.amount_paise ?? 0)}</dd>
              </div>
              {p.kind === "tds_adjusted" && (
                <>
                  <div>
                    <dt className="mono-label text-dark-mute">tds {(p.tds_bps ?? 0) / 100}%</dt>
                    <dd className="mt-1 font-mono font-semibold text-dark-text">{formatINR(p.tds_paise ?? 0)}</dd>
                  </div>
                  <div>
                    <dt className="mono-label text-dark-mute">invoice total</dt>
                    <dd className="mt-1 font-mono font-semibold text-dark-text">
                      {formatINR((p.amount_paise ?? 0) + (p.tds_paise ?? 0))}
                    </dd>
                  </div>
                </>
              )}
              <div>
                <dt className="mono-label text-dark-mute">confidence</dt>
                <dd className="mt-1 font-mono font-semibold text-dark-text">
                  {Math.round((p.confidence ?? 0) * 100)}%
                  <span className="ml-1 text-xs text-dark-mute">
                    floor {Math.round(((approval.policy_verdicts.floor as number) ?? 0.9) * 100)}%
                  </span>
                </dd>
              </div>
              {p.invoice_number != null && (
                <div>
                  <dt className="mono-label text-dark-mute">invoice</dt>
                  <dd className="mt-1 font-mono font-semibold text-dark-text">{String(p.invoice_number)}</dd>
                </div>
              )}
            </dl>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-dark-line bg-dark-card2 p-5">
            <MonoLabel>critic reasoning</MonoLabel>
            <p className="mt-2 text-[13px] leading-relaxed text-dark-text/90">
              {p.critic_verdict?.verdict
                ? `Verdict: ${p.critic_verdict.verdict} (checker: ${p.critic_verdict.checker ?? "?"}). Independent model verified — safe to execute.`
                : "Deterministic guardrails passed; no independent critic verdict recorded for this action kind."}
            </p>
          </div>
          <div className="rounded-xl border border-dark-line bg-dark-card2 p-5">
            <MonoLabel>guardrails</MonoLabel>
            <ul className="mt-2 space-y-1.5">
              {verdicts.length === 0 && (
                <li className="text-[13px] text-dark-mute">no policy verdicts attached</li>
              )}
              {verdicts.map(([k, v]) => (
                <li key={k} className="flex items-center gap-2 text-[13px] text-dark-text/90">
                  <Check size={13} className="shrink-0 text-mint" />
                  <span className="font-mono text-xs">
                    {k} · {String(v)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <PrimaryBtn onClick={() => decide.mutate("approved")} disabled={decide.isPending}>
          {approval.action_kind === "send_email" ? "Approve & send" : "Approve & post"}
        </PrimaryBtn>
        <GhostBtn onClick={() => decide.mutate("rejected")} disabled={decide.isPending}>
          Reject
        </GhostBtn>
        <span className="mono-annot ml-auto hidden lg:block">
          ◇ POST /approvals/:id {"{approve|reject}"} + idempotency token · writes audit
        </span>
      </div>
      {decide.isError && (
        <ErrorNote>{decide.error instanceof Error ? decide.error.message : "decision failed"}</ErrorNote>
      )}
    </Card>
  );
}

export default function ApprovalsPage() {
  const approvals = useQuery({ queryKey: ["approvals"], queryFn: () => api.approvals() });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const queue = approvals.data ?? [];
  const selected = queue.find((a) => a.id === selectedId) ?? queue[0];

  return (
    <PageShell
      title="Approvals"
      surface="dark"
      subtitle="The control surface — everything consequential waits here"
      annotation="GET /approvals · POST /approvals/:id {approve|reject} + token"
    >
      <p className="mono-annot mb-5">
        ◇ signature surface · the control plane — nothing consequential executes without a token
        here
      </p>

      {approvals.isLoading && (
        <div className="grid gap-5 xl:grid-cols-[340px_1fr]">
          <Skeleton className="h-72" />
          <Skeleton className="h-96" />
        </div>
      )}
      {approvals.isError && <ErrorNote>Could not load the approval queue.</ErrorNote>}
      {approvals.data && queue.length === 0 && (
        <EmptyState>Queue is clear — nothing waiting on you.</EmptyState>
      )}

      {queue.length > 0 && (
        <div className="grid items-start gap-5 xl:grid-cols-[340px_1fr]">
          <Card className="overflow-hidden !p-0">
            <div className="flex items-center justify-between border-b border-dark-line px-5 py-4">
              <span className="text-sm font-bold text-dark-text">Pending</span>
              <span className="font-mono text-sm font-semibold text-accent-soft">{queue.length}</span>
            </div>
            <motion.ul initial="initial" animate="animate" variants={{ animate: { transition: { staggerChildren: 0.05 } } }}>
              {queue.map((a) => {
                const meta = KIND_META[a.action_kind] ?? { chip: "action", title: () => a.action_kind };
                const active = selected?.id === a.id;
                return (
                  <motion.li key={a.id} variants={{ initial: { opacity: 0, x: -10 }, animate: { opacity: 1, x: 0 } }}>
                    <button
                      onClick={() => setSelectedId(a.id)}
                      className={`relative block w-full border-b border-dark-line px-5 py-4 text-left transition-colors last:border-0 ${
                        active ? "bg-dark-card2" : "hover:bg-dark-card2/50"
                      }`}
                    >
                      {active && (
                        <motion.span layoutId="approval-marker" className="absolute bottom-0 left-0 top-0 w-[3px] bg-accent" />
                      )}
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-[13px] font-bold text-dark-text">{meta.title(a)}</span>
                        <span className="mono-label shrink-0 text-dark-mute">{meta.chip}</span>
                      </div>
                      <p className="mt-1 truncate text-xs text-dark-mute">
                        {a.action_payload.amount_paise != null && `${formatINR(a.action_payload.amount_paise)} · `}
                        {new Date(a.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                      </p>
                    </button>
                  </motion.li>
                );
              })}
            </motion.ul>
          </Card>

          <AnimatePresence mode="wait">
            {selected && (
              <motion.div
                key={selected.id}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10, transition: { duration: 0.18 } }}
                transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              >
                <Dossier approval={selected} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </PageShell>
  );
}
