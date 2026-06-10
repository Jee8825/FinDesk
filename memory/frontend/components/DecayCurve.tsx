"use client";

import { useState } from "react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { LAMBDAS, decaySeries } from "@/lib/decay";

const TIERS = ["episodic", "semantic", "procedural"] as const;

export default function DecayCurve() {
  const [tier, setTier] = useState<(typeof TIERS)[number]>("episodic");
  const [reinforce, setReinforce] = useState(true);
  const lambda = LAMBDAS[tier];
  const horizon = tier === "episodic" ? 30 : tier === "semantic" ? 365 : 365;
  const data = decaySeries(lambda, horizon, Math.max(1, horizon / 60), reinforce ? Math.round(horizon / 6) : 0);

  return (
    <div className="card">
      <h2>Forgetting curve · S(t) = S₀·e^(−λt)</h2>
      <div className="flex items-center gap-3 mb-3">
        <select
          className="input w-auto"
          value={tier}
          onChange={(e) => setTier(e.target.value as (typeof TIERS)[number])}
        >
          {TIERS.map((t) => (
            <option key={t} value={t}>
              {t} (λ={LAMBDAS[t]})
            </option>
          ))}
        </select>
        <label className="text-sm flex items-center gap-2">
          <input
            type="checkbox"
            checked={reinforce}
            onChange={(e) => setReinforce(e.target.checked)}
          />
          show retrieval reinforcement
        </label>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data}>
          <XAxis dataKey="day" stroke="#64748b" fontSize={11} unit="d" />
          <YAxis domain={[0, 1]} stroke="#64748b" fontSize={11} />
          <Tooltip
            contentStyle={{ background: "#0b1726", border: "1px solid #334155" }}
          />
          <Line
            type="monotone"
            dataKey="strength"
            stroke="#64748b"
            dot={false}
            name="no retrieval"
          />
          {reinforce && (
            <Line
              type="monotone"
              dataKey="reinforced"
              stroke="#38bdf8"
              strokeWidth={2}
              dot={false}
              name="reinforced"
            />
          )}
        </LineChart>
      </ResponsiveContainer>
      <p className="text-xs text-slate-500 mt-2">
        Grey: strength decays untouched and tombstones below τ. Blue: each
        retrieval boosts strength back up — the memory stays alive because it is
        used.
      </p>
    </div>
  );
}
