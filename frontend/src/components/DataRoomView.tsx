"use client";
// B5's shared surface — rendered identically for the owner (dark surface) and
// (read-only) for a lender holding a share link (light surface).
import { motion } from "framer-motion";

import { AnimatedNumber, Card, MonoLabel, Pill, useSurface, stagger } from "@/components/ui";
import { formatINR, type DataRoom } from "@/lib/api";

const COMPONENT_LABELS: Record<string, string> = {
  reconciliation: "Reconciliation coverage",
  categorization: "Categorization coverage",
  audit_integrity: "Audit-chain integrity",
  receivables_discipline: "Receivables discipline",
  conflict_hygiene: "Conflict hygiene",
  forecast_freshness: "Forecast freshness",
};

function ScoreDial({ score }: { score: number }) {
  const dark = useSurface() === "dark";
  const r = 54;
  const c = 2 * Math.PI * r;
  const filled = (score / 100) * c;
  const track = dark ? "#2e2c28" : "#e2dccd";
  const fill = score >= 75 ? "#43d695" : score >= 50 ? "#ffa028" : "#ff6e66";
  return (
    <svg viewBox="0 0 140 140" className="h-40 w-40" role="img" aria-label={`FinDesk score ${score}`}>
      <circle cx="70" cy="70" r={r} fill="none" stroke={track} strokeWidth="12" />
      <motion.circle
        cx="70"
        cy="70"
        r={r}
        fill="none"
        stroke={fill}
        strokeWidth="12"
        strokeLinecap="round"
        strokeDasharray={c}
        transform="rotate(-90 70 70)"
        initial={{ strokeDashoffset: c }}
        animate={{ strokeDashoffset: c - filled }}
        transition={{ duration: 1.4, ease: [0.22, 1, 0.36, 1] }}
      />
      <text
        x="70"
        y="70"
        textAnchor="middle"
        fontSize="34"
        fontWeight="700"
        fill={dark ? "#f0eee8" : "#26241f"}
        fontFamily="var(--font-plex-mono)"
      >
        {score}
      </text>
      <text x="70" y="90" textAnchor="middle" fontSize="10" fill={dark ? "#7d7a72" : "#9b968a"} fontFamily="var(--font-plex-mono)">
        / 100
      </text>
    </svg>
  );
}

export function DataRoomView({ room }: { room: DataRoom }) {
  const dark = useSurface() === "dark";
  const ev = room.evidence;
  const score = room.findesk_score.score;
  const verdict = score >= 75 ? "Credit-ready" : score >= 50 ? "Getting there" : "Needs work";

  return (
    <div className="grid items-start gap-5 lg:grid-cols-[280px_1fr]">
      <Card className="flex flex-col items-center p-7 text-center">
        <MonoLabel>findesk score</MonoLabel>
        <div className="mt-3">
          <ScoreDial score={score} />
        </div>
        <p className={`mt-2 text-lg font-bold ${dark ? "text-mint" : "text-moss"}`}>{verdict}</p>
        <p className={`mt-1 text-xs leading-relaxed ${dark ? "text-dark-mute" : "text-faint"}`}>
          Books reconciled, clean provenance, verifiable audit chain.
        </p>
        <div className="mt-4">
          <Pill tone={room.audit_chain.ok ? "good" : "bad"}>
            {room.audit_chain.ok ? `⛓ chain verified · ${room.audit_chain.rows} events` : "⚠ audit chain broken"}
          </Pill>
        </div>
      </Card>

      <div className="space-y-5">
        <Card className="p-6">
          <h3 className={`text-[15px] font-bold ${dark ? "text-dark-text" : "text-ink"}`}>Score factors</h3>
          <div className="mt-4 space-y-3.5">
            {Object.entries(room.findesk_score.components).map(([key, c], i) => (
              <div key={key}>
                <div className="flex items-center justify-between text-[13px]">
                  <span className={dark ? "text-dark-text/90" : "text-mute"}>
                    {COMPONENT_LABELS[key] ?? key}
                  </span>
                  <span className={`font-mono font-semibold ${dark ? "text-dark-text" : "text-ink"}`}>
                    {c.points}/{c.weight}
                  </span>
                </div>
                <div className={`mt-1.5 h-1.5 w-full overflow-hidden rounded-full ${dark ? "bg-dark-line" : "bg-line2"}`}>
                  <motion.div
                    className={`h-full rounded-full ${c.ratio >= 0.75 ? (dark ? "bg-mint" : "bg-moss") : "bg-accent-soft"}`}
                    initial={{ width: 0 }}
                    animate={{ width: `${c.ratio * 100}%` }}
                    transition={{ duration: 0.9, delay: 0.08 * i, ease: [0.22, 1, 0.36, 1] }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>

        <motion.div className="grid grid-cols-2 gap-3 sm:grid-cols-3" initial="initial" animate="animate" variants={stagger}>
          {(
            [
              ["Bank transactions", ev.bank_transactions],
              ["Auto-matched & posted", ev.committed_matches],
              ["TDS-adjusted settlements", ev.tds_adjusted_matches],
              ["Debits categorized", ev.debits_categorized],
              ["Conflicts resolved", ev.conflicts_resolved],
              ["Audit events (chained)", ev.audit_events],
            ] as const
          ).map(([label, value]) => (
            <Card key={label} hover className="p-4">
              <MonoLabel>{label}</MonoLabel>
              <div className={`mt-1.5 font-mono text-lg font-bold ${dark ? "text-dark-text" : "text-ink"}`}>
                {typeof value === "number" ? (
                  <AnimatedNumber value={value} format={(n) => String(Math.round(n))} />
                ) : (
                  <span>{value ?? "—"}</span>
                )}
              </div>
            </Card>
          ))}
          <Card hover className="p-4">
            <MonoLabel>open receivables</MonoLabel>
            <div className={`mt-1.5 font-mono text-lg font-bold ${dark ? "text-dark-text" : "text-ink"}`}>
              {formatINR(Number(ev.open_receivables_paise ?? 0))}
            </div>
            <p className={`mt-0.5 text-[11px] ${dark ? "text-dark-mute" : "text-faint"}`}>
              overdue {formatINR(Number(ev.overdue_receivables_paise ?? 0))}
            </p>
          </Card>
        </motion.div>

        <p className="mono-annot">{room.methodology_note}</p>
      </div>
    </div>
  );
}
