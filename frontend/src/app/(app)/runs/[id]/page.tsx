"use client";
// Run Viewer — detail. Persisted steps for finished runs; the live SSE tail
// (reconnecting, FE2) for running ones. Durations from the step lifecycle,
// critic passes highlighted — the maker-checker story made visible.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowLeft, CheckCircle2, CircleDot, ShieldCheck, XCircle } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect } from "react";

import { Card, PageShell, Pill, Skeleton, stagger } from "@/components/ui";
import { useRunStream, type RunEvent } from "@/hooks/useRunStream";
import { api, type RunStep } from "@/lib/api";

const TERMINAL = new Set(["succeeded", "failed", "cancelled"]);
const TONE: Record<string, "good" | "warn" | "bad" | "neutral"> = {
  succeeded: "good",
  failed: "bad",
  cancelled: "neutral",
  running: "warn",
  queued: "warn",
};

function fmtMs(ms: number | null | undefined): string {
  if (ms == null) return "";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

function StepIcon({ status }: { status: string }) {
  if (status === "finished") return <CheckCircle2 size={16} className="text-mint" />;
  if (status === "failed") return <XCircle size={16} className="text-blush" />;
  return <CircleDot size={16} className="animate-pulse text-accent-soft" />;
}

function liveSteps(events: RunEvent[]): RunStep[] {
  // reduce the replayed+live frames to ordered unique steps, last status wins
  const order: string[] = [];
  const byId = new Map<string, RunStep>();
  for (const e of events) {
    if (!e.event?.startsWith("run.step@") || !e.step_id) continue;
    if (!byId.has(e.step_id)) order.push(e.step_id);
    byId.set(e.step_id, {
      step_id: e.step_id,
      name: e.name ?? byId.get(e.step_id)?.name ?? "?",
      status: e.status ?? "started",
    });
  }
  return order.map((id) => byId.get(id)!);
}

function DetailChips({ detail }: { detail?: Record<string, unknown> }) {
  if (!detail) return null;
  const entries = Object.entries(detail)
    .filter(([, v]) => ["string", "number", "boolean"].includes(typeof v))
    .slice(0, 4);
  if (entries.length === 0) return null;
  return (
    <span className="ml-2 inline-flex flex-wrap gap-1.5">
      {entries.map(([k, v]) => (
        <span key={k} className="mono-annot rounded border border-dark-line px-1.5 py-0.5">
          {k}={String(v)}
        </span>
      ))}
    </span>
  );
}

export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const runId = params.id;
  const queryClient = useQueryClient();

  const run = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId),
  });
  const terminal = run.data ? TERMINAL.has(run.data.status) : false;
  const stream = useRunStream(run.isSuccess && !terminal ? runId : null);

  useEffect(() => {
    if (stream.done) {
      void queryClient.invalidateQueries({ queryKey: ["run", runId] });
      void queryClient.invalidateQueries({ queryKey: ["runs"] });
    }
  }, [stream.done, queryClient, runId]);

  const steps: RunStep[] = terminal ? (run.data?.steps ?? []) : liveSteps(stream.events);
  const totalMs = terminal
    ? (run.data?.steps ?? []).reduce((s, x) => s + (x.duration_ms ?? 0), 0)
    : null;

  return (
    <PageShell
      title={run.data ? `run · ${run.data.graph}` : "run"}
      surface="dark"
      subtitle="Step timeline — the agent's visible working"
      annotation={`GET /agent/runs/${runId.slice(0, 13)}… · SSE tail while running`}
      actions={
        <Link
          href="/runs"
          className="inline-flex items-center gap-1 font-mono text-xs text-dark-mute hover:text-accent-soft"
        >
          <ArrowLeft size={13} /> all runs
        </Link>
      }
    >
      {run.isLoading && <Skeleton className="h-72" />}

      {run.data && (
        <>
          <div className="mb-5 flex flex-wrap items-center gap-3">
            <Pill tone={TONE[run.data.status] ?? "neutral"}>{run.data.status}</Pill>
            {!terminal && (
              <Pill tone={stream.state === "live" ? "good" : "warn"}>
                stream {stream.state}
              </Pill>
            )}
            {totalMs != null && totalMs > 0 && (
              <span className="mono-annot">total {fmtMs(totalMs)}</span>
            )}
            {run.data.created_at && (
              <span className="mono-annot">
                started {new Date(run.data.created_at).toLocaleString("en-IN")}
              </span>
            )}
            <span className="mono-annot select-all">{runId}</span>
          </div>

          <Card className="p-0">
            <motion.ol {...stagger} className="divide-y divide-dark-line">
              {steps.length === 0 && (
                <li className="px-5 py-6 text-sm text-dark-mute">
                  Waiting for the first step event…
                </li>
              )}
              {steps.map((s, idx) => {
                const critic = s.name.toLowerCase().includes("critic");
                return (
                  <motion.li
                    key={s.step_id}
                    variants={{ initial: { opacity: 0, x: -8 }, animate: { opacity: 1, x: 0 } }}
                    className="flex items-center gap-3 px-5 py-3.5"
                  >
                    <span className="mono-label w-6 shrink-0 text-dark-mute">{idx + 1}</span>
                    <StepIcon status={s.status} />
                    <span className="min-w-0 flex-1">
                      <span className="font-mono text-sm font-semibold text-dark-text">
                        {s.name}
                      </span>
                      {critic && (
                        <span className="ml-2 inline-flex items-center gap-1 align-middle">
                          <ShieldCheck size={13} className="text-mint" />
                          <span className="mono-annot text-mint">critic gate</span>
                        </span>
                      )}
                      <DetailChips detail={s.detail} />
                    </span>
                    <span className="mono-annot shrink-0">{fmtMs(s.duration_ms)}</span>
                  </motion.li>
                );
              })}
            </motion.ol>
          </Card>

          <p className="mono-annot mt-4">
            Same events the audit chain records — approvals reference run + step ids, so every
            consequential action traces back to a visible line above.
          </p>
        </>
      )}
    </PageShell>
  );
}
