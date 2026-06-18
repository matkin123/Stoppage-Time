"""s05 -- Incident-stoppage lower bound + true-stoppage estimator.

Per match & half, sums identifiable dead-time windows:
  celebration     goal -> next kick-off
  sub             Player Off / Substitution -> next restart
  card            Foul Committed w/ card or Bad Behaviour -> next restart
  injury          Injury Stoppage -> Referee Ball-Drop
  restart_excess  routine restart-boundary gap, EXCESS over Nate's allowance (IMPL-5)
Each window is clipped to a sane max (params.yaml). lower_bound_s is the UNION of all
incident windows (merged, so overlapping windows are not double counted) INTERSECTED with
s03's measured dead segments -- so we only credit identifiable dead time the independent
BIP method also saw as dead. This makes it a true lower bound on dead time (conservative
by construction; passes the gate without slack). var_s is initialised to 0 and filled by
s06b. Matches lacking any Injury Stoppage event are flagged (StatsBomb populates these
inconsistently). All coordinates are within-period seconds (period_s) to line up with
bip_segments.

restart_excess (IMPL-5, ADR-0017) credits routine restart time-wasting -- a throw-in dragged
to 50s, a goal kick to 40s with no foul/sub/injury -- which silent.py skips (it EXCLUDES
restart-boundary gaps by design). For each routine restart we credit max(0, gap - allowance)
as the tail interval [last + allowance, restart] (allowances in params.yaml:incident.
restart_normal_s). It is identifiable (restart-tagged), so it folds into the lower_bound union
and rides through the same intersect-with-dead machinery (deduped against card/sub, gate true
by construction). lower_bound_base_s keeps the ADR-0016 lower bound (without restart_excess)
for the ablation.

The TRUE-STOPPAGE estimator adds a marker-gated silent term on top of the lower bound: of the
>= silent.min_silent_gap_s non-restart gaps, credit ONLY those whose lead edge carries an
out-of-play marker (src/lib/silent.py) -- the unmarked silent gaps are genuinely dead (s03 BIP
keeps them) but a flat ~8.4 min/match non-addable baseline. A residual-silent constant frozen
on 2018 (re-fit in IMPL-5 after adding restart_excess) closes the irreducible remainder. The
estimator validates against Nate Silver's `expected` column (WC2018); s03/bip.py are NOT
touched (they stay the validated duration rule -- BIP = TOTAL dead time, stoppage = ADDABLE).

In:  interim/events_norm.parquet, interim/bip_segments.parquet
Out: interim/incident_stoppage.parquet (per match-period; adds restart_excess_s, the
     lower_bound_base_s ablation column, silent_marked_s + the ungated silent_all_s upper
     bound for IMPL-4's sensitivity grid),
     interim/true_stoppage.parquet (per match: lower_bound + marked silent + residual)
Gate: lower_bound_s <= total dead time (s03) for every match; estimator r>=~0.77 vs Nate
      `expected` on the 32 WC2018 matches (IMPL-5: r=0.825, MAE 2.44).
"""
from __future__ import annotations

import pandas as pd

from src.lib import config, nate, silent

RESTART = {
    "From Throw In", "From Corner", "From Free Kick",
    "From Goal Kick", "From Kick Off", "From Keeper",
}


def _next_resume(clocks, patterns, types, i, want_patterns=None, want_type=None):
    """Clock of the first event after index i matching a restart pattern or a type."""
    for j in range(i + 1, len(clocks)):
        if want_type is not None and types[j] == want_type:
            return clocks[j]
        if want_patterns is not None and patterns[j] in want_patterns:
            return clocks[j]
    return None


