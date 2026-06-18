"""s08 -- Counterfactual headline (closed-form any-extra-goal model; IMPL-6 / ADR-0019).

Question: if the OMITTED stoppage minutes (true stoppage that was never played) had been
played, in how many matches would >=1 additional goal have been scored?

Closed form, per match, per added-time window h in {1H, 2H}:
    true_stoppage_h      = s05 estimator minutes (silent-knob dependent)      [FROZEN r=0.825]
    played_in_stoppage_h = minutes actually played past 45:00/90:00 (period_end-2700) [DC2 rename]
    omitted_h            = max(0, true_stoppage_h - played_in_stoppage_h)
    omitted_live_h       = omitted_h * live_share_h        (ball-in-play share, s07; DC1 table)
    lambda_h             = two-team goals / match-live-minute in window h (pooled, overall)
    mu                   = sum_h lambda_h * omitted_live_h
    P(change)            = 1 - exp(-mu)                     (P[>=1 extra goal by either team])
    X%                   = mean over matches of P(change)

This replaces the IMPL-4 W/D/L Monte Carlo: the central estimate is now DETERMINISTIC and
exact (no flip sim, no seed for the headline). The seed survives only for the CI bootstrap
(per-cell Jeffreys Gamma on lambda + a silent_marked estimator-error draw). Every knob
combination (silent x conditioning x source) is a sensitivity-grid row. The headline window
pools both added-time windows (params:counterfactual.headline_window); "2H_only" is reported
alongside for comparison. STOP after this stage and read the grid before locking a single X%.

In:  interim/{matches,goals,match_state,incident_stoppage,played_in_stoppage}.parquet
     processed/stoppage_live_share.parquet
Out: processed/counterfactual.parquet (per-match P(change)) + counterfactual_summary.parquet
"""
from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd

from src.lib import config


def p_change(mu):
    """P(>=1 extra goal) for a Poisson mean mu of expected extra goals. Monotone increasing,
    p_change(0)=0, p_change(inf)->1. Exposed for the closed-form unit test."""
    return 1.0 - np.exp(-mu)


# ---- lambda estimation ---------------------------------------------------
def two_h_addable_share(incident):
    """Fraction of measured addable stoppage (lower_bound + marked silent) that falls in the 2H,
    over regulation periods. The IMPL-3 residual constant and estimator MAE were fit on
    FULL-MATCH totals vs Nate `expected`; this share splits those full-match constants across the
    two half-windows (f2 to 2H, 1-f2 to 1H) instead of bolting a full-match number onto one
    window (the IMPL-4 LANDMINE). Derived from incident_stoppage.parquet (not hard-coded); stable
    ~0.63 so a single frozen scalar is safe."""
    reg = incident[incident["period"].isin([1, 2])]
    addable = reg["lower_bound_s"] + reg["silent_marked_s"]
    return float(addable[reg["period"] == 2].sum() / addable.sum())


def build_lambda_cells(matches, goals, state, live_min):
    """cells[(cohort, window, conditioning, key)] = (count, exposure_match_min).

    TWO-TEAM rate: count = goals by EITHER team in the window; exposure = sum of match-live-
    minutes in the window (the DC1 canonical table). lambda = count/exposure is goals per
    match-live-minute, so for a match with omitted_live match-minutes mu = lambda*omitted_live
    is the expected number of extra goals by either team. cohort in {all,pre,post};
    window in {1H,2H}; conditioning in {overall, tied_nontied} keyed by state_at_45 (1H) /
    state_at_90 (2H). team_role is gone (IMPL-6): with any-extra-goal only the total rate enters.
    """
    grp = matches.set_index("match_id")["group"].to_dict()
    mids = list(matches["match_id"])
    cohorts = {
        "all": mids,
        "pre": [m for m in mids if grp[m] == "PRE"],
        "post": [m for m in mids if grp[m] == "POST"],
    }
    state_col = {"1H": "state_at_45", "2H": "state_at_90"}
    st = state.set_index("match_id")
    cells: dict = {}
    for window in ("1H", "2H"):
        sc = state_col[window]
        gcount = goals[goals["is_stoppage"] == window].groupby("match_id").size().to_dict()
        tied = {m: (st.loc[m, sc] == "tied") for m in mids}

        def agg(ms):
            return (sum(gcount.get(m, 0) for m in ms),
                    sum(live_min.get((m, window), 0.0) for m in ms))

        for cohort, cmids in cohorts.items():
            cells[(cohort, window, "overall", "all")] = agg(cmids)
            cells[(cohort, window, "tied_nontied", "tied")] = agg([m for m in cmids if tied[m]])
            cells[(cohort, window, "tied_nontied", "nontied")] = agg([m for m in cmids if not tied[m]])
    return cells


