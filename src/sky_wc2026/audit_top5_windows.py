"""READ-ONLY manual audit: dump the OWED windows (largest->smallest) for the top-5
high-owed / high-discrepancy WC2026 matches, with the constituent Match_Event_Log rows
per window. No estimator change -- reuses build_wc2026_inputs mechanics."""
from __future__ import annotations
import sys
from collections import defaultdict
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.sky_wc2026.build_wc2026_inputs as B
from src.lib import config

XLSX = B.XLSX

TARGETS = [
    "Canada v Qatar", "Sweden v Tunisia", "Jordan v Argentina",
    "USA v Australia", "Germany v Paraguay",
]

DELAY_EVT = B.DELAY_EVT


def fmt_clk(sec_abs, period):
    # candidate abs minute is cumulative match-clock minutes; show mm:ss
    s = sec_abs * 60.0
    return f"{int(s // 60):02d}:{int(s % 60):02d}"


def classify(w):
    """Return (credit_seconds, rule) replicating compute_owed for one stitched window.
    Simplified: only the delay-full branch vs a coarse per-gap label for reporting."""
    D = sum(g["D"] for g in w)
    if any(g["start_evt"] in DELAY_EVT or g["end_evt"] in DELAY_EVT for g in w):
        return D, "DELAY-FULL (Type 27/28/65)"
    return None, "per-gap ladder (non-delay)"


def load_event_log():
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    it, ix = B._rows(wb["Match_Event_Log"])
    rows = defaultdict(list)  # (fixture_uuid, period) -> list of event dicts
    for r in it:
        per = r[ix["periodId"]]
        if per not in (1, 2, 3, 4):
            continue
        uu = r[ix["fixture_uuid"]]
        clock_s = float(r[ix["Time minute"]] or 0) * 60.0 + float(r[ix["Time second"]] or 0)
        rows[(uu, int(per))].append({
            "clock_s": clock_s,
            "etid": r[ix["Event type ID"]],
            "etype": r[ix["Event type"]] or "",
            "family": r[ix["Default stoppage family"]] or "",
            "qual": r[ix["Qualifiers"]] or "",
            "player": r[ix["Player"]] or "",
        })
    wb.close()
    for k in rows:
        rows[k].sort(key=lambda e: e["clock_s"])
    return rows


def main():
    T = B.load_workbook_tables()
    evlog = load_event_log()
    fx_by_name = {f["match"]: f for f in T["fixtures"].values()}

    by_mp = defaultdict(list)
    for g in T["cand"]:
        by_mp[(g["fixture_uuid"], g["period"])].append(g)

    for name in TARGETS:
        fx = fx_by_name[name]
        uu = fx["fixture_uuid"]
        # provenance
        cand_sum = sum(g["D"] for g in T["cand"] if g["fixture_uuid"] == uu)
        summ = T["summ_dead"].get(name, float("nan"))
        print("=" * 88)
        print(f"{name}   [{uu}]  {fx['date']}")
        print(f"  candidate ΣD = {cand_sum:.1f}s  vs Stoppage_Summary dead = {summ:.1f}s"
              f"  (Δ {cand_sum-summ:+.1f}s)")

        # build stitched windows across periods, credit them, collect
        wins = []
        for per in (1, 2, 3, 4):
            gaps = by_mp.get((uu, per))
            if not gaps:
                continue
            for w in B._stitch_windows(gaps):
                credit, rule = classify(w)
                D = sum(g["D"] for g in w)
                wins.append({"per": per, "w": w, "D": D,
                             "credit": credit if credit is not None else None,
                             "rule": rule,
                             "s": min(g["start_min_abs"] for g in w),
                             "e": max(g["end_min_abs"] for g in w)})
        wins.sort(key=lambda x: -x["D"])
        print(f"  {len(wins)} stitched windows (top 8 by dead D shown):\n")
        for i, wn in enumerate(wins[:8], 1):
            per = wn["per"]
            cr = f"{wn['credit']:.1f}s FULL" if wn["credit"] is not None else "ladder (excess/marker)"
            print(f"  #{i} P{per} {fmt_clk(wn['s'],per)}->{fmt_clk(wn['e'],per)}  "
                  f"dead={wn['D']:.1f}s  credit={cr}  [{wn['rule']}]  "
                  f"({len(wn['w'])} candidate gap(s))")
            # event-log rows spanning the window
            lo, hi = wn["s"] * 60.0 - 2.0, wn["e"] * 60.0 + 2.0
            for e in evlog.get((uu, per), []):
                if lo <= e["clock_s"] <= hi:
                    q = e["qual"][:60]
                    print(f"       {int(e['clock_s']//60):02d}:{int(e['clock_s']%60):02d} "
                          f"T{e['etid']:>3} {e['etype'][:24]:24} | {e['family'][:18]:18} | "
                          f"{e['player'][:16]:16} | {q}")
            print()


if __name__ == "__main__":
    main()