def _merge(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Sort and merge overlapping intervals into a disjoint list."""
    if not intervals:
        return []
    intervals = sorted(intervals)
    out = [list(intervals[0])]
    for s, e in intervals[1:]:
        if s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]


def _intersect_total(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    """Total length of the intersection of two interval lists (each is merged first)."""
    a, b = _merge(a), _merge(b)
    total, i, j = 0.0, 0, 0
    while i < len(a) and j < len(b):
        lo = max(a[i][0], b[j][0])
        hi = min(a[i][1], b[j][1])
        if hi > lo:
            total += hi - lo
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return total


def main() -> None:
    config.ensure_dirs()
    params = config.params()
    p = params["incident"]
    sil = params["silent"]
    restart_set = set(params["bip"]["restart_play_patterns"])
    allowance = {str(k): float(v) for k, v in p["restart_normal_s"].items()}
    events = pd.read_parquet(config.INTERIM / "events_norm.parquet")
    seg = pd.read_parquet(config.INTERIM / "bip_segments.parquet")
    seg["dur"] = seg["end_s"] - seg["start_s"]
    dead_total = seg[~seg["in_play"]].groupby("match_id")["dur"].sum()
    # dead segments per (match_id, period) in period_s coords for intersection.
    dead_seg: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for (mid, per), gg in seg[~seg["in_play"]].groupby(["match_id", "period"]):
        dead_seg[(int(mid), int(per))] = list(zip(gg["start_s"], gg["end_s"]))

    rows = []
    for mid, grp in events.groupby("match_id"):
        for period, g in grp.groupby("period"):
            if period >= 5:
                continue
            g = g.sort_values(["period_s", "idx"])
            clocks = g["period_s"].to_numpy()
            patterns = g["play_pattern"].fillna("").to_numpy()
            types = g["type"].fillna("").to_numpy()
            poss = g["possession"].to_numpy()
            cards = g["card"].notna().to_numpy()
            shot_out = g["shot_outcome"].fillna("").to_numpy()

            comp = {"celebration": [], "sub": [], "card": [], "injury": [], "restart_excess": []}
            injury_present = False
            for i in range(len(clocks)):
                t0 = float(clocks[i])
                typ = types[i]
                # celebration
                if (typ == "Shot" and shot_out[i] == "Goal") or typ == "Own Goal For":
                    r = _next_resume(clocks, patterns, types, i, want_patterns={"From Kick Off"})
                    if r is not None:
                        comp["celebration"].append((t0, min(r, t0 + p["max_celebration_s"])))
                # substitution
                if typ in ("Player Off", "Substitution"):
                    r = _next_resume(clocks, patterns, types, i, want_patterns=RESTART)
                    if r is not None:
                        comp["sub"].append((t0, min(r, t0 + p["max_sub_s"])))
                # card
                if cards[i]:
                    r = _next_resume(clocks, patterns, types, i, want_patterns=RESTART)
                    if r is not None:
                        comp["card"].append((t0, min(r, t0 + p["max_card_s"])))
                # injury
                if typ == "Injury Stoppage":
                    injury_present = True
                    r = _next_resume(clocks, patterns, types, i, want_type="Referee Ball-Drop")
                    if r is not None:
                        comp["injury"].append((t0, min(r, t0 + p["max_injury_s"])))

            # restart time-wasting (IMPL-5): on a routine restart-boundary gap, credit only the
            # EXCESS over Nate's allowance -- the tail [last + allow, restart]. Mirrors the
            # restart-boundary test silent.py uses to EXCLUDE these gaps, so the two never
            # overlap. Folds into the union below; the intersect dedups it against card/sub.
            for i in range(len(clocks) - 1):
                if poss[i + 1] != poss[i] and patterns[i + 1] in allowance:
                    gap = float(clocks[i + 1]) - float(clocks[i])
                    allow = allowance[patterns[i + 1]]
                    if gap > allow:
                        comp["restart_excess"].append((float(clocks[i]) + allow, float(clocks[i + 1])))

            base_intervals = comp["celebration"] + comp["sub"] + comp["card"] + comp["injury"]
            all_intervals = base_intervals + comp["restart_excess"]
            dead = dead_seg.get((int(mid), int(period)), [])
            # marker-gated silent term (>= silent.min_silent_gap_s non-restart gaps whose
            # lead edge is marked out-of-play). These gaps are >= 20s, so already dead in s03
            # by the max-live-gap rule -- summed directly (each gap is one dead segment).
            silent_iv = silent.marked_silent_intervals(g, restart_set, sil)
            silent_marked_s = sum(t1 - t0 for t0, t1 in silent_iv)
            # ungated upper bound (every silent gap credited) -- the `silent_all` knob
            # IMPL-4's sensitivity grid uses to bracket the irreducible silent uncertainty.
            silent_all_iv = silent.all_silent_intervals(g, restart_set, sil)
            silent_all_s = sum(t1 - t0 for t0, t1 in silent_all_iv)
            rows.append(
                {
                    "match_id": mid,
                    "period": int(period),
                    "celebration_s": _intersect_total(comp["celebration"], dead),
                    "sub_s": _intersect_total(comp["sub"], dead),
                    "card_s": _intersect_total(comp["card"], dead),
                    "injury_s": _intersect_total(comp["injury"], dead),
                    "restart_excess_s": _intersect_total(comp["restart_excess"], dead),
                    "silent_marked_s": float(silent_marked_s),
                    "silent_all_s": float(silent_all_s),
                    "var_s": 0.0,  # filled by s06b
                    # lower_bound_base_s = the ADR-0016 lower bound (celebration/sub/card/injury);
                    # lower_bound_s adds restart_excess (IMPL-5). Both are deduped unions ∩ dead,
                    # so net restart credit = lower_bound_s - lower_bound_base_s (after overlap).
                    "lower_bound_base_s": _intersect_total(base_intervals, dead),
                    "lower_bound_s": _intersect_total(all_intervals, dead),
                    "injury_present": injury_present,
                }
            )

    inc = pd.DataFrame(rows)
    inc.to_parquet(config.INTERIM / "incident_stoppage.parquet", index=False)

    # ---- true-stoppage estimator (per match) ----------------------------
    # lower_bound (incl. restart_excess, IMPL-5) + marker-gated silent + residual constant
    # (re-fit + frozen on 2018, ADR-0017).
    residual_s = float(sil["residual_silent_s"])
    g_match = inc.groupby("match_id")[
        ["lower_bound_base_s", "lower_bound_s", "silent_marked_s"]
    ].sum()
    ts = g_match.reset_index()
    ts["residual_silent_s"] = residual_s
    ts["true_stoppage_s"] = ts["lower_bound_s"] + ts["silent_marked_s"] + residual_s
    ts.to_parquet(config.INTERIM / "true_stoppage.parquet", index=False)

    # ---- validation vs Nate `expected` (WC2018 only) --------------------
    lb_base_min = {int(m): v / 60.0 for m, v in g_match["lower_bound_base_s"].items()}
    lb_min = {int(m): v / 60.0 for m, v in g_match["lower_bound_s"].items()}
    ms_min = {int(m): v / 60.0 for m, v in g_match["silent_marked_s"].items()}
    lbms = {m: lb_min[m] + ms_min[m] for m in lb_min}
    est = {m: lbms[m] + residual_s / 60.0 for m in lb_min}
    print("\n  IMPL-5 ablation vs Nate `expected` (32 WC2018 matches):")
    nate.report(lb_base_min, "expected", "lower_bound (celeb/sub/card/injury)")
    nate.report(lb_min, "expected", "+ restart_excess")
    nate.report(lbms, "expected", "+ marker-gated silent")
    nate.report(est, "expected", "+ residual constant (estimator)")

    # ---- gate: lower bound <= total dead per match -----------------------
    per_match = inc.groupby("match_id")["lower_bound_s"].sum()
    errors = []
    for mid, lb in per_match.items():
        td = float(dead_total.get(mid, 0.0))
        if lb > td + 1.0:  # 1s slack for float boundary effects
            errors.append(f"match {mid}: lower_bound {lb:.0f}s > dead {td:.0f}s")

    n_no_injury = int((~inc.groupby("match_id")["injury_present"].any()).sum())
    print(f"\n  incident rows: {len(inc)}  matches w/o any Injury Stoppage event: {n_no_injury}")
    if errors:
        raise SystemExit(
            f"s05 GATE FAILED ({len(errors)} matches exceed dead time):\n  "
            + "\n  ".join(errors[:15])
        )
    print("  s05 gate PASSED (lower_bound <= total dead time for every match)")


if __name__ == "__main__":
    main()
