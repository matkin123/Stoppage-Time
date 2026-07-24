"""READ-ONLY: Find WC2026 matches with the highest 2H (P2) discrepancy between owed and played
stoppage time. Designed for finding punchy anecdote candidates for editorial use.

Outputs:
1. Ranked table of P2 discrepancy (owed - played) for all / R16 matches
2. For top candidates: all stoppage windows (sorted largest->smallest by dead D), each with
   a snippet of the Match_Event_Log rows showing what the model is classifying.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.sky_wc2026.build_wc2026_inputs as B

XLSX = B.XLSX
DELAY_EVT = B.DELAY_EVT
NOMINAL_END = B.NOMINAL_END


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt_s(clock_s: float) -> str:
    """Format absolute cumulative match-clock seconds -> MM:SS."""
    m = int(clock_s // 60)
    s = int(clock_s % 60)
    return f"{m:02d}:{s:02d}"


def fmt_min(min_abs: float) -> str:
    """Format absolute minute (float) stored in candidate rows -> MM:SS."""
    return fmt_s(min_abs * 60.0)


# ---------------------------------------------------------------------------
# Load extended event log (with match-clock string for context)
# ---------------------------------------------------------------------------

def load_event_log_extended():
    """Return dict (fixture_uuid, period) -> sorted list of event dicts, with all columns."""
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    it, ix = B._rows(wb["Match_Event_Log"])
    rows: dict = defaultdict(list)
    for r in it:
        per = r[ix["periodId"]]
        if per not in (1, 2, 3, 4):
            continue
        uu = r[ix["fixture_uuid"]]
        clock_s = float(r[ix["Time minute"]] or 0) * 60.0 + float(r[ix["Time second"]] or 0)
        rows[(uu, int(per))].append({
            "clock_s": clock_s,
            "match_clock": str(r[ix.get("Match clock", -1)] or "").strip() if "Match clock" in ix else "",
            "etid": r[ix["Event type ID"]],
            "etype": str(r[ix["Event type"]] or ""),
            "family": str(r[ix["Default stoppage family"]] or ""),
            "player": str(r[ix.get("Player", -1)] or "") if "Player" in ix else "",
            "qualifiers": str(r[ix.get("Qualifiers", -1)] or "")[:80] if "Qualifiers" in ix else "",
        })
    wb.close()
    for k in rows:
        rows[k].sort(key=lambda e: e["clock_s"])
    return rows


# ---------------------------------------------------------------------------
# Per-period OWED (replicates compute_owed but returns per-period breakdown)
# ---------------------------------------------------------------------------

def compute_owed_per_period(T):
    """Return dict fixture_uuid -> dict period -> owed_s (float).
    Full ADR-0038 logic: delay-full, seam, lead-in, half-time-sub removal."""
    from src.lib import config as cfg
    p = cfg.params()["incident"]
    allow = {str(k): float(v) for k, v in p["restart_normal_s"].items()}
    caps = dict(injury=p["max_injury_s"], sub=p["max_sub_s"], card=p["max_card_s"],
                celebration=p["max_celebration_s"])

    COMP = ["hydration", "injury", "sub", "card", "celebration",
            "throw-in", "goal-kick", "corner", "free-kick", "delay", "seam", "leadin"]

    # (uu, per) -> component sums
    per_acc: dict = defaultdict(lambda: {c: 0.0 for c in COMP})
    hyd_used: set = set()

    by_mp: dict = defaultdict(list)
    for g in T["cand"]:
        by_mp[(g["fixture_uuid"], g["period"])].append(g)

    for (uu, per), gaps in by_mp.items():
        acc = per_acc[(uu, per)]
        op = T["openplay"].get((uu, per), [])
        bd = T["balldeath"].get((uu, per), [])
        ps_mc = B.PERIOD_START_MC.get(per, "")
        prev_end = None

        for w in B._stitch_windows(gaps):
            w_start, w_end = w[0]["start_min_abs"], w[-1]["end_min_abs"]

            # seam
            if prev_end is not None and (w_start - prev_end) * 60.0 > B.STITCH_TOL_S \
                    and not B._has_openplay(op, prev_end, w_start):
                acc["seam"] += (w_start - prev_end) * 60.0

            # lead-in
            op0 = B._last_openplay_before(op, w_start)
            if op0 is not None and (prev_end is None or op0 > prev_end):
                bdt = B._first_balldeath_in(bd, op0, w_start)
                if bdt is not None:
                    leadin_s = min((w_start - bdt) * 60.0, B.LEADIN_CAP_S)
                    if leadin_s > 0:
                        acc["leadin"] += leadin_s

            prev_end = w_end

            if any(g["start_evt"] in DELAY_EVT or g["end_evt"] in DELAY_EVT for g in w):
                acc["delay"] += sum(g["D"] for g in w)
                continue

            for g in w:
                D, fam = g["D"], g["family"]
                sET, eET, qids = g["start_evt"], g["end_evt"], g["end_qids"]

                mids = T["hyd"].get((g["match"], per), [])
                if mids and any(g["start_min_abs"] <= m <= g["end_min_abs"] for m in mids):
                    if (g["match"], per) not in hyd_used:
                        acc["hydration"] += D
                        hyd_used.add((g["match"], per))
                    continue
                if sET in B.INJURY_EVT or eET in B.INJURY_EVT or fam in B.INJURY_FAM:
                    acc["injury"] += min(D, caps["injury"]); continue
                if sET in B.SUB_EVT or eET in B.SUB_EVT or fam.startswith("Substitution"):
                    pre_whistle = ((sET in B.SUB_EVT and g["start_mc"] == ps_mc)
                                   or (eET in B.SUB_EVT and g["end_mc"] == ps_mc))
                    if pre_whistle:
                        continue  # excluded, contributes 0
                    acc["sub"] += min(D, caps["sub"]); continue
                if sET in B.CARD_EVT or eET in B.CARD_EVT or fam in B.CARD_FAM:
                    acc["card"] += min(D, caps["card"]); continue
                if sET in B.CELEB_EVT or fam in B.CELEB_FAM:
                    acc["celebration"] += min(D, caps["celebration"]); continue
                rtype, a = B.resolve_restart(qids, fam, allow)
                if rtype in ("throw-in", "goal-kick", "corner", "free-kick"):
                    acc[rtype] += max(0.0, D - a); continue
                # keeper / excluded -> 0

    # collapse per-period to total owed_s
    result: dict = defaultdict(dict)
    for (uu, per), acc in per_acc.items():
        result[uu][per] = sum(acc.values())
    return dict(result)


# ---------------------------------------------------------------------------
# Per-period PLAYED
# ---------------------------------------------------------------------------

def compute_played_per_period(T):
    """Return dict fixture_uuid -> dict period -> played_s."""
    result: dict = {}
    for uu in T["fixtures"]:
        result[uu] = {}
        for per in (1, 2, 3, 4):
            clk = T["ends"].get((uu, per))
            if clk is not None:
                result[uu][per] = max(0.0, clk - NOMINAL_END[per])
    return result


# ---------------------------------------------------------------------------
# Window classifier (for display)
# ---------------------------------------------------------------------------

def classify_window(w) -> tuple[str, float]:
    """Return (rule_label, credited_s) for a stitched window -- simplified for display."""
    D = sum(g["D"] for g in w)
    if any(g["start_evt"] in DELAY_EVT or g["end_evt"] in DELAY_EVT for g in w):
        return "DELAY (Type 27/28/65) — full D credited", D
    # coarse per-gap: report first matched marker
    labels = []
    for g in w:
        sET, eET, fam = g["start_evt"], g["end_evt"], g["family"]
        if sET in B.INJURY_EVT or eET in B.INJURY_EVT or fam in B.INJURY_FAM:
            labels.append("injury"); continue
        if sET in B.SUB_EVT or eET in B.SUB_EVT or fam.startswith("Substitution"):
            labels.append("sub"); continue
        if sET in B.CARD_EVT or eET in B.CARD_EVT or fam in B.CARD_FAM:
            labels.append("card"); continue
        if sET in B.CELEB_EVT or fam in B.CELEB_FAM:
            labels.append("celebration"); continue
        qids = g["end_qids"]
        if "107" in qids: labels.append("throw-in excess"); continue
        if "124" in qids: labels.append("goal-kick excess"); continue
        if "6" in qids or fam == "Corner / set piece": labels.append("corner excess"); continue
        if "5" in qids or fam in ("Foul", "Offside"): labels.append("free-kick excess"); continue
        if "123" in qids: labels.append("keeper (0)"); continue
        labels.append(f"excluded [{fam or 'blank'}]")
    unique = list(dict.fromkeys(labels))
    return " + ".join(unique) if unique else "unknown", None  # partial per-gap credit


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(top_n: int = 5, show_n_windows: int = 99, show_all_matches: bool = False):
    print(f"Loading {XLSX.name} ...")
    T = B.load_workbook_tables()
    evlog = load_event_log_extended()

    owed_per = compute_owed_per_period(T)
    played_per = compute_played_per_period(T)

    # Compute per-match P2 discrepancy
    rows = []
    for uu, fx in T["fixtures"].items():
        owed_p2 = owed_per.get(uu, {}).get(2, 0.0)
        played_p2 = played_per.get(uu, {}).get(2, 0.0)
        disc_p2 = owed_p2 - played_p2
        owed_p1 = owed_per.get(uu, {}).get(1, 0.0)
        played_p1 = played_per.get(uu, {}).get(1, 0.0)
        rows.append({
            "match": fx["match"],
            "uu": uu,
            "owed_p2_min": owed_p2 / 60.0,
            "played_p2_min": played_p2 / 60.0,
            "disc_p2_min": disc_p2 / 60.0,
            "owed_p1_min": owed_p1 / 60.0,
            "played_p1_min": played_p1 / 60.0,
        })

    rows.sort(key=lambda r: -r["disc_p2_min"])

    print("\n" + "=" * 80)
    print("ALL MATCHES — ranked by P2 discrepancy (owed minus played, minutes)")
    print("=" * 80)
    print(f"{'#':>3}  {'Match':<35} {'Owed_P2':>8} {'Played_P2':>10} {'Disc_P2':>8}")
    print("-" * 70)
    for i, r in enumerate(rows, 1):
        print(f"{i:3d}  {r['match']:<35} {r['owed_p2_min']:8.1f} {r['played_p2_min']:10.1f} "
              f"{r['disc_p2_min']:8.1f}")

    # --- Per-match window dump ---
    by_mp: dict = defaultdict(list)
    for g in T["cand"]:
        by_mp[(g["fixture_uuid"], g["period"])].append(g)

    targets = rows[:top_n]
    for rank, r in enumerate(targets, 1):
        uu = r["uu"]
        name = r["match"]

        print("\n" + "=" * 88)
        print(f"RANK #{rank}: {name}")
        print(f"  P2 owed={r['owed_p2_min']:.1f} min  played={r['played_p2_min']:.1f} min  "
              f"disc={r['disc_p2_min']:.1f} min")
        print(f"  P1 owed={r['owed_p1_min']:.1f} min  played={r['played_p1_min']:.1f} min")

        # Build all P2 windows and sort by dead D
        per = 2
        gaps = by_mp.get((uu, per), [])
        if not gaps:
            print("  (no candidate gaps in P2)")
            continue

        wins = []
        for w in B._stitch_windows(gaps):
            D = sum(g["D"] for g in w)
            rule, cred = classify_window(w)
            wins.append({
                "w": w, "D": D, "rule": rule, "credit": cred,
                "s_min": min(g["start_min_abs"] for g in w),
                "e_min": max(g["end_min_abs"] for g in w),
                "n_gaps": len(w),
            })
        wins.sort(key=lambda x: -x["D"])

        total_owed_p2 = owed_per.get(uu, {}).get(2, 0.0)
        total_dead_p2 = sum(g["D"] for g in gaps)
        print(f"  P2 candidate windows: {len(wins)}  total dead: {total_dead_p2/60:.1f} min  "
              f"total owed: {total_owed_p2/60:.1f} min\n")

        for i, wn in enumerate(wins[:show_n_windows], 1):
            s_str = fmt_min(wn["s_min"])
            e_str = fmt_min(wn["e_min"])
            cred_str = (f"{wn['credit']/60:.1f} min FULL" if wn["credit"] is not None
                        else "excess/marker only")
            print(f"  WINDOW #{i}  {s_str} → {e_str}  dead={wn['D']/60:.1f} min ({wn['D']:.0f}s)  "
                  f"credit={cred_str}")
            print(f"    Rule: {wn['rule']}  ({wn['n_gaps']} gap(s))")

            # Event log rows spanning the window ±5s buffer
            lo = wn["s_min"] * 60.0 - 5.0
            hi = wn["e_min"] * 60.0 + 5.0
            evs = [e for e in evlog.get((uu, per), []) if lo <= e["clock_s"] <= hi]
            if evs:
                print(f"    {'Time':>6}  {'TypeID':>6}  {'Event type':<28}  {'Family':<22}  "
                      f"{'Player':<18}  Notes")
                print("    " + "-" * 100)
                for e in evs:
                    note = ""
                    etid = e["etid"]
                    if etid == 27:
                        note = "▶ START DELAY"
                    elif etid == 28:
                        note = "◀ END DELAY"
                    elif etid == 65:
                        note = "⚡ CONTENTIOUS/VAR"
                    elif etid == 30:
                        note = "🏁 PERIOD END"
                    elif etid == 16:
                        note = "⚽ GOAL"
                    elif etid == 40:
                        note = "ADMIN"
                    elif etid == 43:
                        note = "DELETED"
                    mc = f"[{e['match_clock']}]" if e["match_clock"] else ""
                    print(f"    {fmt_s(e['clock_s']):>6}  T{etid:>5}  {e['etype'][:28]:<28}  "
                          f"{e['family'][:22]:<22}  {e['player'][:18]:<18}  {note} {mc}")
            else:
                print("    (no event-log rows in this window range)")
            print()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=5, help="Number of top matches to detail")
    ap.add_argument("--windows", type=int, default=99, help="Max windows to show per match")
    args = ap.parse_args()
    main(top_n=args.top, show_n_windows=args.windows)
