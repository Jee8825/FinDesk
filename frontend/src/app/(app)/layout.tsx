"use client";
// App shell — cream sidebar with grouped nav (wireframe shell), live queue
// badges, tenant card and sign-out. Content surface is owned by each page.
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, clearTokens, getToken, setTokens } from "@/lib/api";

import { CommandPalette } from "@/components/CommandPalette";
import { LiquidMark, LiveRing } from "@/components/fx";

import { Providers } from "../providers";

type NavItem = { href: string; label: string; badge?: number };
type NavGroup = { label: string; items: NavItem[] };

function useQueueCounts(enabled: boolean) {
  const conflicts = useQuery({
    queryKey: ["conflicts"],
    queryFn: () => api.conflicts(),
    enabled,
    staleTime: 30_000,
  });
  const anomalies = useQuery({
    queryKey: ["anomalies"],
    queryFn: () => api.anomalies(),
    enabled,
    staleTime: 30_000,
  });
  const approvals = useQuery({
    queryKey: ["approvals"],
    queryFn: () => api.approvals(),
    enabled,
    staleTime: 30_000,
  });
  const radar = useQuery({
    queryKey: ["radar"],
    queryFn: () => api.radar(),
    enabled,
    staleTime: 30_000,
  });
  return {
    conflicts: conflicts.data?.length,
    anomalies: anomalies.data?.filter((a) => a.status === "open").length,
    approvals: approvals.data?.length,
    radar: radar.data?.items.filter((i) => i.clock.overdue_days > 0).length,
  };
}

function useAgentLive(): boolean {
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.listRuns(),
    refetchInterval: 15_000,
    staleTime: 10_000,
  });
  return (runs.data ?? []).some((r) => r.status === "running" || r.status === "queued");
}

function useAgentHealth() {
  const health = useQuery({
    queryKey: ["agent-health"],
    queryFn: () => api.agentHealth(),
    refetchInterval: 30_000,
    staleTime: 25_000,
  });
  // no data yet (or request failed) = unknown, render as degraded-neutral
  return {
    worker: health.data?.worker,
    memory: health.data?.memory,
    known: health.isSuccess,
  };
}

