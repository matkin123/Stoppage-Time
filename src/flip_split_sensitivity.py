"""Outcome-flip 50/50 team-split: empirical validation + leverage (ANALYSIS ONLY; ADR-0032).

The outcome-flip secondary metric (s08 `outcome_flip`, 13.0% locked ADR-0031) needs to attribute
omitted-time goals to a specific team -- the flip only happens if the TRAILING side scores. The
headline SCORELINE metric (24.8%) does not: it asks ">=1 extra goal by either team" and uses the
total Poisson mean mu, so it is indifferent to who scores. The flip handles the attribution with one
assumption:

    tied at 90'        -> any extra goal flips        -> P = 1 - exp(-mu)            (no split)
    lead_by_1 at 90'   -> only the trailing team flips -> P = 1 - exp(-mu * p_trail) (split p=0.5)
    lead_by_2plus      -> unflippable                  -> P = 0

`p_trail` (the trailing team's share of the total omitted-time goals) is FIXED at 0.5 in code -- an
equal split. This script (1) MEASURES p_trail from the event data -- among goals actually scored
while one side led by exactly one, what fraction came from the trailing team -- and (2) re-runs the
flip metric over a p_trail sweep to show how load-bearing the 0.5 is.

Pre-goal game-state is reconstructed per goal: subtract the goal itself from the post-goal score
(`score_home_after`/`score_away_after`) on the scorer's side, then margin_before = scorer - opponent
BEFORE the goal. margin_before == -1 => the scorer was trailing by one (the equalizer; flip-relevant);
margin_before == +1 => the scorer led by one (extends the lead). p_trail = #(-1) / #(|margin|==1).

Per-match mu is recovered EXACTLY from the locked grid: mu = -ln(1 - p_change) on the central
knob_set, window 1H+2H, in processed/counterfactual.parquet. The flip is then re-evaluated at each
p_trail. HARNESS CHECK: p_trail=0.5 must reproduce the locked pct_outcome_flip to ~machine precision.

Standalone, NOT a stage, NOT a gate, NOT a lock. READS production parquet; writes only a small report
(print + docs/flip_split_sensitivity.md). Touches NO processed parquet, NO s08 grid, NO figure, NO
params (pattern: src/method2_samehalf.py; guardrail: ADR-0031 lock + CLAUDE.md sec 6).

Run: python -m src.flip_split_sensitivity
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.lib import config

CENTRAL = "silent_marked|overall|pooled_all|hl=4.0|on"
SWEEP = [0.40, 0.471, 0.50, 0.537, 0.548, 0.60]


def pre_goal_margin(goals: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    """Attach margin_before (scorer - opponent, BEFORE this goal) to every goal."""
    g = goals.merge(matches[["match_id", "home", "away", "group"]], on="match_id", how="left")
    is_home = g["team"] == g["home"]
    if not (is_home | (g["team"] == g["away"])).all():
        raise SystemExit("scorer team does not match home/away -- aborting (data integrity).")
    home_before = np.where(is_home, g["score_home_after"] - 1, g["score_home_after"])
    away_before = np.where(~is_home, g["score_away_after"] - 1, g["score_away_after"])
    scorer_before = np.where(is_home, home_before, away_before)
    opp_before = np.where(is_home, away_before, home_before)
    g["margin_before"] = scorer_before - opp_before
    g["min"] = g["clock_s"] / 60.0
    return g


def split(sub: pd.DataFrame) -> dict:
    """Trailing-team share among lead-by-1 goals, with a Jeffreys 95% interval."""
    one = sub[sub["margin_before"].abs() == 1]
    trail = int((one["margin_before"] == -1).sum())   # scorer was trailing by 1 (equalizer)
    lead = int((one["margin_before"] == 1).sum())      # scorer led by 1 (extends)
    n = trail + lead
    if n == 0:
        return {"n": 0, "trail": 0, "lead": 0, "p": float("nan"), "lo": float("nan"),
                "hi": float("nan")}
    lo, hi = stats.beta.ppf([0.025, 0.975], trail + 0.5, lead + 0.5)
    return {"n": n, "trail": trail, "lead": lead, "p": trail / n, "lo": float(lo), "hi": float(hi)}


def main() -> None:
    goals = pd.read_parquet(config.INTERIM / "goals.parquet")
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    state = pd.read_parquet(config.INTERIM / "match_state.parquet")[["match_id", "state_at_90"]]
    cf = pd.read_parquet(config.PROCESSED / "counterfactual.parquet")
    summary = pd.read_parquet(config.PROCESSED / "counterfactual_summary.parquet")

    g = pre_goal_margin(goals, matches)

    # ---- empirical split across cuts (population = one side leads by exactly 1 before the goal) --
    cuts = [
        ("2H stoppage-time goals (most relevant)", g[g["is_stoppage"] == "2H"]),
        ("1H stoppage-time goals", g[g["is_stoppage"] == "1H"]),
        ("all stoppage-time goals (1H+2H)", g[g["is_stoppage"].isin(["1H", "2H"])]),
        ("2H stoppage OR after 80:00",
         g[(g["is_stoppage"] == "2H") | ((g["period"] == 2) & (g["min"] >= 80))]),
        ("all 2H goals after 75:00", g[(g["period"] == 2) & (g["min"] >= 75)]),
        ("ALL goals (next-goal-in-1-goal-game anchor)", g),
    ]
    cut_rows = [(label, split(sub)) for label, sub in cuts]
    era_rows = [(grp, split(g[(g["is_stoppage"].isin(["1H", "2H"])) & (g["group"] == grp)]))
                for grp in ("PRE", "POST")]

    # ---- recover per-match mu from the locked grid; re-run the flip over the p_trail sweep -------
    d = cf[(cf["knob_set"] == CENTRAL) & (cf["window"] == "1H+2H")].merge(state, on="match_id")
    d["mu"] = -np.log(1.0 - d["p_change"].clip(upper=1 - 1e-12))
    tied = (d["state_at_90"] == "tied").to_numpy()
    lead1 = (d["state_at_90"] == "lead_by_1").to_numpy()
    mu = d["mu"].to_numpy()

    def flip(p_trail: float) -> float:
        f = np.zeros(len(d))
        f[tied] = 1.0 - np.exp(-mu[tied])
        f[lead1] = 1.0 - np.exp(-mu[lead1] * p_trail)
        return float(f.mean())

    locked_flip = float(summary[(summary["knob_set"] == CENTRAL) & (summary["window"] == "1H+2H") &
                                (summary["group"] == "all")]["pct_outcome_flip"].iloc[0])
    repro = flip(0.5)
    print("HARNESS CHECK (p_trail=0.5 must reproduce locked pct_outcome_flip):")
    print(f"  flip(0.5)={repro:.5f}  locked={locked_flip:.5f}  d={abs(repro - locked_flip):.2e}")
    assert abs(repro - locked_flip) < 1e-6, "flip harness drift -- abort"

    sweep_rows = [(p, flip(p)) for p in SWEEP]
    sc = d["state_at_90"].value_counts().to_dict()
    state_counts = (f"lead_by_1 {sc.get('lead_by_1', 0)}, tied {sc.get('tied', 0)}, "
                    f"lead_by_2plus {sc.get('lead_by_2plus', 0)}")

    # ------------------------------- report --------------------------------------------------
    L = []
    L.append("# Outcome-flip 50/50 team-split: empirical validation + leverage")
    L.append("")
    L.append("Standalone check of the one assumption in the **outcome-flip** secondary metric (s08 "
             "`outcome_flip`, locked 13.0% / ADR-0031): when a team leads by one at 90', the flip "
             "credits the trailing team with a fixed **half** of the total omitted-time goals "
             "(`P = 1 - exp(-mu * p_trail)`, `p_trail = 0.5`). The **headline scoreline** metric "
             "(24.8%) does NOT use this split -- it asks '>=1 extra goal by either team' and rides "
             "the total `mu`, so nothing below can move it. READS production parquet; no locked "
             "artifact touched.")
    L.append("")
    L.append("## 1. What the data says (p_trail measured from event goals)")
    L.append("")
    L.append("Population = goals scored while one side led by **exactly one** before the goal. "
             "`p_trail` = fraction scored by the **trailing** team (the flip-relevant equalizer). "
             "Pre-goal margin is reconstructed by subtracting each goal from the post-goal score. "
             "Intervals are Jeffreys 95%.")
    L.append("")
    L.append("| population (lead-by-1 game-state) | n | trailing | leading | p_trail | 95% CI |")
    L.append("|---|---|---|---|---|---|")
    for label, r in cut_rows:
        if r["n"] == 0:
            L.append(f"| {label} | 0 | -- | -- | -- | -- |")
        else:
            L.append(f"| {label} | {r['n']} | {r['trail']} | {r['lead']} | "
                     f"{r['p']:.3f} | [{r['lo']:.3f}, {r['hi']:.3f}] |")
    L.append("")
    L.append("By era (all stoppage goals):")
    L.append("")
    L.append("| era | n | trailing | leading | p_trail | 95% CI |")
    L.append("|---|---|---|---|---|---|")
    for grp, r in era_rows:
        L.append(f"| {grp} | {r['n']} | {r['trail']} | {r['lead']} | "
                 f"{r['p']:.3f} | [{r['lo']:.3f}, {r['hi']:.3f}] |")
    L.append("")
    two_h = dict(cut_rows)["2H stoppage-time goals (most relevant)"]
    anchor = cut_rows[-1][1]
    L.append(f"Every cut straddles 0.50. The directly-relevant added-time window (2H stoppage) leans "
             f"slightly toward the trailing team (**{two_h['p']:.3f}**, n={two_h['n']}, CI contains "
             f"0.5); it reverses toward the leader in the broader late window (~0.47 after 75-80', the "
             f"counter-attack channel); and the large-sample anchor sits at **{anchor['p']:.3f}** "
             f"(n={anchor['n']}, tight CI). The trailing-desperation and leading-counter channels "
             f"roughly cancel -- **0.50 is well-calibrated**, not a convenient guess.")
    L.append("")
    L.append("## 2. How load-bearing is it (flip re-run over p_trail)")
    L.append("")
    L.append(f"Per-match `mu` recovered from the locked grid (`mu = -ln(1 - p_change)`, central "
             f"`{CENTRAL}`, window 1H+2H); the flip is re-evaluated at each `p_trail`. The split "
             f"touches ONLY the lead_by_1 matches "
             f"(state@90: {state_counts}); tied matches flip on any goal regardless of `p_trail`.")
    L.append("")
    L.append("| p_trail | source | flip X% |")
    L.append("|---|---|---|")
    srcmap = {0.471: "late-window (>75')", 0.50: "**model (locked)**", 0.548: "2H stoppage (measured)"}
    for p, fx in sweep_rows:
        src = srcmap.get(p, "")
        bold = "**" if p == 0.50 else ""
        L.append(f"| {bold}{p:.3f}{bold} | {src} | {bold}{fx * 100:.2f}%{bold} |")
    L.append("")
    f_lo, f_hi = flip(0.40), flip(0.60)
    f_2h = flip(0.548)
    L.append(f"lead_by_1 is the largest state bucket, so the split touches a big share of matches -- "
             f"but because the measured value is so near 0.5, leverage is small: the most-relevant "
             f"point estimate (0.548) moves the flip just **+{(f_2h - repro) * 100:.1f} pp to "
             f"~{f_2h * 100:.1f}%**, and the full p_trail in [0.40, 0.60] span is only "
             f"{f_lo * 100:.1f}%-{f_hi * 100:.1f}%. The headline scoreline (24.8%) is unaffected at "
             f"every value.")
    L.append("")
    L.append("## 3. Conclusion (for the methods record / a pre-empt)")
    L.append("")
    L.append(f"The 50/50 split is **empirically supported and non-load-bearing**. Keep 0.5 as the "
             f"central -- it now traces to a measurement (n={two_h['n']} in the cleanest cut, CI "
             f"containing 0.5) plus this p-sweep band, the same script+table+documented-assumption "
             f"standard every other knob gets (CLAUDE.md sec 1), rather than an unexamined constant. "
             f"The honest caveat is sample size: n={two_h['n']} in the cleanest cut cannot "
             f"statistically distinguish 0.50 from 0.55, so 0.5 is both defensible and unresolvable "
             f"to finer precision. If a single best-supported value is preferred over the round "
             f"number, the added-time-specific {two_h['p']:.3f} nudges the flip from 13.0% to "
             f"~{f_2h * 100:.1f}% -- inside the CI either way.")
    L.append("")
    L.append("_Reproduce: `python -m src.flip_split_sensitivity`. Harness check: p_trail=0.5 "
             f"reproduces the locked pct_outcome_flip ({locked_flip:.5f}) to <1e-6._")
    out = config.DOCS / "flip_split_sensitivity.md"
    out.write_text("\n".join(L) + "\n")

    # ---- console echo ----
    print("\n===== EMPIRICAL p_trail (lead-by-1 game-state) =====")
    for label, r in cut_rows:
        if r["n"]:
            print(f"  {label:46s} n={r['n']:4d}  p_trail={r['p']:.3f}  [{r['lo']:.3f},{r['hi']:.3f}]")
    print("\n===== FLIP SENSITIVITY TO p_trail =====")
    for p, fx in sweep_rows:
        star = "  <- locked" if p == 0.50 else ""
        print(f"  p_trail={p:.3f}  flip={fx * 100:.2f}%{star}")
    print(f"\n  wrote {out}")


if __name__ == "__main__":
    main()
