"use client";
// Categorization — "COA tree + table" (wireframe Categorization A): the chart
// of accounts on the left; crystallized vendor→category mappings (derived
// from the live feed) on the right, with stability bars.
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Bar, Card, EmptyState, ErrorNote, MonoLabel, PageShell, Skeleton, stagger } from "@/components/ui";
import { api, formatINRCompact } from "@/lib/api";

type VendorRow = {
  vendor: string;
  code: string | null;
  total_paise: number;
  txns: number;
  share: number; // how consistently this vendor lands in its dominant category
  source: string | null;
};

export default function CategorizationPage() {
  const [selected, setSelected] = useState<string | null>(null);
  const accounts = useQuery({ queryKey: ["chart-of-accounts"], queryFn: () => api.chartOfAccounts() });
  const txns = useQuery({ queryKey: ["transactions"], queryFn: () => api.transactions() });

  const groups = useMemo(() => {
    const byType = new Map<string, { code: string; name: string }[]>();
    for (const a of accounts.data ?? []) {
      const list = byType.get(a.type) ?? [];
      list.push(a);
      byType.set(a.type, list);
    }
    return Array.from(byType.entries());
  }, [accounts.data]);

  const vendors = useMemo<VendorRow[]>(() => {
    const debits = (txns.data?.items ?? []).filter((t) => t.direction === "dr");
    const byVendor = new Map<string, typeof debits>();
    for (const t of debits) {
      const key = t.counterparty_hint ?? "unknown";
      byVendor.set(key, [...(byVendor.get(key) ?? []), t]);
    }
    const rows: VendorRow[] = [];
    for (const [vendor, list] of Array.from(byVendor.entries())) {
      const byCode = new Map<string | null, number>();
      for (const t of list) byCode.set(t.category_code, (byCode.get(t.category_code) ?? 0) + 1);
      const [code, hits] = Array.from(byCode.entries()).sort((a, b) => b[1] - a[1])[0];
      rows.push({
        vendor,
        code,
        total_paise: list.reduce((s, t) => s + t.amount_paise, 0),
        txns: list.length,
        share: hits / list.length,
        source: list.find((t) => t.category_code === code)?.category_source ?? null,
      });
    }
    return rows.sort((a, b) => b.total_paise - a.total_paise);
  }, [txns.data]);

  const visible = selected ? vendors.filter((v) => v.code === selected) : vendors;
  const selectedName = accounts.data?.find((a) => a.code === selected)?.name;

  return (
    <PageShell
      title="Categorization"
      subtitle="Chart of accounts & crystallized vendor mappings"
      annotation="GET /books/chart-of-accounts · PATCH /books/transactions/:id/category"
    >
      <div className="grid gap-5 lg:grid-cols-[300px_1fr]">
        <Card className="self-start p-5">
          <MonoLabel>chart of accounts</MonoLabel>
          {accounts.isLoading && <Skeleton className="mt-3 h-40" />}
          {accounts.isError && <ErrorNote>Could not load the chart of accounts.</ErrorNote>}
          <motion.div className="mt-3 space-y-4" initial="initial" animate="animate" variants={stagger}>
            {groups.map(([type, list]) => (
              <motion.div key={type} variants={{ initial: { opacity: 0 }, animate: { opacity: 1 } }}>
                <p className="text-[13px] font-bold capitalize text-ink">{type.replace(/_/g, " ")}</p>
                <ul className="mt-1">
                  {list.map((a) => (
                    <li key={a.code}>
                      <button
                        onClick={() => setSelected(selected === a.code ? null : a.code)}
                        className={`w-full rounded-lg px-2.5 py-1.5 text-left text-[13px] transition-colors ${
                          selected === a.code
                            ? "bg-accent/10 font-semibold text-accent"
                            : "text-mute hover:bg-cream"
                        }`}
                      >
                        {a.name}
                      </button>
                    </li>
                  ))}
                </ul>
              </motion.div>
            ))}
          </motion.div>
        </Card>

        <Card className="self-start overflow-hidden !p-0">
          <div className="flex items-start justify-between gap-4 border-b border-line2 px-6 py-4">
            <h2 className="text-[15px] font-bold text-ink">
              {selectedName ? `${selectedName} — crystallized vendor mappings` : "All vendors — crystallized mappings"}
            </h2>
            <span className="mono-annot hidden max-w-64 text-right lg:block">
              ◇ memory beliefs · editing PATCHes the mapping & logs provenance
            </span>
          </div>
          {txns.isLoading && (
            <div className="space-y-2 p-6">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-12" />
              ))}
            </div>
          )}
          {txns.data && visible.length === 0 && (
            <div className="p-6">
              <EmptyState>No debit transactions {selectedName ? `mapped to ${selectedName}` : "yet"}.</EmptyState>
            </div>
          )}
          {visible.length > 0 && (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line2 text-left">
                  <th className="mono-label px-6 py-3 font-normal text-faint">vendor</th>
                  <th className="mono-label px-6 py-3 text-right font-normal text-faint">ytd</th>
                  <th className="mono-label w-60 px-6 py-3 font-normal text-faint">stability</th>
                  <th className="mono-label px-6 py-3 font-normal text-faint" />
                </tr>
              </thead>
              <motion.tbody initial="initial" animate="animate" variants={{ animate: { transition: { staggerChildren: 0.04 } } }}>
                {visible.map((v) => {
                  const label = v.share >= 0.95 ? "stable" : v.share >= 0.75 ? "learning" : "contested";
                  return (
                    <motion.tr
                      key={v.vendor}
                      variants={{ initial: { opacity: 0 }, animate: { opacity: 1 } }}
                      className="border-b border-line2/70 last:border-0 hover:bg-cream"
                    >
                      <td className="px-6 py-3.5">
                        <span className="font-bold text-ink">{v.vendor}</span>
                        {v.source && <span className="mono-label ml-2 text-faint">{v.source}</span>}
                      </td>
                      <td className="whitespace-nowrap px-6 py-3.5 text-right font-mono font-semibold text-ink">
                        {formatINRCompact(v.total_paise)}
                      </td>
                      <td className="px-6 py-3.5">
                        <Bar pct={v.share * 100} tone={v.share >= 0.95 ? "good" : v.share >= 0.75 ? "accent" : "bad"} />
                        <span className="mono-annot mt-1 block">
                          {v.share.toFixed(2)} · {label} · {v.txns} txn{v.txns > 1 ? "s" : ""}
                        </span>
                      </td>
                      <td className="px-6 py-3.5 text-right">
                        <Link
                          href="/books"
                          className="text-[13px] font-bold text-accent transition-transform hover:translate-x-0.5"
                        >
                          Edit →
                        </Link>
                      </td>
                    </motion.tr>
                  );
                })}
              </motion.tbody>
            </table>
          )}
        </Card>
      </div>
    </PageShell>
  );
}
