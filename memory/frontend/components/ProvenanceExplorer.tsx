"use client";

import { useEffect, useState } from "react";
import { api, type WhyResult } from "@/lib/api";

const EV_COLOR: Record<string, string> = {
  direct: "#38bdf8",
  corroboration: "#a3e635",
  contradiction: "#f87171",
  tool_pattern: "#c084fc",
};

export default function ProvenanceExplorer({ memoryId }: { memoryId: string | null }) {
  const [why, setWhy] = useState<WhyResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!memoryId) return;
    setErr(null);
    api.why(memoryId).then(setWhy).catch((e) => setErr(String(e)));
  }, [memoryId]);

  return (
    <div className="card">
      <h2>Provenance · why is this believed?</h2>
      {!memoryId ? (
        <p className="text-sm text-slate-600">
          Select a retrieved memory in the Playground to trace its evidence chain.
        </p>
      ) : err ? (
        <p className="text-sm text-amber-400">{err}</p>
      ) : !why ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <div className="bg-accent text-ink rounded-lg px-3 py-2 text-sm font-semibold">
              Belief
              {why.confidence != null && (
                <span className="ml-2 font-normal">
                  conf {why.confidence.toFixed(2)}
                </span>
              )}
            </div>
            <span className="text-xs text-slate-500">{why.status}</span>
          </div>
          <div className="space-y-2">
            {why.evidence.length === 0 && (
              <p className="text-sm text-slate-600">No evidence recorded.</p>
            )}
            {why.evidence.map((e, i) => (
              <div key={i} className="flex items-center gap-2">
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ background: EV_COLOR[e.type] || "#64748b" }}
                />
                <span className="text-sm">
                  <span className="text-slate-400">{e.type}</span>{" "}
                  <span className="text-xs text-slate-600">
                    (session {e.session_id}, weight {e.weight})
                  </span>
                  {e.note && <span className="text-slate-300"> — {e.note}</span>}
                </span>
              </div>
            ))}
          </div>
          {why.resolved_from.length > 0 && (
            <p className="mt-3 text-xs text-slate-500">
              Resolved from prior beliefs: {why.resolved_from.join(", ")}
            </p>
          )}
          <pre className="mt-4 bg-ink rounded-lg p-3 text-xs text-slate-400 whitespace-pre-wrap">
            {why.explanation}
          </pre>
        </div>
      )}
    </div>
  );
}
