"use client";
// Reconciliation — "Run + residuals" (wireframe Reconciliation A): the live
// Planner → Executor → Critic → Approval-gate pipeline over SSE, plus the
// residual queue the critic refused to auto-commit.
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Upload } from "lucide-react";
import Link from "next/link";
import { useMemo, useRef, useState } from "react";

import {
  Card,
  EmptyState,
  ErrorNote,
  PageShell,
  PrimaryBtn,
  Skeleton,
  stagger,
} from "@/components/ui";
import { useRunStream } from "@/hooks/useRunStream";
import { api, formatINR } from "@/lib/api";

const STAGES = [
  { key: "planner", label: "planner", blurb: "decomposes: match → categorize → conflict-check" },
  { key: "executor", label: "executor", blurb: "matches lines · memory recalled per counterparty" },
  { key: "critic", label: "critic", blurb: "validates against beliefs · disagreements → human queue" },
  { key: "approval", label: "approval gate", blurb: "consequential commits wait for maker-checker" },
];

function stageState(events: { name?: string; status?: string; event: string }[], done: boolean) {
  // Map run step events onto the four canonical stages for the pipeline strip.
  const seen = events.filter((e) => e.event.startsWith("step."));
  const finished = seen.filter((e) => e.status === "finished").length;
  const active = done ? STAGES.length : Math.min(finished, STAGES.length - 1);
  return STAGES.map((s, i) => ({
    ...s,
    state: i < active ? "done" : i === active && !done ? "active" : done ? "done" : "waiting",
  }));
}

export default function ReconciliationPage() {
  const fileInput = useRef<HTMLInputElement>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const { events, done } = useRunStream(runId);

  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api.listRuns(), refetchInterval: 10_000 });
  const residuals = useQuery({
    queryKey: ["exceptions"],
    queryFn: () => api.exceptions(),
    refetchInterval: runId && !done ? 3000 : false,
  });

  async function upload(file: File) {
    setError(null);
    setUploading(true);
    try {
      const result = await api.importStatement(file);
      setRunId(result.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "upload failed");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  const stages = useMemo(() => stageState(events, done), [events, done]);
  const lastRun = runs.data?.[0];

  return (
    <PageShell
      title="Reconciliation"
      subtitle="Live agent runs (SSE) and the residual queue"
      annotation="SSE useRunStream(runId) · GET /books/exceptions"
      actions={
        <>
          <input
            ref={fileInput}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
          />
          <PrimaryBtn onClick={() => fileInput.current?.click()} disabled={uploading}>
            <Upload size={14} /> {uploading ? "Uploading…" : "Run on a statement"}
          </PrimaryBtn>
        </>
      }
    >
      {error && <ErrorNote>{error}</ErrorNote>}

      <Card className="p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-bold text-ink">
            {runId
              ? `Run ${runId.slice(0, 13)}…`
              : lastRun
                ? `Last run · ${lastRun.graph} · ${lastRun.status}`
                : "No runs yet"}
          </h2>
          {runId && !done && (
            <span className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-moss" />
              <span className="mono-label text-moss">streaming · useRunStream(runId)</span>
            </span>
          )}
          {runId && done && <span className="mono-label text-moss">run complete</span>}
        </div>

        <motion.div className="mt-5 grid gap-3 md:grid-cols-4" initial="initial" animate="animate" variants={stagger}>
          {stages.map((s, i) => (
            <motion.div
              key={s.key}
              variants={{ initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 } }}
              className={`rounded-xl border-[1.5px] p-4 transition-colors ${
                s.state === "done"
                  ? "border-moss/30 bg-moss/5"
                  : s.state === "active"
                    ? "border-accent/50 bg-accent/5"
                    : "border-dashed border-line bg-transparent"
              }`}
            >
              <div
                className={`mono-label ${
                  s.state === "done" ? "text-moss" : s.state === "active" ? "text-accent" : "text-faint"
                }`}
              >
                {i + 1} · {s.label} {s.state === "done" ? "✓" : s.state === "active" ? "◇" : ""}
              </div>
              <p className="mt-1.5 text-[13px] leading-snug text-mute">{s.blurb}</p>
            </motion.div>
          ))}
        </motion.div>

        {runId && (
          <div className="mt-5 max-h-56 space-y-1.5 overflow-y-auto rounded-xl border border-line2 bg-white/[0.05] p-4">
            {events.map((evt, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                className="flex items-center gap-2 text-[13px]"
              >
                <span
                  className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                    evt.event.startsWith("run.done")
                      ? "bg-moss"
                      : evt.status === "finished"
                        ? "bg-moss/60"
                        : evt.status === "failed"
                          ? "bg-claret"
                          : "bg-accent"
                  }`}
                />
                <span className="font-mono text-[11px] text-faint">{evt.name ?? evt.event}</span>
                <span className="truncate text-mute">{evt.summary ?? evt.status ?? ""}</span>
              </motion.div>
            ))}
          </div>
        )}
        <p className="mono-annot mt-4">◇ no LLM call in request handlers — all queued · everything consequential exits via the approval gate</p>
      </Card>

      <div className="mt-6">
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-bold text-ink">Residual queue — needs a human</h2>
          <span className="mono-annot hidden lg:block">◇ everything the critic or guardrails refused to auto-commit</span>
        </div>

        {residuals.isLoading && (
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
          </div>
        )}
        {residuals.isError && <ErrorNote>Could not load the residual queue.</ErrorNote>}
        {residuals.data && residuals.data.items.length === 0 && (
          <div className="mt-3">
            <EmptyState>Residual queue is clear — everything matched or was resolved.</EmptyState>
          </div>
        )}
        {residuals.data && residuals.data.items.length > 0 && (
          <motion.div className="mt-3 grid gap-3 md:grid-cols-2" initial="initial" animate="animate" variants={stagger}>
            {residuals.data.items.map((t) => (
              <motion.div
                key={t.id}
                variants={{ initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 } }}
                className="rounded-xl border-[1.5px] border-dashed border-line bg-card p-4 shadow-card"
              >
                <p className="text-sm font-bold text-ink">
                  {t.counterparty_hint ?? "Unknown counterparty"}{" "}
                  <span className="font-mono font-semibold text-mute">
                    {t.direction === "cr" ? "+" : "−"}
                    {formatINR(t.amount_paise)}
                  </span>
                </p>
                <p className="mt-1 truncate text-[13px] text-faint" title={t.narration}>
                  {t.narration}
                </p>
                <Link
                  href="/books"
                  className="mt-2 inline-block text-[13px] font-bold text-accent transition-transform hover:translate-x-0.5"
                >
                  Review →
                </Link>
              </motion.div>
            ))}
          </motion.div>
        )}
      </div>
    </PageShell>
  );
}
