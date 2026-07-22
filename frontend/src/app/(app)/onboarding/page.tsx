"use client";
// Onboarding — "Stepper" (wireframe Onboarding A): connect books → seed
// memory from history → first autonomous scan. This is what makes the agent
// accurate from day one.
import { AnimatePresence, motion } from "framer-motion";
import { Check, FileUp, ScanLine } from "lucide-react";
import { useRef, useState } from "react";

import {
  AnimatedNumber,
  Card,
  ErrorNote,
  MonoLabel,
  PageShell,
  PrimaryBtn,
  stagger,
} from "@/components/ui";
import { useRunStream } from "@/hooks/useRunStream";
import { api } from "@/lib/api";

type SeedResult = {
  source_hint: string;
  counterparties_created: number;
  invoices_created: number;
  invoices_skipped: number;
  observations_seeded: number;
};

const STEPS = ["Connect", "Seed memory", "First scan"];

function StepDot({ index, current }: { index: number; current: number }) {
  const done = index < current;
  const active = index === current;
  return (
    <div className="flex items-center gap-3">
      <motion.span
        animate={{ scale: active ? 1.1 : 1 }}
        className={`flex h-8 w-8 items-center justify-center rounded-full font-mono text-sm font-bold ${
          done
            ? "bg-moss text-white"
            : active
              ? "bg-accent text-white shadow-[0_8px_20px_-8px_rgba(232,115,10,0.8)]"
              : "border-2 border-line bg-cream text-faint"
        }`}
      >
        {done ? <Check size={14} /> : index + 1}
      </motion.span>
      <span className={`text-sm font-bold ${active ? "text-ink" : done ? "text-moss" : "text-faint"}`}>
        {STEPS[index]}
      </span>
    </div>
  );
}

