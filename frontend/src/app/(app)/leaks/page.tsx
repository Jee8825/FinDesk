"use client";
// LeakRadar — recurring-payment leak detector (PS1).
// Every figure here is computed server-side by pure detectors: cadence from
// inter-arrival gaps, silent price drift from changepoint detection, and a leak
// score whose components are always shown. The one thing the engine cannot
// derive is whether a service is still USED — that answer comes from the human
// and is what licenses counting a whole subscription as recoverable.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Check, Radar, Send, TrendingUp, X } from "lucide-react";
import { useState } from "react";

import {
  Card,
  EmptyState,
  ErrorNote,
  PageShell,
  Pill,
  PrimaryBtn,
  Skeleton,
  stagger,
} from "@/components/ui";
import { useGraphRun } from "@/hooks/useGraphRun";
import {
  api,
  formatINR,
  formatINRCompact,
  formatISTDate,
  type LeakRow,
  type LeakTotals,
} from "@/lib/api";

const CADENCE_LABEL: Record<string, string> = {
  weekly: "weekly",
  fortnightly: "fortnightly",
  monthly: "monthly",
  quarterly: "quarterly",
  annual: "annual",
  irregular: "irregular",
};

const DRIFT_LABEL: Record<string, string> = {
  price_increase: "price rose",
  price_decrease: "price fell",
  seat_creep: "seats added",
  usage_based: "usage-based",
  stable: "stable",
  stopped: "stopped",
  excluded: "commitment",
};

const CATEGORY_LABEL: Record<string, string> = {
  software_cloud: "software & cloud",
  streaming: "streaming",
  cloud_storage: "cloud storage",
  telecom: "telecom",
  fitness: "fitness",
  insurance: "insurance",
  loan_emi: "loan / EMI",
  rent: "rent",
  payroll: "payroll",
  uncategorized: "uncategorized",
};

/** Category-wise annualized cost. Plain divs, not a chart library — the widths
 *  are a proportion of the largest bar, computed from server figures. */
