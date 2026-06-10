"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useRunStream } from "@/hooks/useRunStream";
import { api, formatINR, type AnomalyCard } from "@/lib/api";

const KIND_STYLES: Record<string, string> = {
  duplicate: "bg-red-50 text-red-700",
  overcharge: "bg-orange-50 text-orange-700",
  out_of_pattern: "bg-amber-50 text-amber-700",
};

function Card({ anomaly }: { anomaly: AnomalyCard }) {
  const queryClient = useQueryClient();
  const decide = useMutation({
    mutationFn: (decision: "accepted" | "dismissed" | "recovered") =>
      api.decideAnomaly(anomaly.id, decision),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["anomalies"] }),
  });
  const ev = anomaly.evidence as {
    amount_paise?: number;
    baseline_paise?: number;
    ratio?: number;
    days_apart?: number;
  };

  return (
    <li className="rounded-xl border bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-ink">
            {anomaly.vendor_label}
            <span
              className={`ml-2 rounded-full px-2 py-0.5 text-xs font-medium ${
                KIND_STYLES[anomaly.kind] ?? "bg-slate-100 text-slate-600"
              }`}
            >
              {anomaly.kind.replace(/_/g, " ")}
            </span>
          </p>
          <p className="mt-2 text-sm text-slate-600">{anomaly.recommended_action}</p>
          <p className="mt-2 text-xs text-slate-500">
            {ev.amount_paise !== undefined && <>amount {formatINR(ev.amount_paise)}</>}
            {ev.baseline_paise !== undefined && (
              <> · usual {formatINR(ev.baseline_paise)} ({ev.ratio}×)</>
            )}
            {ev.days_apart !== undefined && <> · {ev.days_apart} days apart</>}
          </p>
        </div>
        <div className="shrink-0 text-right">
          {anomaly.recoverable_paise != null && (
            <p className="rounded-lg bg-emerald-50 px-3 py-1.5 text-sm font-semibold text-emerald-700">
              {formatINR(anomaly.recoverable_paise)} recoverable
            </p>
          )}
          <div className="mt-3 flex justify-end gap-2">
            {anomaly.recoverable_paise != null && (
              <button
                onClick={() => decide.mutate("recovered")}
                disabled={decide.isPending}
                className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
              >
                Mark recovered
              </button>
            )}
            <button
              onClick={() => decide.mutate("accepted")}
              disabled={decide.isPending}
              className="rounded-md bg-ink px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
            >
              Legit charge
            </button>
            <button
              onClick={() => decide.mutate("dismissed")}
              disabled={decide.isPending}
              className="rounded-md border px-3 py-1.5 text-xs text-slate-600 disabled:opacity-50"
            >
              Dismiss
            </button>
          </div>
        </div>
      </div>
    </li>
  );
}

export default function AnomaliesPage() {
  const queryClient = useQueryClient();
  const [runId, setRunId] = useState<string | null>(null);
  const { events, done } = useRunStream(runId);
  const anomalies = useQuery({
    queryKey: ["anomalies"],
    queryFn: () => api.anomalies(),
    refetchInterval: runId && !done ? 2000 : false,
  });

  async function scan() {
    const run = await api.startRunByGraph("anomaly_scan");
    setRunId(run.run_id);
    queryClient.invalidateQueries({ queryKey: ["anomalies"] });
  }

  const totalRecoverable = (anomalies.data ?? []).reduce(
    (sum, a) => sum + (a.recoverable_paise ?? 0),
    0,
  );

  return (
    <div className="max-w-3xl">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Anomalies</h1>
          <p className="mt-1 text-sm text-slate-500">
            Duplicates, overcharges and pattern breaks — with the money you could get back.
          </p>
        </div>
        <button
          onClick={scan}
          className="rounded-md bg-teal-brand px-4 py-2 text-sm font-medium text-white"
        >
          Run scan
        </button>
      </div>

      {totalRecoverable > 0 && (
        <p className="mt-4 rounded-lg bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-800">
          {formatINR(totalRecoverable)} potentially recoverable across{" "}
          {anomalies.data?.length} findings
        </p>
      )}

      {runId && !done && (
        <p className="mt-3 text-xs text-slate-500">
          scanning… {events[events.length - 1]?.name ?? ""}
        </p>
      )}

      {anomalies.isLoading && (
        <div className="mt-6 space-y-3">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-xl bg-slate-100" />
          ))}
        </div>
      )}
      {anomalies.isError && (
        <p className="mt-6 text-sm text-red-600">Could not load anomalies.</p>
      )}
      {anomalies.data && anomalies.data.length === 0 && (
        <div className="mt-6 rounded-xl border border-dashed bg-white p-10 text-center text-sm text-slate-500">
          No open anomalies. Run a scan after importing statements.
        </div>
      )}
      {anomalies.data && anomalies.data.length > 0 && (
        <ul className="mt-6 space-y-3">
          {anomalies.data.map((a) => (
            <Card key={a.id} anomaly={a} />
          ))}
        </ul>
      )}
    </div>
  );
}
