"use client";
// A8's signature affordance: any number explains itself. Renders the
// hash-chained audit trail for one entity as a provenance chain.
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Link2, X } from "lucide-react";

import { api, type WhyRef } from "@/lib/api";

export function WhyDrawer({ refs, onClose }: { refs: WhyRef[]; onClose: () => void }) {
  const first = refs[0];
  const trail = useQuery({
    queryKey: ["why", first?.kind, first?.id],
    queryFn: () => api.why(first.kind, first.id),
    enabled: Boolean(first),
  });

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex justify-end bg-ink/40 backdrop-blur-[2px]"
        role="dialog"
        aria-label="evidence trail"
        onClick={onClose}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <motion.div
          className="glass-strong grain h-full w-full max-w-lg overflow-y-auto border-l border-line p-6"
          onClick={(e) => e.stopPropagation()}
          initial={{ x: 64, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 64, opacity: 0 }}
          transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="flex items-center justify-between">
            <div>
              <div className="mono-label text-accent">why? · provenance chain</div>
              <h2 className="mt-1 text-lg font-bold text-ink">Every figure answers Why?</h2>
            </div>
            <button
              onClick={onClose}
              aria-label="close"
              className="rounded-lg border border-line p-2 text-mute transition-colors hover:bg-white/[0.06]"
            >
              <X size={14} />
            </button>
          </div>
          <p className="mono-annot mt-2">
            {first ? `${first.kind} · ${first.id.slice(0, 13)}…` : ""}
            {refs.length > 1 && ` · +${refs.length - 1} related`}
          </p>

          {trail.isLoading && (
            <div className="mt-6 space-y-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-16 animate-pulse rounded-xl bg-white/[0.05]" />
              ))}
            </div>
          )}
          {trail.isError && (
            <p className="mt-6 text-sm text-claret">Could not load the evidence trail.</p>
          )}
          {trail.data && trail.data.events.length === 0 && (
            <p className="mt-6 text-sm text-faint">
              No agent actions recorded for this entity yet — it came in via import and
              hasn&apos;t been touched.
            </p>
          )}
          {trail.data && (trail.data.memory?.length ?? 0) > 0 && (
            <div className="mt-6">
              <div className="mono-label text-accent">what the agent believed</div>
              <div className="mt-2 space-y-2.5">
                {trail.data.memory!.map((b) => (
                  <div
                    key={b.memory_id}
                    className="rounded-xl border border-line2 bg-card p-3"
                  >
                    <p className="text-sm text-ink">{b.content}</p>
                    <p className="mono-annot mt-1.5">
                      {b.scope_key}
                      {b.confidence != null && ` · confidence ${b.confidence.toFixed(2)}`}
                    </p>
                    {b.explanation && (
                      <p className="mt-1.5 text-xs text-faint">{b.explanation}</p>
                    )}
                  </div>
                ))}
              </div>
              <p className="mono-annot mt-2">
                ◇ live from the memory engine — beliefs recalled for this counterparty
              </p>
            </div>
          )}
          {trail.data && trail.data.events.length > 0 && (
            <motion.ol
              className="relative mt-6 space-y-5 pl-5"
              initial="initial"
              animate="animate"
              variants={{ animate: { transition: { staggerChildren: 0.07 } } }}
            >
              <span className="absolute bottom-1 left-[5px] top-1 w-[2px] rounded bg-line" />
              {trail.data.events.map((e, i) => (
                <motion.li
                  key={i}
                  className="relative"
                  variants={{
                    initial: { opacity: 0, x: 16 },
                    animate: { opacity: 1, x: 0, transition: { duration: 0.35 } },
                  }}
                >
                  <span
                    className={`absolute -left-5 top-1 h-3 w-3 rounded-full border-2 border-cream ${
                      i === trail.data!.events.length - 1 ? "bg-moss" : "bg-accent"
                    }`}
                  />
                  <p className="text-sm font-semibold text-ink">{e.action}</p>
                  <p className="mt-0.5 text-xs text-faint">
                    {new Date(e.at).toLocaleString("en-IN")} · {String(e.actor.kind ?? "system")}
                    {e.actor.run_id ? ` · run ${String(e.actor.run_id).slice(0, 13)}…` : ""}
                  </p>
                  <pre className="mt-1.5 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg border border-line2 bg-card p-2.5 font-mono text-[11px] leading-relaxed text-mute">
                    {JSON.stringify(e.payload, null, 1)}
                  </pre>
                  <p
                    className="mono-annot mt-1 flex items-center gap-1"
                    title="audit chain hash"
                  >
                    <Link2 size={10} /> {e.row_hash.slice(0, 24)}…
                  </p>
                </motion.li>
              ))}
            </motion.ol>
          )}
          <p className="mono-annot mt-6">
            ◇ hash-chained audit log · deterministic rollup · no LLM in the math
          </p>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
