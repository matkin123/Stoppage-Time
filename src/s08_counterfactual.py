"""s08 -- Counterfactual Monte Carlo (the headline).

Question: if the omitted stoppage minutes had been played, in how many matches would the
result differ from what actually happened?

Per match: omitted clock minutes m = max(0, true_stoppage - board_added); omitted live
minutes m_live = m * live_share (measured 2H-stoppage live-share from s07); expected goals
for each team = lambda(state, role) * m_live, lambda = empirical goals-per-live-minute in
2H stoppage. Add seeded-Poisson draws to the actual final; flip = simulated W/D/L differs.
Aggregate -> per-match p_flip -> % of matches changed (+ % of non-tied changed). CI via a
bootstrap over lambda uncertainty (Gamma posterior on each lambda cell).

Every knob combination (true_stoppage x lambda_conditioning x lambda_source) is a row in
the sensitivity grid. STOP after this stage and read the grid before locking a single X%.

In:  interim/{matches,goals,match_state,incident_stoppage,board_added_time}.parquet
     processed/stoppage_live_share.parquet
Out: processed/counterfactual.parquet (per-match p_flip + summary rows w/ CIs)
"""
from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd
from scipy import stats as sstats

from src.lib import config


# ---- lambda estimation ---------------------------------------------------
def _role_of(goal_team, home, away, leader):
    if leader == "none":
        return "level"
    leader_team = home if leader == "home" else away
    return "leading" if goal_team == leader_team else "trailing"


def build_lambda_cells(matches, goals, state, live_share):
    """Return cells[(source, conditioning, key)] = (count, exposure_minutes)."""
    lm2 = (
        live_share[live_share["phase"] == "2H_stoppage"]
        .set_index("match_id")["live_seconds"] / 60
    ).to_dict()
    home = matches.set_index("match_id")["home"].to_dict()
    away = matches.set_index("match_id")["away"].to_dict()
    group = matches.set_index("match_id")["group"].to_dict()
    st = state.set_index("match_id")
    g2 = goals[goals["is_stoppage"] == "2H"].copy()

    # Each source key maps to the set of group labels whose matches estimate its lambda.
    source_groups = {
        "pooled_post": {"POST"},
        "pooled_pre": {"PRE"},
        "regime_matched_PRE": {"PRE"},
        "regime_matched_POST": {"POST"},
    }

    cells: dict = {}
    for source, want_groups in source_groups.items():
        mids = [m for m in matches["match_id"] if group.get(m) in want_groups]

        tied = [m for m in mids if st.loc[m, "state_at_90"] == "tied"]
        nontied = [m for m in mids if st.loc[m, "state_at_90"] != "tied"]
        exp_all = 2 * sum(lm2.get(m, 0.0) for m in mids)
        exp_tied = 2 * sum(lm2.get(m, 0.0) for m in tied)
        exp_nontied_team = sum(lm2.get(m, 0.0) for m in nontied)  # per role, one team each

        gsrc = g2[g2["match_id"].isin(mids)]
        n_all = len(gsrc)
        n_tied = len(gsrc[gsrc["match_id"].isin(tied)])
        n_nontied = n_all - n_tied
        # team-role goal counts (non-tied only for leading/trailing)
        n_lead = n_trail = 0
        for r in gsrc[gsrc["match_id"].isin(nontied)].itertuples(index=False):
            role = _role_of(r.team, home[r.match_id], away[r.match_id], st.loc[r.match_id, "leader"])
            if role == "leading":
                n_lead += 1
            elif role == "trailing":
                n_trail += 1

        cells[(source, "overall", "all")] = (n_all, exp_all)
        cells[(source, "tied_nontied", "tied")] = (n_tied, exp_tied)
        cells[(source, "tied_nontied", "nontied")] = (n_nontied, 2 * exp_nontied_team)
        cells[(source, "team_role", "level")] = (n_tied, exp_tied)
        cells[(source, "team_role", "leading")] = (n_lead, exp_nontied_team)
        cells[(source, "team_role", "trailing")] = (n_trail, exp_nontied_team)
    return cells


def _lam(cells, source, conditioning, key, draw_rng=None):
    """Point lambda (count/exposure) or a Gamma posterior draw if draw_rng given."""
    count, exposure = cells[(source, conditioning, key)]
    if exposure <= 0:
        return 0.0
    if draw_rng is None:
        return count / exposure
    # Jeffreys posterior: Gamma(count + 0.5, rate=exposure)
    return draw_rng.gamma(count + 0.5, 1.0 / exposure)


