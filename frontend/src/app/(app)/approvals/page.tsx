"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, formatINR, type Approval } from "@/lib/api";

function ApprovalCard({ approval }: { approval: Approval }) {
  const queryClient = useQueryClient();
  const decide = useMutation({
    mutationFn: ({ decision }: { decision: "approved" | "rejected" }) =>
      api.decideApproval(approval.id, decision),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["approvals"] }),
  });

  const p = approval.action_payload;
  const isTds = p.kind === "tds_adjusted";
  const invoiceTotal = (p.amount_paise ?? 0) + (p.tds_paise ?? 0);

  return (
    <li className="rounded-xl border bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-ink">
            Post payment against {p.invoice_number ?? "invoice"}
            {isTds && (
              <span className="ml-2 rounded-full bg-violet-50 px-2 py-0.5 text-xs font-medium text-violet-700">
                TDS-adjusted
              </span>
            )}
          </p>
          <dl className="mt-3 grid grid-cols-2 gap-x-8 gap-y-1 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-xs uppercase text-slate-400">Received</dt>
              <dd className="font-mono">{formatINR(p.amount_paise ?? 0)}</dd>
            </div>
            {isTds && (
              <>
                <dt className="sr-only">TDS</dt>
                <div>
                  <dt className="text-xs uppercase text-slate-400">
                    TDS {(p.tds_bps ?? 0) / 100}%
                  </dt>
                  <dd className="font-mono">{formatINR(p.tds_paise ?? 0)}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-slate-400">Invoice total</dt>
                  <dd className="font-mono">{formatINR(invoiceTotal)}</dd>
                </div>
              </>
            )}
            <div>
              <dt className="text-xs uppercase text-slate-400">Confidence</dt>
              <dd>
                {Math.round((p.confidence ?? 0) * 100)}%
                <span className="ml-1 text-xs text-slate-400">
                  (floor {Math.round(((approval.policy_verdicts.floor as number) ?? 0.9) * 100)}%)
                </span>
              </dd>
            </div>
          </dl>
          <p className="mt-2 text-xs text-slate-500">
            critic: {p.critic_verdict?.verdict ?? "?"} ({p.critic_verdict?.checker ?? "?"}) ·
            requested by run {String(approval.requested_by.run_id ?? "?").slice(0, 13)}…
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            onClick={() => decide.mutate({ decision: "approved" })}
            disabled={decide.isPending}
            className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            Approve & post
          </button>
          <button
            onClick={() => decide.mutate({ decision: "rejected" })}
            disabled={decide.isPending}
            className="rounded-md border px-3 py-1.5 text-sm text-slate-600 disabled:opacity-50"
          >
            Reject
          </button>
        </div>
      </div>
      {decide.isError && (
        <p className="mt-2 text-sm text-red-600" role="alert">
          {decide.error instanceof Error ? decide.error.message : "decision failed"}
        </p>
      )}
    </li>
  );
}

export default function ApprovalsPage() {
  const approvals = useQuery({ queryKey: ["approvals"], queryFn: () => api.approvals() });

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-semibold text-ink">Approvals</h1>
      <p className="mt-1 text-sm text-slate-500">
        Everything consequential waits here. The agent recommends with evidence; you decide.
        Approving posts to the books and records a single-use, hash-bound token in the audit
        trail.
      </p>

      {approvals.isLoading && (
        <div className="mt-6 space-y-3">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="h-28 animate-pulse rounded-xl bg-slate-100" />
          ))}
        </div>
      )}
      {approvals.isError && (
        <p className="mt-6 text-sm text-red-600">Could not load the approval queue.</p>
      )}
      {approvals.data && approvals.data.length === 0 && (
        <div className="mt-6 rounded-xl border border-dashed bg-white p-10 text-center text-sm text-slate-500">
          Queue is clear — nothing waiting on you.
        </div>
      )}
      {approvals.data && approvals.data.length > 0 && (
        <ul className="mt-6 space-y-3">
          {approvals.data.map((a) => (
            <ApprovalCard key={a.id} approval={a} />
          ))}
        </ul>
      )}
    </div>
  );
}
