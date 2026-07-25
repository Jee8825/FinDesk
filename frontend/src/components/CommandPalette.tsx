"use client";
// ⌘K Command Palette — navigate anywhere, trigger agent runs, find a
// transaction and jump straight to its Why? chain. Runs land in the same
// gated pipeline as everywhere else (nothing consequential bypasses
// approvals). cmdk does the fuzzy matching; we feed it value strings.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Command, useCommandState } from "cmdk";
import {
  ArrowRight,
  BookOpen,
  ClipboardCheck,
  Radar,
  ScanSearch,
  Send,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { api, formatINR, type TxnPage } from "@/lib/api";

const PAGES: Array<{ href: string; label: string; hint: string }> = [
  { href: "/", label: "Dashboard", hint: "cash position, runway, live agent feed" },
  { href: "/brief", label: "Daily Brief", hint: "your morning front page" },
  { href: "/books", label: "Transactions", hint: "normalized feed, match states" },
  { href: "/reconciliation", label: "Reconciliation", hint: "match queue" },
  { href: "/categorization", label: "Categorization", hint: "rules + memory" },
  { href: "/conflicts", label: "Conflicts", hint: "belief vs books" },
  { href: "/anomalies", label: "Anomalies", hint: "duplicates, overcharges" },
  { href: "/approvals", label: "Approvals", hint: "the control surface" },
  { href: "/receivables", label: "45-Day Radar", hint: "MSME clocks, interest" },
  { href: "/payables", label: "Payables Shield", hint: "43B(h) exposure, §15 clock" },
  { href: "/leaks", label: "LeakRadar", hint: "recurring payments, silent price hikes, leak score" },
  { href: "/ims", label: "IMS · ITC Shield", hint: "accept/reject supplier filings, ITC at stake" },
  { href: "/runs", label: "Run Viewer", hint: "glass box — every step, duration, verdict" },
  { href: "/collections", label: "Collections", hint: "chase drafts" },
  { href: "/forecast", label: "Forecast", hint: "13-week scenarios" },
  { href: "/actions", label: "WC Actions", hint: "working-capital options" },
  { href: "/reports", label: "Reports + Why?", hint: "month-end pack" },
  { href: "/dataroom", label: "Data Room", hint: "FinDesk Score, lender links" },
  { href: "/ca", label: "Client Roster", hint: "multi-tenant switch" },
  { href: "/onboarding", label: "Onboarding", hint: "import invoices" },
  { href: "/settings", label: "Settings", hint: "tenant setup" },
];

const AGENT_ACTIONS: Array<{
  graph: string;
  label: string;
  hint: string;
  icon: React.ReactNode;
}> = [
  {
    graph: "anomaly_scan",
    label: "Scan for anomalies",
    hint: "duplicates · overcharges · out-of-pattern",
    icon: <ScanSearch size={15} />,
  },
  {
    graph: "cash_forecast",
    label: "Recompute cash forecast",
    hint: "13-week scenario bands",
    icon: <TrendingUp size={15} />,
  },
  {
    graph: "collections",
    label: "Draft collection chases",
    hint: "drafts wait in approvals — never auto-sent",
    icon: <Send size={15} />,
  },
  {
    graph: "month_end_close",
    label: "Run month-end close",
    hint: "evidence checklist · critic-checked · sign-off stays yours",
    icon: <ClipboardCheck size={15} />,
  },
  {
    graph: "working_capital",
    label: "Rank working-capital options",
    hint: "TReDS · invoice discounting",
    icon: <Radar size={15} />,
  },
];

// How much of the book the palette can search. Both matter: the fetch bounds
// what we have, the render bounds what cmdk can filter.
const PALETTE_TXN_LIMIT = 500;
const PALETTE_TXN_RENDER = 40;
// below this, the user is still typing a page name — do not flood the list
const PALETTE_TXN_MIN_QUERY = 3;

export function CommandPalette() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [queued, setQueued] = useState<string | null>(null);

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  // Load the feed only while the palette is open; cmdk filters client-side over
  // what is RENDERED, so both numbers below bound what search can ever find.
  // The default page (50) meant the palette silently could not locate anything
  // outside the newest 50 transactions — the same first-page dead-end FE3 fixed
  // on the books table. Server clamps limit at 500. Proper full-text search
  // belongs server-side; this makes the palette honest for a real SME book.
  const txns = useQuery({
    queryKey: ["palette-txns"],
    queryFn: () => api.transactions(undefined, undefined, PALETTE_TXN_LIMIT),
    enabled: open,
    staleTime: 60_000,
  });

  const go = useCallback(
    (href: string) => {
      setOpen(false);
      router.push(href);
    },
    [router],
  );

  async function runAgent(graph: string, label: string) {
    setQueued(label);
    try {
      await api.startRun(graph);
      queryClient.invalidateQueries({ queryKey: ["runs"] }); // beam pulses now
      setTimeout(() => {
        setQueued(null);
        setOpen(false);
      }, 900);
    } catch {
      setQueued(null);
    }
  }

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-50 bg-[#04070d]/70 backdrop-blur-[2px]"
          onClick={() => setOpen(false)}
          aria-hidden
        />
      )}
      <Command.Dialog
        open={open}
        onOpenChange={setOpen}
        label="Command palette"
        className="glass-strong grain fixed left-1/2 top-[18%] z-50 w-[min(640px,92vw)] -translate-x-1/2 overflow-hidden rounded-glass border border-line"
      >
        <div className="flex items-center gap-2 border-b border-line2 px-4">
          <Sparkles size={15} className="shrink-0 text-accent" />
          <Command.Input
            placeholder="Jump to a page, run the agent, find a transaction…"
            className="w-full bg-transparent py-3.5 text-sm text-ink outline-none placeholder:text-faint"
          />
          <kbd className="mono-label shrink-0 rounded border border-line2 px-1.5 py-0.5 text-faint">
            esc
          </kbd>
        </div>

        {queued ? (
          <div className="flex items-center gap-2 px-4 py-6 text-sm text-mint">
            <span className="h-2 w-2 animate-ping rounded-full bg-mint" />
            {queued} — queued. Watch it land on the dashboard feed.
          </div>
        ) : (
          <Command.List className="max-h-[420px] overflow-y-auto p-2">
            <Command.Empty className="px-3 py-6 text-center text-sm text-faint">
              Nothing matches. Try a page name, an action, or a narration.
            </Command.Empty>

            <Command.Group
              heading="Go to"
              className="[&_[cmdk-group-heading]]:mono-label [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-faint"
            >
              {PAGES.map((p) => (
                <Command.Item
                  key={p.href}
                  value={`go ${p.label} ${p.hint}`}
                  onSelect={() => go(p.href)}
                  className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-mute aria-selected:bg-[var(--fill-3)] aria-selected:text-ink"
                >
                  <BookOpen size={15} className="text-faint" />
                  <span className="font-semibold">{p.label}</span>
                  <span className="mono-label ml-auto hidden text-faint sm:block">{p.hint}</span>
                </Command.Item>
              ))}
            </Command.Group>

            <Command.Group
              heading="Agent actions"
              className="[&_[cmdk-group-heading]]:mono-label [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-faint"
            >
              {AGENT_ACTIONS.map((a) => (
                <Command.Item
                  key={a.graph}
                  value={`run ${a.label} ${a.hint}`}
                  onSelect={() => runAgent(a.graph, a.label)}
                  className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-mute aria-selected:bg-[var(--fill-3)] aria-selected:text-ink"
                >
                  <span className="text-accent">{a.icon}</span>
                  <span className="font-semibold">{a.label}</span>
                  <span className="mono-label ml-auto hidden text-faint sm:block">{a.hint}</span>
                </Command.Item>
              ))}
            </Command.Group>

            <TransactionResults items={txns.data?.items ?? []} onPick={go} />
          </Command.List>
        )}
      </Command.Dialog>
    </>
  );
}

