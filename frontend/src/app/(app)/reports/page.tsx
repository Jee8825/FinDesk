"use client";
// Reports + Why? — "Pack + drawer" (wireframe Reports A, signature surface
// A8): the month-end pack where every figure answers "Why?" via the
// provenance drawer.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, FileDown, Info, XCircle } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { WhyDrawer } from "@/components/WhyDrawer";
import {
  Card,
  ErrorNote,
  MonoLabel,
  PageShell,
  PrimaryBtn,
  Skeleton,
  StatCard,
  stagger,
} from "@/components/ui";
import { api, authorizedFetch, formatINR, type WhyRef } from "@/lib/api";

const PERIODS = ["2026-04", "2026-05", "2026-06", "2026-07"];

function CloseCard() {
  const queryClient = useQueryClient();
  const checklist = useQuery({ queryKey: ["close-checklist"], queryFn: () => api.closeChecklist() });
  const [rationale, setRationale] = useState("");
  const [signedNote, setSignedNote] = useState<string | null>(null);
  const signoff = useMutation({
    mutationFn: () => api.closeSignoff(rationale.trim() || undefined),
    onSuccess: (r) => {
      setSignedNote(`Close ${r.period} signed off — recorded on the audit chain.`);
      void queryClient.invalidateQueries({ queryKey: ["close-checklist"] });
    },
  });
  const c = checklist.data;
  if (checklist.isLoading) return <Skeleton className="mb-5 h-40" />;
  if (!c) return null;
  const needRationale = c.warnings.length > 0;

  return (
    <Card className="mb-5 px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-bold text-ink">Month-end close — {c.period}</p>
          <p className="mono-annot mt-0.5">
            evidence-linked checklist · sign-off lands on the audit chain
            {c.audit_head && ` · head ${c.audit_head.slice(0, 10)}…`}
          </p>
        </div>
        <button
          className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-[13px] font-bold text-ink transition-colors hover:bg-[var(--fill-2)]"
          onClick={async () => {
            const res = await authorizedFetch(api.closePackPath());
            if (!res.ok) return;
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `findesk-close-${c.period}.zip`;
            a.click();
            URL.revokeObjectURL(url);
          }}
          title="credit pack + close_checklist.md — deterministic, regenerate-and-diff"
        >
          <FileDown size={14} /> Close pack
        </button>
      </div>

      <ul className="mt-3 grid gap-1.5 sm:grid-cols-2">
        {c.checks.map((chk) => (
          <li key={chk.id} className="flex items-center gap-2 text-[13px]">
            {chk.ok ? (
              <CheckCircle2 size={14} className="shrink-0 text-moss" />
            ) : chk.severity === "block" ? (
              <XCircle size={14} className="shrink-0 text-rust" />
            ) : (
              <AlertTriangle size={14} className="shrink-0 text-amber-600" />
            )}
            <Link href={chk.href} className="text-ink hover:underline">
              {chk.label}
            </Link>
            <span className="mono-annot ml-auto">{chk.value}</span>
          </li>
        ))}
      </ul>

      <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-line pt-3">
        {signedNote ? (
          <p className="text-[13px] font-bold text-moss">{signedNote}</p>
        ) : c.ready ? (
          <>
            {needRationale && (
              <input
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                placeholder={`rationale for: ${c.warnings.join(", ")}`}
                aria-label="sign-off rationale for open warnings"
                className="min-w-64 flex-1 rounded-lg border border-line bg-[var(--fill-2)] px-3 py-2 text-[13px] text-ink"
              />
            )}
            <PrimaryBtn
              onClick={() => signoff.mutate()}
              disabled={signoff.isPending || (needRationale && !rationale.trim())}
            >
              {signoff.isPending ? "Signing…" : "Sign off close"}
            </PrimaryBtn>
          </>
        ) : (
          <p className="text-[13px] font-semibold text-rust">
            Blocked: {c.blockers.join(", ")} — resolve before sign-off.
          </p>
        )}
        {signoff.isError && <p className="mono-annot text-rust">{String(signoff.error)}</p>}
      </div>
    </Card>
  );
}

function WhyButton({ refs, onOpen }: { refs: WhyRef[]; onOpen: (refs: WhyRef[]) => void }) {
  if (!refs.length) return null;
  return (
    <motion.button
      whileHover={{ scale: 1.15 }}
      whileTap={{ scale: 0.9 }}
      onClick={() => onOpen(refs)}
      className="inline-flex items-center gap-1 text-accent"
      title="show the evidence trail"
      aria-label="why?"
    >
      <Info size={14} />
    </motion.button>
  );
}

