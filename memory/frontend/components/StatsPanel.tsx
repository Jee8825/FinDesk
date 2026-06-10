"use client";

import { useEffect, useState } from "react";
import { api, type Stats } from "@/lib/api";

const TIER_COLORS: Record<string, string> = {
  episodic: "text-episodic",
  semantic: "text-semantic",
  procedural: "text-procedural",
};

export default function StatsPanel({ refreshKey }: { refreshKey: number }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api
      .stats()
      .then(setStats)
      .catch((e) => setErr(String(e)));
  }, [refreshKey]);

  if (err)
    return (
      <div className="card text-amber-400 text-sm">
        API unreachable ({err}). Is the engine running on :8000?
      </div>
    );
  if (!stats) return <div className="card text-slate-500">Loading stats…</div>;

  const total = (tier: string) =>
    Object.values(stats.memory_by_tier[tier] || {}).reduce((a, b) => a + b, 0);

  return (
    <div className="card">
      <h2>Memory tiers</h2>
      <div className="grid grid-cols-3 gap-3 mb-4">
        {["episodic", "semantic", "procedural"].map((t) => (
          <div key={t} className="bg-ink rounded-lg p-3 text-center">
            <div className={`text-2xl font-bold ${TIER_COLORS[t]}`}>
              {total(t)}
            </div>
            <div className="text-xs text-slate-500 capitalize">{t}</div>
            <div className="text-[10px] text-slate-600">
              {stats.memory_by_tier[t]?.tombstoned
                ? `${stats.memory_by_tier[t].tombstoned} tombstoned`
                : ""}
            </div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-3 gap-3 text-center text-sm">
        <Metric label="Conflicts" value={stats.conflicts_total} />
        <Metric
          label="Prefetch hit-rate"
          value={`${Math.round(stats.prefetch.hit_rate * 100)}%`}
        />
        <Metric label="Redis" value={stats.redis} />
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-ink rounded-lg p-3">
      <div className="text-lg font-semibold text-white">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}
