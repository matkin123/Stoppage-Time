"""s08 -- Counterfactual headline (closed-form any-extra-goal model; IMPL-6 / ADR-0019).

Question: if the OMITTED stoppage minutes (true stoppage that was never played) had been
played, in how many matches would >=1 additional goal have been scored?

Closed form, per match, per added-time window h in {1H, 2H}:
    true_stoppage_h      = s05 estimator minutes (silent-knob dependent)      [FROZEN r=0.825]
    played_in_stoppage_h = minutes actually played past 45:00/90:00 (period_end-2700) [DC2 rename]
    omitted_h            = max(0, true_stoppage_h - played_in_stoppage_h)
    omitted_live_h       = omitted_h * ls_half_h * (1 + z_half_h*(1-ls_half_h))   [gross-up ON]
                           SAME-HALF conversion (Method 2, ADR-0029): the omitted minutes are assumed
                           to look like the average minute of that WHOLE played half (its regulation
                           play + its played added time), so BOTH the live share ls_half_h AND the
                           gross-up z_half_h are per-(match,half), measured over all period-h segments
                           (bip_segments + incident_stoppage), NOT the stoppage-window live share /
                           pooled scalar z=0.382 (the asymmetry ADR-0027/0028 flagged). The
                           lambda-EXPOSURE live-minutes are UNCHANGED (still the stoppage-window
                           table), so this deliberately BREAKS the live-share cancellation (ADR-0026).
                           gross-up OFF uses omitted_live_h = omitted_h * ls_half_h.
    lambda_h             = two-team goals / match-live-minute in window h (pooled, overall). The
                           2H rate DECAYS with the omitted-window length (IMPL-8 / Method A,
                           ADR-0024): avg_lambda(T,h) ramps from the observed 2H-stoppage rate down
                           toward the open-play floor as the counterfactual window grows; 1H keeps
                           the observed rate. The old productivity-premium rails ARE the limits.
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


def avg_lambda(T_min, halflife_min, obs_rate, floor_rate):
    """Window-average decayed 2H goal rate (IMPL-8 Method A, ADR-0024).

    Per marginal omitted 2H minute t the rate decays from the observed 2H-stoppage rate toward the
    open-play floor: lambda(t) = floor + (obs-floor)*0.5**(t/h). Averaged over a match's omitted
    window [0, T] this has the closed form
        avg_lambda(T, h) = floor + (obs-floor)*(1-exp(-k*T))/(k*T),  k = ln(2)/h.
    Limits (the two old productivity-premium rails ARE the endpoints): h->inf (k->0) gives obs (NO
    decay); h->0 (k->inf) gives floor; T->0 gives obs. Monotone increasing in h. Vectorized over
    per-match T and over obs/floor (both endpoints are drawn per iteration in the bootstrap)."""
    obs = np.asarray(obs_rate, dtype=float)
    floor = np.asarray(floor_rate, dtype=float)
    T = np.asarray(T_min, dtype=float)
    if math.isinf(halflife_min):
        return obs + 0.0 * T                     # no decay -> observed rail (broadcast to T)
    if halflife_min <= 0.0:
        return np.where(T > 0.0, floor, obs)     # instant decay -> floor (obs only at T=0 limit)
    k = math.log(2.0) / halflife_min
    kT = k * T
    ramp = np.where(kT > 1e-12, -np.expm1(-kT) / np.where(kT > 1e-12, kT, 1.0), 1.0)
    return floor + (obs - floor) * ramp


def _geom_ceiling(window, ci, halflife=4.0):
    """Geometric (full stoppage-within-stoppage) gross-up ceiling X% for the central spec. Only the
    genuine-stoppage fraction of dead time recurs (ADR-0024 z-correction); under Method 2 (ADR-0029)
    that fraction is the per-(match,half) z_half, so the geometric-limit live factor is the fixed
    point ls_half/(1 - z_half*(1-ls_half)) -- compensating ONLY for the stoppage (not normal flow)
    within the added time. With z_half<1 this sits just above single-pass `on`. Reported as the upper
    rail above `on`, not a swept knob."""
    fl1 = np.where(ci["ls1"] > 0, ci["ls1"] / (1.0 - ci["z1"] * (1.0 - ci["ls1"])), 0.0)
    fl2 = np.where(ci["ls2"] > 0, ci["ls2"] / (1.0 - ci["z2"] * (1.0 - ci["ls2"])), 0.0)
    ol1 = np.maximum(0.0, ci["ts1"] - ci["pl1"]) * fl1
    ol2 = np.maximum(0.0, ci["ts2"] - ci["pl2"]) * fl2
    ls2_safe = np.where(ci["ls2"] > 0, ci["ls2"], 1.0)
    T2 = np.where(ci["ls2"] > 0, ol2 / ls2_safe, 0.0)
    avg2 = avg_lambda(T2, halflife, ci["obs2"], ci["floor2"])
    mu = avg2 * ol2 if window == "2H_only" else ci["lam1"] * ol1 + avg2 * ol2
    return float(p_change(mu).mean())


def _stage_x(window, ci, lam1, obs2, floor2, halflife=4.0):
    """Headline X% at the central spec (silent_marked|overall|hl=4|gross-up ON) with the goal RATES
    sourced from a single stage cohort (group-stage or knockout), applied to all matches -- the stage
    analogue of the pooled_pre/pooled_post lambda sources (ADR-0033). The per-match omitted-live
    minutes and decay horizon are lambda-source INDEPENDENT, so they are reused from the central
    snapshot `ci`; only the scalar cohort rates (1H lambda, observed 2H rate, open-play floor) swap
    in. Computed AFTER the main grid so it never perturbs the locked bootstrap RNG stream (ADR-0031).
    Point estimate only -- a reported robustness row, NOT a swept knob (excluded from the band /
    joint envelope, like the geometric ceiling)."""
    fl1 = ci["ls1"] * (1.0 + ci["z1"] * (1.0 - ci["ls1"]))    # gross-up ON
    ol1 = np.maximum(0.0, ci["ts1"] - ci["pl1"]) * fl1
    ol2 = ci["T2_grossed"] * ci["ls2"]                        # omitted-live 2H = grossed clock x live share
    avg2 = avg_lambda(ci["T2_grossed"], halflife, obs2, floor2)
    mu = avg2 * ol2 if window == "2H_only" else lam1 * ol1 + avg2 * ol2
    return float(p_change(mu).mean())


# ---- lambda estimation ---------------------------------------------------
def genuine_stoppage_share(incident, seg):
    """z = genuine-stoppage fraction of dead time, measured in regulation (ADR-0024 gross-up
    correction). Of all ball-out-of-play time in periods 1-2, only the part the s05 estimator
    COUNTS as stoppage (lower_bound restart-excess + marked silent) is compensable; the rest is
    normal flow (throw-ins, prompt goal kicks) that no ref adds back. The time-wasting gross-up
    therefore recurs only z*(1-live_share) of the added-time clock, NOT the whole dead share -- the
    old z=1 over-credited the stoppage-within-stoppage tail (the geometric ceiling was ~1/live_share
    rather than just above single-pass). Pooled scalar; traces to bip_segments (dead) +
    incident_stoppage (counted stoppage). Residual silent is excluded (a frozen estimator constant,
    not a per-event stoppage mechanism), matching the chosen z definition."""
    s = seg.copy()
    s["dur"] = s["end_s"] - s["start_s"]
    reg = s[s["period"].isin([1, 2])]
    dead = reg[~reg["in_play"]]["dur"].sum()
    ri = incident[incident["period"].isin([1, 2])]
    counted = (ri["lower_bound_s"] + ri["silent_marked_s"]).sum()
    return float(counted / dead)


def same_half_factors(seg, incident):
    """Per-(match,window) SAME-HALF live share ls_half and gross-up z_half (Method 2, ADR-0029).

    The omitted added-time minutes are assumed to look like the average minute of that WHOLE played
    half -- regulation play PLUS the added time actually played (ALL period-h segments in
    bip_segments, NOT clipped at 2700) -- so the CLOCK->LIVE conversion sources BOTH factors from the
    SAME reference period (replacing the stoppage-window live share + the pooled scalar z=0.382 whose
    asymmetry ADR-0027/0028 flagged):
        ls_half = sum dur(in_play) / sum dur                       over the whole half
        z_half  = (lower_bound_s + silent_marked_s) / sum dur(dead)   over the whole half
    Residual silent is EXCLUDED from z_half (a frozen estimator constant, not a per-event mechanism),
    matching genuine_stoppage_share's pooled z definition. A half with zero dead time gets z_half=0
    (no gross-up to apply). Returns two dicts keyed (match_id, window)."""
    s = seg.copy()
    s["dur"] = s["end_s"] - s["start_s"]
    half = s[s["period"].isin([1, 2])]
    tot = half.groupby(["match_id", "period"])["dur"].sum()
    live = half[half["in_play"]].groupby(["match_id", "period"])["dur"].sum()
    dead = half[~half["in_play"]].groupby(["match_id", "period"])["dur"].sum()
    counted = (incident.assign(_c=incident["lower_bound_s"] + incident["silent_marked_s"])
               .query("period in [1, 2]").set_index(["match_id", "period"])["_c"])
    wmap = {1: "1H", 2: "2H"}
    ls_half, z_half = {}, {}
    for (mid, per), t in tot.items():
        w = wmap[per]
        ls_half[(mid, w)] = float(live.get((mid, per), 0.0) / t) if t > 0 else 0.0
        d = float(dead.get((mid, per), 0.0))
        z_half[(mid, w)] = float(counted.get((mid, per), 0.0) / d) if d > 0 else 0.0
    return ls_half, z_half


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
    stg = matches.set_index("match_id")["stage"].to_dict()
    mids = list(matches["match_id"])
    cohorts = {
        "all": mids,
        "pre": [m for m in mids if grp[m] == "PRE"],
        "post": [m for m in mids if grp[m] == "POST"],
        # stage cohorts feed the group-stage-vs-knockout lambda-source robustness row (ADR-0033).
        # knockout = every non-group match (Round of 16 .. Final).
        "group": [m for m in mids if stg[m] == "Group Stage"],
        "elim": [m for m in mids if stg[m] != "Group Stage"],
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


def regular_lambda_cells(prod):
    """reg_cells[cohort] = (goal_count, live_minutes) for OPEN PLAY (phase=regular), per cohort.

    The decay FLOOR (IMPL-8 / ADR-0024; was the old open_play rail, ADR-0021 #2): the regular-play
    goal rate -- the same goals-per-live-minute people see for 95% of the match, with no end-game
    urgency premium -- is what the decayed 2H rate relaxes TOWARD as the omitted window grows.
    Pulled straight from s07's productivity table (scope pooled / group:PRE / group:POST) so the
    floor lambda traces to the ledger. Registered as a drawn cell so its sampling error enters CI."""
    scope_of = {"all": "pooled", "pre": "group:PRE", "post": "group:POST",
                "group": "stage:Group Stage", "elim": "stage:Knockout"}
    out = {}
    for cohort, scope in scope_of.items():
        row = prod[(prod["scope"] == scope) & (prod["dimension"] == "phase") &
                   (prod["phase_or_bucket"] == "regular") & (prod["metric"] == "goals")]
        if row.empty:
            out[cohort] = (0.0, 0.0)
        else:
            r = row.iloc[0]
            out[cohort] = (float(r["n_events"]), float(r["live_minutes"]))
    return out


def main() -> None:
    config.ensure_dirs()
    p = config.params()
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    goals = pd.read_parquet(config.INTERIM / "goals.parquet")
    state = pd.read_parquet(config.INTERIM / "match_state.parquet")
    incident = pd.read_parquet(config.INTERIM / "incident_stoppage.parquet")
    seg = pd.read_parquet(config.INTERIM / "bip_segments.parquet")
    live_share = pd.read_parquet(config.PROCESSED / "stoppage_live_share.parquet")
    prod = pd.read_parquet(config.PROCESSED / "productivity.parquet")
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

    # canonical live-minutes per (match, window) -- the lambda-EXPOSURE table (build_lambda_cells).
    # Method 2 (ADR-0029) sources the CLOCK->LIVE conversion live share from the WHOLE played half
    # instead (same_half_factors below), NOT this stoppage-window table, so omitted-live and
    # lambda-exposure live share are now DIFFERENT objects -- the live-share cancellation (ADR-0026)
    # is deliberately broken.
    pmap = {"1H_stoppage": "1H", "2H_stoppage": "2H"}
    live_min = {}
    for r in live_share.itertuples(index=False):
        w = pmap.get(r.phase)
        if w is None:
            continue
        live_min[(r.match_id, w)] = r.live_seconds / 60.0
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
    # Method 2 (ADR-0029): per-(match,half) SAME-HALF live share + gross-up z replace the
    # stoppage-window live share + the pooled scalar z in the CLOCK->LIVE conversion. The pooled
    # scalar z_genuine is kept ONLY as a reported diagnostic (pooled-mean of z_half vs the old 0.382).
    ls_half, z_half = same_half_factors(seg, incident)
    z_genuine = genuine_stoppage_share(incident, seg)
    lsh_mean = float(np.mean([v for v in ls_half.values()]))
    zh_mean = float(np.mean([v for v in z_half.values()]))
    print(f"  Method 2 same-half conversion (ADR-0029): mean ls_half={lsh_mean:.3f}, "
          f"mean z_half={zh_mean:.3f}  (vs pooled scalar z={z_genuine:.3f})")
    # ADR-0030: era-conditional residual. PRE matches (celebration credited as excess) use the re-fit
    # PRE residual; POST (full-gap celebration) keeps 24.2s. Keyed by match_id so ts_window_min scales
    # the right value by the window addable share fshare[window] (matching s05's per-match residual).
    post_resid_s = float(sil["residual_silent_s"])
    pre_resid_s = float(sil["residual_silent_pre_s"])
    match_resid_s = {int(m): (pre_resid_s if gr == "PRE" else post_resid_s)
                     for m, gr in zip(matches["match_id"], matches["group"])}
    sigma_full_min = float(sil["estimator_mae_min"]) * math.sqrt(math.pi / 2.0)
    print(f"  addable share f2(2H)={f2:.3f} f1(1H)={f1:.3f}; residual PRE {pre_resid_s:.1f}s / POST "
          f"{post_resid_s:.1f}s (ADR-0030 era-conditional) split by fshare; estimator sigma_full="
          f"{sigma_full_min:.2f}min (MAE {sil['estimator_mae_min']}min)")

    def ts_window_min(mid, window, knob):
        """true_stoppage minutes for one window under a silent-treatment knob."""
        lb, sm, sa = inc.get((mid, window), (0.0, 0.0, 0.0))
        if knob == "silent_none":
            s = lb
        elif knob == "silent_marked":
            s = lb + sm + match_resid_s.get(int(mid), post_resid_s) * fshare[window]
        elif knob == "silent_all":
            s = lb + sa
        else:
            raise ValueError(f"unknown true_stoppage knob: {knob!r}")
        return s / 60.0

    cells = build_lambda_cells(matches, goals, state, live_min)
    # open-play floor cells for the productivity-premium LOWER rail (keyed ("__regular__", cohort))
    for coh, ce in regular_lambda_cells(prod).items():
        cells[("__regular__", coh)] = ce
    st_dict = state.set_index("match_id").to_dict("index")
    group = matches.set_index("match_id")["group"].to_dict()
    eligible = [m for m in matches["match_id"] if (m, "2H") in played]
    n = len(eligible)
    grp_arr = np.array([group[m] for m in eligible])
    group_masks = {"all": np.ones(n, bool),
                   "PRE": grp_arr == "PRE", "POST": grp_arr == "POST"}
    # state at 90' per match -> which matches can flip the OUTCOME (winner/draw), not just the
    # scoreline (ADR-0021 #1). Only tied (any extra goal flips) and lead_by_1 (the TRAILING team
    # must score; per-team half-rate split) can flip; lead_by_2plus is treated as unflippable.
    s90 = np.array([st_dict[m]["state_at_90"] for m in eligible])
    tied90 = s90 == "tied"
    lead1_90 = s90 == "lead_by_1"

    def outcome_flip(mu_arr):
        pf = np.zeros(n)
        pf[tied90] = p_change(mu_arr[tied90])              # any goal breaks the tie
        pf[lead1_90] = p_change(mu_arr[lead1_90] / 2.0)    # trailing team (half rate) equalizes+
        return pf

    central = "silent_marked|overall|pooled_all|hl=4.0|on"   # IMPL-8: gross-up ON, decay h=4
    per_match_rows, summary_rows = [], []
    central_2h_only = {}   # knob_set -> central X% (2H_only) for the comparison line
    central_inputs = {}    # snapshot of the central spec's per-match arrays (geometric ceiling)
    grid = list(itertools.product(
        cfg["true_stoppage_knobs"], cfg["lambda_conditioning_knobs"], cfg["lambda_source_knobs"],
        cfg["productivity_decay_halflife_min"], cfg["timewaste_grossup_knobs"]))
    for ts_knob, cond_knob, src_knob, h_knob, gw_knob in grid:
        knob_set = f"{ts_knob}|{cond_knob}|{src_knob}|hl={h_knob}|{gw_knob}"
        grossup = gw_knob == "on"

        # per-window per-match arrays + per-window cell indices for the bootstrap. For the 2H
        # window the decay needs BOTH endpoint cells per match: the observed 2H-stoppage rate
        # (decay START) and the open-play floor (decay FLOOR). 1H is UNCHANGED (observed 1H lambda).
        ts_arr, played_arr, ls_arr, z_arr, fl_arr, olive, lam, cellidx = ({}, {}, {}, {},
                                                                          {}, {}, {}, {})
        distinct, cell_ce = {}, []
        floor2 = flooridx2 = None
        for window in ("1H", "2H"):
            tsw = np.array([ts_window_min(m, window, ts_knob) for m in eligible])
            plw = np.array([played.get((m, window), 0.0) for m in eligible])
            # Method 2 (ADR-0029): SAME-HALF live share + per-(match,half) gross-up z (over the whole
            # played half), NOT the stoppage-window live share / pooled scalar z. nan_to_num guards a
            # half with no segments (never expected for periods 1-2).
            lsw = np.nan_to_num(
                np.array([ls_half.get((m, window), 0.0) for m in eligible]), nan=0.0)
            zw = np.nan_to_num(
                np.array([z_half.get((m, window), 0.0) for m in eligible]), nan=0.0)
            # O3 gross-up (ADR-0021 #3 / ADR-0024 z-correction): inflate omitted CLOCK for the
            # stoppage WITHIN the added time, then take the live portion. Only the genuine-stoppage
            # fraction z_half of dead time recurs (refs compensate stoppage, not normal flow) -- NOT
            # the whole dead share. One pass adds z_half*(1-ls) of the clock, so the live factor is
            # ls*(1 + z_half*(1-ls)) vs ls at base. The decay HORIZON tracks this via T = olive/ls
            # (= the grossed clock), so horizon and live-minutes never drift.
            flw = lsw * (1.0 + zw * (1.0 - lsw)) if grossup else lsw
            olivew = np.maximum(0.0, tsw - plw) * flw
            cnt_w = np.zeros(n)
            exp_w = np.zeros(n)
            idx_w = np.zeros(n, dtype=int)
            fcnt = np.zeros(n)
            fexp = np.zeros(n)
            fidx = np.zeros(n, dtype=int)
            for i, m in enumerate(eligible):
                coh = _cohort_of(src_knob, group[m])
                ck = (coh, window) + _state_key(cond_knob, window, m, st_dict)  # observed cell
                c, e = cells[ck]
                cnt_w[i], exp_w[i] = c, e
                if ck not in distinct:
                    distinct[ck] = len(cell_ce)
                    cell_ce.append((c, e))
                idx_w[i] = distinct[ck]
                if window == "2H":                          # open-play floor cell (decay FLOOR)
                    fk = ("__regular__", coh)
                    fc, fe = cells[fk]
                    fcnt[i], fexp[i] = fc, fe
                    if fk not in distinct:
                        distinct[fk] = len(cell_ce)
                        cell_ce.append((fc, fe))
                    fidx[i] = distinct[fk]
            exp_safe = np.where(exp_w > 0, exp_w, 1.0)
            ts_arr[window], played_arr[window], ls_arr[window], fl_arr[window] = tsw, plw, lsw, flw
            z_arr[window] = zw
            olive[window] = olivew
            lam[window] = cnt_w / exp_safe * (exp_w > 0)
            cellidx[window] = idx_w
            if window == "2H":
                fexp_safe = np.where(fexp > 0, fexp, 1.0)
                floor2 = fcnt / fexp_safe * (fexp > 0)      # per-match open-play floor rate
                flooridx2 = fidx

        # 2H decay: grossed omitted clock T = olive_2H / live_share_2H (off -> raw omitted clock;
        # on -> one-pass grossed clock), guarding live_share > 0. obs2 = observed 2H rate per match.
        ls2 = ls_arr["2H"]
        ls2_safe = np.where(ls2 > 0, ls2, 1.0)
        T2 = np.where(ls2 > 0, olive["2H"] / ls2_safe, 0.0)
        obs2 = lam["2H"]
        avg2 = avg_lambda(T2, h_knob, obs2, floor2)         # decayed average 2H rate per match

        # central (deterministic) mu per window-set; 2H uses the decayed rate, 1H is unchanged.
        mu = {
            "2H_only": avg2 * olive["2H"],
            "1H+2H": lam["1H"] * olive["1H"] + avg2 * olive["2H"],
        }
        central_2h_only[knob_set] = float(p_change(mu["2H_only"]).mean())
        if knob_set == central:
            central_inputs = dict(
                ts1=ts_arr["1H"], pl1=played_arr["1H"], ls1=ls_arr["1H"], z1=z_arr["1H"],
                lam1=lam["1H"], ts2=ts_arr["2H"], pl2=played_arr["2H"], ls2=ls2, z2=z_arr["2H"],
                obs2=obs2, floor2=floor2, T2_grossed=T2)

        # bootstrap: one Jeffreys-Gamma lambda draw per distinct cell per iteration (shared across
        # matches in that cell). The decay is a transform of TWO drawn rates, so the 2H window draws
        # BOTH the observed cell AND the open-play floor cell -> the CI now reflects sampling error
        # in the 73-goal 2H rate AND the 675-goal floor, combined through avg_lambda. Plus the
        # silent_marked estimator-error draw on true_stoppage (which also re-shifts the horizon T2).
        cell_count = np.array([c for c, _ in cell_ce], dtype=float)
        cell_exp = np.array([e for _, e in cell_ce], dtype=float)
        cell_exp_safe = np.where(cell_exp > 0, cell_exp, 1.0)
        cell_valid = (cell_exp > 0).astype(float)
        sigma = sigma_full_min if ts_knob == "silent_marked" else 0.0
        boot = {w: {g: np.empty(B) for g in group_masks} for w in mu}
        # outcome_flip() is pure arithmetic on the drawn mu (no RNG draws), so computing it here
        # does NOT perturb the stream.
        boot_flip = {w: {g: np.empty(B) for g in group_masks} for w in mu}
        for b in range(B):
            g = rng.gamma(cell_count + 0.5, 1.0 / cell_exp_safe) * cell_valid
            lam1 = g[cellidx["1H"]]
            obs2_b, floor2_b = g[cellidx["2H"]], g[flooridx2]
            if sigma > 0:
                E = rng.normal(0.0, sigma, size=n)
                ol1 = np.maximum(0.0, ts_arr["1H"] + E * f1 - played_arr["1H"]) * fl_arr["1H"]
                ol2 = np.maximum(0.0, ts_arr["2H"] + E * f2 - played_arr["2H"]) * fl_arr["2H"]
            else:
                ol1, ol2 = olive["1H"], olive["2H"]
            T2_b = np.where(ls2 > 0, ol2 / ls2_safe, 0.0)   # horizon recomputed per draw (ADR-0024)
            avg2_b = avg_lambda(T2_b, h_knob, obs2_b, floor2_b)
            mub = {"2H_only": avg2_b * ol2, "1H+2H": lam1 * ol1 + avg2_b * ol2}
            for w in mu:
                pcb = p_change(mub[w])
                flipb = outcome_flip(mub[w])
                for gl, mask in group_masks.items():
                    boot[w][gl][b] = pcb[mask].mean()
                    boot_flip[w][gl][b] = flipb[mask].mean()

        for w in mu:
            pc = p_change(mu[w])
            flip = outcome_flip(mu[w])
            for gl, mask in group_masks.items():
                summary_rows.append({
                    "window": w, "group": gl, "knob_set": knob_set,
                    "pct_changed": float(pc[mask].mean()),
                    "pct_outcome_flip": float(flip[mask].mean()),
                    "ci_lo": float(np.quantile(boot[w][gl], 0.025)),
                    "ci_hi": float(np.quantile(boot[w][gl], 0.975)),
                    "flip_ci_lo": float(np.quantile(boot_flip[w][gl], 0.025)),
                    "flip_ci_hi": float(np.quantile(boot_flip[w][gl], 0.975)),
                    "n_matches": int(mask.sum()),
                })
            for m, pcv in zip(eligible, pc):
                per_match_rows.append(
                    {"match_id": m, "window": w, "knob_set": knob_set, "p_change": float(pcv)})

    # geometric (full stoppage-within-stoppage) ceiling rows -- REPORTED, not a swept knob
    # (ADR-0024). Live factor 1 (omitted_live == raw omitted clock; horizon = clock/live_share),
    # the true upper rail above single-pass `on`. Appended to the summary so the ledger traces to a
    # table; deterministic point at the central spec (no CI -- it is a reported bound, not a knob).
    if central_inputs:
        for w in mu:
            summary_rows.append({
                "window": w, "group": "all",
                "knob_set": "silent_marked|overall|pooled_all|hl=4.0|geometric",
                "pct_changed": _geom_ceiling(w, central_inputs),
                "pct_outcome_flip": float("nan"),
                "ci_lo": float("nan"), "ci_hi": float("nan"),
                "flip_ci_lo": float("nan"), "flip_ci_hi": float("nan"),
                "n_matches": int(group_masks["all"].sum()),
            })

    # group-stage vs knockout lambda-source robustness rows (ADR-0033) -- REPORTED, not a swept knob.
    # Same recipe as the geometric ceiling: deterministic point at the central spec, computed AFTER the
    # main grid so it never perturbs the locked bootstrap RNG stream (ADR-0031). The omitted-live
    # minutes / decay horizon are lambda-source independent (reused from central_inputs); only the
    # cohort goal RATES swap in. Excluded from the one-at-a-time band / joint envelope (which restrict
    # to the four pooled/regime sources), so this row reports a span without re-centering the headline.
    if central_inputs:
        def _scalar(ck):
            c, e = cells[ck]
            return c / e if e > 0 else float("nan")
        for src, coh in (("pooled_group", "group"), ("pooled_elim", "elim")):
            lam1_s = _scalar((coh, "1H", "overall", "all"))
            obs2_s = _scalar((coh, "2H", "overall", "all"))
            floor_s = _scalar(("__regular__", coh))
            for w in mu:
                summary_rows.append({
                    "window": w, "group": "all",
                    "knob_set": f"silent_marked|overall|{src}|hl=4.0|on",
                    "pct_changed": _stage_x(w, central_inputs, lam1_s, obs2_s, floor_s),
                    "pct_outcome_flip": float("nan"),
                    "ci_lo": float("nan"), "ci_hi": float("nan"),
                    "flip_ci_lo": float("nan"), "flip_ci_hi": float("nan"),
                    "n_matches": int(group_masks["all"].sum()),
                })

    summary = pd.DataFrame(summary_rows)
    per_match = pd.DataFrame(per_match_rows)
    per_match.to_parquet(config.PROCESSED / "counterfactual.parquet", index=False)
    summary.to_parquet(config.PROCESSED / "counterfactual_summary.parquet", index=False)

    # decay_profile: the central spec's per-match grossed omitted-2H CLOCK (decay horizon T) +
    # the obs/floor rates, so the s09 decay figure traces to a checkpointed table (CLAUDE.md
    # standard of proof). olive_2H = T2_grossed * live_share_2H (gross-up ON, the central).
    if central_inputs:
        ci = central_inputs
        pd.DataFrame({
            "match_id": eligible,
            "omitted_2h_clock_min": ci["T2_grossed"],
            "live_share_2h": ci["ls2"],            # Method 2: SAME-HALF 2H live share (ADR-0029)
            "z_half_2h": ci["z2"],                 # Method 2: per-match 2H gross-up z (ADR-0029)
            "omitted_2h_live_min": ci["T2_grossed"] * ci["ls2"],
            "obs_rate": ci["obs2"],
            "floor_rate": ci["floor2"],
        }).to_parquet(config.PROCESSED / "decay_profile.parquet", index=False)

    # ---- print the headline-window sensitivity grid + the IMPL-8 bands -------------------
    hl = summary[(summary["window"] == headline_window) & (summary["group"] == "all")].copy()
    print(f"\n  HEADLINE WINDOW = {headline_window}  (X% = mean P[>=1 extra goal]); group=all "
          f"({len(hl)} knob_sets):")
    for _, r in hl.sort_values("pct_changed").iterrows():
        star = "  <- CENTRAL" if r["knob_set"] == central else ""
        print(f"    {r['knob_set']:<52} X={r['pct_changed']:6.3f}  "
              f"ci=[{r['ci_lo']:.3f},{r['ci_hi']:.3f}]  flip={r['pct_outcome_flip']:.3f}{star}")

    c_all = hl[hl["knob_set"] == central]
    if not c_all.empty:
        r = c_all.iloc[0]
        print(f"\n  CENTRAL ({central}): {headline_window} X={r['pct_changed']:.3f} "
              f"ci=[{r['ci_lo']:.3f},{r['ci_hi']:.3f}]; 2H_only X={central_2h_only[central]:.3f}; "
              f"outcome-flip {r['pct_outcome_flip']:.3f} ci=[{r['flip_ci_lo']:.3f},{r['flip_ci_hi']:.3f}]")

    # IMPL-8 (ADR-0024): the half-life sweep [2,8]min IS the reported productivity band (replaces the
    # old observed/open_play rails); gross-up ON is the central. h=inf/0.0 back out the OLD rails.
    def at(silent, hlf, gw, win):
        q = summary[(summary["group"] == "all") & (summary["window"] == win) &
                    (summary["knob_set"] == f"{silent}|overall|pooled_all|hl={hlf}|{gw}")]
        return q.iloc[0] if not q.empty else None
    print("\n  DECAY HALF-LIFE BAND (silent_marked|overall|pooled_all, gross-up ON):")
    for win in (headline_window, "2H_only"):
        ceil, mid, floor = at("silent_marked", 8.0, "on", win), at("silent_marked", 4.0, "on", win), \
            at("silent_marked", 2.0, "on", win)
        if mid is not None:
            print(f"    {win:<7}  h2(FLOOR) {floor['pct_changed']:.3f} .. h4(CENTRAL) "
                  f"{mid['pct_changed']:.3f} ci=[{mid['ci_lo']:.3f},{mid['ci_hi']:.3f}] .. "
                  f"h8(CEIL) {ceil['pct_changed']:.3f}")
    print("  ENDPOINT REGRESSION (gross-up OFF; must back out the OLD two rails):")
    for win in (headline_window, "2H_only"):
        no_decay = at("silent_marked", float("inf"), "off", win)   # = old `observed` rail
        instant = at("silent_marked", 0.0, "off", win)            # = old `open_play` floor (2H only exact)
        if no_decay is not None and instant is not None:
            print(f"    {win:<7}  h=inf(=observed) {no_decay['pct_changed']:.3f} .. "
                  f"h=0(=open_play) {instant['pct_changed']:.3f}")
    print("  GROSS-UP RAILS (silent_marked|overall|pooled_all, h=4 central):")
    for win in (headline_window, "2H_only"):
        off, on = at("silent_marked", 4.0, "off", win), at("silent_marked", 4.0, "on", win)
        geom = _geom_ceiling(win, central_inputs) if central_inputs else float("nan")
        if off is not None and on is not None:
            print(f"    {win:<7}  off {off['pct_changed']:.3f} -> on(CENTRAL) {on['pct_changed']:.3f} "
                  f"-> geometric-ceiling {geom:.3f}")

    print(f"\n  wrote counterfactual.parquet ({len(per_match)} rows), counterfactual_summary.parquet, "
          f"decay_profile.parquet")
    print("  STOP: read the sensitivity grid above before locking a single X% in decisions.md.")


if __name__ == "__main__":
    main()
