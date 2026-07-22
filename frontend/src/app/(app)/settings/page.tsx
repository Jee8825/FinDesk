"use client";
// Settings — "Integration cards" (wireframe Settings A): integrations,
// entities, team & roles. Maker-checker roles are enforced server-side.
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import Link from "next/link";

import { Card, MonoLabel, PageShell, Pill, Skeleton, stagger } from "@/components/ui";
import { api } from "@/lib/api";

const INTEGRATIONS = [
  {
    name: "Bank statements",
    status: "live" as const,
    detail: "CSV import · reconciliation runs on upload",
    action: { label: "Upload →", href: "/books" },
  },
  {
    name: "Tally / Zoho Books",
    status: "live" as const,
    detail: "invoice export import · seeds payment memory",
    action: { label: "Import →", href: "/onboarding" },
  },
  {
    name: "Account Aggregator",
    status: "planned" as const,
    detail: "consent-based bank feed — lands with the AA rails",
    action: { label: "Roadmap", href: "#" },
  },
  {
    name: "GST portal / IMS",
    status: "planned" as const,
    detail: "returns sync for the GST summary pack",
    action: { label: "Roadmap", href: "#" },
  },
];

export default function SettingsPage() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => api.me(), staleTime: 60_000 });

  return (
    <PageShell
      title="Settings"
      subtitle="Integrations, entities, team & roles, plan"
      annotation="GET/PATCH /settings/* · maker-checker enforced server-side"
    >
      <p className="mono-annot mb-5">
        ◇ integrations · entities · team & roles · plan — maker-checker roles enforced server-side
      </p>

      <motion.div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" initial="initial" animate="animate" variants={stagger}>
        {INTEGRATIONS.map((integ) => (
          <Card key={integ.name} hover className="p-5">
            <div className="flex items-center justify-between">
              <h3 className="text-[15px] font-bold text-ink">{integ.name}</h3>
              <Pill tone={integ.status === "live" ? "good" : "neutral"}>{integ.status}</Pill>
            </div>
            <p className="mt-2 text-[13px] leading-snug text-mute">{integ.detail}</p>
            <Link
              href={integ.action.href}
              className={`mt-3 inline-block text-[13px] font-bold transition-transform hover:translate-x-0.5 ${
                integ.status === "live" ? "text-accent" : "text-faint"
              }`}
            >
              {integ.action.label}
            </Link>
          </Card>
        ))}
      </motion.div>

      <Card className="mt-6 overflow-hidden !p-0">
        <div className="flex items-center justify-between border-b border-line2 px-6 py-4">
          <h2 className="text-[15px] font-bold text-ink">Team & roles</h2>
          <span className="mono-annot hidden lg:block">◇ roles gate the approval queue — approver ≠ requester</span>
        </div>
        {me.isLoading && (
          <div className="space-y-2 p-6">
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
          </div>
        )}
        {me.data && (
          <motion.ul initial="initial" animate="animate" variants={{ animate: { transition: { staggerChildren: 0.06 } } }}>
            <motion.li
              variants={{ initial: { opacity: 0, x: -8 }, animate: { opacity: 1, x: 0 } }}
              className="flex items-center justify-between border-b border-line2/70 px-6 py-4"
            >
              <div>
                <p className="text-sm font-bold text-ink">You</p>
                <p className="mt-0.5 text-xs text-faint">{me.data.email}</p>
              </div>
              <Pill tone="ink">{me.data.role} · active</Pill>
            </motion.li>
            {me.data.memberships
              .filter((m) => m.tenant_id !== me.data!.active_tenant_id)
              .map((m) => (
                <motion.li
                  key={m.tenant_id}
                  variants={{ initial: { opacity: 0, x: -8 }, animate: { opacity: 1, x: 0 } }}
                  className="flex items-center justify-between border-b border-line2/70 px-6 py-4 last:border-0"
                >
                  <div>
                    <p className="text-sm font-bold text-ink">{m.tenant_name}</p>
                    <p className="mt-0.5 text-xs text-faint">other tenant membership</p>
                  </div>
                  <Pill tone="neutral">{m.role}</Pill>
                </motion.li>
              ))}
          </motion.ul>
        )}
      </Card>

      <Card className="mt-6 p-6">
        <MonoLabel>trust by construction</MonoLabel>
        <ul className="mt-3 grid gap-2 text-[13.5px] text-mute md:grid-cols-2">
          <li>✓ No money movement — everything is recommend-only</li>
          <li>✓ No external communication without approval</li>
          <li>✓ Every action is explainable (Why? on every figure)</li>
          <li>✓ Every change is audited (hash-chained log)</li>
        </ul>
      </Card>
    </PageShell>
  );
}
