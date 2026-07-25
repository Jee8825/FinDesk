"use client";
// Anomalies — "Cards + rollup" (wireframe Anomalies A): duplicates,
// overcharges, out-of-pattern — with the recoverable ₹ as the headline KPI.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { ScanLine } from "lucide-react";
import { useState } from "react";

import {
  AnimatedNumber,
  Card,
  EmptyState,
  ErrorNote,
  GhostBtn,
  InkBtn,
  MonoLabel,
  PageShell,
  Pill,
  PrimaryBtn,
  Skeleton,
} from "@/components/ui";
import { useRunStream } from "@/hooks/useRunStream";
import { api, formatINR, type AnomalyCard } from "@/lib/api";

const KIND_LABEL: Record<string, { label: string; tone: "bad" | "warn" | "neutral" }> = {
  duplicate: { label: "duplicate payment", tone: "bad" },
  overcharge: { label: "over baseline", tone: "warn" },
  out_of_pattern: { label: "out of pattern", tone: "neutral" },
};

function AnomalyRow({ anomaly }: { anomaly: AnomalyCard }) {
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
  const meta = KIND_LABEL[anomaly.kind] ?? { label: anomaly.kind, tone: "neutral" as const };

  return (
    <Card hover className="p-6">
      <div className="flex items-start justify-between gap-6">
        <div className="min-w-0">
          <MonoLabel className={meta.tone === "bad" ? "!text-claret" : meta.tone === "warn" ? "!text-accent" : ""}>
            {meta.label}
          </MonoLabel>
          <p className="mt-1.5 text-[17px] font-bold leading-snug text-ink">
            {anomaly.vendor_label} <Pill tone={meta.tone} className="ml-1 align-middle">{anomaly.kind.replace(/_/g, " ")}</Pill>
          </p>
          <p className="mt-2 text-sm leading-relaxed text-mute">{anomaly.recommended_action}</p>
          <p className="mono-annot mt-2">
            {ev.amount_paise !== undefined && <>amount {formatINR(ev.amount_paise)}</>}
            {ev.baseline_paise !== undefined && <> · baseline {formatINR(ev.baseline_paise)} ({ev.ratio}×)</>}
            {ev.days_apart !== undefined && <> · {ev.days_apart} days apart</>}
          </p>
        </div>
        {anomaly.recoverable_paise != null && (
          <div className="shrink-0 text-right font-mono text-lg font-bold text-moss">
            +{formatINR(anomaly.recoverable_paise)}
          </div>
        )}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {anomaly.recoverable_paise != null && (
          <InkBtn onClick={() => decide.mutate("recovered")} disabled={decide.isPending}>
            Mark recovered
          </InkBtn>
        )}
        <GhostBtn onClick={() => decide.mutate("accepted")} disabled={decide.isPending}>
          Legit charge
        </GhostBtn>
        <GhostBtn onClick={() => decide.mutate("dismissed")} disabled={decide.isPending}>
          Dismiss
        </GhostBtn>
      </div>
      {decide.isError && (
        <ErrorNote>{decide.error instanceof Error ? decide.error.message : "decision failed"}</ErrorNote>
      )}
    </Card>
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

  const open = (anomalies.data ?? []).filter((a) => a.status === "open");
  const totalRecoverable = open.reduce((s, a) => s + (a.recoverable_paise ?? 0), 0);
  const dupes = open.filter((a) => a.kind === "duplicate").reduce((s, a) => s + (a.recoverable_paise ?? 0), 0);
  const over = open.filter((a) => a.kind === "overcharge").reduce((s, a) => s + (a.recoverable_paise ?? 0), 0);
  const handled = (anomalies.data ?? []).filter((a) => a.status !== "open");
  const recoveredToDate = handled
    .filter((a) => a.status === "recovered")
    .reduce((s, a) => s + (a.recoverable_paise ?? 0), 0);

  return (
    <PageShell
      title="Anomalies"
      subtitle="Duplicates, overcharges, out-of-pattern — recoverable ₹ flagged"
      annotation="GET /anomalies · recoverable rollup"
      actions={
        <PrimaryBtn onClick={scan} disabled={Boolean(runId) && !done}>
          <ScanLine size={14} /> {runId && !done ? "Scanning…" : "Run scan"}
        </PrimaryBtn>
      }
    >
      <AnimatePresence>
        {runId && !done && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="mono-annot mb-4"
          >
            ◇ scanning… {events[events.length - 1]?.name ?? ""}
          </motion.p>
        )}
      </AnimatePresence>

      <div className="grid gap-5 xl:grid-cols-[1fr_320px]">
        <div className="space-y-4">
          {anomalies.isLoading && (
            <>
              <Skeleton className="h-44" />
              <Skeleton className="h-44" />
            </>
          )}
          {anomalies.isError && <ErrorNote>Could not load anomalies.</ErrorNote>}
          {anomalies.data && open.length === 0 && (
            <EmptyState hint="run a scan after importing statements">
              No open anomalies — nothing is leaking.
            </EmptyState>
          )}
          <AnimatePresence mode="popLayout">
            {open.map((a) => (
              <motion.div
                key={a.id}
                layout
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: 60, transition: { duration: 0.25 } }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
              >
                <AnomalyRow anomaly={a} />
              </motion.div>
            ))}
          </AnimatePresence>
        </div>

        <Card className="sticky top-6 self-start p-6">
          <MonoLabel className="!text-moss">recoverable — open findings</MonoLabel>
          <div className="mt-3 font-mono text-[34px] font-bold leading-none text-moss">
            <AnimatedNumber value={totalRecoverable} format={formatINR} />
          </div>
          <p className="mt-2 text-xs text-faint">across {open.length} open finding{open.length === 1 ? "" : "s"}</p>
          <div className="mt-5 space-y-2.5 border-t border-line2 pt-4 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-mute">Duplicates</span>
              <span className="font-mono font-semibold text-ink">{formatINR(dupes)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-mute">Overcharges</span>
              <span className="font-mono font-semibold text-ink">{formatINR(over)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-faint">Other patterns</span>
              <span className="font-mono text-faint">{formatINR(totalRecoverable - dupes - over)}</span>
            </div>
          </div>
          {handled.length > 0 && (
            <div className="mt-4 space-y-2.5 border-t border-line2 pt-4 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-mute">Recovered to date</span>
                <span className="font-mono font-semibold text-moss">
                  {formatINR(recoveredToDate)}
                </span>
              </div>
              <p className="text-xs text-faint">
                {handled.length} finding{handled.length === 1 ? "" : "s"} caught &amp; decided —
                duplicates never resurface once handled
              </p>
            </div>
          )}
          <p className="mono-annot mt-5">
            ◇ &quot;defends your cash&quot; — this number is the product&apos;s headline KPI
          </p>
        </Card>
      </div>
    </PageShell>
  );
}
