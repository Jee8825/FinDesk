#!/usr/bin/env python3
"""Generate LeakRadar demo statements — one business, one personal.

Every vendor below exists to exercise a specific branch of the detectors, and
each carries a `why` note so the demo can be narrated from the data. Two of them
exist to prove the tool stays *quiet* where it should: a stopped series (already
cancelled — must not be flagged) and rent/payroll/EMI (recurring commitments,
never "subscription leaks").

Deterministic: same input, same bytes out. Run:

    .venv/bin/python scripts/make_leak_fixtures.py

Writes scripts/fixtures/leakradar_business.csv and leakradar_personal.csv in the
same shape the bank_statements parser already accepts
(Date, Narration, Ref No, Debit, Credit, Balance · DD/MM/YYYY · Indian grouping).
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "fixtures"
# Anchored, not "today": fixtures must be reproducible byte-for-byte. Chosen so
# the newest charges sit a few weeks before the 2026-07-25 demo date.
ANCHOR = datetime(2026, 7, 20, tzinfo=UTC)


def months_back(n: int, *, day: int) -> datetime:
    """The `n`-th month before the anchor, on `day`."""
    y, m = ANCHOR.year, ANCHOR.month - n
    while m <= 0:
        m += 12
        y -= 1
    return datetime(y, m, day, tzinfo=UTC)


def monthly(
    narration: str,
    amounts: list[int],
    *,
    day: int,
    skip: set[int] | None = None,
    ended_months_ago: int = 0,
):
    """One charge per month, oldest first. `amounts` is newest-last.

    `ended_months_ago` walks the whole series back, which is how a *stopped*
    subscription is expressed — without it the newest charge always lands in the
    current month and nothing ever looks cancelled.
    """
    skip = skip or set()
    n = len(amounts)
    rows = []
    for i, amount in enumerate(amounts):
        back = (n - 1 - i) + ended_months_ago
        if (n - 1 - i) in skip:
            continue
        rows.append((months_back(back, day=day), narration, amount))
    return rows


def every(narration: str, amount: int, *, gap_days: int, n: int, newest_offset: int = 0):
    """`n` charges `gap_days` apart, newest `newest_offset` days before anchor."""
    newest = ANCHOR - timedelta(days=newest_offset)
    return [
        (newest - timedelta(days=gap_days * (n - 1 - i)), narration, amount)
        for i in range(n)
    ]


# --------------------------------------------------------------- business
# 7 monthly cycles (Jan-Jul 2026) so a monthly vendor has 6-7 points.
BUSINESS = [
    # 1. flat monthly — the clean baseline every other case is measured against
    (monthly("ZOHO ONE SUBSCRIPTION", [840000] * 7, day=3),
     "flat monthly · no leak signal"),

    # 2. THE headline case: +15% in April. Invisible to anomaly_scan's ratio
    #    test (verified in test_drift.py), caught by the changepoint detector.
    (monthly("NOTION TEAM PLAN", [400000] * 3 + [460000] * 4, day=6),
     "silent +15% hike from April — the case the old detector cannot see"),

    # 3. equal ₹1,200 steps — seats added, NOT a price rise. Different action.
    (monthly("FIGMA ORG SEATS", [360000, 360000, 480000, 600000, 720000, 720000, 720000],
             day=8),
     "seat creep in ₹1,200 steps — reconcile headcount, do not dispute"),

    # 4. +51% — large enough that both detectors agree, proving they don't
    #    contradict each other on the obvious case.
    (monthly("ADOBE CREATIVE CLOUD", [530000] * 4 + [800000] * 3, day=11),
     "+51% hike — both detectors agree"),

    # 5. usage-based: monthly cadence, wild amounts. Must be excluded from
    #    drift or it cries wolf every single month.
    (monthly("AWS INDIA CLOUD SERVICES",
             [1940000, 6410000, 2870000, 4420000, 1980000, 5330000, 3110000], day=6),
     "usage-based — regular dates, unstable amounts, excluded from drift"),

    # 6. cancelled three months ago. MUST NOT be flagged.
    (monthly("SLACK BUSINESS PLUS", [620000] * 4, day=9, ended_months_ago=3),
     "stopped 3 months ago — must be reported as stopped, never as a leak"),

    # 7. same category as Zoho/Notion/Figma → redundancy signal
    (monthly("ASANA PREMIUM PLAN", [510000] * 6, day=14),
     "redundant with other software_cloud tools — consolidation candidate"),

    # 8. one skipped month (May) — gap normalization must hold the cadence
    (monthly("GITHUB TEAM PLAN", [290000] * 7, day=17, skip={2}),
     "skipped May — cadence must survive a missed charge"),

    # 9. quarterly
    (every("ZOOM ONE PRO QUARTERLY", 1140000, gap_days=91, n=4, newest_offset=25),
     "quarterly cadence"),

    # 10. annual, renewal inside the 60-day horizon → actionable before it hits
    (every("TALLY PRIME RENEWAL", 1800000, gap_days=365, n=3, newest_offset=330),
     "annual renewal due in ~35 days — reviewable before it auto-charges"),

    # 11. a regular monthly vendor that got billed TWICE in one month. The
    #     duplicate has to sit inside an otherwise-clean series, or the series
    #     reads as irregular and the real finding is buried.
    (monthly("PAYU GATEWAY AMC CHARGES", [236000] * 7, day=13)
     + [(months_back(2, day=16), "PAYU GATEWAY AMC CHARGES", 236000)],
     "double-billed in May — cadence intact, duplicate recoverable"),

    # 12-13. commitments. If either of these ranks as a leak, the tool is wrong.
    (monthly("WEWORK BKC RENT", [8500000] * 7, day=2),
     "rent — recurring commitment, must score zero"),
    (monthly("SALARY PAYOUT STAFF BATCH", [42000000] * 7, day=1),
     "payroll — must score zero"),
]

# --------------------------------------------------------------- personal
PERSONAL = [
    (monthly("NETFLIX PREMIUM SUBSCRIPTION", [64900] * 7, day=4),
     "flat monthly streaming"),

    (monthly("SPOTIFY FAMILY PLAN", [17900] * 4 + [19900] * 3, day=7),
     "silent +11% hike — below every ratio-test threshold"),

    (monthly("YOUTUBE PREMIUM INDIA", [14900] * 7, day=12),
     "redundant with Netflix/Hotstar → streaming consolidation"),

    (monthly("HOTSTAR SUPER PLAN", [29900] * 4, day=9, ended_months_ago=3),
     "stopped 3 months ago — must not be flagged"),

    # The meaty one: a large personal subscription with no leak *signal* at all.
    # Nothing in the bank data marks it as waste — it surfaces only once the
    # human answers "no, I stopped going", which is the confirmation loop's
    # whole point and the biggest single number in personal mode.
    (monthly("GOLD GYM ELITE MEMBERSHIP", [299900] * 7, day=23),
     "expensive, no drift, no redundancy — only a human can call this waste"),

    (monthly("GOOGLE ONE 2TB STORAGE", [21000] * 7, day=15),
     "cloud storage"),

    (monthly("ICLOUD PLUS STORAGE", [21900] * 7, day=18),
     "redundant with Google One → cloud_storage consolidation"),

    (monthly("AIRTEL POSTPAID BILL", [99900, 99900, 99900, 119900, 119900, 119900, 119900],
             day=21),
     "+20% telecom rise — downgradeable, not cancellable"),

    (every("CULT FIT QUARTERLY PACK", 450000, gap_days=91, n=4, newest_offset=30),
     "quarterly fitness"),

    (every("AMAZON PRIME MEMBERSHIP", 149900, gap_days=365, n=3, newest_offset=325),
     "annual renewal due in ~40 days"),

    ([(ANCHOR - timedelta(days=33), "SWIGGY ONE MEMBERSHIP", 9900),
      (ANCHOR - timedelta(days=31), "SWIGGY ONE MEMBERSHIP", 9900),
      (ANCHOR - timedelta(days=63), "SWIGGY ONE MEMBERSHIP", 9900)],
     "duplicate charge two days apart"),

    (monthly("HOUSE RENT PAYMENT", [2800000] * 7, day=1),
     "rent — must score zero"),
    (monthly("HDFC HOME LOAN EMI", [4200000] * 7, day=5),
     "EMI — must score zero"),
    (every("LIC PREMIUM DEBIT", 900000, gap_days=91, n=4, newest_offset=20),
     "insurance — excluded in personal mode"),
]


def write(path: Path, groups, *, opening_paise: int) -> None:
    rows = []
    for txns, _why in groups:
        rows.extend(txns)
    rows.sort(key=lambda r: r[0])

    balance = opening_paise
    out = [["Date", "Narration", "Ref No", "Debit", "Credit", "Balance"]]
    for i, (dt, narration, amount) in enumerate(rows, start=1):
        balance -= amount
        out.append([
            dt.strftime("%d/%m/%Y"),
            narration,
            f"L{i:05d}",
            f"{amount / 100:,.2f}",
            "",
            f"{balance / 100:,.2f}",
        ])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(out)
    print(f"  {path.name}: {len(rows)} debits, {len(groups)} vendors")


def main() -> None:
    print("LeakRadar fixtures (anchor", ANCHOR.date(), "):")
    write(OUT_DIR / "leakradar_business.csv", BUSINESS, opening_paise=250_000_000)
    write(OUT_DIR / "leakradar_personal.csv", PERSONAL, opening_paise=40_000_000)
    print("\nvendor plan:")
    for label, groups in (("business", BUSINESS), ("personal", PERSONAL)):
        print(f"  [{label}]")
        for txns, why in groups:
            print(f"    {txns[0][1][:30]:<32} {len(txns)}x  {why}")


if __name__ == "__main__":
    main()
