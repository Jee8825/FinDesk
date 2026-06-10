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
  }[];
  next_cursor: string | null;
  counts: Record<string, number>;
};

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

export const api = {
  login: (email: string, password: string) =>
    request<TokenPair>("POST", apiPaths.POST_AUTH_LOGIN, { email, password }),
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
