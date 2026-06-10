"use client";
// Public lender view — no login; the signed share token is the credential.
import { useQuery } from "@tanstack/react-query";
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
    <main className="mx-auto max-w-3xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <p className="text-lg font-semibold text-ink">FinDesk</p>
          <p className="text-xs text-slate-500">credit data room · read-only lender view</p>
        </div>
        {room.data?.shared && (
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
            link expires {new Date(room.data.shared.expires_at * 1000).toLocaleDateString("en-IN")}
          </span>
        )}
      </div>
      {!token && <p className="text-sm text-slate-500">Missing share token.</p>}
      {room.isLoading && <div className="h-64 animate-pulse rounded-xl bg-slate-100" />}
      {room.isError && (
        <p className="text-sm text-red-600">This share link is invalid or has expired.</p>
      )}
      {room.data && <DataRoomView room={room.data} />}
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
