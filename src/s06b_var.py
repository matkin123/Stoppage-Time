"""s06b -- VAR review log (fallback estimator).

VAR is only needed for the s05 *attribution* -- for s03 ball-in-play and all
productivity it is already captured as dead time automatically (the "stoppage within
stoppage" effect, in our favour). So this stage just fills the var_s column.

Primary source would be scraped ESPN/Sofascore commentary "VAR review" events with a
clock. That is brittle and is left as a documented manual path. The implemented path is
the spec's FALLBACK: flag decision events (goals, red / second-yellow cards) and
attribute the EXCESS of the surrounding dead gap over a no-VAR baseline (the tournament
median goal-celebration gap) to review time.

Limitation: penalty awards and overturned offsides need nested fields not carried in
events_norm; they are omitted from the fallback (documented in decisions.md), so var_s
here is itself a lower bound on review time.

In:  interim/events_norm.parquet, interim/incident_stoppage.parquet, interim/matches.parquet
Out: (updated) interim/incident_stoppage.parquet  (var_s column populated)
Gate: var_s >= 0 for every row; var_s reported per tournament.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.lib import config

RESTART = {
    "From Throw In", "From Corner", "From Free Kick",
    "From Goal Kick", "From Kick Off", "From Keeper",
}
DECISION_CARDS = {"Red Card", "Second Yellow"}


def _gap_to_restart(clocks, patterns, i) -> float | None:
    for j in range(i + 1, len(clocks)):
        if patterns[j] in RESTART:
            return float(clocks[j]) - float(clocks[i])
    return None


def main() -> None:
    config.ensure_dirs()
    events = pd.read_parquet(config.INTERIM / "events_norm.parquet")
    inc = pd.read_parquet(config.INTERIM / "incident_stoppage.parquet")
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    tourn = matches.set_index("match_id")["tournament"].to_dict()

    # per-tournament baseline = median goal->kickoff gap
    goal_gaps: dict[str, list[float]] = {}
    for mid, g in events.groupby("match_id"):
        g = g.sort_values(["period", "clock_s", "idx"])
        clocks = g["clock_s"].to_numpy()
        patterns = g["play_pattern"].fillna("").to_numpy()
        types = g["type"].fillna("").to_numpy()
        shot_out = g["shot_outcome"].fillna("").to_numpy()
        t = tourn.get(mid)
        for i in range(len(clocks)):
            if (types[i] == "Shot" and shot_out[i] == "Goal") or types[i] == "Own Goal For":
                for j in range(i + 1, len(clocks)):
                    if patterns[j] == "From Kick Off":
                        goal_gaps.setdefault(t, []).append(float(clocks[j]) - float(clocks[i]))
                        break
    baseline = {t: float(np.median(v)) for t, v in goal_gaps.items() if v}
    print("  per-tournament baseline goal-celebration gap (s):")
    for t, b in baseline.items():
        print(f"    {t:<20} {b:.1f}")

    var_by_key: dict[tuple[int, int], float] = {}
    for mid, g in events.groupby("match_id"):
        base = baseline.get(tourn.get(mid), 0.0)
        for period, gp in g.groupby("period"):
            if period >= 5:
                continue
            gp = gp.sort_values(["clock_s", "idx"])
            clocks = gp["clock_s"].to_numpy()
            patterns = gp["play_pattern"].fillna("").to_numpy()
            types = gp["type"].fillna("").to_numpy()
            shot_out = gp["shot_outcome"].fillna("").to_numpy()
            cards = gp["card"].fillna("").to_numpy()
            total = 0.0
            for i in range(len(clocks)):
                is_goal = (types[i] == "Shot" and shot_out[i] == "Goal") or types[i] == "Own Goal For"
                is_card = cards[i] in DECISION_CARDS
                if not (is_goal or is_card):
                    continue
                gap = _gap_to_restart(clocks, patterns, i)
                if gap is not None and gap > base:
                    total += gap - base
            var_by_key[(int(mid), int(period))] = total

    inc["var_s"] = [
        var_by_key.get((int(r.match_id), int(r.period)), 0.0) for r in inc.itertuples(index=False)
    ]
    inc.to_parquet(config.INTERIM / "incident_stoppage.parquet", index=False)

    by_t = (
        inc.assign(tournament=inc["match_id"].map(tourn))
        .groupby("tournament")["var_s"]
        .sum()
        / 60
    )
    print("\n  attributed VAR-excess minutes per tournament (fallback, lower bound):")
    for t, m in by_t.items():
        print(f"    {t:<20} {m:.1f} min")
    if (inc["var_s"] < 0).any():
        raise SystemExit("s06b GATE FAILED: negative var_s")
    print("  s06b gate PASSED (var_s populated, non-negative)")


if __name__ == "__main__":
    main()
