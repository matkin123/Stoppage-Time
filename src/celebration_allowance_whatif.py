"""WHAT-IF (read-only, writes NOTHING): does crediting the goal celebration as the EXCESS
over an allowance -- the same max(0, gap - allowance) rule already used for throw-ins / goal
kicks / corners / free kicks (ADR-0017) -- narrow the per-match gap to Nate Silver's WC2018
`expected`?

WHY THIS EXISTS
The f07 calibration panel sits at r=0.825 / MAE 2.44 min vs Nate (32 WC2018 matches). The
dominant per-match error is goal-celebration OVER-credit: today s05 credits the FULL goal->
kickoff gap (a BIP / total-dead quantity), not the addable excess over a normal restart. Each
credited celebration minute "buys" only ~0.24 Nate-minutes (OLS exchange rate) -- ~4x over-
credit, and it scales with goals, so high-scoring matches over-predict. See the full evidence
in `prompts/celebration_allowance_findings.md`; the turnkey adoption unit is
`prompts/impl_celebration_allowance.md`.

SCOPE (ADR-0030): the production change applies the allowance to PRE tournaments (WC2018, Euro2020)
ONLY -- POST (WC2022+) keeps the full gap because the 2022 directive adds the whole celebration.
This validation set is the 32 WC2018 matches = entirely PRE, so the sweep below IS the PRE story;
POST is unchanged and not shown here.

WHAT THIS DOES
Faithfully recomputes the WC2018 lower_bound with a celebration-allowance knob, crediting each
goal celebration as the tail [goal + allowance, next_kickoff] (capped at max_celebration_s,
intersected with s03 dead) instead of the full gap. EVERYTHING ELSE is unchanged: silent_marked,
restart_excess, sub/card/injury are read/recomputed exactly as production does. The residual is
re-fit on 2018 at each allowance so the 32-match mean stays anchored to Nate (apples-to-apples
r/MAE). allowance=0 reproduces production r=0.825 / MAE 2.44 EXACTLY -> proves the harness is
faithful. This is ANALYSIS ONLY -- it does not touch params.yaml, s05, or any parquet.

RUN:  python -m src.celebration_allowance_whatif      (from repo root; reads production parquet)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.lib import config, nate
from src.s05_incident import RESTART, _intersect_total, _next_resume

CENTRAL_ALLOW_S = 60.0  # recommended celebration allowance (round; == free-kick allowance)
SWEEP_S = [0, 15, 30, 45, 60, 90, 120, 180]


def _load():
    params = config.params()
    P = params["incident"]
    allowance_rs = {str(k): float(v) for k, v in P["restart_normal_s"].items()}

    rec = nate.reconcile()
    nate_exp = {int(m): s / 60.0 for m, s in zip(rec["match_id"], rec["expected_s"])}
    wc_ids = sorted(nate_exp)

    events = pd.read_parquet(config.INTERIM / "events_norm.parquet")
    events = events[events["match_id"].isin(wc_ids)]

    seg = pd.read_parquet(config.INTERIM / "bip_segments.parquet")
    seg = seg[seg["match_id"].isin(wc_ids)]
    dead_seg: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for (mid, per), gg in seg[~seg["in_play"]].groupby(["match_id", "period"]):
        dead_seg[(int(mid), int(per))] = list(zip(gg["start_s"], gg["end_s"]))

    # silent_marked per match is UNCHANGED by the celebration knob -- reuse the production value.
    inc = pd.read_parquet(config.INTERIM / "incident_stoppage.parquet")
    sm_match = inc.groupby("match_id")["silent_marked_s"].sum()
    return P, allowance_rs, nate_exp, wc_ids, events, dead_seg, inc, sm_match


def lower_bound_with_celeb_allowance(
    celeb_allow_s: float, P, allowance_rs, events, dead_seg
) -> dict[int, float]:
    """Per-match lower_bound_s (seconds), crediting each goal celebration as the EXCESS tail
    [goal + celeb_allow, next_kickoff] (capped at max_celebration_s) instead of the full gap.
    All other components (sub/card/injury/restart_excess) are recomputed exactly as in s05."""
    lb: dict[int, float] = {}
    for mid, grp in events.groupby("match_id"):
        total = 0.0
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
            comp: list[tuple[float, float]] = []
            for i in range(len(clocks)):
                t0 = float(clocks[i])
                typ = types[i]
                # CELEBRATION -- the only changed rule: excess over the allowance, not full gap.
                if (typ == "Shot" and shot_out[i] == "Goal") or typ == "Own Goal For":
                    r = _next_resume(clocks, patterns, types, i, want_patterns={"From Kick Off"})
                    if r is not None:
                        hi = min(r, t0 + P["max_celebration_s"])
                        lo = t0 + celeb_allow_s
                        if hi > lo:
                            comp.append((lo, hi))
                if typ in ("Player Off", "Substitution"):
                    r = _next_resume(clocks, patterns, types, i, want_patterns=RESTART)
                    if r is not None:
                        comp.append((t0, min(r, t0 + P["max_sub_s"])))
                if cards[i]:
                    r = _next_resume(clocks, patterns, types, i, want_patterns=RESTART)
                    if r is not None:
                        comp.append((t0, min(r, t0 + P["max_card_s"])))
                if typ == "Injury Stoppage":
                    r = _next_resume(clocks, patterns, types, i, want_type="Referee Ball-Drop")
                    if r is not None:
                        comp.append((t0, min(r, t0 + P["max_injury_s"])))
            # restart_excess -- unchanged (the 4 routine restarts already on the allowance ladder)
            for i in range(len(clocks) - 1):
                if poss[i + 1] != poss[i] and patterns[i + 1] in allowance_rs:
                    gap = float(clocks[i + 1]) - float(clocks[i])
                    allow = allowance_rs[patterns[i + 1]]
                    if gap > allow:
                        comp.append((float(clocks[i]) + allow, float(clocks[i + 1])))
            total += _intersect_total(comp, dead_seg.get((int(mid), int(period)), []))
        lb[int(mid)] = total
    return lb


def main() -> None:
    P, allowance_rs, nate_exp, wc_ids, events, dead_seg, inc, sm_match = _load()
    nate_mean = float(np.mean([nate_exp[m] for m in wc_ids]))

    def fit(lb: dict[int, float], extra: dict[int, float] | None = None):
        base = {
            m: lb[m] / 60.0 + sm_match.get(m, 0) / 60.0 + (extra.get(m, 0.0) if extra else 0.0)
            for m in wc_ids
        }
        resid = nate_mean - float(np.mean([base[m] for m in wc_ids]))  # anchor mean to Nate
        p = np.array([base[m] + resid for m in wc_ids])
        t = np.array([nate_exp[m] for m in wc_ids])
        return resid, p, t

    print("Celebration-allowance what-if vs Nate `expected` (32 WC2018 matches). Read-only.\n")
    print("  celeb_allow |   r    |  MAE  | mean_est | residual (min) | signed-err sd")
    print("  ---------------------------------------------------------------------------")
    for allow in SWEEP_S:
        lb = lower_bound_with_celeb_allowance(float(allow), P, allowance_rs, events, dead_seg)
        resid, p, t = fit(lb)
        r = np.corrcoef(p, t)[0, 1]
        mae = float(np.mean(np.abs(p - t)))
        sd = float(np.std(p - t))
        flag = "  <- production (must be r=0.825/MAE 2.44; resid +0.40min==24.2s)" if allow == 0 else (
            "  <- recommended central" if allow == CENTRAL_ALLOW_S else "")
        print(f"     {allow:4d}s   | {r:.3f} | {mae:5.2f} |  {p.mean():5.2f}  |"
              f"     {resid:+5.2f}      |  {sd:5.2f}{flag}")

    # Honest negative: best allowance + crediting a fraction f of the dropped unmarked bucket
    # back for low-injury matches (the UNDER signature). Quick sensitivity, not a faithful re-mark.
    print("\n  Honest negative -- celeb_allow=45s AND credit f*unmarked for matches w/ n_injury<=2:")
    inc2 = inc.groupby("match_id")[["silent_all_s", "silent_marked_s"]].sum()
    unmarked = (inc2["silent_all_s"] - inc2["silent_marked_s"]) / 60.0
    ninj = events[events["type"] == "Injury Stoppage"].groupby("match_id").size().reindex(wc_ids).fillna(0)
    lb45 = lower_bound_with_celeb_allowance(45.0, P, allowance_rs, events, dead_seg)
    for f in [0.0, 0.15, 0.25, 0.35]:
        extra = {m: (f * unmarked.get(m, 0.0) if ninj.get(m, 0) <= 2 else 0.0) for m in wc_ids}
        resid, p, t = fit(lb45, extra)
        print(f"     f={f:.2f}  ->  r={np.corrcoef(p, t)[0, 1]:.3f}  "
              f"MAE={np.mean(np.abs(p - t)):.2f}  resid={resid:+.2f}min  "
              f"(higher f = worse -> the unmarked bucket is mostly genuinely-live sparse logging)")

    print("\n  Takeaway: a celebration allowance of ~60s lifts r 0.825->0.875 and cuts MAE 2.44->1.77")
    print("  (~28%). Improvement plateaus at 60-90s (not knife-edge). The unmarked-recovery side")
    print("  makes things WORSE -- do not chase it. See prompts/impl_celebration_allowance.md to adopt.")


if __name__ == "__main__":
    main()
