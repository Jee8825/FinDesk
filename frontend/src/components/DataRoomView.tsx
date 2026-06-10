"use client";
// B5's shared surface — rendered identically for the owner and (read-only)
// for a lender holding a share link.
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
  const r = 54;
  const c = 2 * Math.PI * r;
  const filled = (score / 100) * c;
  return (
    <svg viewBox="0 0 140 140" className="h-36 w-36" role="img" aria-label={`FinDesk score ${score}`}>
      <circle cx="70" cy="70" r={r} fill="none" stroke="#e2e8f0" strokeWidth="12" />
      <circle
        cx="70"
        cy="70"
        r={r}
        fill="none"
        stroke="#0e6e74"
        strokeWidth="12"
        strokeDasharray={`${filled} ${c - filled}`}
        strokeLinecap="round"
        transform="rotate(-90 70 70)"
      />
      <text x="70" y="66" textAnchor="middle" fontSize="30" fontWeight="700" fill="#0b1f33">
        {score}
      </text>
      <text x="70" y="86" textAnchor="middle" fontSize="10" fill="#64748b">
        FinDesk Score
      </text>
    </svg>
  );
}

export function DataRoomView({ room }: { room: DataRoom }) {
  const ev = room.evidence;
  return (
    <div>
      <section className="flex items-center gap-8 rounded-xl border bg-white p-6 shadow-sm">
        <ScoreDial score={room.findesk_score.score} />
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                room.audit_chain.ok
                  ? "bg-emerald-50 text-emerald-700"
                  : "bg-red-50 text-red-700"
              }`}
            >
              {room.audit_chain.ok
                ? `⛓ audit chain verified — ${room.audit_chain.rows} events`
                : "⚠ audit chain BROKEN"}
            </span>
          </div>
          <div className="mt-3 space-y-1.5">
            {Object.entries(room.findesk_score.components).map(([key, c]) => (
              <div key={key} className="flex items-center gap-2 text-xs">
                <span className="w-44 text-slate-500">{COMPONENT_LABELS[key] ?? key}</span>
                <div className="h-1.5 flex-1 rounded bg-slate-100">
                  <div
                    className="h-1.5 rounded bg-teal-brand"
                    style={{ width: `${c.ratio * 100}%` }}
                  />
                </div>
                <span className="w-16 text-right font-mono text-slate-600">
                  {c.points}/{c.weight}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {[
          ["Bank transactions", ev.bank_transactions],
          ["Auto-matched & posted", ev.committed_matches],
          ["TDS-adjusted settlements", ev.tds_adjusted_matches],
          ["Debits categorized", ev.debits_categorized],
          ["Conflicts resolved", ev.conflicts_resolved],
          ["Audit events (hash-chained)", ev.audit_events],
        ].map(([label, value]) => (
          <div key={String(label)} className="rounded-xl border bg-white p-4 shadow-sm">
            <p className="text-xs uppercase text-slate-400">{label}</p>
            <p className="mt-1 font-mono text-lg font-semibold text-ink">{String(value)}</p>
          </div>
        ))}
        <div className="rounded-xl border bg-white p-4 shadow-sm">
          <p className="text-xs uppercase text-slate-400">Open receivables</p>
          <p className="mt-1 font-mono text-lg font-semibold text-ink">
            {formatINR(Number(ev.open_receivables_paise ?? 0))}
          </p>
          <p className="text-xs text-slate-400">
            of which overdue {formatINR(Number(ev.overdue_receivables_paise ?? 0))}
          </p>
        </div>
      </section>

      <p className="mt-4 text-xs text-slate-400">{room.methodology_note}</p>
    </div>
  );
}
