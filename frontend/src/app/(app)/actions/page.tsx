"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { api, formatINR, type WcAction } from "@/lib/api";

function ActionCard({ action }: { action: WcAction }) {
  const queryClient = useQueryClient();
  const requestApproval = useMutation({
    mutationFn: () => api.requestWcAction(action.id),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["wc-actions"] }),
  });
  const q = action.detail.quote;

  return (
    <li className="rounded-xl border bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-ink">
            <span className="mr-2 text-slate-400">#{action.rank}</span>
            {action.kind === "treds" ? "Discount on TReDS" : "Accelerate collection"} —{" "}
            {action.client} · {action.invoice_number}
          </p>
          <p className="mt-2 text-sm text-slate-600">
            {action.kind === "treds" && q ? (
              <>
                Unlock <strong>{formatINR(action.unlock_paise)}</strong> today instead of
                waiting ~{action.detail.days_to_cash_without_action} days (expected{" "}
                {action.detail.predicted_payment}). Cost {formatINR(action.cost_paise)} @{" "}
                {q.discount_rate_bps_annual / 100}% p.a. over {q.tenor_days} days.
              </>
            ) : (
              <>
                {formatINR(action.unlock_paise)} overdue by {action.detail.days_overdue} days.{" "}
                {action.detail.note}
              </>
            )}
          </p>
        </div>
        <div className="shrink-0 text-right">
          {action.status === "executed" && (
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
              listed ✓
            </span>
          )}
          {action.status === "approval_requested" && (
            <Link
              href="/approvals"
              className="rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700"
            >
              awaiting approval →
            </Link>
          )}
          {action.status === "proposed" &&
            (action.kind === "treds" ? (
              <button
                onClick={() => requestApproval.mutate()}
                disabled={requestApproval.isPending}
                className="rounded-md bg-teal-brand px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              >
                Request approval
              </button>
            ) : (
              <Link
                href="/receivables"
                className="rounded-md border px-3 py-1.5 text-sm text-slate-600"
              >
                Open radar →
              </Link>
            ))}
        </div>
      </div>
      {requestApproval.isError && (
        <p className="mt-2 text-sm text-red-600" role="alert">
          {requestApproval.error instanceof Error
            ? requestApproval.error.message
            : "request failed"}
        </p>
      )}
    </li>
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

  const unlockable = (actions.data ?? [])
    .filter((a) => a.status === "proposed")
    .reduce((sum, a) => sum + a.unlock_paise, 0);

  return (
    <div className="max-w-3xl">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Working capital</h1>
          <p className="mt-1 text-sm text-slate-500">
            Ranked, costed options to bring cash forward. Recommend-only — nothing executes
            without your approval.
          </p>
        </div>
        <button
          onClick={recompute}
          disabled={running}
          className="rounded-md bg-teal-brand px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {running ? "Computing…" : "Recompute options"}
        </button>
      </div>

      {unlockable > 0 && (
        <p className="mt-4 rounded-lg bg-teal-brand/10 px-4 py-2 text-sm font-medium text-teal-brand">
          {formatINR(unlockable)} unlockable across{" "}
          {(actions.data ?? []).filter((a) => a.status === "proposed").length} open options
        </p>
      )}

      {actions.isLoading && (
        <div className="mt-6 space-y-3">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="h-28 animate-pulse rounded-xl bg-slate-100" />
          ))}
        </div>
      )}
      {actions.isError && <p className="mt-6 text-sm text-red-600">Could not load options.</p>}
      {actions.data && actions.data.length === 0 && (
        <div className="mt-6 rounded-xl border border-dashed bg-white p-10 text-center text-sm text-slate-500">
          No options yet — hit Recompute to run the agent.
        </div>
      )}
      {actions.data && actions.data.length > 0 && (
        <ul className="mt-6 space-y-3">
          {actions.data.map((a) => (
            <ActionCard key={a.id} action={a} />
          ))}
        </ul>
      )}
    </div>
  );
}
