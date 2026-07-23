"use client";
// IMS · ITC Shield — the tenant's GST Invoice Management System queue.
// Mandatory since Apr 2026: accept/reject/pending decides input-tax credit.
// The match + recommendation are deterministic 3-way checks against the
// purchase register; accept/reject never executes here — each action queues
// a maker-checker approval and the token-gated tool call happens on decide.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { CheckCircle2, Download, ShieldQuestion, XCircle } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import {
  Card,
  EmptyState,
  ErrorNote,
  PageShell,
  Pill,
  PrimaryBtn,
  Skeleton,
  StatCard,
  stagger,
} from "@/components/ui";
import { api, formatINR, formatINRCompact, type ImsRecordItem } from "@/lib/api";

const TIER_LABEL: Record<string, string> = {
  exact: "exact match",
  tolerant: "rounding delta",
  amount_mismatch: "amount mismatch",
  credit_note: "credit note",
  no_bill: "no purchase bill",
  unknown_supplier: "unknown supplier",
};

const STATE_TONE: Record<string, "good" | "warn" | "bad" | "neutral"> = {
  accepted: "good",
  rejected: "bad",
  pending: "neutral",
};

function RecordRow({
  rec,
  queuedApproval,
  onAct,
  acting,
}: {
  rec: ImsRecordItem;
  queuedApproval: string | null;
  onAct: (id: string, state: "accepted" | "rejected") => void;
  acting: boolean;
}) {
  const pending = rec.state === "pending";
  const recTone = rec.recommendation === "accept" ? "good" : "warn";
  return (
    <motion.tr
      variants={{ initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 } }}
      className="border-b border-dark-line align-top transition-colors last:border-0 hover:bg-dark-card2/50"
    >
      <td className="px-5 py-4">
        <p className="text-sm font-bold text-dark-text">{rec.supplier_name}</p>
        <p className="mt-0.5 font-mono text-xs text-dark-mute">
          {rec.doc_number} · {rec.doc_type.replace("_", " ")} · {rec.doc_date}
        </p>
        {rec.note && <p className="mt-1.5 max-w-md text-xs leading-relaxed text-dark-mute">{rec.note}</p>}
      </td>
      <td className="whitespace-nowrap px-5 py-4 text-right font-mono font-semibold text-dark-text">
        {formatINRCompact(rec.total_paise)}
      </td>
      <td className="whitespace-nowrap px-5 py-4 text-right">
        <span className="font-mono text-sm font-bold text-accent-soft">
          {formatINR(rec.tax_paise)}
        </span>
        <p className="mono-annot mt-0.5">ITC</p>
      </td>
      <td className="px-5 py-4">
        {rec.match_tier && (
          <Pill tone={recTone}>{TIER_LABEL[rec.match_tier] ?? rec.match_tier}</Pill>
        )}
        {rec.matched_bill_number && (
          <p className="mono-annot mt-1">↳ bill {rec.matched_bill_number}</p>
        )}
      </td>
      <td className="px-5 py-4">
        {pending && rec.recommendation && (
          <Pill tone={recTone}>
            {rec.recommendation === "accept" ? "recommend accept" : "needs review"}
          </Pill>
        )}
        {!pending && <Pill tone={STATE_TONE[rec.state] ?? "neutral"}>{rec.state}</Pill>}
      </td>
      <td className="whitespace-nowrap px-5 py-4 text-right">
        {queuedApproval ? (
          <Link href="/approvals" className="inline-block">
            <Pill tone="warn">queued → approvals</Pill>
          </Link>
        ) : pending ? (
          <div className="flex justify-end gap-2">
            <button
              onClick={() => onAct(rec.id, "accepted")}
              disabled={acting}
              className="inline-flex items-center gap-1 rounded-md border border-dark-line px-2.5 py-1.5 font-mono text-xs font-semibold text-mint transition-colors hover:bg-dark-card2 disabled:opacity-40"
            >
              <CheckCircle2 size={13} /> accept
            </button>
            <button
              onClick={() => onAct(rec.id, "rejected")}
              disabled={acting}
              className="inline-flex items-center gap-1 rounded-md border border-dark-line px-2.5 py-1.5 font-mono text-xs font-semibold text-blush transition-colors hover:bg-dark-card2 disabled:opacity-40"
            >
              <XCircle size={13} /> reject
            </button>
          </div>
        ) : (
          <span className="mono-annot">decided</span>
        )}
      </td>
    </motion.tr>
  );
}