def _cohort_of(source, group):
    """Map a lambda_source knob to the cohort whose matches estimate lambda for `group`."""
    if source == "pooled_all":
        return "all"
    if source == "pooled_pre":
        return "pre"
    if source == "pooled_post":
        return "post"
    if source == "regime_matched":
        return "pre" if group == "PRE" else "post"
    raise ValueError(f"unknown lambda_source knob: {source!r}")


def _state_key(conditioning, window, mid, st_dict):
    """(conditioning, key) suffix of the cell a match maps into under a conditioning knob."""
    if conditioning == "overall":
        return ("overall", "all")
    sc = "state_at_45" if window == "1H" else "state_at_90"
    return ("tied_nontied", "tied" if st_dict[mid][sc] == "tied" else "nontied")


def main() -> None:
    config.ensure_dirs()
    p = config.params()
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    goals = pd.read_parquet(config.INTERIM / "goals.parquet")
    state = pd.read_parquet(config.INTERIM / "match_state.parquet")
    incident = pd.read_parquet(config.INTERIM / "incident_stoppage.parquet")
    live_share = pd.read_parquet(config.PROCESSED / "stoppage_live_share.parquet")
    pis_path = config.INTERIM / "played_in_stoppage.parquet"
    if not pis_path.exists():
        raise SystemExit(
            "s08 needs played-in-stoppage time. Run s06a (populate raw/board/board_added_time.csv) first."
        )
    pis = pd.read_parquet(pis_path)

    cfg = p["counterfactual"]
    sil = p["silent"]
    B = cfg["n_bootstrap"]
    headline_window = cfg["headline_window"]
    # Central estimate is the closed form (deterministic). The seed is consumed ONLY by the CI
    # bootstrap, so the headline X% is reproducible without any Monte Carlo (ADR-0019).
    rng = np.random.default_rng(cfg["seed"] + 1)

    # canonical live-minutes + live-share per (match, window) -- the SAME table that feeds lambda
    # exposure (build_lambda_cells) and per-match omitted-live, so they cannot drift (DC1).
    pmap = {"1H_stoppage": "1H", "2H_stoppage": "2H"}
    live_min, ls_ratio = {}, {}
    for r in live_share.itertuples(index=False):
        w = pmap.get(r.phase)
        if w is None:
            continue
        live_min[(r.match_id, w)] = r.live_seconds / 60.0
        ls_ratio[(r.match_id, w)] = r.live_share
    played = {}
    for r in pis.itertuples(index=False):
        if r.period in (1, 2):
            played[(r.match_id, "1H" if r.period == 1 else "2H")] = float(r.played_in_stoppage_min)
    inc = {}
    for r in incident.itertuples(index=False):
        if r.period in (1, 2):
            inc[(r.match_id, "1H" if r.period == 1 else "2H")] = (
                float(r.lower_bound_s), float(r.silent_marked_s), float(r.silent_all_s))

    # Split the full-match IMPL-3 constants into the two windows by addable share (LANDMINE: do
    # NOT bolt the full-match residual/MAE onto a single window). The estimator error E is a
    # single full-match draw shared across the two windows (correlated), scaled by f1/f2 -- this
    # reduces to the old 2H-only sigma when 1H is dropped.
    f2 = two_h_addable_share(incident)
    f1 = 1.0 - f2
    fshare = {"1H": f1, "2H": f2}
    residual_s = float(sil["residual_silent_s"])
    sigma_full_min = float(sil["estimator_mae_min"]) * math.sqrt(math.pi / 2.0)
    print(f"  addable share f2(2H)={f2:.3f} f1(1H)={f1:.3f}; residual {residual_s:.1f}s split -> "
          f"1H {residual_s * f1:.1f}s / 2H {residual_s * f2:.1f}s; estimator sigma_full="
          f"{sigma_full_min:.2f}min (MAE {sil['estimator_mae_min']}min)")

    def ts_window_min(mid, window, knob):
        """true_stoppage minutes for one window under a silent-treatment knob."""
        lb, sm, sa = inc.get((mid, window), (0.0, 0.0, 0.0))
        if knob == "silent_none":
            s = lb
        elif knob == "silent_marked":
            s = lb + sm + residual_s * fshare[window]
        elif knob == "silent_all":
            s = lb + sa
        else:
            raise ValueError(f"unknown true_stoppage knob: {knob!r}")
        return s / 60.0

    cells = build_lambda_cells(matches, goals, state, live_min)
    st_dict = state.set_index("match_id").to_dict("index")
    group = matches.set_index("match_id")["group"].to_dict()
    eligible = [m for m in matches["match_id"] if (m, "2H") in played]
    n = len(eligible)
    grp_arr = np.array([group[m] for m in eligible])
    group_masks = {"all": np.ones(n, bool),
                   "PRE": grp_arr == "PRE", "POST": grp_arr == "POST"}

    per_match_rows, summary_rows = [], []
    central_2h_only = {}  # knob_set -> central X% (2H_only) for the comparison line
    grid = list(itertools.product(
        cfg["true_stoppage_knobs"], cfg["lambda_conditioning_knobs"], cfg["lambda_source_knobs"]))
    for ts_knob, cond_knob, src_knob in grid:
        knob_set = f"{ts_knob}|{cond_knob}|{src_knob}"

        # per-window per-match arrays + a per-window cell index for the bootstrap
        ts_arr, played_arr, ls_arr, olive, lam, cellidx = {}, {}, {}, {}, {}, {}
        distinct, cell_ce = {}, []
        for window in ("1H", "2H"):
            tsw = np.array([ts_window_min(m, window, ts_knob) for m in eligible])
            plw = np.array([played.get((m, window), 0.0) for m in eligible])
            lsw = np.nan_to_num(
                np.array([ls_ratio.get((m, window), 0.0) for m in eligible]), nan=0.0)
            olivew = np.maximum(0.0, tsw - plw) * lsw
            cnt_w = np.zeros(n)
            exp_w = np.zeros(n)
            idx_w = np.zeros(n, dtype=int)
            for i, m in enumerate(eligible):
                ck = (_cohort_of(src_knob, group[m]), window) + _state_key(cond_knob, window, m, st_dict)
                c, e = cells[ck]
                cnt_w[i], exp_w[i] = c, e
                if ck not in distinct:
                    distinct[ck] = len(cell_ce)
                    cell_ce.append((c, e))
                idx_w[i] = distinct[ck]
            exp_safe = np.where(exp_w > 0, exp_w, 1.0)
            ts_arr[window], played_arr[window], ls_arr[window] = tsw, plw, lsw
            olive[window] = olivew
            lam[window] = cnt_w / exp_safe * (exp_w > 0)
            cellidx[window] = idx_w

        # central (deterministic) mu per window-set
        mu = {
            "2H_only": lam["2H"] * olive["2H"],
            "1H+2H": lam["1H"] * olive["1H"] + lam["2H"] * olive["2H"],
        }
        central_2h_only[knob_set] = float(p_change(mu["2H_only"]).mean())

        # bootstrap: one Jeffreys-Gamma lambda draw per distinct cell per iteration (shared across
        # matches in that cell -> honest shared-cell uncertainty, unlike per-match-independent
        # draws), plus the silent_marked estimator-error draw on true_stoppage.
        cell_count = np.array([c for c, _ in cell_ce], dtype=float)
        cell_exp = np.array([e for _, e in cell_ce], dtype=float)
        cell_exp_safe = np.where(cell_exp > 0, cell_exp, 1.0)
        cell_valid = (cell_exp > 0).astype(float)
        sigma = sigma_full_min if ts_knob == "silent_marked" else 0.0
        boot = {w: {g: np.empty(B) for g in group_masks} for w in mu}
        for b in range(B):
            g = rng.gamma(cell_count + 0.5, 1.0 / cell_exp_safe) * cell_valid
            lam1, lam2 = g[cellidx["1H"]], g[cellidx["2H"]]
            if sigma > 0:
                E = rng.normal(0.0, sigma, size=n)
                ol1 = np.maximum(0.0, ts_arr["1H"] + E * f1 - played_arr["1H"]) * ls_arr["1H"]
                ol2 = np.maximum(0.0, ts_arr["2H"] + E * f2 - played_arr["2H"]) * ls_arr["2H"]
            else:
                ol1, ol2 = olive["1H"], olive["2H"]
            mub = {"2H_only": lam2 * ol2, "1H+2H": lam1 * ol1 + lam2 * ol2}
            for w in mu:
                pcb = p_change(mub[w])
                for gl, mask in group_masks.items():
                    boot[w][gl][b] = pcb[mask].mean()

        for w in mu:
            pc = p_change(mu[w])
            for gl, mask in group_masks.items():
                summary_rows.append({
                    "window": w, "group": gl, "knob_set": knob_set,
                    "pct_changed": float(pc[mask].mean()),
                    "ci_lo": float(np.quantile(boot[w][gl], 0.025)),
                    "ci_hi": float(np.quantile(boot[w][gl], 0.975)),
                    "n_matches": int(mask.sum()),
                })
            for m, pcv in zip(eligible, pc):
                per_match_rows.append(
                    {"match_id": m, "window": w, "knob_set": knob_set, "p_change": float(pcv)})

    summary = pd.DataFrame(summary_rows)
    per_match = pd.DataFrame(per_match_rows)
    per_match.to_parquet(config.PROCESSED / "counterfactual.parquet", index=False)
    summary.to_parquet(config.PROCESSED / "counterfactual_summary.parquet", index=False)

    # ---- print the headline-window sensitivity grid + the window comparison --------------
    print(f"\n  HEADLINE WINDOW = {headline_window}  (X% = mean P[>=1 extra goal]); group=all:")
    hl = summary[(summary["window"] == headline_window) & (summary["group"] == "all")]
    for _, r in hl.sort_values("pct_changed").iterrows():
        print(f"    {r['knob_set']:<45} X={r['pct_changed']:6.3f}  "
              f"ci=[{r['ci_lo']:.3f},{r['ci_hi']:.3f}]")
    central = "silent_marked|overall|pooled_all"
    c_all = hl[hl["knob_set"] == central]
    if not c_all.empty:
        r = c_all.iloc[0]
        print(f"\n  central knob ({central}): 2H_only X={central_2h_only[central]:.3f} vs "
              f"{headline_window} X={r['pct_changed']:.3f} "
              f"ci=[{r['ci_lo']:.3f},{r['ci_hi']:.3f}]")
    print(f"\n  wrote counterfactual.parquet ({len(per_match)} rows) and counterfactual_summary.parquet")
    print("  STOP: read the sensitivity grid above before locking a single X% in decisions.md.")


if __name__ == "__main__":
    main()
