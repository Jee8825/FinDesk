"use client";
// Run Viewer — the glass box, list side. Every agent run the tenant has,
// newest first; open one to watch its steps, durations and verdicts.
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import Link from "next/link";

import { Card, EmptyState, PageShell, Pill, Skeleton, stagger } from "@/components/ui";
import { api } from "@/lib/api";

const TONE: Record<string, "good" | "warn" | "bad" | "neutral"> = {
  succeeded: "good",
  failed: "bad",
  cancelled: "neutral",
  running: "warn",
  queued: "warn",
};

const TERMINAL = new Set(["succeeded", "failed", "cancelled"]);

export default function RunsPage() {
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.listRuns(),
    refetchInterval: (q) =>
      (q.state.data ?? []).some((r) => !TERMINAL.has(r.status)) ? 3000 : false,
  });
  const list = runs.data ?? [];

  return (
    <PageShell
      title="Run Viewer"
      surface="dark"
      subtitle="Every agent run, step by step — deterministic engines, visible working"
      annotation="GET /agent/runs · SSE per run · steps persisted with durations"
    >
      <p className="mono-annot mb-5">
        ◇ glass box: the same event stream the approval gate audits — nothing summarized,
        nothing hidden
      </p>

      {runs.isLoading && <Skeleton className="h-72" />}
      {runs.isSuccess && list.length === 0 && (
        <EmptyState hint="POST /agent/runs — any Recompute button wakes the agent">
          No runs yet — import a statement or hit Recompute on the forecast.
        </EmptyState>
      )}

      {list.length > 0 && (
        <Card className="overflow-x-auto p-0">
          <table className="w-full min-w-[640px] text-left">
            <thead>
              <tr className="border-b border-dark-line">
                {["graph", "status", "started", "run id"].map((h) => (
                  <th key={h} className="mono-label px-5 py-3 text-dark-mute">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <motion.tbody {...stagger}>
              {list.map((r) => (
                <motion.tr
                  key={r.run_id}
                  variants={{ initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 } }}
                  className="border-b border-dark-line transition-colors last:border-0 hover:bg-dark-card2/50"
                >
                  <td className="px-5 py-3.5">
                    <Link
                      href={`/runs/${r.run_id}`}
                      className="text-sm font-bold text-dark-text hover:text-accent-soft"
                    >
                      {r.graph}
                    </Link>
                  </td>
                  <td className="px-5 py-3.5">
                    <Pill tone={TONE[r.status] ?? "neutral"}>{r.status}</Pill>
                  </td>
                  <td className="whitespace-nowrap px-5 py-3.5 font-mono text-xs text-dark-mute">
                    {r.created_at ? new Date(r.created_at).toLocaleString("en-IN") : "—"}
                  </td>
                  <td className="whitespace-nowrap px-5 py-3.5">
                    <Link
                      href={`/runs/${r.run_id}`}
                      className="font-mono text-xs text-dark-mute hover:text-accent-soft"
                    >
                      {r.run_id.slice(0, 13)}…
                    </Link>
                  </td>
                </motion.tr>
              ))}
            </motion.tbody>
          </table>
        </Card>
      )}
    </PageShell>
  );
}