export default function ImsPage() {
  const queryClient = useQueryClient();
  const queue = useQuery({ queryKey: ["ims"], queryFn: () => api.imsQueue() });
  const [queued, setQueued] = useState<Record<string, string>>({});

  const sync = useMutation({
    mutationFn: () => api.imsSync(),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["ims"] }),
  });
  const act = useMutation({
    mutationFn: (v: { id: string; state: "accepted" | "rejected" }) =>
      api.imsAction(v.id, v.state),
    onSuccess: (out, v) => {
      setQueued((q) => ({ ...q, [v.id]: out.approval_id }));
      void queryClient.invalidateQueries({ queryKey: ["approvals"] });
    },
  });

  const d = queue.data;
  const records = d?.records ?? [];

  return (
    <PageShell
      title="IMS · ITC Shield"
      surface="dark"
      subtitle="Supplier filings vs your purchase register — every accept/reject is maker-checker gated"
      annotation="GET /ims/queue · POST /ims/records/:id/action → approvals · mandatory since Apr 2026"
      actions={
        <PrimaryBtn onClick={() => sync.mutate()} disabled={sync.isPending}>
          <Download size={14} className={sync.isPending ? "animate-pulse" : ""} />
          {sync.isPending ? "Pulling…" : "Pull IMS queue"}
        </PrimaryBtn>
      }
    >
      <p className="mono-annot mb-5">
        ◇ Section 38: ITC now rides on IMS state · recommendations are deterministic 3-way
        checks · a wrong reject punishes your supplier — review tiers never auto-reject
      </p>

      {queue.isLoading && <Skeleton className="h-96" />}
      {queue.isError && <ErrorNote>{String(queue.error)}</ErrorNote>}

      {d && records.length === 0 && (
        <EmptyState hint="POST /ims/sync — fixture GSP records land here">
          <ShieldQuestion className="mb-2 inline" size={18} /> No IMS records pulled yet — hit
          “Pull IMS queue”.
        </EmptyState>
      )}

      {d && records.length > 0 && (
        <>
          <motion.div
            {...stagger}
            className="mb-5 grid grid-cols-2 gap-4 lg:grid-cols-4"
          >
            <StatCard
              label="ITC at stake (pending)"
              value={d.totals.itc_at_stake_paise}
              format={formatINRCompact}
              tone="accent"
            />
            <StatCard label="needs review" value={d.totals.review_count} tone="bad" />
            <StatCard
              label="accept-ready ITC"
              value={d.totals.accept_ready_paise}
              format={formatINRCompact}
              tone="good"
            />
            <StatCard
              label="accepted this period"
              value={d.totals.accepted_tax_paise}
              format={formatINRCompact}
            />
          </motion.div>

          <Card className="overflow-x-auto p-0">
            <table className="w-full min-w-[820px] text-left">
              <thead>
                <tr className="border-b border-dark-line">
                  {["supplier / document / evidence", "total", "tax (ITC)", "match", "recommendation", ""].map(
                    (h) => (
                      <th key={h} className="mono-label px-5 py-3 text-dark-mute">
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <motion.tbody {...stagger}>
                {records.map((rec) => (
                  <RecordRow
                    key={rec.id}
                    rec={rec}
                    queuedApproval={queued[rec.id] ?? null}
                    onAct={(id, state) => act.mutate({ id, state })}
                    acting={act.isPending}
                  />
                ))}
              </motion.tbody>
            </table>
          </Card>
          <p className="mono-annot mt-4">{d.ca_note}</p>
        </>
      )}
    </PageShell>
  );
}
