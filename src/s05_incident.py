"""s05 -- Incident-stoppage lower bound.

Per match & half, sums identifiable dead-time windows:
  celebration  goal -> next kick-off
  sub          Player Off / Substitution -> next restart
  card         Foul Committed w/ card or Bad Behaviour -> next restart
  injury       Injury Stoppage -> Referee Ball-Drop
Each window is clipped to a sane max (params.yaml). lower_bound_s is the UNION of all
incident windows (merged, so overlapping windows are not double counted) INTERSECTED with
s03's measured dead segments -- so we only credit identifiable dead time the independent
BIP method also saw as dead. This makes it a true lower bound on dead time (conservative
by construction; passes the gate without slack). var_s is initialised to 0 and filled by
s06b. Matches lacking any Injury Stoppage event are flagged (StatsBomb populates these
inconsistently). All coordinates are within-period seconds (period_s) to line up with
bip_segments.

In:  interim/events_norm.parquet, interim/bip_segments.parquet
Out: interim/incident_stoppage.parquet
Gate: lower_bound_s <= total dead time (s03) for every match.
"""
from __future__ import annotations

import pandas as pd

from src.lib import config

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
    p = config.params()["incident"]
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
            cards = g["card"].notna().to_numpy()
            shot_out = g["shot_outcome"].fillna("").to_numpy()

            comp = {"celebration": [], "sub": [], "card": [], "injury": []}
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

            all_intervals = sum(comp.values(), [])
            dead = dead_seg.get((int(mid), int(period)), [])
            rows.append(
                {
                    "match_id": mid,
                    "period": int(period),
                    "celebration_s": _intersect_total(comp["celebration"], dead),
                    "sub_s": _intersect_total(comp["sub"], dead),
                    "card_s": _intersect_total(comp["card"], dead),
                    "injury_s": _intersect_total(comp["injury"], dead),
                    "var_s": 0.0,  # filled by s06b
                    "lower_bound_s": _intersect_total(all_intervals, dead),
                    "injury_present": injury_present,
                }
            )

    inc = pd.DataFrame(rows)
    inc.to_parquet(config.INTERIM / "incident_stoppage.parquet", index=False)

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
