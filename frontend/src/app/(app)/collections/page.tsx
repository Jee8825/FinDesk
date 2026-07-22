"use client";
// Collections — "Drafts + preview" (wireframe Collections A, dark surface):
// agent-drafted chasers with per-client tone. The agent drafts, never sends —
// every send is a send_email approval with a token.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { PenLine } from "lucide-react";
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

function DraftPreview({ draft }: { draft: Approval }) {
  const queryClient = useQueryClient();
  const decide = useMutation({
    mutationFn: (decision: "approved" | "rejected") => api.decideApproval(draft.id, decision),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["approvals"] }),
  });
  const p = draft.action_payload;
  const to = (p.to as string[] | undefined) ?? [];

  return (
    <Card className="p-7">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-[-0.01em] text-dark-text">
            Chaser · {String(p.invoice_number ?? "invoice")}
          </h2>
          <p className="mt-1 text-sm text-dark-mute">to {to.join(", ") || "client accounts team"}</p>
        </div>
        <span className="mono-label text-accent-soft">
          tone: {String(p.tone ?? "neutral")} (auto-selected)
        </span>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Pill tone="neutral">
          {String(draft.policy_verdicts.days_overdue ?? "—")} days overdue
        </Pill>
        {p.amount_paise != null && <Pill tone="warn">{formatINR(p.amount_paise)} outstanding</Pill>}
        <Pill tone="neutral">policy P2 (tone) passed</Pill>
      </div>

      <div className="mt-5 rounded-xl border border-dark-line bg-dark-card2 p-6">
        <p className="text-sm font-semibold text-dark-text">Subject: {String(p.subject ?? "")}</p>
        <pre className="mt-4 max-h-72 overflow-auto whitespace-pre-wrap font-sans text-[13.5px] leading-relaxed text-dark-text/90">
          {String(p.body_md ?? "")}
        </pre>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <PrimaryBtn onClick={() => decide.mutate("approved")} disabled={decide.isPending}>
          Approve & send →
        </PrimaryBtn>
        <GhostBtn onClick={() => decide.mutate("rejected")} disabled={decide.isPending}>
          Reject draft
        </GhostBtn>
        <span className="mono-annot ml-auto hidden lg:block">
          ◇ agent drafts, never sends — all routes through approvals
        </span>
      </div>
      {decide.isError && (
        <ErrorNote>{decide.error instanceof Error ? decide.error.message : "decision failed"}</ErrorNote>
      )}
    </Card>
  );
}

export default function CollectionsPage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drafting, setDrafting] = useState(false);
  const approvals = useQuery({ queryKey: ["approvals"], queryFn: () => api.approvals() });

  const drafts = (approvals.data ?? []).filter((a) => a.action_kind === "send_email");
  const selected = drafts.find((d) => d.id === selectedId) ?? drafts[0];

  async function draftChasers() {
    setDrafting(true);
    try {
      await api.startRunByGraph("collections");
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["approvals"] });
        setDrafting(false);
      }, 5000);
    } catch {
      setDrafting(false);
    }
  }

  return (
    <PageShell
      title="Collections"
      surface="dark"
      subtitle="Drafted chasers awaiting approval, per-client tone"
      annotation="drafts → approval queue · POST /agent/runs {collections}"
      actions={
        <PrimaryBtn onClick={draftChasers} disabled={drafting}>
          <PenLine size={14} /> {drafting ? "Drafting…" : "Draft chasers"}
        </PrimaryBtn>
      }
    >
      <p className="mono-annot mb-5">
        ◇ agent drafts, never sends — per-client tone tuned from payment history · all routes to
        approvals
      </p>

      {approvals.isLoading && (
        <div className="grid gap-5 xl:grid-cols-[320px_1fr]">
          <Skeleton className="h-60" />
          <Skeleton className="h-96" />
        </div>
      )}
      {approvals.isError && <ErrorNote>Could not load drafts.</ErrorNote>}
      {approvals.data && drafts.length === 0 && (
        <EmptyState hint="the collections graph reads the radar and drafts one chaser per overdue invoice">
          No chaser drafts waiting. Hit “Draft chasers” to put the agent to work.
        </EmptyState>
      )}

      {drafts.length > 0 && (
        <div className="grid items-start gap-5 xl:grid-cols-[320px_1fr]">
          <Card className="overflow-hidden !p-0">
            <motion.ul initial="initial" animate="animate" variants={{ animate: { transition: { staggerChildren: 0.05 } } }}>
              {drafts.map((d) => {
                const active = selected?.id === d.id;
                return (
                  <motion.li key={d.id} variants={{ initial: { opacity: 0, x: -10 }, animate: { opacity: 1, x: 0 } }}>
                    <button
                      onClick={() => setSelectedId(d.id)}
                      className={`relative block w-full border-b border-dark-line px-5 py-4 text-left transition-colors last:border-0 ${
                        active ? "bg-dark-card2" : "hover:bg-dark-card2/50"
                      }`}
                    >
                      {active && (
                        <motion.span layoutId="draft-marker" className="absolute bottom-0 left-0 top-0 w-[3px] bg-accent" />
                      )}
                      <p className="truncate text-[13px] font-bold text-dark-text">
                        {String(d.action_payload.invoice_number ?? "draft")} ·{" "}
                        {String(d.action_payload.tone ?? "neutral")}
                      </p>
                      <p className="mt-1 truncate text-xs text-dark-mute">
                        {d.action_payload.amount_paise != null && `${formatINR(d.action_payload.amount_paise)} · `}
                        {String(d.policy_verdicts.days_overdue ?? "—")}d overdue
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
                <DraftPreview draft={selected} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </PageShell>
  );
}
