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

let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  // Single-flight: concurrent 401s share one refresh call.
  refreshing ??= (async () => {
    const refresh = typeof window === "undefined" ? null : window.localStorage.getItem(REFRESH_KEY);
    if (!refresh) return false;
    const res = await fetch(`${API_PREFIX}${apiPaths.POST_AUTH_REFRESH}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return false;
    setTokens((await res.json()) as TokenPair);
    return true;
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

/** Fetch with Bearer auth and a single-flight refresh→retry on 401.
 *  `url` is the full same-origin URL (API_PREFIX included). Every call that
 *  talks to the API — JSON, multipart uploads, the SSE stream — goes through
 *  here so token expiry never strands a request. */
export async function authorizedFetch(
  url: string,
  init: RequestInit = {},
  retried = false,
): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(url, { ...init, headers });
  if (res.status === 401 && !retried && url !== `${API_PREFIX}${apiPaths.POST_AUTH_LOGIN}`) {
    if (await tryRefresh()) return authorizedFetch(url, init, true);
    clearTokens();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
  }
  return res;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await authorizedFetch(`${API_PREFIX}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
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

// Compact Indian notation for hero figures: ₹86.4L / ₹2.3Cr / ₹12,300
export function formatINRCompact(amountPaise: number): string {
  const rupees = amountPaise / 100;
  const abs = Math.abs(rupees);
  const sign = rupees < 0 ? "−" : "";
  if (abs >= 1e7) return `${sign}₹${(abs / 1e7).toFixed(1)}Cr`;
  if (abs >= 1e5) return `${sign}₹${(abs / 1e5).toFixed(1)}L`;
  if (abs >= 1e3) return `${sign}₹${(abs / 1e3).toFixed(1)}k`;
  return `${sign}₹${Math.round(abs).toLocaleString("en-IN")}`;
}

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

export type MemoryBelief = {
  memory_id: string;
  scope_key: string;
  content: string;
  confidence: number | null;
  explanation: string;
};

export type RadarItem = {
  invoice_id: string;
  invoice_number: string;
  client: string;
  amount_paise: number;
  clock: {
    statutory_due_date: string;
    overdue_days: number;
    accrued_interest_paise: number;
    annual_rate_bps: number;
    escalation_level: string;
  };
  predicted_payment_date: string | null;
  avg_days_late: number | null;
  behavior_observations: number;
};

export type RadarOut = {
  items: RadarItem[];
  totals: { overdue_paise: number; accrued_interest_paise: number };
  ca_note: string;
};

export type ForecastWeek = {
  week: number;
  week_start: string;
  inflow_paise: number;
  outflow_paise: number;
  closing_paise: number;
  drivers: { invoice_number: string; client: string; amount_paise: number; expected: string }[];
};

export type ForecastOut = {
  forecast_id: string;
  generated_at: string;
  horizon_weeks: number;
  opening_balance_paise: number;
  weekly_outflow_paise: number;
  outflow_basis: { vendor: string; monthly_paise: number }[];
  gap: {
    scenario: string;
    week: number;
    week_start: string;
    shortfall_paise: number;
    delayed_inflows: { invoice_number: string; client: string; amount_paise: number; expected: string }[];
  } | null;
  narrative: string[];
  scenarios: Record<string, ForecastWeek[]>;
};

export type WhatifOut = {
  forecast_id: string;
  params: Record<string, number>;
  weeks: ForecastWeek[];
  gap: { scenario: string; week: number; week_start: string; shortfall_paise: number } | null;
  pushed_out_paise: number;
  end_delta_paise: number;
};

export type WcAction = {
  id: string;
  kind: string;
  invoice_number: string;
  client: string;
  unlock_paise: number;
  cost_paise: number;
  rank: number;
  detail: {
    quote?: { tenor_days: number; discount_rate_bps_annual: number };
    predicted_payment?: string;
    days_to_cash_without_action?: number;
    days_overdue?: number;
    note?: string;
  };
  status: string;
};

export type DataRoom = {
  generated_at: string;
  findesk_score: {
    score: number;
    components: Record<string, { ratio: number; weight: number; points: number }>;
  };
  audit_chain: { ok: boolean; rows: number };
  evidence: Record<string, string | number | null>;
  methodology_note: string;
  shared?: { read_only: boolean; expires_at: number };
};

export const api = {
  login: (email: string, password: string) =>
    request<TokenPair>("POST", apiPaths.POST_AUTH_LOGIN, { email, password }),
  dataroom: () => request<DataRoom>("GET", apiPaths.GET_DATAROOM),
  shareDataroom: () =>
    request<{ share_token: string; expires_in_days: number }>(
      "POST",
      apiPaths.POST_DATAROOM_SHARE,
    ),
  sharedDataroom: (token: string) =>
    request<DataRoom>("GET", `${apiPaths.GET_DATAROOM_SHARED}?token=${encodeURIComponent(token)}`),
  wcActions: () => request<WcAction[]>("GET", apiPaths.GET_WC_ACTIONS),
  requestWcAction: (id: string) =>
    request<{ ok: boolean; approval_id: string }>(
      "POST",
      apiPaths.POST_WC_ACTIONS_ACTION_ID_REQUEST.replace("{action_id}", id),
    ),
  forecast: () => request<ForecastOut>("GET", apiPaths.GET_FORECAST),
  whatif: (params: {
    collection_delay_days?: number;
    inflow_haircut_bps?: number;
    extra_monthly_outflow_paise?: number;
  }) => request<WhatifOut>("POST", apiPaths.POST_FORECAST_WHATIF, params),
  radar: () => request<RadarOut>("GET", apiPaths.GET_RECEIVABLES_RADAR),
  monthEndReport: (period: string) =>
    request<MonthEndReport>(
      "GET",
      `${apiPaths.GET_REPORTS_MONTH_END}?period=${period}`,
    ),
  why: (kind: string, id: string) =>
    request<{ entity_ref: string; events: WhyEvent[]; memory?: MemoryBelief[] }>(
      "GET",
      apiPaths.GET_WHY_ENTITY_TYPE_ENTITY_ID.replace("{entity_type}", kind).replace(
        "{entity_id}",
        id,
      ),
    ),
  // status_filter "" = all statuses; the page splits open vs handled itself.
  anomalies: (statusFilter = "") =>
    request<AnomalyCard[]>("GET", `${apiPaths.GET_ANOMALIES}?status_filter=${statusFilter}`),
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
  exceptions: () => request<TxnPage>("GET", apiPaths.GET_BOOKS_EXCEPTIONS),
  switchTenant: (tenantId: string) =>
    request<TokenPair>(
      "POST",
      apiPaths.POST_TENANTS_TENANT_ID_SWITCH.replace("{tenant_id}", tenantId),
    ),
  chartOfAccounts: () =>
    request<ChartAccount[]>("GET", apiPaths.GET_BOOKS_CHART_OF_ACCOUNTS),
  correctCategory: (txnId: string, code: string) =>
    request<{ ok: boolean }>(
      "PATCH",
      apiPaths.PATCH_BOOKS_TRANSACTIONS_TXN_ID_CATEGORY.replace("{txn_id}", txnId),
      { category_code: code },
    ),
  onboardInvoices: async (
    file: File,
  ): Promise<{
    source_hint: string;
    counterparties_created: number;
    invoices_created: number;
    invoices_skipped: number;
    observations_seeded: number;
  }> => {
    const form = new FormData();
    form.append("file", file);
    const res = await authorizedFetch(`${API_PREFIX}${apiPaths.POST_BOOKS_ONBOARDING}`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail ?? `import failed (${res.status})`);
    }
    return res.json();
  },
  importStatement: async (file: File): Promise<{ document_id: string; run_id: string }> => {
    const form = new FormData();
    form.append("file", file);
    const res = await authorizedFetch(`${API_PREFIX}${apiPaths.POST_BOOKS_IMPORTS}`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail ?? `upload failed (${res.status})`);
    }
    return res.json();
  },
  me: () =>
    request<{
      email: string;
      active_tenant_id: string;
      role: string;
      memberships: { tenant_id: string; tenant_name: string; role: string }[];
    }>("GET", apiPaths.GET_ME),
  agentHealth: () =>
    request<{ worker: boolean; memory: boolean }>("GET", apiPaths.GET_AGENT_HEALTH),
  startRun: (graph: string, params: Record<string, unknown> = {}) =>
    request<RunOut>("POST", apiPaths.POST_AGENT_RUNS, { graph, params }),
  listRuns: () => request<RunOut[]>("GET", apiPaths.GET_AGENT_RUNS),
  streamPath: (runId: string) =>
    `${API_PREFIX}${apiPaths.GET_AGENT_RUNS_RUN_ID_STREAM.replace("{run_id}", runId)}`,
};
