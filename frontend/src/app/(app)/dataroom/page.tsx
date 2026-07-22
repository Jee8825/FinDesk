"use client";
// Data Room — "Score hero" (wireframe Data Room A, dark surface B5):
// credit-ready exports, FinDesk Score, tokenized lender share links.
import { useMutation, useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Link2 } from "lucide-react";
import { useState } from "react";

import { DataRoomView } from "@/components/DataRoomView";
import { Card, ErrorNote, MonoLabel, PageShell, PrimaryBtn, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";

function AuditChip() {
  const audit = useQuery({ queryKey: ["audit-verify"], queryFn: () => api.auditVerify() });
  const a = audit.data;
  if (!a) return null;
  return (
    <span
      className={`mono-label inline-flex items-center gap-1.5 rounded-full border px-3 py-1 ${
        a.valid ? "border-mint/40 text-mint" : "border-blush/50 text-blush"
      }`}
      title={
        a.valid
          ? `hash chain recomputed live · head ${a.head_hash.slice(0, 12)}…`
          : `chain breaks at entry #${a.broken_at?.index} (${a.broken_at?.action})`
      }
    >
      <span className={`h-1.5 w-1.5 rounded-full ${a.valid ? "bg-mint" : "bg-blush"}`} />
      {a.valid ? `audit chain verified · ${a.entries} entries` : "audit chain BROKEN"}
    </span>
  );
}

export default function DataRoomPage() {
  const room = useQuery({ queryKey: ["dataroom"], queryFn: () => api.dataroom() });
  const [copied, setCopied] = useState(false);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const share = useMutation({
    mutationFn: () => api.shareDataroom(),
    onSuccess: async (data) => {
      const url = `${window.location.origin}/share?token=${encodeURIComponent(data.share_token)}`;
      setShareUrl(url); // always visible — clipboard is best-effort
      try {
        await navigator.clipboard.writeText(url);
        setCopied(true);
        setTimeout(() => setCopied(false), 4000);
      } catch {
        // clipboard unavailable (permissions/headless) — the inline URL suffices
      }
    },
  });

  return (
    <PageShell
      title="Data Room"
      surface="dark"
      subtitle="Credit-ready exports, FinDesk Score, lender share links"
      annotation="GET /dataroom · tokenized share links"
    >
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <p className="mono-annot">
          ◇ b5 · credit-ready exports + findesk score · tokenized share links for lenders
        </p>
        <AuditChip />
      </div>

      {room.isLoading && <Skeleton className="h-96" />}
      {room.isError && <ErrorNote>Could not build the data room.</ErrorNote>}
      {room.data && (
        <>
          <DataRoomView room={room.data} />
          <Card className="mt-5 flex flex-wrap items-center justify-between gap-4 p-6">
            <div>
              <h3 className="text-[15px] font-bold text-dark-text">Lender share link</h3>
              <p className="mono-annot mt-1 flex items-center gap-1.5">
                <Link2 size={11} /> expires 7d · view-only · the signed token is the credential
              </p>
            </div>
            <PrimaryBtn onClick={() => share.mutate()} disabled={share.isPending}>
              {copied ? "Link copied ✓" : share.isPending ? "Minting…" : "Generate link"}
            </PrimaryBtn>
            {shareUrl && (
              <div className="w-full">
                <MonoLabel>share url</MonoLabel>
                <input
                  readOnly
                  value={shareUrl}
                  aria-label="lender share url"
                  onFocus={(e) => e.currentTarget.select()}
                  className="mt-1.5 w-full rounded-lg border border-dark-line bg-transparent p-2.5 font-mono text-xs text-dark-text"
                />
              </div>
            )}
          </Card>
          {share.isError && (
            <ErrorNote>
              {share.error instanceof Error ? share.error.message : "could not create share link"}
            </ErrorNote>
          )}
        </>
      )}
    </PageShell>
  );
}
