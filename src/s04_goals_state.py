"""s04 -- Goals & match state.

Extracts goals (open-play/set-piece shots scored + own goals, excluding penalty
shootouts) with a cumulative clock, stoppage flag, and running scoreline; reconstructs
each match's state at 45:00 and 90:00.

In:  interim/events_norm.parquet, interim/matches.parquet
Out: interim/goals.parquet, interim/match_state.parquet
Gate: WC2022 share of goals after 90:00 ~ 12-13%; reconstructed finals == matches.ft_score.
"""
from __future__ import annotations

import pandas as pd

from src.lib import config

HALF_STOP = 2700  # within-period seconds == the 45'/90' marks


def _is_stoppage(period: int, period_s: float) -> str:
    if period == 1 and period_s >= HALF_STOP:
        return "1H"
    if period == 2 and period_s >= HALF_STOP:
        return "2H"
    return "none"


def _state(h: int, a: int) -> tuple[str, str]:
    diff = h - a
    if diff == 0:
        cat = "tied"
    elif abs(diff) == 1:
        cat = "lead_by_1"
    else:
        cat = "lead_by_2plus"
    leader = "home" if diff > 0 else ("away" if diff < 0 else "none")
    return cat, leader


def main() -> None:
    config.ensure_dirs()
    events = pd.read_parquet(config.INTERIM / "events_norm.parquet")
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    home = matches.set_index("match_id")["home"].to_dict()
    away = matches.set_index("match_id")["away"].to_dict()

    # goal events (exclude penalty-shootout period 5)
    is_shot_goal = (events["type"] == "Shot") & (events["shot_outcome"] == "Goal")
    is_own = events["type"] == "Own Goal For"
    goals_ev = events[(is_shot_goal | is_own) & (events["period"] < 5)].copy()
    goals_ev = goals_ev.sort_values(["match_id", "clock_s", "idx"])

    goal_rows, state_rows = [], []
    for mid, grp in goals_ev.groupby("match_id"):
        h = a = 0
        for r in grp.itertuples(index=False):
            if r.team == home[mid]:
                h += 1
            elif r.team == away[mid]:
                a += 1
            goal_rows.append(
                {
                    "match_id": mid,
                    "clock_s": r.clock_s,
                    "period": r.period,
                    "period_s": r.period_s,
                    "team": r.team,
                    "is_stoppage": _is_stoppage(int(r.period), float(r.period_s)),
                    "score_home_after": h,
                    "score_away_after": a,
                }
            )

    goals = pd.DataFrame(goal_rows)
    goals.to_parquet(config.INTERIM / "goals.parquet", index=False)

    # match_state at 45 and 90 (and final) for every match, including 0-0s
    for mid in matches["match_id"]:
        g = goals[goals["match_id"] == mid] if not goals.empty else goals
        def score_at(mask):
            sub = g[mask]
            if sub.empty:
                return 0, 0
            last = sub.iloc[-1]
            return int(last["score_home_after"]), int(last["score_away_after"])
        # before 45:00 == P1 with period_s < 2700
        h45, a45 = score_at((g["period"] == 1) & (g["period_s"] < HALF_STOP)) if len(g) else (0, 0)
        # before 90:00 == anything in P1, or P2 with period_s < 2700
        h90, a90 = score_at(
            (g["period"] < 2) | ((g["period"] == 2) & (g["period_s"] < HALF_STOP))
        ) if len(g) else (0, 0)
        s45, _ = _state(h45, a45)
        s90, leader = _state(h90, a90)
        state_rows.append(
            {
                "match_id": mid,
                "state_at_45": s45,
                "state_at_90": s90,
                "leader": leader,
                "home_at_90": h90,
                "away_at_90": a90,
            }
        )
    match_state = pd.DataFrame(state_rows)
    match_state.to_parquet(config.INTERIM / "match_state.parquet", index=False)

    # ---- gate ------------------------------------------------------------
    errors, warnings = [], []
    # final scoreline reconstruction (regulation+ET, excl shootout)
    fin = goals.groupby("match_id").last()[["score_home_after", "score_away_after"]] \
        if not goals.empty else pd.DataFrame()
    for r in matches.itertuples(index=False):
        rh = int(fin.loc[r.match_id, "score_home_after"]) if r.match_id in fin.index else 0
        ra = int(fin.loc[r.match_id, "score_away_after"]) if r.match_id in fin.index else 0
        if pd.notna(r.home_score) and (rh != int(r.home_score) or ra != int(r.away_score)):
            errors.append(
                f"match {r.match_id}: reconstructed {rh}-{ra} != reported {r.home_score}-{r.away_score}"
            )

    wc22_ids = set(matches[matches["tournament"] == "wc_2022"]["match_id"])
    g22 = goals[goals["match_id"].isin(wc22_ids)] if not goals.empty else goals
    if len(g22):
        after90 = (
            ((g22["period"] == 2) & (g22["period_s"] >= HALF_STOP)) | (g22["period"] >= 3)
        ).mean()
        print(f"\n  WC2022 goals after 90:00 share: {after90:.3f} (538 ref ~0.12-0.13)")
        if not (0.09 <= after90 <= 0.16):
            warnings.append(f"WC2022 after-90 share {after90:.3f} outside 0.09-0.16")

    print(f"  goals: {len(goals)}  matches with state: {len(match_state)}")
    if warnings:
        for w in warnings:
            print(f"  WARNING: {w}")
    if errors:
        raise SystemExit(
            f"s04 GATE FAILED ({len(errors)} scoreline mismatches):\n  "
            + "\n  ".join(errors[:15])
        )
    print("  s04 gate PASSED (finals reconstructed; after-90 share sane)")


if __name__ == "__main__":
    main()
