"use client";

import { useState } from "react";

import { useRunStream } from "@/hooks/useRunStream";
import { api } from "@/lib/api";

export default function Dashboard() {
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { events, done } = useRunStream(runId);

  async function startPing() {
    setError(null);
    try {
      const run = await api.startRun("ping");
      setRunId(run.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed to start run");
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold text-ink">Dashboard</h1>
      <p className="mt-1 text-sm text-slate-500">
        Phase 0 — the walking skeleton. Cash position, runway and alerts land in
        later phases; today this proves the agent loop end to end.
      </p>

      <section className="mt-8 rounded-xl border bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-medium">Agent pulse check</h2>
            <p className="text-sm text-slate-500">
              Queues a <code>ping</code> graph: Planner → Executor → Critic, streamed live.
            </p>
          </div>
          <button
            onClick={startPing}
            className="rounded-md bg-teal-brand px-4 py-2 text-sm font-medium text-white"
          >
            Run ping
          </button>
        </div>

        {error && <p className="mt-4 text-sm text-red-600" role="alert">{error}</p>}

        {runId && (
          <div className="mt-6">
            <p className="text-xs text-slate-400">run {runId}</p>
            <ul className="mt-2 space-y-1">
              {events.map((evt, i) => (
                <li key={i} className="flex items-center gap-2 text-sm">
                  <span
                    className={`inline-block h-2 w-2 rounded-full ${
                      evt.event.startsWith("run.done")
                        ? "bg-emerald-500"
                        : evt.status === "finished"
                          ? "bg-teal-brand"
                          : "bg-amber-400"
                    }`}
                  />
                  <span className="font-mono text-xs text-slate-500">{evt.event}</span>
                  <span>{evt.name ?? evt.summary ?? ""}</span>
                  <span className="text-slate-400">{evt.status ?? ""}</span>
                </li>
              ))}
            </ul>
            {done && <p className="mt-3 text-sm font-medium text-emerald-600">Run complete.</p>}
          </div>
        )}
      </section>
    </div>
  );
}
