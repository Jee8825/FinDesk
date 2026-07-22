"use client";
// Conflicts — "Card stack" (wireframe Conflicts A, signature surface A4):
// both claims side-by-side, confidence bars, one-tap resolve. The agent never
// silently overwrites a contested belief.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";

import {
  Bar,
  Card,
  EmptyState,
  ErrorNote,
  MonoLabel,
  PageShell,
  Skeleton,
} from "@/components/ui";
import { api, type ConflictCard } from "@/lib/api";

function ClaimBox({
  label,
  content,
  confidence,
  kind,
}: {
  label: string;
  content: string;
  confidence: number | null;
  kind: "memory" | "new";
}) {
  const pct = Math.round((confidence ?? 0) * 100);
  const memory = kind === "memory";
  return (
    <motion.div
      initial={{ opacity: 0, x: memory ? -18 : 18 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className={`flex flex-1 flex-col rounded-2xl border p-5 ${
        memory ? "border-memory/30 bg-memory/5" : "border-accent/30 bg-accent/5"
      }`}
    >
      <MonoLabel className={memory ? "!text-memory" : "!text-accent"}>{label}</MonoLabel>
      <p className="mt-2 flex-1 text-[15px] font-semibold leading-snug text-ink">{content}</p>
      <div className="mt-4">
        <Bar pct={pct} tone={memory ? "memory" : "accent"} />
        <p className={`mono-annot mt-1.5 ${memory ? "!text-memory" : "!text-accent"}`}>
          confidence {(pct / 100).toFixed(2)}
        </p>
      </div>
    </motion.div>
  );
}

function TopCard({ conflict, index, total }: { conflict: ConflictCard; index: number; total: number }) {
  const queryClient = useQueryClient();
  const resolve = useMutation({
    mutationFn: (winner: "a" | "b") => api.resolveConflict(conflict.id, winner),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["conflicts"] }),
  });

  return (
    <Card className="border-accent/30 p-7">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-[-0.01em] text-ink">
            {conflict.engine_view.counterparty ?? conflict.scope_key} —{" "}
            {conflict.claim_kind.replace(/_/g, " ")} in conflict
          </h2>
          <p className="mt-1 text-sm text-mute">
            two claims disagree · engine distance{" "}
            {(conflict.engine_view.semantic_distance ?? 0).toFixed(3)}
          </p>
        </div>
        <span className="mono-annot whitespace-nowrap">
          conflict <span className="font-semibold text-accent">{index + 1} of {total}</span>
        </span>
      </div>

      <div className="mt-6 flex flex-col items-stretch gap-4 md:flex-row md:items-center">
        <ClaimBox
          label="claim a · memory (stored belief)"
          content={conflict.claim_a.content}
          confidence={conflict.claim_a.confidence}
          kind="memory"
        />
        <span className="mono-label shrink-0 self-center text-faint">vs</span>
        <ClaimBox
          label="claim b · new observation"
          content={conflict.claim_b.content}
          confidence={conflict.claim_b.confidence}
          kind="new"
        />
      </div>

      <div className="mt-6 grid gap-3 md:grid-cols-2">
        <motion.button
          whileHover={{ scale: 1.015 }}
          whileTap={{ scale: 0.97 }}
          disabled={resolve.isPending}
          onClick={() => resolve.mutate("a")}
          className="rounded-xl bg-memory px-4 py-3 text-sm font-bold text-white shadow-[0_10px_24px_-10px_rgba(74,111,165,0.7)] transition-colors hover:bg-[#3d5e8e] disabled:opacity-50"
        >
          Keep the stored belief
        </motion.button>
        <motion.button
          whileHover={{ scale: 1.015 }}
          whileTap={{ scale: 0.97 }}
          disabled={resolve.isPending}
          onClick={() => resolve.mutate("b")}
          className="rounded-xl bg-accent px-4 py-3 text-sm font-bold text-white shadow-[0_10px_24px_-10px_rgba(232,115,10,0.7)] transition-colors hover:bg-[#d96905] disabled:opacity-50"
        >
          Accept the new observation
        </motion.button>
      </div>

      {conflict.engine_view.engine_rationale && (
        <p className="mono-annot mt-4">◇ engine: {conflict.engine_view.engine_rationale}</p>
      )}
      <p className="mono-annot mt-1.5">
        ◇ POST /conflicts/:id/resolve — writes belief + provenance atomically; the loser is
        forgotten, the winner reinforced
      </p>
      {resolve.isError && (
        <ErrorNote>
          {resolve.error instanceof Error ? resolve.error.message : "resolution failed"}
        </ErrorNote>
      )}
    </Card>
  );
}

export default function ConflictsPage() {
  const conflicts = useQuery({ queryKey: ["conflicts"], queryFn: () => api.conflicts() });
  const open = conflicts.data ?? [];
  const [top, ...rest] = open;

  return (
    <PageShell
      title="Conflicts"
      subtitle="Cross-period conflicts — both claims, confidence, one-tap resolve"
      annotation="GET /conflicts · POST /conflicts/:id/resolve"
    >
      <p className="mono-annot mb-5">
        ◇ signature surface a4 · both claims shown side-by-side · the agent never silently
        overwrites a belief
      </p>

      {conflicts.isLoading && <Skeleton className="h-80" />}
      {conflicts.isError && <ErrorNote>Could not load conflicts.</ErrorNote>}
      {conflicts.data && open.length === 0 && (
        <EmptyState>No open conflicts — the books and the agent&apos;s beliefs agree.</EmptyState>
      )}

      <AnimatePresence mode="popLayout">
        {top && (
          <motion.div
            key={top.id}
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, x: 80, scale: 0.96, transition: { duration: 0.3 } }}
            transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
          >
            <TopCard conflict={top} index={0} total={open.length} />
          </motion.div>
        )}
      </AnimatePresence>

      {rest.length > 0 && (
        <motion.div
          className="mt-4 grid gap-3 md:grid-cols-2"
          initial="initial"
          animate="animate"
          variants={{ animate: { transition: { staggerChildren: 0.06 } } }}
        >
          {rest.map((c, i) => (
            <motion.div
              key={c.id}
              variants={{ initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 } }}
              className="rounded-xl border border-line2 bg-card/70 px-5 py-4 shadow-card"
            >
              <p className="text-sm font-bold text-ink">
                {c.engine_view.counterparty ?? c.scope_key} · {c.claim_kind.replace(/_/g, " ")}
              </p>
              <p className="mono-annot mt-1">{i === 0 ? "up next" : "queued"}</p>
            </motion.div>
          ))}
        </motion.div>
      )}
    </PageShell>
  );
}
