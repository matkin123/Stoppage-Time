"""READ-ONLY: dump EVERY owed-credited window for Sweden v Tunisia, largest->smallest,
with constituent Match_Event_Log rows + plain-English Type interpretation."""
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

NAME = "Sweden v Tunisia"

# plain-English Opta Type interpretations (from Event_Type_Lookup + project notes)
TYPE_HINT = {
    1: "Pass (ball live)", 4: "Foul", 5: "Ball out of play", 6: "Corner awarded",
    7: "Tackle", 8: "Interception", 10: "Keeper save", 12: "Clearance", 13: "Shot missed",
    15: "Shot saved", 16: "GOAL", 17: "Card", 18: "Sub OFF", 19: "Sub ON",
    27: "START of delay (referee stoppage begins)", 28: "END of delay (play resumes)",
    30: "Period end", 32: "Period start", 40: "Formation change (admin)",
    43: "Deleted event (admin, credited 0)", 49: "Ball recovery", 50: "Dispossessed",
    51: "Error", 58: "Penalty faced", 61: "Ball touch", 65: "Contentious ref decision (VAR proxy)",
    68: "Referee drop ball", 74: "Blocked pass", 84: "Unmapped Opta event (credited 0)",
    90: "Type 90 (unmapped)",
}
DELAY_EVT = B.DELAY_EVT


def load_event_log(uu):
    wb = openpyxl.load_workbook(B.XLSX, read_only=True, data_only=True)
    it, ix = B._rows(wb["Match_Event_Log"])
    rows = defaultdict(list)
    for r in it:
        if r[ix["fixture_uuid"]] != uu:
            continue
        per = r[ix["periodId"]]
        if per not in (1, 2, 3, 4):
            continue
        clock_s = float(r[ix["Time minute"]] or 0) * 60.0 + float(r[ix["Time second"]] or 0)
        rows[int(per)].append({
            "clock_s": clock_s, "etid": r[ix["Event type ID"]],
            "etype": r[ix["Event type"]] or "", "family": r[ix["Default stoppage family"]] or "",
            "qual": r[ix["Qualifiers"]] or "", "player": r[ix["Player"]] or "",
        })
    wb.close()
    for k in rows:
        rows[k].sort(key=lambda e: e["clock_s"])
    return rows


def mmss(sec):
    return f"{int(sec//60):02d}:{int(sec%60):02d}"


def credit_window(w, allow, caps, hyd, match, per):
    """Replicate compute_owed crediting for one stitched window -> (owed_s, rule_label)."""
    D = sum(g["D"] for g in w)
    if any(g["start_evt"] in DELAY_EVT or g["end_evt"] in DELAY_EVT for g in w):
        return D, "DELAY-FULL (has Type 27/28/65 -> whole window addable)"
    tot = 0.0
    labels = []
    for g in w:
        Dg, fam = g["D"], g["family"]
        sET, eET, qids = g["start_evt"], g["end_evt"], g["end_qids"]
        mids = hyd.get((match, per), [])
        if mids and any(g["start_min_abs"] <= m <= g["end_min_abs"] for m in mids):
            tot += Dg; labels.append("hydration"); continue
        if sET in B.INJURY_EVT or eET in B.INJURY_EVT or fam in B.INJURY_FAM:
            tot += min(Dg, caps["injury"]); labels.append("injury"); continue
        if sET in B.SUB_EVT or eET in B.SUB_EVT or fam.startswith("Substitution"):
            tot += min(Dg, caps["sub"]); labels.append("sub"); continue
        if sET in B.CARD_EVT or eET in B.CARD_EVT or fam in B.CARD_FAM:
            tot += min(Dg, caps["card"]); labels.append("card"); continue
        if sET in B.CELEB_EVT or fam in B.CELEB_FAM:
            tot += min(Dg, caps["celebration"]); labels.append("celebration(full)"); continue
        rtype, a = B.resolve_restart(qids, fam, allow)
        if rtype in ("throw-in", "goal-kick", "corner", "free-kick"):
            tot += max(0.0, Dg - a); labels.append(f"{rtype} excess>{a:.0f}s"); continue
        if rtype == "keeper":
            labels.append("keeper(0)"); continue
        labels.append("excluded-silent(0)")
    return tot, "ladder: " + ", ".join(labels)


def main():
    T = B.load_workbook_tables()
    p = config.params()["incident"]
    allow = {str(k): float(v) for k, v in p["restart_normal_s"].items()}
    caps = dict(injury=p["max_injury_s"], sub=p["max_sub_s"], card=p["max_card_s"],
                celebration=p["max_celebration_s"])
    fx = next(f for f in T["fixtures"].values() if f["match"] == NAME)
    uu = fx["fixture_uuid"]
    evlog = load_event_log(uu)

    by_mp = defaultdict(list)
    for g in T["cand"]:
        if g["fixture_uuid"] == uu:
            by_mp[g["period"]].append(g)

    wins = []
    for per in (1, 2, 3, 4):
        if per not in by_mp:
            continue
        for w in B._stitch_windows(by_mp[per]):
            owed_s, rule = credit_window(w, allow, caps, T["hyd"], NAME, per)
            wins.append({"per": per, "w": w, "owed": owed_s, "rule": rule,
                         "D": sum(g["D"] for g in w),
                         "s": min(g["start_min_abs"] for g in w),
                         "e": max(g["end_min_abs"] for g in w)})
    credited = [x for x in wins if x["owed"] > 0.5]
    credited.sort(key=lambda x: -x["owed"])
    print(f"{NAME}  [{uu}]  {fx['date']}")
    print(f"  {len(wins)} stitched windows total; {len(credited)} credited (owed>0.5s)")
    print(f"  total OWED across credited = {sum(x['owed'] for x in credited)/60:.2f} min\n")
    for i, wn in enumerate(credited, 1):
        per = wn["per"]
        print(f"#{i}  P{per} {mmss(wn['s']*60)}->{mmss(wn['e']*60)}  "
              f"OWED={wn['owed']:.0f}s ({wn['owed']/60:.2f}m)  dead={wn['D']:.0f}s  | {wn['rule']}")
        lo, hi = wn["s"]*60 - 2, wn["e"]*60 + 2
        for e in evlog.get(per, []):
            if lo <= e["clock_s"] <= hi:
                hint = TYPE_HINT.get(e["etid"], "")
                print(f"     {mmss(e['clock_s'])} T{e['etid']:>3} {e['etype'][:22]:22} "
                      f"{('['+hint+']') if hint else '':44} {e['player'][:16]}")
        print()


if __name__ == "__main__":
    main()
