"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { clearTokens, getToken } from "@/lib/api";

import { Providers } from "../providers";

// Page map from docs/architecture/07-frontend.md §1 — placeholders until each
// feature phase lands its surface.
const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/books", label: "Books" },
  { href: "/conflicts", label: "Conflicts" },
  { href: "/anomalies", label: "Anomalies" },
  { href: "/receivables", label: "Receivables" },
  { href: "/forecast", label: "Forecast" },
  { href: "/actions", label: "Actions" },
  { href: "/approvals", label: "Approvals" },
  { href: "/reports", label: "Reports" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!getToken()) router.replace("/login");
  }, [router]);

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 border-r bg-ink p-4 text-white">
        <div className="mb-8 px-2">
          <span className="text-lg font-semibold">FinDesk</span>
          <p className="text-xs text-slate-400">autonomous CFO</p>
        </div>
        <nav className="space-y-1">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`block rounded-md px-3 py-2 text-sm ${
                pathname === item.href
                  ? "bg-teal-brand text-white"
                  : "text-slate-300 hover:bg-slate-800"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <button
          onClick={() => {
            clearTokens();
            router.replace("/login");
          }}
          className="mt-8 w-full rounded-md px-3 py-2 text-left text-sm text-slate-400 hover:bg-slate-800"
        >
          Sign out
        </button>
      </aside>
      <main className="flex-1 p-8">
        <Providers>{children}</Providers>
      </main>
    </div>
  );
}
