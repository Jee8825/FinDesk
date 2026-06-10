"use client";

import { useState } from "react";
import { api, type RetrievedMemory } from "@/lib/api";

export default function Playground({
  userId,
  onChange,
  onSelectMemory,
}: {
  userId: string;
  onChange: () => void;
  onSelectMemory: (id: string) => void;
}) {
  const [content, setContent] = useState("");
  const [query, setQuery] = useState("");
  const [budget, setBudget] = useState(800);
  const [results, setResults] = useState<RetrievedMemory[]>([]);
  const [status, setStatus] = useState<string>("");
  const [busy, setBusy] = useState(false);

  async function ingest() {
    if (!content.trim()) return;
    setBusy(true);
    try {
      const r = await api.ingest({
        user_id: userId,
        session_id: "dashboard",
        content,
      });
      setStatus(
        `Extracted ${r.units.length} memory unit(s)` +
          (r.conflicts_detected
            ? `, ${r.conflicts_detected} conflict(s) resolved`
            : "")
      );
      setContent("");
      onChange();
    } catch (e) {
      setStatus(`Error: ${e}`);
    } finally {
      setBusy(false);
    }
  }

  async function retrieve() {
    if (!query.trim()) return;
    setBusy(true);
    try {
      const r = await api.retrieve({
        user_id: userId,
        query,
        token_budget: budget,
        session_id: "dashboard",
      });
      setResults(r.memories);
      setStatus(
        `Packed ${r.memories.length} memories into ${r.tokens_used}/${r.token_budget} tokens` +
          (r.cache_hit ? " · prefetch cache hit" : "")
      );
    } catch (e) {
      setStatus(`Error: ${e}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>Playground</h2>
      <div className="space-y-3">
        <div>
          <label className="text-xs text-slate-500">Ingest conversation</label>
          <textarea
            className="input h-20"
            placeholder="e.g. I deploy our backend on AWS using kubectl."
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
          <button className="btn mt-2" onClick={ingest} disabled={busy}>
            Ingest
          </button>
        </div>
        <div>
          <label className="text-xs text-slate-500">Retrieve (token budget)</label>
          <div className="flex gap-2">
            <input
              className="input"
              placeholder="where do I deploy?"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <input
              className="input w-24"
              type="number"
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
            />
            <button className="btn" onClick={retrieve} disabled={busy}>
              Recall
            </button>
          </div>
        </div>
        {status && <p className="text-xs text-accent">{status}</p>}
        <div className="space-y-2">
          {results.map((m) => (
            <button
              key={m.id}
              onClick={() => onSelectMemory(m.id)}
              className="w-full text-left bg-ink rounded-lg p-3 hover:border-accent border border-transparent"
            >
              <div className="flex justify-between items-center">
                <span className="text-sm">{m.content}</span>
                {m.summarized && (
                  <span className="text-[10px] bg-slate-700 rounded px-1.5 py-0.5">
                    compressed
                  </span>
                )}
              </div>
              <div className="flex gap-4 mt-2 text-[10px] text-slate-500">
                <Bar label="strength" value={m.strength} color="#38bdf8" />
                <Bar label="confidence" value={m.confidence} color="#a3e635" />
                <span>score {m.score.toFixed(3)}</span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function Bar({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <span className="flex items-center gap-1">
      {label}
      <span className="inline-block w-16 h-1.5 bg-slate-800 rounded">
        <span
          className="block h-1.5 rounded"
          style={{ width: `${Math.min(100, value * 100)}%`, background: color }}
        />
      </span>
    </span>
  );
}