# ---- per-match expected goals -------------------------------------------
def _cell_keys(mid, conditioning, src, st_dict):
    """The (home_cell, away_cell) keys into `cells` for a match under a conditioning knob.
    `src` is already a concrete cell-source key (regime matching resolved by caller)."""
    row = st_dict[mid]
    state90, leader = row["state_at_90"], row["leader"]
    if conditioning == "overall":
        k = (src, "overall", "all")
        return k, k
    if conditioning == "tied_nontied":
        key = "tied" if state90 == "tied" else "nontied"
        k = (src, "tied_nontied", key)
        return k, k
    # team_role
    if state90 == "tied":
        k = (src, "team_role", "level")
        return k, k
    home_role = "leading" if leader == "home" else "trailing"
    away_role = "leading" if leader == "away" else "trailing"
    return (src, "team_role", home_role), (src, "team_role", away_role)


def match_lambdas(mid, conditioning, source, cells, st_dict, home, away, draw_rng=None):
    kh, ka = _cell_keys(mid, conditioning, source, st_dict)
    return (
        _lam(cells, *kh, draw_rng=draw_rng),
        _lam(cells, *ka, draw_rng=draw_rng),
    )


# ---- true_stoppage per match (2H / period 2) ----------------------------
def true_stoppage_minutes(matches, incident, knob, params):
    inc2 = incident[incident["period"] == 2].set_index("match_id")
    out = {}
    conv = params["incident"]["conservative_injury_estimate_s"]
    for mid in matches["match_id"]:
        lb = float(inc2["lower_bound_s"].get(mid, 0.0))
        injury_present = bool(inc2["injury_present"].get(mid, False))
        if knob == "lower_bound":
            s = lb
        elif knob == "lower_bound_plus_injury":
            s = lb + (0.0 if injury_present else conv)
        else:  # full_measure_538: not wired per-match; fall back to lower_bound
            s = lb
        out[mid] = s / 60
    return out


_K = 14
_I = np.arange(_K + 1)
_DIFF = _I[:, None] - _I[None, :]  # (added_home_i - added_away_j)
_FACT = np.array([float(math.factorial(int(k))) for k in _I])


def _pois_pmf(lam: float) -> np.ndarray:
    """Poisson pmf over k=0.._K. Manual (no scipy per-call dispatch) -- this runs millions
    of times in the bootstrap. lam=0 -> [1,0,0,...] (0**0==1), matching the degenerate mass."""
    return np.exp(-lam) * lam ** _I / _FACT


def _analytic_pflip(eh, ea, ah, aa):
    """P(result flips) given Poisson means eh, ea added to actual ah-aa.

    Vectorized form of the i,j double sum: P(flip) = sum_{i,j: sign((ah+i)-(aa+j)) != s}
    ph[i]*pa[j], where ph/pa are added-goal pmfs. Identical math to the loop version.
    """
    actual = np.sign(ah - aa)
    flip = np.sign((ah - aa) + _DIFF) != actual
    return float((np.outer(_pois_pmf(eh), _pois_pmf(ea)) * flip).sum())


