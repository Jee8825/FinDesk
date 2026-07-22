"use client";
// Client Roster — "Roster table" (wireframe CA Console A, dark surface):
// one CA, many tenants. Opening a client explicitly switches tenant context —
// tenant_id scopes every call; the switch is audited.
import { useMutation, useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";

import { Card, EmptyState, ErrorNote, PageShell, Pill, Skeleton } from "@/components/ui";
import { api, setTokens } from "@/lib/api";

export default function CaRosterPage() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => api.me(), staleTime: 60_000 });
  const switchTenant = useMutation({
    mutationFn: (tenantId: string) => api.switchTenant(tenantId),
    onSuccess: (pair) => {
      setTokens(pair);
      window.location.href = "/";
    },
  });

  const memberships = me.data?.memberships ?? [];

  return (
    <PageShell
      title="Client Roster"
      surface="dark"
      subtitle="Cross-tenant queue rollup — one CA, many tenants, explicit switch"
      annotation="GET /me · POST /tenants/:id/switch · tenant_id on every call"
    >
      <p className="mono-annot mb-5">
        ◇ multi-tenant · one ca, many clients · tenant_id scopes every call · explicit switch,
        never implicit
      </p>

      {me.isLoading && <Skeleton className="h-64" />}
      {me.isError && <ErrorNote>Could not load your memberships.</ErrorNote>}
      {me.data && memberships.length <= 1 && (
        <EmptyState hint="CA-firm accounts hold one membership per client tenant">
          Only one tenant on this account — the roster shows when you manage multiple clients.
        </EmptyState>
      )}

      {memberships.length > 1 && (
        <Card className="overflow-hidden !p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-dark-line text-left">
                <th className="mono-label px-6 py-3.5 font-normal text-dark-mute">client</th>
                <th className="mono-label px-6 py-3.5 font-normal text-dark-mute">your role</th>
                <th className="mono-label px-6 py-3.5 font-normal text-dark-mute">context</th>
                <th className="px-6 py-3.5" />
              </tr>
            </thead>
            <motion.tbody initial="initial" animate="animate" variants={{ animate: { transition: { staggerChildren: 0.06 } } }}>
              {memberships.map((m) => {
                const active = m.tenant_id === me.data!.active_tenant_id;
                return (
                  <motion.tr
                    key={m.tenant_id}
                    variants={{ initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 } }}
                    className="border-b border-dark-line transition-colors last:border-0 hover:bg-dark-card2/50"
                  >
                    <td className="px-6 py-4">
                      <p className="text-sm font-bold text-dark-text">{m.tenant_name}</p>
                      <p className="mt-0.5 font-mono text-xs text-dark-mute">{m.tenant_id.slice(0, 13)}…</p>
                    </td>
                    <td className="px-6 py-4">
                      <Pill tone="neutral">{m.role}</Pill>
                    </td>
                    <td className="px-6 py-4">
                      {active ? <Pill tone="good">active context</Pill> : <span className="text-xs text-dark-mute">—</span>}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {!active && (
                        <motion.button
                          whileHover={{ scale: 1.05 }}
                          whileTap={{ scale: 0.95 }}
                          onClick={() => switchTenant.mutate(m.tenant_id)}
                          disabled={switchTenant.isPending}
                          className="text-[13px] font-bold text-accent-soft disabled:opacity-50"
                        >
                          Open →
                        </motion.button>
                      )}
                    </td>
                  </motion.tr>
                );
              })}
            </motion.tbody>
          </table>
        </Card>
      )}
      {switchTenant.isError && (
        <ErrorNote>
          {switchTenant.error instanceof Error ? switchTenant.error.message : "switch failed"}
        </ErrorNote>
      )}

      <p className="mono-annot mt-4">
        ◇ opening a client sets tenant context · all subsequent screens scope to that tenant_id ·
        audit logs the switch
      </p>
    </PageShell>
  );
}