export default function OnboardingPage() {
  const invoiceInput = useRef<HTMLInputElement>(null);
  const stmtInput = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [seed, setSeed] = useState<SeedResult | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const { events, done } = useRunStream(runId);

  async function importInvoices(file: File) {
    setError(null);
    setBusy(true);
    try {
      const r = await api.onboardInvoices(file);
      setSeed(r);
      setStep(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "import failed");
    } finally {
      setBusy(false);
      if (invoiceInput.current) invoiceInput.current.value = "";
    }
  }

  async function firstScan(file: File) {
    setError(null);
    setBusy(true);
    try {
      const r = await api.importStatement(file);
      setRunId(r.run_id);
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : "upload failed");
    } finally {
      setBusy(false);
      if (stmtInput.current) stmtInput.current.value = "";
    }
  }

  return (
    <PageShell
      title="Onboarding"
      subtitle="Connect books → seed memory → first scan"
      annotation="POST /books/onboarding · POST /books/imports · seeding job stream"
    >
      <p className="mono-annot mb-6">
        ◇ first-run · connect books → seed memory from history → first autonomous scan
      </p>

      <div className="mx-auto max-w-3xl">
        <div className="flex items-center justify-between px-2">
          {STEPS.map((_, i) => (
            <div key={i} className="flex flex-1 items-center">
              <StepDot index={i} current={step} />
              {i < STEPS.length - 1 && (
                <div className="mx-4 h-[2px] flex-1 overflow-hidden rounded bg-line">
                  <motion.div
                    className="h-full bg-moss"
                    initial={{ width: 0 }}
                    animate={{ width: step > i ? "100%" : "0%" }}
                    transition={{ duration: 0.6 }}
                  />
                </div>
              )}
            </div>
          ))}
        </div>

        {error && <ErrorNote>{error}</ErrorNote>}

        <AnimatePresence mode="wait">
          {step === 0 && (
            <motion.div
              key="s0"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.35 }}
            >
              <Card className="mt-8 p-8">
                <h2 className="text-xl font-bold text-ink">Connect your books</h2>
                <p className="mt-2 max-w-xl text-sm leading-relaxed text-mute">
                  Import your Tally or Zoho invoice export. FinDesk reads your history to learn
                  your vendors, categories, and how each client actually pays — this is what makes
                  the agent accurate from day one.
                </p>
                <input
                  ref={invoiceInput}
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && importInvoices(e.target.files[0])}
                />
                <PrimaryBtn className="mt-6" onClick={() => invoiceInput.current?.click()} disabled={busy}>
                  <FileUp size={14} /> {busy ? "Importing…" : "Import invoice export (CSV)"}
                </PrimaryBtn>
                <p className="mono-annot mt-4">◇ Tally / Zoho column formats auto-detected</p>
              </Card>
            </motion.div>
          )}

          {step === 1 && seed && (
            <motion.div
              key="s1"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.35 }}
            >
              <Card className="mt-8 p-8">
                <h2 className="text-xl font-bold text-ink">Memory seeded from your history</h2>
                <p className="mt-2 max-w-xl text-sm leading-relaxed text-mute">
                  Detected a <span className="font-semibold text-ink">{seed.source_hint}</span>{" "}
                  export. The agent now knows your clients and their payment patterns.
                </p>
                <motion.div className="mt-6 grid grid-cols-3 gap-4" initial="initial" animate="animate" variants={stagger}>
                  {(
                    [
                      ["clients learned", seed.counterparties_created],
                      ["invoices imported", seed.invoices_created],
                      ["behaviors remembered", seed.observations_seeded],
                    ] as const
                  ).map(([label, value]) => (
                    <motion.div
                      key={label}
                      variants={{ initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 } }}
                      className="rounded-xl border-[1.5px] border-dashed border-line p-5 text-center"
                    >
                      <div className="font-mono text-3xl font-bold text-ink">
                        <AnimatedNumber value={value} format={(n) => String(Math.round(n))} />
                      </div>
                      <MonoLabel className="mt-1">{label}</MonoLabel>
                    </motion.div>
                  ))}
                </motion.div>
                {seed.invoices_skipped > 0 && (
                  <p className="mono-annot mt-3">◇ {seed.invoices_skipped} duplicates skipped</p>
                )}
                <input
                  ref={stmtInput}
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && firstScan(e.target.files[0])}
                />
                <PrimaryBtn className="mt-6" onClick={() => stmtInput.current?.click()} disabled={busy}>
                  <ScanLine size={14} /> {busy ? "Uploading…" : "Upload a bank statement → first scan"}
                </PrimaryBtn>
              </Card>
            </motion.div>
          )}

          {step === 2 && (
            <motion.div
              key="s2"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.35 }}
            >
              <Card className="mt-8 p-8">
                <h2 className="text-xl font-bold text-ink">
                  {done ? "First scan complete 🎉" : "First autonomous scan running…"}
                </h2>
                <p className="mt-2 max-w-xl text-sm leading-relaxed text-mute">
                  Planner → Executor → Critic, live. Anything ambiguous waits for you in the
                  queues — nothing consequential commits without approval.
                </p>
                <div className="mt-5 max-h-64 space-y-1.5 overflow-y-auto rounded-xl border border-line2 bg-cream p-4">
                  {events.map((evt, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="flex items-center gap-2 text-[13px]"
                    >
                      <span
                        className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                          evt.event.startsWith("run.done") ? "bg-moss" : evt.status === "failed" ? "bg-claret" : "bg-accent"
                        }`}
                      />
                      <span className="font-mono text-[11px] text-faint">{evt.name ?? evt.event}</span>
                      <span className="truncate text-mute">{evt.summary ?? evt.status ?? ""}</span>
                    </motion.div>
                  ))}
                </div>
                {done && (
                  <div className="mt-6 flex gap-3">
                    <a href="/">
                      <PrimaryBtn>Go to the dashboard →</PrimaryBtn>
                    </a>
                  </div>
                )}
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </PageShell>
  );
}
