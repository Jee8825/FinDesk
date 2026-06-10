// Typed client for the Recall API, used by the dashboard.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export type Tier = "episodic" | "semantic" | "procedural";

export interface Stats {
  tenant_id: string;
  memory_by_tier: Record<string, Record<string, number>>;
  conflicts_total: number;
  prefetch: { total: number; hits: number; hit_rate: number };
  redis: string;
}

export interface RetrievedMemory {
  id: string;
  content: string;
  tier: Tier;
  score: number;
  strength: number;
  confidence: number;
  summarized: boolean;
}

export interface RetrieveResult {
  memories: RetrievedMemory[];
  tokens_used: number;
  token_budget: number;
  cache_hit: boolean;
}

export interface IngestResult {
  units: {
    id: string;
    tier: Tier;
    content: string;
    strength: number;
    confidence: number;
  }[];
  conflicts_detected: number;
}

export interface Conflict {
  id: string;
  user_id: string;
  semantic_distance: number;
  resolution: string;
  resolved_belief: string | null;
  rationale: string | null;
  created_at: string;
}

export interface WhyResult {
  memory_id: string;
  confidence: number | null;
  status: string | null;
  explanation: string;
  evidence: {
    type: string;
    session_id: string;
    weight: number;
    note: string;
    relation: string;
  }[];
  resolved_from: string[];
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  stats: (tenant = "default") => http<Stats>(`/stats?tenant_id=${tenant}`),
  ingest: (body: {
    user_id: string;
    session_id: string;
    content: string;
    scope?: string;
  }) =>
    http<IngestResult>("/memory/ingest", {
      method: "POST",
      body: JSON.stringify({ scope: "user-owned", ...body }),
    }),
  retrieve: (body: {
    user_id: string;
    query: string;
    token_budget: number;
    session_id?: string;
  }) =>
    http<RetrieveResult>("/memory/retrieve", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  conflicts: (user_id: string) =>
    http<Conflict[]>(`/conflicts?user_id=${encodeURIComponent(user_id)}`),
  why: (id: string) => http<WhyResult>(`/memory/${id}/why`),
};