function TenantCard() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const me = useQuery({ queryKey: ["me"], queryFn: () => api.me(), staleTime: 60_000 });
  const active = me.data?.memberships.find((m) => m.tenant_id === me.data?.active_tenant_id);

  async function switchTo(tenantId: string) {
    setOpen(false);
    if (tenantId === me.data?.active_tenant_id) return;
    setTokens(await api.switchTenant(tenantId));
    router.refresh();
    window.location.reload();
  }

  return (
    <div className="relative mt-3">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-2 rounded-lg border-[1.5px] border-dashed border-line px-2.5 py-2 text-left transition-colors hover:border-faint"
      >
        <div className="min-w-0">
          <div className="truncate text-xs font-semibold text-ink">
            {active?.tenant_name ?? "…"}
          </div>
          <div className="mono-label mt-0.5 text-faint">
            tenant · {me.data?.role ?? ""}
          </div>
        </div>
        <ChevronDown size={13} className="shrink-0 text-faint" />
      </button>
      <AnimatePresence>
        {open && (me.data?.memberships.length ?? 0) > 0 && (
          <motion.ul
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.16 }}
            className="absolute left-0 right-0 z-40 mt-1 overflow-hidden glass-strong rounded-lg border border-line shadow-card"
          >
            {me.data!.memberships.map((m) => (
              <li key={m.tenant_id}>
                <button
                  onClick={() => switchTo(m.tenant_id)}
                  className={`block w-full px-3 py-2 text-left text-xs transition-colors hover:bg-[var(--fill-3)] ${
                    m.tenant_id === me.data!.active_tenant_id
                      ? "font-semibold text-ink"
                      : "text-mute"
                  }`}
                >
                  {m.tenant_name}
                  <span className="mono-label ml-2 text-faint">{m.role}</span>
                </button>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}

function AgentHealthBadge() {
  const { worker, memory, known } = useAgentHealth();
  const allLive = known && worker && memory;
  const label = !known
    ? "agent · checking…"
    : allLive
      ? "agent · all systems live"
      : [!worker && "worker offline", !memory && "memory offline"]
          .filter(Boolean)
          .join(" · ");
  const dot = allLive ? "bg-moss" : known ? "bg-claret" : "bg-line";
  return (
    <div className="flex items-center gap-2" title="live probe: worker consumer + memory engine">
      {known ? (
        <LiveRing live={!!allLive} size={22} />
      ) : (
        <span className={`relative inline-flex h-2 w-2 rounded-full ${dot}`} />
      )}
      <span className="mono-label text-mute">{label}</span>
    </div>
  );
}

function Sidebar() {
  const pathname = usePathname();
  const counts = useQueueCounts(true);

  const groups: NavGroup[] = [
    {
      label: "Overview",
      items: [
        { href: "/", label: "Dashboard" },
        { href: "/brief", label: "Daily Brief" },
      ],
    },
    {
      label: "Books",
      items: [
        { href: "/books", label: "Transactions" },
        { href: "/reconciliation", label: "Reconciliation" },
        { href: "/categorization", label: "Categorization" },
      ],
    },
    {
      label: "Agent queues",
      items: [
        { href: "/conflicts", label: "Conflicts", badge: counts.conflicts },
        { href: "/anomalies", label: "Anomalies", badge: counts.anomalies },
        { href: "/approvals", label: "Approvals", badge: counts.approvals },
      ],
    },
    {
      label: "Receivables",
      items: [
        { href: "/receivables", label: "45-Day Radar", badge: counts.radar },
        { href: "/collections", label: "Collections" },
      ],
    },
    {
      label: "Payables",
      items: [
        { href: "/payables", label: "Payables Shield" },
        { href: "/ims", label: "IMS · ITC Shield" },
      ],
    },
    {
      label: "Cash command",
      items: [
        { href: "/forecast", label: "Forecast" },
        { href: "/actions", label: "WC Actions" },
      ],
    },
    {
      label: "Trust layer",
      items: [
        { href: "/reports", label: "Reports + Why?" },
        { href: "/dataroom", label: "Data Room" },
      ],
    },
    {
      label: "Setup",
      items: [
        { href: "/onboarding", label: "Onboarding" },
        { href: "/settings", label: "Settings" },
        { href: "/ca", label: "Client Roster" },
      ],
    },
  ];

  const router = useRouter();

  return (
    <aside className="glass-rail sticky top-0 flex h-screen w-[236px] shrink-0 flex-col overflow-y-auto border-r border-line2 shadow-side">
      <div className="border-b-[1.5px] border-line2 px-4 pb-4 pt-5">
        <Link href="/" className="flex items-center gap-2.5">
          <motion.div whileHover={{ rotate: -4, scale: 1.05 }}>
            <LiquidMark size={34} />
          </motion.div>
          <div>
            <div className="font-display text-[15px] font-bold tracking-[-0.01em] text-ink">FinDesk</div>
            <div className="mono-label text-faint">autonomous cfo</div>
          </div>
        </Link>
        <TenantCard />
        <button
          onClick={() =>
            document.dispatchEvent(
              new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }),
            )
          }
          className="mt-3 flex w-full items-center justify-between rounded-lg border border-line2 bg-[var(--fill-1)] px-2.5 py-2 text-left text-xs text-faint transition-colors hover:border-line hover:text-mute"
        >
          <span>Search & command…</span>
          <kbd className="mono-label rounded border border-line2 px-1.5 py-0.5">⌘K</kbd>
        </button>
      </div>

      <nav className="flex-1 px-3 py-4">
        {groups.map((group) => (
          <div key={group.label} className="mb-4">
            <div className="mono-label mb-1.5 px-2 text-faint">{group.label}</div>
            {group.items.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="relative block"
                  aria-current={active ? "page" : undefined}
                >
                  {active && (
                    <motion.span
                      layoutId="nav-pill"
                      className="absolute inset-0 rounded-lg bg-ink"
                      transition={{ type: "spring", stiffness: 500, damping: 40 }}
                    />
                  )}
                  <span
                    className={`relative z-10 flex items-center justify-between rounded-lg px-2.5 py-[7px] text-[13px] font-semibold transition-colors ${
                      active ? "text-paper" : "text-mute hover:text-ink"
                    }`}
                  >
                    {item.label}
                    {!!item.badge && !active && (
                      <span className="rounded-full border border-accent/40 bg-accent/10 px-1.5 font-mono text-[10px] font-medium text-accent">
                        {item.badge}
                      </span>
                    )}
                  </span>
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="border-t-[1.5px] border-line2 px-4 py-4">
        <AgentHealthBadge />
        <button
          onClick={() => {
            clearTokens();
            router.replace("/login");
          }}
          className="mt-3 flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs text-faint transition-colors hover:bg-[var(--fill-3)] hover:text-ink"
        >
          <LogOut size={12} /> Sign out
        </button>
      </div>
    </aside>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  const live = useAgentLive();
  return (
    <div className="flex min-h-screen" data-agent-live={live || undefined}>
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col">{children}</main>
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  useEffect(() => {
    if (!getToken()) router.replace("/login");
  }, [router]);

  return (
    <Providers>
      <CommandPalette />
      <Shell>{children}</Shell>
    </Providers>
  );
}
