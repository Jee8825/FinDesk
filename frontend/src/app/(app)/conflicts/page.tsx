"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type ConflictCard } from "@/lib/api";

function ClaimBox({
  label,
  content,
  confidence,
  onPick,
  disabled,
}: {
  label: string;
  content: string;
  confidence: number | null;
  onPick: () => void;
  disabled: boolean;
}) {
  const pct = Math.round((confidence ?? 0) * 100);
  return (
    <div className="flex flex-1 flex-col rounded-lg border bg-slate-50 p-4">
      <p className="text-xs font-medium uppercase text-slate-400">{label}</p>
      <p className="mt-1 flex-1 text-sm text-slate-800">{content}</p>
      <div className="mt-3">
        <div className="h-1.5 w-full rounded bg-slate-200">
          <div className="h-1.5 rounded bg-teal-brand" style={{ width: `${pct}%` }} />
        </div>
        <p className="mt-1 text-xs text-slate-500">confidence {pct}%</p>
      </div>
      <button
        onClick={onPick}
        disabled={disabled}
        className="mt-3 rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
      >
        Keep this
      </button>
    </div>
  );
}

function Card({ conflict }: { conflict: ConflictCard }) {
  const queryClient = useQueryClient();
  const resolve = useMutation({
    mutationFn: (winner: "a" | "b") => api.resolveConflict(conflict.id, winner),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["conflicts"] }),
  });

  return (
    <li className="rounded-xl border bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-ink">
          {conflict.engine_view.counterparty ?? conflict.scope_key}
          <span className="ml-2 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
            {conflict.claim_kind.replace("_", " ")}
          </span>
        </p>
        <p className="text-xs text-slate-400">
          semantic distance {(conflict.engine_view.semantic_distance ?? 0).toFixed(3)}
        </p>
      </div>
      <div className="mt-4 flex flex-col gap-3 sm:flex-row">
        <ClaimBox
          label="Existing belief"
          content={conflict.claim_a.content}
          confidence={conflict.claim_a.confidence}
          onPick={() => resolve.mutate("a")}
          disabled={resolve.isPending}
        />
        <ClaimBox
          label="New observation"
          content={conflict.claim_b.content}
          confidence={conflict.claim_b.confidence}
          onPick={() => resolve.mutate("b")}
          disabled={resolve.isPending}
        />
      </div>
      {conflict.engine_view.engine_rationale && (
        <p className="mt-3 text-xs text-slate-500">
          engine: {conflict.engine_view.engine_rationale}
        </p>
      )}
      {resolve.isError && (
        <p className="mt-2 text-sm text-red-600" role="alert">
          {resolve.error instanceof Error ? resolve.error.message : "resolution failed"}
        </p>
      )}
    </li>
  );
}

export default function ConflictsPage() {
  const conflicts = useQuery({ queryKey: ["conflicts"], queryFn: () => api.conflicts() });

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-semibold text-ink">Conflicts</h1>
      <p className="mt-1 text-sm text-slate-500">
        The agent never overwrites a belief it has contradicting evidence about. Pick the claim
        that&apos;s true — the loser is forgotten (atomically, with provenance), the winner is
        reinforced.
      </p>

      {conflicts.isLoading && (
        <div className="mt-6 space-y-3">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="h-40 animate-pulse rounded-xl bg-slate-100" />
          ))}
        </div>
      )}
      {conflicts.isError && (
        <p className="mt-6 text-sm text-red-600">Could not load conflicts.</p>
      )}
      {conflicts.data && conflicts.data.length === 0 && (
        <div className="mt-6 rounded-xl border border-dashed bg-white p-10 text-center text-sm text-slate-500">
          No open conflicts — the books and the agent&apos;s beliefs agree.
        </div>
      )}
      {conflicts.data && conflicts.data.length > 0 && (
        <ul className="mt-6 space-y-3">
          {conflicts.data.map((c) => (
            <Card key={c.id} conflict={c} />
          ))}
        </ul>
      )}
    </div>
  );
}