def main() -> None:
    config.ensure_dirs()
    p = config.params()
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    goals = pd.read_parquet(config.INTERIM / "goals.parquet")
    state = pd.read_parquet(config.INTERIM / "match_state.parquet")
    incident = pd.read_parquet(config.INTERIM / "incident_stoppage.parquet")
    live_share = pd.read_parquet(config.PROCESSED / "stoppage_live_share.parquet")
    board_path = config.INTERIM / "board_added_time.parquet"
    if not board_path.exists():
        raise SystemExit(
            "s08 needs board added time. Run s06a (populate raw/board/board_added_time.csv) first."
        )
    board = pd.read_parquet(board_path)

    cfg = p["counterfactual"]
    # Two independent streams: the headline central estimate (MC) must not shift when the
    # CI bootstrap's RNG consumption changes, so they get separate seeds.
    rng_mc = np.random.default_rng(cfg["seed"])
    rng_boot = np.random.default_rng(cfg["seed"] + 1)
    N = cfg["n_sims"]
    B = cfg["n_bootstrap"]

    cells = build_lambda_cells(matches, goals, state, live_share)
    st_dict = state.set_index("match_id").to_dict("index")
    group = matches.set_index("match_id")["group"].to_dict()
    board2 = board[board["period"] == 2].groupby("match_id")["board_min"].sum().to_dict()
    ls2 = (
        live_share[live_share["phase"] == "2H_stoppage"].set_index("match_id")["live_share"]
    ).to_dict()
    actual = matches.set_index("match_id")[["home_score", "away_score"]].to_dict("index")

    per_match_rows, summary_rows = [], []
    grid = itertools.product(
        cfg["true_stoppage_knobs"], cfg["lambda_conditioning_knobs"], cfg["lambda_source_knobs"]
    )
    for ts_knob, cond_knob, src_knob in grid:
        knob_set = f"{ts_knob}|{cond_knob}|{src_knob}"
        ts_min = true_stoppage_minutes(matches, incident, ts_knob, p)

        eligible = [m for m in matches["match_id"] if m in board2 and not np.isnan(ls2.get(m, np.nan))]
        n = len(eligible)
        ah = np.array([actual[m]["home_score"] for m in eligible], dtype=float)
        aa = np.array([actual[m]["away_score"] for m in eligible], dtype=float)
        mlive = np.array([max(0.0, ts_min[m] - board2[m]) * ls2.get(m, 0.0) for m in eligible])
        # per-match cell (count, exposure) for home/away lambdas under this knob set
        cnt_h, exp_h, cnt_a, exp_a = (np.zeros(n) for _ in range(4))
        for i, m in enumerate(eligible):
            src = f"regime_matched_{group[m]}" if src_knob == "regime_matched" else src_knob
            kh, ka = _cell_keys(m, cond_knob, src, st_dict)
            cnt_h[i], exp_h[i] = cells[kh]
            cnt_a[i], exp_a[i] = cells[ka]
        exp_h_safe = np.where(exp_h > 0, exp_h, 1.0)
        exp_a_safe = np.where(exp_a > 0, exp_a, 1.0)
        lam_h = cnt_h / exp_h_safe * (exp_h > 0)
        lam_a = cnt_a / exp_a_safe * (exp_a > 0)
        eh, ea = lam_h * mlive, lam_a * mlive

        # seeded MC central per-match p_flip
        draw_h = rng_mc.poisson(eh[:, None], size=(n, N))
        draw_a = rng_mc.poisson(ea[:, None], size=(n, N))
        actual_sign = np.sign(ah - aa)
        new_sign = np.sign((ah[:, None] + draw_h) - (aa[:, None] + draw_a))
        p_flip = (new_sign != actual_sign[:, None]).mean(axis=1)
        for m, pf in zip(eligible, p_flip):
            per_match_rows.append({"match_id": m, "knob_set": knob_set, "p_flip": pf})

        nontied_mask = actual_sign != 0
        pct_changed = float(p_flip.mean())
        pct_nontied = float(p_flip[nontied_mask].mean()) if nontied_mask.any() else np.nan

        # bootstrap over lambda uncertainty (Jeffreys Gamma posterior), analytic + vectorized.
        # One gamma draw per cell-backed lambda per iteration; exact flip prob via outer-product.
        flipmask = (np.sign((ah - aa)[:, None, None] + _DIFF[None, :, :])
                    != actual_sign[:, None, None])
        boot = np.empty(B)
        for b in range(B):
            lh = rng_boot.gamma(cnt_h + 0.5, 1.0 / exp_h_safe) * (exp_h > 0)
            la = rng_boot.gamma(cnt_a + 0.5, 1.0 / exp_a_safe) * (exp_a > 0)
            ehb, eab = lh * mlive, la * mlive
            ph = np.exp(-ehb)[:, None] * ehb[:, None] ** _I[None, :] / _FACT[None, :]
            pa = np.exp(-eab)[:, None] * eab[:, None] ** _I[None, :] / _FACT[None, :]
            boot[b] = np.einsum("ni,nj,nij->n", ph, pa, flipmask).mean()

        for grp_label, mask in (("all", np.ones(n, bool)),
                                ("PRE", np.array([group[m] == "PRE" for m in eligible])),
                                ("POST", np.array([group[m] == "POST" for m in eligible]))):
            if not mask.any():
                continue
            summary_rows.append({
                "group": grp_label, "knob_set": knob_set,
                "pct_changed": float(p_flip[mask].mean()),
                "ci_lo": float(np.quantile(boot, 0.025)) if grp_label == "all" else np.nan,
                "ci_hi": float(np.quantile(boot, 0.975)) if grp_label == "all" else np.nan,
                "pct_nontied_changed": pct_nontied if grp_label == "all" else np.nan,
                "n_matches": int(mask.sum()),
            })
        print(f"  {knob_set:<55} all={pct_changed:6.3f}  ci=[{np.quantile(boot,0.025):.3f},{np.quantile(boot,0.975):.3f}]  nontied={pct_nontied:.3f}")

    per_match = pd.DataFrame(per_match_rows)
    summary = pd.DataFrame(summary_rows)
    out = config.PROCESSED / "counterfactual.parquet"
    per_match.to_parquet(out, index=False)
    summary.to_parquet(config.PROCESSED / "counterfactual_summary.parquet", index=False)
    print(f"\n  wrote {out} ({len(per_match)} match-rows) and counterfactual_summary.parquet")
    print("  STOP: read the sensitivity grid above before locking a single X% in decisions.md.")


if __name__ == "__main__":
    main()
