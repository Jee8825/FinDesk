// Thin API client over the generated contract paths. Handwritten fetch shapes
// for endpoints are banned — paths come from src/lib/generated/api-paths.ts.
import { API_PREFIX, apiPaths } from "@/lib/generated/api-paths";

const TOKEN_KEY = "findesk.access";
const REFRESH_KEY = "findesk.refresh";

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  tenant_id: string;
  role: string;
};

export type RunOut = {
  run_id: string;
  graph: string;
  status: string;
  params: Record<string, unknown>;
  steps?: { step_id: string; name: string; status: string }[];
};

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setTokens(pair: TokenPair) {
  window.localStorage.setItem(TOKEN_KEY, pair.access_token);
  window.localStorage.setItem(REFRESH_KEY, pair.refresh_token);
}

export function clearTokens() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_PREFIX}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `${method} ${path} → ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export type TxnPage = {
  items: {
    id: string;
    value_date: string;
    amount_paise: number;
    direction: string;
    narration: string;
    counterparty_hint: string | null;
    match_status: string;
    category_code: string | null;
    category_source: string | null;
  }[];
  next_cursor: string | null;
  counts: Record<string, number>;
};

export type ChartAccount = { code: string; name: string; type: string };

export function formatINR(amountPaise: number): string {
  const rupees = amountPaise / 100;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
  }).format(rupees);
}

export type Approval = {
  id: string;
  action_kind: string;
  action_payload: {
    invoice_number?: string;
    amount_paise?: number;
    tds_paise?: number;
    tds_bps?: number;
    kind?: string;
    confidence?: number;
    critic_verdict?: { verdict?: string; checker?: string };
    [k: string]: unknown;
  };
  policy_verdicts: Record<string, unknown>;
  requested_by: Record<string, unknown>;
  status: string;
  created_at: string;
};

export type ConflictCard = {
  id: string;
  claim_kind: string;
  scope_key: string;
  claim_a: { memory_id: string; content: string; confidence: number | null };
  claim_b: { memory_id: string; content: string; confidence: number | null };
  engine_view: {
    semantic_distance?: number;
    engine_rationale?: string;
    counterparty?: string;
  };
  status: string;
  created_at: string;
};

export type AnomalyCard = {
  id: string;
  kind: string;
  severity: string;
  vendor_label: string;
  evidence: Record<string, unknown>;
  recommended_action: string;
  recoverable_paise: number | null;
  status: string;
  created_at: string;
};

export type WhyRef = { kind: string; id: string };

export type MonthEndReport = {
  period: string;
  generated_at: string;
  cash: {
    inflow_paise: number;
    outflow_paise: number;
    net_paise: number;
    by_category: {
      category_code: string;
      category_name: string;
      amount_paise: number;
      count: number;
      why: WhyRef[];
    }[];
  };
  reconciliation: {
    transactions: number;
    matched: number;
    matched_amount_paise: number;
    tds_matches: number;
    unmatched: number;
    why: WhyRef[];
  };
  receivables: {
    overdue_total_paise: number;
    aging: {
      bucket: string;
      amount_paise: number;
      items: {
        invoice_number: string;
        client: string;
        amount_paise: number;
        days_overdue: number;
        why: WhyRef[];
      }[];
    }[];
  };
  anomalies: { open: number; recoverable_paise: number; why: WhyRef[] };
  narrative: string[];
};

export type WhyEvent = {
  at: string;
  actor: Record<string, unknown>;
  action: string;
  payload: Record<string, unknown>;
  row_hash: string;
};

export const api = {
  login: (email: string, password: string) =>
    request<TokenPair>("POST", apiPaths.POST_AUTH_LOGIN, { email, password }),
  monthEndReport: (period: string) =>
    request<MonthEndReport>(
      "GET",
      `${apiPaths.GET_REPORTS_MONTH_END}?period=${period}`,
    ),
  why: (kind: string, id: string) =>
    request<{ entity_ref: string; events: WhyEvent[] }>(
      "GET",
      apiPaths.GET_WHY_ENTITY_TYPE_ENTITY_ID.replace("{entity_type}", kind).replace(
        "{entity_id}",
        id,
      ),
    ),
  anomalies: () => request<AnomalyCard[]>("GET", apiPaths.GET_ANOMALIES),
  decideAnomaly: (id: string, decision: "accepted" | "dismissed" | "recovered") =>
    request<{ ok: boolean }>(
      "POST",
      apiPaths.POST_ANOMALIES_ANOMALY_ID_DECIDE.replace("{anomaly_id}", id),
      { decision },
    ),
  startRunByGraph: (graph: string) =>
    request<RunOut>("POST", apiPaths.POST_AGENT_RUNS, { graph, params: {} }),
  conflicts: () => request<ConflictCard[]>("GET", apiPaths.GET_CONFLICTS),
  resolveConflict: (id: string, winner: "a" | "b", rationale?: string) =>
    request<{ ok: boolean; kept: string }>(
      "POST",
      apiPaths.POST_CONFLICTS_CONFLICT_ID_RESOLVE.replace("{conflict_id}", id),
      { winner, rationale },
    ),
  approvals: (statusFilter = "pending") =>
    request<Approval[]>("GET", `${apiPaths.GET_APPROVALS}?status_filter=${statusFilter}`),
  decideApproval: (id: string, decision: "approved" | "rejected", rationale?: string) =>
    request<{ ok: boolean; status: string }>(
      "POST",
      apiPaths.POST_APPROVALS_APPROVAL_ID_DECIDE.replace("{approval_id}", id),
      { decision, rationale },
    ),
  transactions: (statusFilter?: string) =>
    request<TxnPage>(
      "GET",
      `${apiPaths.GET_BOOKS_TRANSACTIONS}${statusFilter ? `?status_filter=${statusFilter}` : ""}`,
    ),
  chartOfAccounts: () =>
    request<ChartAccount[]>("GET", apiPaths.GET_BOOKS_CHART_OF_ACCOUNTS),
  correctCategory: (txnId: string, code: string) =>
    request<{ ok: boolean }>(
      "PATCH",
      apiPaths.PATCH_BOOKS_TRANSACTIONS_TXN_ID_CATEGORY.replace("{txn_id}", txnId),
      { category_code: code },
    ),
  importStatement: async (file: File): Promise<{ document_id: string; run_id: string }> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_PREFIX}${apiPaths.POST_BOOKS_IMPORTS}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${getToken()}` },
      body: form,
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail ?? `upload failed (${res.status})`);
    }
    return res.json();
  },
  me: () => request<{ email: string; active_tenant_id: string; role: string }>("GET", apiPaths.GET_ME),
  startRun: (graph: string, params: Record<string, unknown> = {}) =>
    request<RunOut>("POST", apiPaths.POST_AGENT_RUNS, { graph, params }),
  listRuns: () => request<RunOut[]>("GET", apiPaths.GET_AGENT_RUNS),
  streamPath: (runId: string) =>
    `${API_PREFIX}${apiPaths.GET_AGENT_RUNS_RUN_ID_STREAM.replace("{run_id}", runId)}`,
};
