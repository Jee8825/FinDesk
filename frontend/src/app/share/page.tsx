"use client";
// Public lender view — no login; the signed share token is the credential.
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

import { DataRoomView } from "@/components/DataRoomView";
import { Providers } from "@/app/providers";
import { api } from "@/lib/api";

function SharedRoom() {
  const token = useSearchParams().get("token") ?? "";
  const room = useQuery({
    queryKey: ["shared-dataroom", token],
    queryFn: () => api.sharedDataroom(token),
    enabled: Boolean(token),
    retry: false,
  });

  return (
    <main className="min-h-screen bg-gradient-to-b from-[#0a0e1a] to-paper">
      <motion.div
        className="mx-auto max-w-4xl p-8"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45 }}
      >
        <div className="mb-7 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-[34px] w-[34px] items-center justify-center rounded-[9px] border-2 border-ink text-base font-bold text-ink">
              F
            </div>
            <div>
              <p className="text-[15px] font-bold tracking-[-0.01em] text-ink">FinDesk</p>
              <p className="mono-label text-faint">credit data room · read-only lender view</p>
            </div>
          </div>
          {room.data?.shared && (
            <span className="mono-label rounded-full border border-line bg-[var(--fill-2)] px-3 py-1.5 text-mute">
              expires {new Date(room.data.shared.expires_at * 1000).toLocaleDateString("en-IN")}
            </span>
          )}
        </div>
        {!token && <p className="text-sm text-faint">Missing share token.</p>}
        {room.isLoading && <div className="h-64 animate-pulse rounded-2xl bg-[var(--fill-2)]" />}
        {room.isError && (
          <p className="text-sm text-claret">This share link is invalid or has expired.</p>
        )}
        {room.data && <DataRoomView room={room.data} />}
      </motion.div>
    </main>
  );
}

export default function SharePage() {
  return (
    <Providers>
      <Suspense fallback={null}>
        <SharedRoom />
      </Suspense>
    </Providers>
  );
}