function CategoryBars({ totals }: { totals: LeakTotals }) {
  const entries = Object.entries(totals.by_category_paise);
  if (entries.length === 0) return null;
  const max = Math.max(...entries.map(([, v]) => v)) || 1;
  return (
    <Card className="mb-5 p-5">
      <p className="mono-label mb-1 text-dark-mute">
        subscription spend per year, by category
      </p>
      <p className="mono-annot mb-4">
        excludes {formatINRCompact(totals.commitments_paise_per_year)} of
        commitments (rent, payroll, EMI) — listed in the table, never scored
      </p>
      <div className="space-y-2.5">
        {entries.map(([code, paise]) => (
          <div key={code} className="flex items-center gap-3">
            <span className="w-32 shrink-0 truncate text-xs text-dark-mute">
              {CATEGORY_LABEL[code] ?? code}
            </span>
            <div className="h-4 flex-1 overflow-hidden rounded-sm bg-dark-card2">
              <div
                className="h-full rounded-sm bg-accent/50"
                style={{ width: `${Math.max(2, (paise / max) * 100)}%` }}
              />
            </div>
            <span className="w-20 shrink-0 text-right font-mono text-xs font-semibold text-dark-text">
              {formatINRCompact(paise)}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}

/** The score with its parts visible. A score nobody can interrogate is a score
 *  nobody will act on. */
function ScoreBadge({ row }: { row: LeakRow }) {
  const parts = Object.entries(row.score_components).filter(([, v]) => v > 0);
  return (
    <div>
      <span
        className={`font-mono text-lg font-bold ${
          row.leak_score >= 40
            ? "text-blush"
            : row.leak_score > 0
              ? "text-accent-soft"
              : "text-dark-mute"
        }`}
      >
        {row.leak_score}
      </span>
      {parts.length > 0 && (
        <p className="mono-annot mt-0.5 max-w-[10rem] leading-tight">
          {parts.map(([k]) => k).join(" · ")}
        </p>
      )}
    </div>
  );
}

function UsageControl({
  row,
  onSet,
  busy,
}: {
  row: LeakRow;
  onSet: (usage: "in_use" | "unused") => void;
  busy: boolean;
}) {
  if (row.status === "stopped") return <span className="mono-annot">already stopped</span>;
  // a commitment is not a subscription — asking whether payroll is "still used"
  // is a nonsense question and offering the control implies it can be cancelled
  if (row.drift_kind === "excluded") return <span className="mono-annot">commitment</span>;
  if (row.usage === "unused")
    return <Pill tone="bad">confirmed unused</Pill>;
  if (row.usage === "in_use") return <Pill tone="good">in use</Pill>;
  return (
    <div className="flex gap-1.5">
      <button
        onClick={() => onSet("in_use")}
        disabled={busy}
        aria-label={`Mark ${row.vendor_label} as still in use`}
        className="inline-flex items-center gap-1 rounded-md border border-dark-line px-2 py-1 font-mono text-xs text-mint transition-colors hover:bg-dark-card2 disabled:opacity-40"
      >
        <Check size={12} /> using
      </button>
      <button
        onClick={() => onSet("unused")}
        disabled={busy}
        aria-label={`Mark ${row.vendor_label} as no longer used`}
        className="inline-flex items-center gap-1 rounded-md border border-dark-line px-2 py-1 font-mono text-xs text-blush transition-colors hover:bg-dark-card2 disabled:opacity-40"
      >
        <X size={12} /> not using
      </button>
    </div>
  );
}

export default function LeaksPage() {
  const queryClient = useQueryClient();
  const leaks = useQuery({ queryKey: ["leaks"], queryFn: () => api.leaks() });
  const scan = useGraphRun("subscription_scan", [["leaks"]]);
  const [queued, setQueued] = useState<Record<string, string>>({});

  const usage = useMutation({
    mutationFn: (v: { id: string; usage: "in_use" | "unused" }) =>
      api.leakUsage(v.id, v.usage),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["leaks"] }),
  });
  const act = useMutation({
    mutationFn: (id: string) => api.leakAction(id, "renegotiate"),
    onSuccess: (out, id) => {
      setQueued((q) => ({ ...q, [id]: out.approval_id }));
      void queryClient.invalidateQueries({ queryKey: ["approvals"] });
    },
  });

  const d = leaks.data;
  const rows = d?.rows ?? [];
  const t = d?.totals;

  return (
    <PageShell
      title="LeakRadar"
      surface="dark"
      subtitle="Every recurring payment, what it really costs you a year, and where it quietly grew"
      annotation="GET /leaks · cadence + price-drift detection is deterministic · no money moves from here"
      actions={
        <PrimaryBtn onClick={() => scan.start()} disabled={scan.running}>
          <Radar size={14} className={scan.running ? "animate-pulse" : ""} />
          {scan.running
            ? `Scanning… ${scan.stepName ?? ""}`.trim()
            : "Scan for leaks"}
        </PrimaryBtn>
      }
    >
      <p className="mono-annot mb-5">
        ◇ recurrence from inter-arrival gaps · silent price hikes via changepoint
        detection (a 12% rise is invisible to a threshold test) · commitments like
        rent and payroll are listed but never scored
      </p>

      {leaks.isLoading && <Skeleton className="h-96" />}
      {leaks.isError && <ErrorNote>{String(leaks.error)}</ErrorNote>}

      {d && rows.length === 0 && (
        <EmptyState hint="POST /agent/runs { graph: subscription_scan }">
          <Radar className="mb-2 inline" size={18} /> No recurring vendors detected
          yet — import a statement, then hit “Scan for leaks”.
        </EmptyState>
      )}

      {d && t && rows.length > 0 && (
        <>
          <div
            role="status"
            className="mb-5 rounded-lg border border-blush/40 bg-blush/5 px-5 py-4"
          >
            <p className="text-sm font-bold text-dark-text">
              {formatINR(t.recoverable_paise_per_year)} a year is recoverable across{" "}
              {t.leaking_count} of {t.subscriptions} recurring payments
            </p>
            <p className="mt-1 text-xs leading-relaxed text-dark-mute">
              You are committed to {formatINR(t.subscription_paise_per_year)} a year in
              recurring subscriptions
              {t.drift_paise_per_year > 0 && (
                <>
                  , of which {formatINR(t.drift_paise_per_year)} comes from price
                  rises you never approved
                </>
              )}
              .{" "}
              {t.unreviewed_count > 0 && (
                <>
                  {t.unreviewed_count} have never been reviewed — marking one
                  “not using” is what turns its full cost into a recoverable figure.
                </>
              )}
            </p>
          </div>

          <CategoryBars totals={t} />

          <Card className="overflow-x-auto p-0">
            <table className="w-full min-w-[1040px] text-left">
              <thead>
                <tr className="border-b border-dark-line">
                  {[
                    "vendor / what changed",
                    "cadence",
                    "per year",
                    "recoverable",
                    "leak score",
                    "still using?",
                    "",
                  ].map((h) => (
                    <th key={h} className="mono-label px-5 py-3 text-dark-mute">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <motion.tbody {...stagger}>
                {rows.map((row) => (
                  <motion.tr
                    key={row.id}
                    variants={{
                      initial: { opacity: 0, y: 8 },
                      animate: { opacity: 1, y: 0 },
                    }}
                    className={`border-b border-dark-line align-top transition-colors last:border-0 hover:bg-dark-card2/50 ${
                      row.status === "stopped" ? "opacity-55" : ""
                    }`}
                  >
                    <td className="px-5 py-4">
                      <p className="text-sm font-bold text-dark-text">
                        {row.vendor_label}
                      </p>
                      <p className="mt-0.5 font-mono text-xs text-dark-mute">
                        {row.occurrences} charges · last{" "}
                        {formatISTDate(row.last_seen)}
                        {row.category_code && (
                          <> · {CATEGORY_LABEL[row.category_code] ?? row.category_code}</>
                        )}
                      </p>
                      <p className="mt-1.5 max-w-md text-xs leading-relaxed text-dark-mute">
                        {row.narrative ?? row.reason}
                      </p>
                      {row.recommended_action && row.leak_score > 0 && (
                        <p className="mt-1.5 max-w-md text-xs font-semibold leading-relaxed text-accent-soft">
                          → {row.recommended_action}
                        </p>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-5 py-4">
                      <Pill tone={row.status === "stopped" ? "neutral" : "warn"}>
                        {CADENCE_LABEL[row.cadence] ?? row.cadence}
                      </Pill>
                      {row.drift_kind && (
                        <p className="mono-annot mt-1">
                          {DRIFT_LABEL[row.drift_kind] ?? row.drift_kind}
                        </p>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-5 py-4 text-right font-mono font-semibold text-dark-text">
                      {row.run_rate_paise > 0 ? formatINRCompact(row.run_rate_paise) : "—"}
                      <p className="mono-annot mt-0.5">
                        {formatINRCompact(row.latest_amount_paise)}/charge
                      </p>
                    </td>
                    <td className="whitespace-nowrap px-5 py-4 text-right">
                      {row.recoverable_paise_per_year > 0 ? (
                        <span className="font-mono text-sm font-bold text-blush">
                          {formatINR(row.recoverable_paise_per_year)}
                        </span>
                      ) : (
                        <span className="mono-annot">—</span>
                      )}
                      {row.drift_paise_per_year > 0 && (
                        <p className="mono-annot mt-0.5 flex items-center justify-end gap-1">
                          <TrendingUp size={10} /> drift
                        </p>
                      )}
                    </td>
                    <td className="px-5 py-4">
                      <ScoreBadge row={row} />
                    </td>
                    <td className="px-5 py-4">
                      <UsageControl
                        row={row}
                        busy={usage.isPending}
                        onSet={(u) => usage.mutate({ id: row.id, usage: u })}
                      />
                    </td>
                    <td className="whitespace-nowrap px-5 py-4 text-right">
                      {queued[row.id] ? (
                        <Pill tone="warn">queued → approvals</Pill>
                      ) : row.has_draft ? (
                        <button
                          onClick={() => act.mutate(row.id)}
                          disabled={act.isPending}
                          className="inline-flex items-center gap-1 rounded-md border border-dark-line px-2.5 py-1.5 font-mono text-xs font-semibold text-accent-soft transition-colors hover:bg-dark-card2 disabled:opacity-40"
                        >
                          <Send size={12} /> draft email
                        </button>
                      ) : (
                        <span className="mono-annot">—</span>
                      )}
                    </td>
                  </motion.tr>
                ))}
              </motion.tbody>
            </table>
          </Card>
          <p className="mono-annot mt-4">{d.note}</p>
        </>
      )}
    </PageShell>
  );
}