export default function ReportsPage() {
  const [period, setPeriod] = useState("2026-04");
  const [whyRefs, setWhyRefs] = useState<WhyRef[] | null>(null);
  const report = useQuery({
    queryKey: ["month-end", period],
    queryFn: () => api.monthEndReport(period),
  });

  const r = report.data;

  return (
    <PageShell
      title="Reports + Why?"
      subtitle="Month-end pack & GST summary — every figure answers Why?"
      annotation="GET /reports/month-end · GET /why/:entity/:id"
      actions={
        <select
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          className="rounded-lg border border-line bg-[var(--fill-2)] px-3 py-2 text-sm font-semibold text-ink outline-none"
          aria-label="report period"
        >
          {PERIODS.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
      }
    >
      <p className="mono-annot mb-5">
        ◇ signature surface a8 · every figure answers &quot;why?&quot; — provenance trail back to
        source transactions
      </p>

      <CloseCard />

      {report.isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-64" />
        </div>
      )}
      {report.isError && <ErrorNote>Could not build the report.</ErrorNote>}

      {r && (
        <div className="grid items-start gap-5 xl:grid-cols-[1fr_340px]">
          <div className="space-y-5">
            <motion.div className="grid grid-cols-3 gap-4" initial="initial" animate="animate" variants={stagger}>
              <StatCard label="inflow" value={r.cash.inflow_paise} format={formatINR} tone="good" />
              <StatCard label="outflow" value={r.cash.outflow_paise} format={formatINR} />
              <StatCard
                label="net"
                value={r.cash.net_paise}
                format={formatINR}
                tone={r.cash.net_paise >= 0 ? "good" : "bad"}
              />
            </motion.div>

            <Card className="overflow-hidden !p-0">
              <div className="flex items-center justify-between border-b border-line2 px-6 py-4">
                <h2 className="text-[15px] font-bold text-ink">Month-end pack · {period}</h2>
                <span className="mono-label text-faint">p&l summary</span>
              </div>
              <table className="w-full text-sm">
                <motion.tbody initial="initial" animate="animate" variants={{ animate: { transition: { staggerChildren: 0.05 } } }}>
                  {r.cash.by_category.map((c) => (
                    <motion.tr
                      key={c.category_code}
                      variants={{ initial: { opacity: 0 }, animate: { opacity: 1 } }}
                      className="border-b border-line2 last:border-0 hover:bg-[var(--fill-3)]"
                    >
                      <td className="px-6 py-3 font-semibold text-ink">{c.category_name}</td>
                      <td className="whitespace-nowrap px-6 py-3 text-right font-mono font-semibold text-ink">
                        {formatINR(c.amount_paise)}
                      </td>
                      <td className="mono-annot w-24 px-3 py-3 text-right">
                        {c.count} txn{c.count > 1 ? "s" : ""}
                      </td>
                      <td className="w-12 px-4 py-3 text-right">
                        <WhyButton refs={c.why} onOpen={setWhyRefs} />
                      </td>
                    </motion.tr>
                  ))}
                </motion.tbody>
              </table>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between">
                <h2 className="text-[15px] font-bold text-ink">
                  Receivables aging — {formatINR(r.receivables.overdue_total_paise)} overdue
                </h2>
              </div>
              {r.receivables.aging.length === 0 && (
                <p className="mt-3 text-sm text-faint">Nothing overdue. Rare air.</p>
              )}
              {r.receivables.aging.map((bucket) => (
                <div key={bucket.bucket} className="mt-4">
                  <MonoLabel>
                    {bucket.bucket} days · {formatINR(bucket.amount_paise)}
                  </MonoLabel>
                  <table className="mt-1.5 w-full text-sm">
                    <tbody>
                      {bucket.items.map((item) => (
                        <tr key={item.invoice_number} className="border-b border-line2 last:border-0">
                          <td className="py-2 font-semibold text-ink">{item.client}</td>
                          <td className="py-2 font-mono text-xs text-faint">{item.invoice_number}</td>
                          <td className="py-2 text-right font-mono font-semibold">{formatINR(item.amount_paise)}</td>
                          <td className="mono-annot w-24 py-2 text-right">{item.days_overdue}d over</td>
                          <td className="w-10 py-2 text-right">
                            <WhyButton refs={item.why} onOpen={setWhyRefs} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </Card>
          </div>

          <div className="space-y-5">
            <Card className="p-6">
              <MonoLabel>summary — the agent&apos;s narrative</MonoLabel>
              <ul className="mt-3 space-y-2 text-[13.5px] leading-relaxed text-mute">
                {r.narrative.map((line, i) => (
                  <motion.li key={i} initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 * i }}>
                    • {line}
                  </motion.li>
                ))}
              </ul>
            </Card>
            <Card className="p-6">
              <div className="flex items-center justify-between">
                <MonoLabel>reconciliation</MonoLabel>
                <WhyButton refs={r.reconciliation.why} onOpen={setWhyRefs} />
              </div>
              <p className="mt-2 text-sm text-mute">
                <span className="font-mono font-bold text-ink">
                  {r.reconciliation.matched}/{r.reconciliation.transactions}
                </span>{" "}
                matched
                {r.reconciliation.tds_matches > 0 && ` (${r.reconciliation.tds_matches} TDS-adjusted)`} ·{" "}
                {r.reconciliation.unmatched} for review
              </p>
              <p className="mt-1 font-mono text-sm font-semibold text-moss">
                {formatINR(r.reconciliation.matched_amount_paise)} posted
              </p>
            </Card>
            <Card className="p-6">
              <div className="flex items-center justify-between">
                <MonoLabel>anomalies</MonoLabel>
                <WhyButton refs={r.anomalies.why} onOpen={setWhyRefs} />
              </div>
              <p className="mt-2 text-sm text-mute">{r.anomalies.open} open</p>
              <p className="mt-1 font-mono text-sm font-semibold text-moss">
                {formatINR(r.anomalies.recoverable_paise)} recoverable
              </p>
            </Card>
            <p className="mono-annot">
              ◇ GET /why/… · the trust primitive — deterministic rollup, no LLM in the math
            </p>
          </div>
        </div>
      )}

      {whyRefs && <WhyDrawer refs={whyRefs} onClose={() => setWhyRefs(null)} />}
    </PageShell>
  );
}
