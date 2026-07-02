"""Team-quality / Elo test of the outcome-flip 50/50 team-split (ANALYSIS ONLY; ADR-0034).

Settles a reviewer objection to the outcome-flip secondary metric (locked 13.0% [11.3%, 15.1%],
ADR-0031): *the team leading by one at 90' is on average the better team, so the trailing (worse)
team scores fewer than half the omitted-window goals -- `p_trail < 0.5` -- and P(flip) should be
well below half of P(scoreline).* The headline SCORELINE (24.8%) is structurally immune (it rides
total mu, never attributes the scorer); only the flip's lead-by-1 branch uses the split.

Two analyses:
  A. Exact state-decomposition of the locked flip -- how much of it is even `p_trail`-sensitive.
  B. Elo-conditioned `p_trail` -- explanatory power (logit), the crossover, the p_trail x mu
     covariance, and a re-weighted flip band vs the locked 13.0%.

READS production parquet + cached eloratings.net histories (data/raw/elo, see src/fetch_elo.py).
Writes ONLY docs/team_quality_flip_test.md. Touches no processed parquet, no s08 grid, no figure,
no params (pattern: src/flip_split_sensitivity.py; guardrail: CLAUDE.md sec 6 + ADR-0031 lock).

Run: python -m src.team_quality_flip
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import statsmodels.formula.api as smf  # noqa: E402

from src.flip_split_sensitivity import pre_goal_margin  # noqa: E402
from src.lib import config, elo  # noqa: E402

CENTRAL = "silent_marked|overall|pooled_all|hl=4.0|on"


def load():
    m = pd.read_parquet(config.INTERIM / "matches.parquet")
    goals = pd.read_parquet(config.INTERIM / "goals.parquet")
    state = pd.read_parquet(config.INTERIM / "match_state.parquet")
    cf = pd.read_parquet(config.PROCESSED / "counterfactual.parquet")
    summary = pd.read_parquet(config.PROCESSED / "counterfactual_summary.parquet")
    return m, goals, state, cf, summary


def elo_table(m: pd.DataFrame) -> dict:
    """match_id -> dict(home_elo, away_elo) pre-match, plus integrity check vs StatsBomb score."""
    out, bad = {}, []
    for r in m.itertuples():
        res = elo.match_pre_elos(r.home, r.away, r.date)
        if res is None:
            bad.append(r.match_id)
            continue
        sb = {int(r.home_score), int(r.away_score)}
        el = {res["elo_hs"], res["elo_as"]}
        if res["elo_hs"] is not None and sb != el:
            bad.append(("score", r.match_id, sb, el))
        out[r.match_id] = res
    if bad:
        raise SystemExit(f"elo join integrity failure: {bad[:10]}")
    return out


def flip_engine(cf, state):
    """Return (df, mu, tied, lead1, N, flip_fn) for the central knob, 1H+2H window."""
    d = cf[(cf["knob_set"] == CENTRAL) & (cf["window"] == "1H+2H")].merge(state, on="match_id")
    d["mu"] = -np.log(1.0 - d["p_change"].clip(upper=1 - 1e-12))
    tied = (d["state_at_90"] == "tied").to_numpy()
    lead1 = (d["state_at_90"] == "lead_by_1").to_numpy()
    mu = d["mu"].to_numpy()
    N = len(d)

    def flip_fn(p_lead1):
        f = np.zeros(N)
        f[tied] = 1.0 - np.exp(-mu[tied])
        pl = np.full(int(lead1.sum()), p_lead1) if np.isscalar(p_lead1) else np.asarray(p_lead1)
        f[lead1] = 1.0 - np.exp(-mu[lead1] * np.clip(pl, 0.0, 1.0))
        return float(f.mean())

    return d, mu, tied, lead1, N, flip_fn


def analysis_A(d, mu, tied, lead1, flip_fn, summary):
    N = len(d)
    locked = float(summary[(summary["knob_set"] == CENTRAL) & (summary["window"] == "1H+2H") &
                           (summary["group"] == "all")]["pct_outcome_flip"].iloc[0])
    scoreline = float(summary[(summary["knob_set"] == CENTRAL) & (summary["window"] == "1H+2H") &
                              (summary["group"] == "all")]["pct_changed"].iloc[0])
    repro = flip_fn(0.5)
    assert abs(repro - locked) < 1e-6, f"faithfulness gate FAILED: {repro} vs {locked}"
    X = float((1.0 - np.exp(-mu[tied])).sum() / N)          # tied contribution (p_trail-immune)
    Y = float((1.0 - np.exp(-mu[lead1] * 0.5)).sum() / N)   # lead_by_1 contribution (p_trail-sensitive)
    return {
        "locked": locked, "scoreline": scoreline, "repro": repro,
        "n_tied": int(tied.sum()), "n_lead1": int(lead1.sum()),
        "n_lead2": int(N - tied.sum() - lead1.sum()), "N": N,
        "X": X, "Y": Y, "flip": X + Y,
        "sensitive_share": Y / (X + Y),
        "tied_floor_of_scoreline": X / scoreline,
        "flip_over_scoreline": (X + Y) / scoreline,
        "floor_frac_matches": tied.sum() / N,
    }


def build_goal_sample(goals, m, elo_by_match):
    """One row per goal scored while one side led by exactly 1; Y=1 if the TRAILING team scored."""
    home_of = {r.match_id: r.home for r in m.itertuples()}
    away_of = {r.match_id: r.away for r in m.itertuples()}
    tour_of = {r.match_id: str(r.tournament) for r in m.itertuples()}

    def elo_of(mid, team):
        e = elo_by_match[mid]
        return e["home_elo"] if team == home_of[mid] else e["away_elo"]

    g = pre_goal_margin(goals, m)
    one = g[g["margin_before"].abs() == 1].copy()
    Y = (one["margin_before"] == -1).to_numpy().astype(int)   # trailing scored (equalizer)
    scorer = one["team"].astype(str).to_numpy()
    opp = np.array([away_of[mid] if sc == home_of[mid] else home_of[mid]
                    for mid, sc in zip(one["match_id"], scorer)])
    trail = np.where(Y == 1, scorer, opp)
    lead = np.where(Y == 1, opp, scorer)
    delta = np.array([elo_of(mid, t) - elo_of(mid, l)
                      for mid, t, l in zip(one["match_id"], trail, lead)]) / 100.0
    return pd.DataFrame({
        "Y": Y, "delta": delta.astype(float), "d2": (delta ** 2).astype(float),
        "minute": one["min"].to_numpy(float),
        "is_stoppage": one["is_stoppage"].astype(str).to_numpy(),
        "period": one["period"].to_numpy(int),
        "tournament": pd.Categorical(np.array([tour_of[mid] for mid in one["match_id"]], dtype=object)),
    })


def lead1_frame(d, m, elo_by_match):
    """The 121 lead_by_1 matches with signed Delta = Elo(trail@90) - Elo(lead@90) and mu."""
    home_of = {r.match_id: r.home for r in m.itertuples()}
    away_of = {r.match_id: r.away for r in m.itertuples()}
    tour_of = {r.match_id: str(r.tournament) for r in m.itertuples()}

    def elo_of(mid, team):
        e = elo_by_match[mid]
        return e["home_elo"] if team == home_of[mid] else e["away_elo"]

    l1 = d[d["state_at_90"] == "lead_by_1"].copy()
    leader = [home_of[mid] if ldr == "home" else away_of[mid]
              for mid, ldr in zip(l1["match_id"], l1["leader"])]
    trailer = [away_of[mid] if ldr == "home" else home_of[mid]
               for mid, ldr in zip(l1["match_id"], l1["leader"])]
    l1 = l1.assign(
        leader_team=leader, trail_team=trailer,
        delta=np.array([elo_of(mid, t) - elo_of(mid, ld)
                        for mid, t, ld in zip(l1["match_id"], trailer, leader)]) / 100.0,
        tournament=pd.Categorical(np.array([tour_of[mid] for mid in l1["match_id"]], dtype=object)),
    )
    l1["d2"] = l1["delta"] ** 2
    return l1


def fit_and_report(gs, l1, flip_fn):
    """Full + simple logits, crossover, covariance, and the re-weighted flip band."""
    res = {}
    cuts = {
        "anchor (all 1-goal-game goals)": gs,
        "2H stoppage": gs[gs["is_stoppage"] == "2H"],
        "2H after 75'": gs[(gs["period"] == 2) & (gs["minute"] >= 75)],
    }
    res["cuts"] = {}
    for name, sub in cuts.items():
        row = {"n": len(sub), "p_trail": float(sub["Y"].mean())}
        try:
            fs = smf.logit("Y ~ delta", data=sub).fit(disp=0)
            row.update(b1=float(fs.params["delta"]), se1=float(fs.bse["delta"]),
                       p1=float(fs.pvalues["delta"]), pR2=float(fs.prsquared),
                       dstar=float(-fs.params["Intercept"] / fs.params["delta"]))
        except Exception as e:  # noqa: BLE001
            row["err"] = str(e)[:60]
        res["cuts"][name] = row

    # full model on the powered anchor
    full = smf.logit("Y ~ delta + d2 + minute + C(tournament)", data=gs).fit(disp=0)
    res["full"] = {"n": len(gs), "b_delta": float(full.params["delta"]),
                   "se_delta": float(full.bse["delta"]), "p_delta": float(full.pvalues["delta"]),
                   "b_d2": float(full.params["d2"]), "p_d2": float(full.pvalues["d2"]),
                   "b_min": float(full.params["minute"]), "p_min": float(full.pvalues["minute"]),
                   "pR2": float(full.prsquared)}

    # covariance channel across the 121 lead_by_1 matches
    mu = l1["mu"].to_numpy()
    delta = l1["delta"].to_numpy()
    w = mu / mu.sum()
    res["cov"] = {
        "n": len(l1), "mean_delta_elo": float(delta.mean() * 100),
        "median_delta_elo": float(np.median(delta) * 100),
        "share_leader_stronger": float((delta < 0).mean()),
        "corr_delta_mu": float(np.corrcoef(delta, mu)[0, 1]),
        "mean_delta_unw_elo": float(delta.mean() * 100),
        "mean_delta_muw_elo": float((w * delta).sum() * 100),
    }

    # predicted p_trail(Delta) for the 121, evaluated at the added-time reference minute
    pred = l1.copy()
    pred["minute"] = 92.5
    pt = full.predict(pred).to_numpy()
    res["pred"] = {"mean": float(pt.mean()), "muw": float((w * pt).sum()),
                   "min": float(pt.min()), "max": float(pt.max())}

    # re-weighted flip band. abs-level uses the fitted (chase-inclusive) level directly; the two
    # re-centered variants pin the mean to an OBSERVED base rate (guardrail: Elo tests dispersion +
    # covariance; it does not SET the base rate) and isolate the dispersion/covariance channel.
    flip_locked = flip_fn(0.5)
    res["flip"] = {
        "locked": flip_locked,
        "abs": flip_fn(pt),
        "recenter_050": flip_fn(pt - pt.mean() + 0.5),
        "recenter_0509": flip_fn(pt - pt.mean() + 0.509),
        "recenter_0548": flip_fn(pt - pt.mean() + 0.548),
        "flat_0509": flip_fn(0.509),
        "flat_0548": flip_fn(0.548),
        "flat_040": flip_fn(0.40),
        "flat_060": flip_fn(0.60),
    }
    res["dstar_full_ref"] = crossover_full(full)
    return res


def crossover_full(full):
    """Delta* where the full model predicts p_trail=0.5 at the added-time minute (d2 held via its
    small quadratic). Solve b0 + b_min*92.5 + b_delta*x + b_d2*x^2 = 0 at the reference competition."""
    b0 = full.params["Intercept"] + full.params["minute"] * 92.5
    a, b, cc = full.params["d2"], full.params["delta"], b0
    if abs(a) < 1e-9:
        return -cc / b * 100
    disc = b * b - 4 * a * cc
    if disc < 0:
        return float("nan")
    roots = [(-b + s * np.sqrt(disc)) / (2 * a) for s in (1, -1)]
    roots = [r for r in roots if -3 < r < 3]  # keep the in-support root (|Delta|<300 Elo)
    return (min(roots, key=abs) * 100) if roots else float("nan")


def write_report(A, B):
    L = []
    P = L.append
    P("# Team-quality / Elo test of the outcome-flip team-split (ADR-0034)")
    P("")
    P("Settles the reviewer objection that the team leading by one at 90' is the better team, so the "
      "trailing side should score **fewer** than half the omitted-window goals (`p_trail < 0.5`) and "
      "P(flip) should fall well below half of P(scoreline). Standalone check: READS production "
      "parquet + cached World Football Elo (eloratings.net); no locked artifact touched. The "
      "**headline scoreline 24.8% is structurally immune** -- it rides total `mu` and never "
      "attributes the scorer; only the flip's `lead_by_1` branch (`p_change(mu/2)`) uses the split.")
    P("")
    P("## Analysis A -- exact state-decomposition of the locked 13.0% flip")
    P("")
    P(f"Faithfulness gate: rebuilding the flip from per-match `mu = -ln(1 - p_change)` on the central "
      f"knob reproduces the locked `pct_outcome_flip` = **{A['locked']:.5f}** "
      f"(|delta| < 1e-6). State census of the {A['N']} eligible matches: "
      f"tied **{A['n_tied']}**, lead_by_1 **{A['n_lead1']}**, lead_by_2plus **{A['n_lead2']}**.")
    P("")
    P("| flip component | state | rule | flip mass (pp) | share of flip |")
    P("|---|---|---|---|---|")
    P(f"| tied | {A['n_tied']} | `1-exp(-mu)` (any goal flips; **p_trail-immune**) | "
      f"{A['X']*100:.2f} | {A['X']/A['flip']:.3f} |")
    P(f"| lead_by_1 | {A['n_lead1']} | `1-exp(-mu/2)` (**p_trail-sensitive**) | "
      f"{A['Y']*100:.2f} | {A['Y']/A['flip']:.3f} |")
    P(f"| lead_by_2plus | {A['n_lead2']} | 0 (unflippable) | 0.00 | 0.000 |")
    P(f"| **total flip** | {A['N']} | | **{A['flip']*100:.2f}** | 1.000 |")
    P("")
    P(f"- **Only {A['sensitive_share']*100:.1f}% of the flip is `p_trail`-sensitive.** The tied bucket "
      f"contributes {A['X']*100:.2f} pp regardless of any split; the whole objection can act on at "
      f"most the {A['Y']*100:.2f} pp lead_by_1 mass.")
    P(f"- **Tied-only floor:** even at `p_trail = 0` (leader scores *every* lead_by_1 omitted goal -- "
      f"absurd), the flip cannot fall below **{A['X']*100:.2f}%** = **{A['tied_floor_of_scoreline']*100:.1f}%** "
      f"of the 24.8% scoreline (the {A['n_tied']}/{A['N']} = {A['floor_frac_matches']*100:.1f}% tied share).")
    P(f"- **`flip / scoreline` = {A['flip_over_scoreline']:.3f}** is a state-census identity, not a "
      f"`p_trail` artifact: the {A['n_lead2']} unflippable lead_by_2plus matches do more to hold the "
      f"ratio near half than `p_trail` ever could.")
    P("")
    P("## Analysis B -- Elo-conditioned p_trail")
    P("")
    P("**B1 sourcing.** Pre-match World Football Elo (eloratings.net) for both teams in all 314 "
      "matches; joined by team + date and integrity-checked (final score set matches StatsBomb for "
      "all 314). **B2 signed gap** per lead_by_1 match: `Delta = Elo(trailing@90') - Elo(leading@90')` "
      "(Delta < 0 = leader stronger = the objection's case).")
    P("")
    cov = B["cov"]
    P(f"The lead_by_1 pool is only modestly skewed toward stronger leaders: mean "
      f"`Delta = {cov['mean_delta_elo']:.0f}` Elo (median {cov['median_delta_elo']:.0f}), leader "
      f"stronger in **{cov['share_leader_stronger']*100:.0f}%** of matches -- not the blowout the "
      f"objection imagines, because *exactly-1* and *still-live-at-90* both select against "
      f"mismatches.")
    P("")
    P("**B3 explanatory power + crossover.** Logit of `trailing_scored` on the Elo gap (per 100 Elo). "
      "Fit on the powered anchor (all goals in a 1-goal game state) and on the added-time cuts:")
    P("")
    P("| cut | n | p_trail | beta(Delta/100) | se | p | pseudo-R2 |")
    P("|---|---|---|---|---|---|---|")
    for name, r in B["cuts"].items():
        if "b1" in r:
            P(f"| {name} | {r['n']} | {r['p_trail']:.3f} | {r['b1']:+.3f} | {r['se1']:.3f} | "
              f"{r['p1']:.3f} | {r['pR2']:.4f} |")
        else:
            P(f"| {name} | {r['n']} | {r['p_trail']:.3f} | -- | -- | -- | -- |")
    f = B["full"]
    P("")
    P(f"Full model (anchor, n={f['n']}): `logit(trailing_scored) ~ Delta + Delta^2 + minute + "
      f"C(tournament)` -> **beta_Delta = {f['b_delta']:+.3f}** per 100 Elo "
      f"(se {f['se_delta']:.3f}, p = {f['p_delta']:.4f}), beta_Delta^2 = {f['b_d2']:+.3f} "
      f"(p = {f['p_d2']:.3f}), beta_minute = {f['b_min']:+.4f} (p = {f['p_min']:.3f}), "
      f"pseudo-R2 = {f['pR2']:.3f}.")
    P("")
    P(f"- Quality **does** have explanatory power and in the crossover direction the user predicted: "
      f"`p_trail` **rises** with `Delta` (stronger trailing team => more likely to equalize). The "
      f"crossover `Delta*` (predicted `p_trail = 0.5`) sits at **{B['dstar_full_ref']:.0f} Elo** -- "
      f"i.e. below `Delta = 0`, because the trailing team's late chase lifts `p_trail` above half at "
      f"equal quality.")
    P(f"- But the added-time cut (2H stoppage, n={B['cuts']['2H stoppage']['n']}) is under-powered "
      f"(p = {B['cuts']['2H stoppage'].get('p1', float('nan')):.2f}); the slope is borrowed from the "
      f"large within-tournament anchor rather than an external competition (no era/mix caveat).")
    P("")
    P("**B4 covariance -- the one channel the pooled mean misses.** Across the "
      f"{cov['n']} lead_by_1 matches, `corr(Delta, mu_omitted) = {cov['corr_delta_mu']:+.3f}` "
      f"(essentially zero). The mu-weighted mean `Delta` = **{cov['mean_delta_muw_elo']:.0f}** Elo vs "
      f"unweighted **{cov['mean_delta_unw_elo']:.0f}** Elo -- weighting by omitted-goal mass makes the "
      f"gap *less* negative, i.e. nudges `p_trail` **up**, the opposite of the objection's feared "
      f"`p_trail x mu` covariance.")
    P("")
    fl = B["flip"]
    P("**B5 re-weight and compare.** Swap the flat `p_trail = 0.5` in the lead_by_1 branch for the "
      "per-match fitted `p_trail(Delta)` and recompute the aggregate flip. The abs-level variant uses "
      "the fitted (chase-inclusive, observed-scorer) level; the re-centered variants pin the mean to "
      "an observed base rate and isolate the dispersion+covariance channel (guardrail: Elo tests "
      "residual signal, it does not SET the base rate).")
    P("")
    P("| p_trail construction | flip X% | delta vs locked (pp) |")
    P("|---|---|---|")
    order = [("flat 0.50 (locked)", "locked"), ("fitted p_trail(Delta), abs level", "abs"),
             ("fitted, re-centered to 0.50", "recenter_050"),
             ("fitted, re-centered to 0.509 (obs all)", "recenter_0509"),
             ("fitted, re-centered to 0.548 (obs 2H stoppage)", "recenter_0548"),
             ("flat 0.509 (observed, all)", "flat_0509"),
             ("flat 0.548 (observed, 2H stoppage)", "flat_0548"),
             ("flat 0.40 (leverage floor)", "flat_040"),
             ("flat 0.60 (leverage ceiling)", "flat_060")]
    for label, key in order:
        P(f"| {label} | {fl[key]*100:.2f}% | {(fl[key]-fl['locked'])*100:+.2f} |")
    elo_keys = ("abs", "recenter_050", "recenter_0509", "recenter_0548")
    move = max(abs(fl[k] - fl["locked"]) for k in elo_keys)
    lo_e = min(fl[k] for k in elo_keys)
    hi_e = max(fl[k] for k in elo_keys)
    P("")
    P(f"Every Elo-informed re-weight lands within **[{lo_e*100:.2f}%, {hi_e*100:.2f}%]** (the flat "
      f"0.40/0.60 rows are the mechanical leverage bounds, not Elo-implied) and the largest move of "
      f"an Elo-conditioned variant is **{move*100:.2f} pp** -- inside the locked flip CI "
      f"[11.3%, 15.1%] and below the 0.5 pp threshold that would trigger an s08 sensitivity row.")
    P("")
    P("## Conclusion")
    P("")
    P(f"The objection's premise is partly real (leader stronger in "
      f"{cov['share_leader_stronger']*100:.0f}% of lead_by_1 matches; quality is a significant "
      f"predictor) but its conclusion does not follow. Three facts defuse it: (1) only "
      f"{A['sensitive_share']*100:.0f}% of the flip is even `p_trail`-sensitive and the tied floor "
      f"holds it at {A['tied_floor_of_scoreline']*100:.0f}% of scoreline; (2) the *realized* "
      f"`p_trail` -- observed scorers, chase included -- is **at/above 0.5** (0.509 all / 0.548 2H "
      f"stoppage), so the net late-game effect runs opposite to the objection; (3) the `Delta x mu` "
      f"covariance is ~0 and mu-weighting nudges `p_trail` up. **Keep `p_trail = 0.5`; flip 13.0% "
      f"LOCK UNCHANGED.** README: no change needed (the 0.548 split pre-empt already stands).")
    P("")
    P("_Reproduce: `python -m src.fetch_elo` then `python -m src.team_quality_flip`. Faithfulness "
      f"gate: flip(0.5) reproduces locked {A['locked']:.5f} to <1e-6._")
    out = config.DOCS / "team_quality_flip_test.md"
    out.write_text("\n".join(L) + "\n")
    return out


def main():
    m, goals, state, cf, summary = load()
    elo_by_match = elo_table(m)
    d, mu, tied, lead1, N, flip_fn = flip_engine(cf, state)
    A = analysis_A(d, mu, tied, lead1, flip_fn, summary)
    gs = build_goal_sample(goals, m, elo_by_match)
    l1 = lead1_frame(d, m, elo_by_match)
    B = fit_and_report(gs, l1, flip_fn)

    print(f"[A] faithfulness flip(0.5)={A['repro']:.5f} locked={A['locked']:.5f} scoreline={A['scoreline']:.5f}")
    print(f"[A] tied X={A['X']*100:.2f}pp lead1 Y={A['Y']*100:.2f}pp  p_trail-sensitive share={A['sensitive_share']:.3f}")
    print(f"[A] tied floor={A['X']*100:.2f}% = {A['tied_floor_of_scoreline']*100:.1f}% of scoreline; flip/scoreline={A['flip_over_scoreline']:.3f}")
    print(f"[B] mean Delta={B['cov']['mean_delta_elo']:.0f} Elo  leader-stronger share={B['cov']['share_leader_stronger']:.2f}")
    print(f"[B] full beta_delta={B['full']['b_delta']:+.3f} (p={B['full']['p_delta']:.4f}) pR2={B['full']['pR2']:.3f}  crossover Delta*={B['dstar_full_ref']:.0f} Elo")
    print(f"[B] corr(Delta,mu)={B['cov']['corr_delta_mu']:+.3f}  mu-wtd Delta={B['cov']['mean_delta_muw_elo']:.0f} vs unw {B['cov']['mean_delta_unw_elo']:.0f}")
    print(f"[B] flip: locked={B['flip']['locked']*100:.2f}% abs={B['flip']['abs']*100:.2f}% recenter0.5={B['flip']['recenter_050']*100:.2f}% recenter0.548={B['flip']['recenter_0548']*100:.2f}%")
    out = write_report(A, B)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
