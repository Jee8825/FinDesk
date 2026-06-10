"use client";
// A8's signature affordance: any number explains itself. Renders the
// hash-chained audit trail for one entity as a readable timeline.
import { useQuery } from "@tanstack/react-query";

import { api, type WhyRef } from "@/lib/api";

export function WhyDrawer({ refs, onClose }: { refs: WhyRef[]; onClose: () => void }) {
  const first = refs[0];
  const trail = useQuery({
    queryKey: ["why", first?.kind, first?.id],
    queryFn: () => api.why(first.kind, first.id),
    enabled: Boolean(first),
  });

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/30"
      role="dialog"
      aria-label="evidence trail"
      onClick={onClose}
    >
      <div
        className="h-full w-full max-w-lg overflow-y-auto bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-ink">Why?</h2>
          <button onClick={onClose} className="rounded-md border px-3 py-1 text-sm">
            Close
          </button>
        </div>
        <p className="mt-1 text-xs text-slate-400">
          {first ? `${first.kind} ${first.id.slice(0, 13)}…` : ""}
          {refs.length > 1 && ` (+${refs.length - 1} related)`}
        </p>

        {trail.isLoading && (
          <div className="mt-6 space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-16 animate-pulse rounded-lg bg-slate-100" />
            ))}
          </div>
        )}
        {trail.isError && (
          <p className="mt-6 text-sm text-red-600">Could not load the evidence trail.</p>
        )}
        {trail.data && trail.data.events.length === 0 && (
          <p className="mt-6 text-sm text-slate-500">
            No agent actions recorded for this entity yet — it came in via import and hasn&apos;t
            been touched.
          </p>
        )}
        {trail.data && trail.data.events.length > 0 && (
          <ol className="mt-6 space-y-4 border-l-2 border-teal-brand/30 pl-4">
            {trail.data.events.map((e, i) => (
              <li key={i}>
                <p className="text-sm font-medium text-ink">{e.action}</p>
                <p className="text-xs text-slate-500">
                  {new Date(e.at).toLocaleString("en-IN")} ·{" "}
                  {String(e.actor.kind ?? "system")}
                  {e.actor.run_id ? ` · run ${String(e.actor.run_id).slice(0, 13)}…` : ""}
                </p>
                <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-2 text-xs text-slate-600">
                  {JSON.stringify(e.payload, null, 1)}
                </pre>
                <p className="mt-1 font-mono text-[10px] text-slate-300" title="audit chain hash">
                  ⛓ {e.row_hash.slice(0, 24)}…
                </p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
