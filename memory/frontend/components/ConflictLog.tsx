"use client";

import { useEffect, useState } from "react";
import { api, type Conflict } from "@/lib/api";

const BADGE: Record<string, string> = {
  auto_resolved: "bg-emerald-900 text-emerald-300",
  merged: "bg-sky-900 text-sky-300",
  flagged: "bg-amber-900 text-amber-300",
};

export default function ConflictLog({
  userId,
  refreshKey,
}: {
  userId: string;
  refreshKey: number;
}) {
  const [conflicts, setConflicts] = useState<Conflict[]>([]);

  useEffect(() => {
    api.conflicts(userId).then(setConflicts).catch(() => setConflicts([]));
  }, [userId, refreshKey]);

  return (
    <div className="card">
      <h2>Conflict log</h2>
      {conflicts.length === 0 ? (
        <p className="text-sm text-slate-600">
          No conflicts yet. Ingest two contradictory facts to see resolution.
        </p>
      ) : (
        <ul className="space-y-2">
          {conflicts.map((c) => (
            <li key={c.id} className="bg-ink rounded-lg p-3 text-sm">
              <div className="flex justify-between items-center">
                <span
                  className={`text-[10px] rounded px-1.5 py-0.5 ${
                    BADGE[c.resolution] || "bg-slate-700"
                  }`}
                >
                  {c.resolution}
                </span>
                <span className="text-[10px] text-slate-500">
                  distance {c.semantic_distance.toFixed(3)}
                </span>
              </div>
              {c.resolved_belief && (
                <p className="mt-1 text-slate-300">→ {c.resolved_belief}</p>
              )}
              {c.rationale && (
                <p className="mt-1 text-xs text-slate-500 italic">{c.rationale}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
