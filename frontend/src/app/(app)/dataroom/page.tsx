"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { DataRoomView } from "@/components/DataRoomView";
import { api } from "@/lib/api";

export default function DataRoomPage() {
  const room = useQuery({ queryKey: ["dataroom"], queryFn: () => api.dataroom() });
  const [copied, setCopied] = useState(false);
  const share = useMutation({
    mutationFn: () => api.shareDataroom(),
    onSuccess: async (data) => {
      const url = `${window.location.origin}/share?token=${encodeURIComponent(data.share_token)}`;
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 4000);
    },
  });

  return (
    <div className="max-w-3xl">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Credit data room</h1>
          <p className="mt-1 text-sm text-slate-500">
            Books a lender can trust cheaply: a published score, a verifiable audit chain, and
            evidence behind every number.
          </p>
        </div>
        <button
          onClick={() => share.mutate()}
          disabled={share.isPending}
          className="rounded-md bg-teal-brand px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {copied ? "Link copied ✓ (7 days)" : "Share with lender"}
        </button>
      </div>

      {room.isLoading && <div className="mt-6 h-64 animate-pulse rounded-xl bg-slate-100" />}
      {room.isError && <p className="mt-6 text-sm text-red-600">Could not build the data room.</p>}
      {room.data && (
        <div className="mt-6">
          <DataRoomView room={room.data} />
        </div>
      )}
      {share.isError && (
        <p className="mt-3 text-sm text-red-600" role="alert">
          {share.error instanceof Error ? share.error.message : "could not create share link"}
        </p>
      )}
    </div>
  );
}