/** Transactions, filtered by SUBSTRING against cmdk's own search state.
 *
 *  Deliberately not left to cmdk's fuzzy scorer. Two reasons, both learned the
 *  hard way: a generic query like "ims" must rank the IMS *page* above a
 *  transaction whose narration merely contains i-m-s as a subsequence, because
 *  navigation is the palette's primary job; and transactions should only appear
 *  once the user has typed something specific.
 *
 *  Reading the search via useCommandState keeps Command.Input UNCONTROLLED —
 *  controlling it made selection depend on a React re-render, so a fast
 *  type-then-Enter (exactly what an e2e test and an impatient user both do)
 *  landed with nothing selected. */
function TransactionResults({
  items,
  onPick,
}: {
  items: TxnPage["items"];
  onPick: (href: string) => void;
}) {
  const search = useCommandState((state) => state.search);
  const needle = search.trim().toLowerCase();
  if (needle.length < PALETTE_TXN_MIN_QUERY) return null;

  const matches = items
    .filter((t) =>
      `${t.narration} ${t.counterparty_hint ?? ""}`.toLowerCase().includes(needle),
    )
    .slice(0, PALETTE_TXN_RENDER);
  if (matches.length === 0) return null;

  return (
    <Command.Group
      heading="Transactions — enter opens Why?"
      className="[&_[cmdk-group-heading]]:mono-label [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-faint"
    >
      {matches.map((t) => (
        <Command.Item
          key={t.id}
          value={`txn ${t.narration} ${t.counterparty_hint ?? ""} ${t.match_status}`}
          onSelect={() => onPick(`/books?why=${t.id}`)}
          className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm text-mute aria-selected:bg-[var(--fill-3)] aria-selected:text-ink"
        >
          <ArrowRight size={13} className="text-faint" />
          <span className="truncate">{t.narration}</span>
          <span className="tnum ml-auto shrink-0 font-mono text-xs text-faint">
            {formatINR(t.amount_paise)}
          </span>
        </Command.Item>
      ))}
    </Command.Group>
  );
}
