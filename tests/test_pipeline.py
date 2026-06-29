"""Acceptance gates that depend on pipeline outputs. Each test skips if the relevant
parquet hasn't been produced yet, so `pytest` is green on a fresh checkout and becomes
a real gate as stages complete."""
import pandas as pd
import pytest

from src.lib import config

P = config.params()


def _load(path):
    if not path.exists():
        pytest.skip(f"{path.name} not produced yet")
    return pd.read_parquet(path)


# ---- s01 -----------------------------------------------------------------
def test_s01_match_counts():
    m = _load(config.INTERIM / "matches.parquet")
    t = config.tournaments()
    for tr in t["tournaments"]:
        n = (m["tournament"] == tr["key"]).sum()
        assert n == tr["expected_matches"], f"{tr['key']}: {n} != {tr['expected_matches']}"


# ---- s02 -----------------------------------------------------------------
def test_s02_clock_monotonic():
    e = _load(config.INTERIM / "events_norm.parquet")
    for mid, g in e.groupby("match_id"):
        c = g.sort_values(["period", "clock_s", "idx"])["clock_s"].to_numpy()
        assert (c[1:] >= c[:-1] - 1e-6).all(), f"non-monotonic clock in match {mid}"


# ---- s03 calibration -----------------------------------------------------
def test_s03_wc2022_calibration():
    seg = _load(config.INTERIM / "bip_segments.parquet")
    matches = _load(config.INTERIM / "matches.parquet")
    seg = seg.merge(matches[["match_id", "tournament"]], on="match_id")
    seg["dur"] = seg["end_s"] - seg["start_s"]
    wc = seg[(seg["tournament"] == "wc_2022") & (seg["period"].isin([1, 2]))]
    bip_per_match = wc[wc["in_play"]].groupby("match_id")["dur"].sum().mean()
    target = P["bip"]["calibration_target_s"]
    tol = P["bip"]["calibration_tolerance_s"]
    assert abs(bip_per_match - target) <= tol, f"BIP {bip_per_match:.0f}s vs {target}+-{tol}"


# ---- s05 -----------------------------------------------------------------
def test_s05_lower_bound_below_dead():
    inc = _load(config.INTERIM / "incident_stoppage.parquet")
    seg = _load(config.INTERIM / "bip_segments.parquet")
    seg["dur"] = seg["end_s"] - seg["start_s"]
    dead = seg[~seg["in_play"]].groupby("match_id")["dur"].sum()
    lb = inc.groupby("match_id")["lower_bound_s"].sum()
    for mid, v in lb.items():
        assert v <= dead.get(mid, 0.0) + 1.0, f"match {mid}: lb {v:.0f} > dead {dead.get(mid,0):.0f}"


def test_s05_silent_marked_within_all():
    """The marker-gated silent term is a subset of the ungated upper bound (IMPL-4 brackets
    the irreducible silent uncertainty between these two columns)."""
    inc = _load(config.INTERIM / "incident_stoppage.parquet")
    assert {"silent_marked_s", "silent_all_s"}.issubset(inc.columns)
    assert (inc["silent_marked_s"] <= inc["silent_all_s"] + 1e-6).all()


def test_s05_true_stoppage_estimator():
    """true_stoppage = lower_bound + marked silent + frozen residual, for every match. The
    residual is ERA-CONDITIONAL (ADR-0030): PRE matches use residual_silent_pre_s (celebration
    credited as excess), POST keeps residual_silent_s (full-gap celebration)."""
    ts = _load(config.INTERIM / "true_stoppage.parquet")
    pre_r = float(P["silent"]["residual_silent_pre_s"])
    post_r = float(P["silent"]["residual_silent_s"])
    for gr, r in (("PRE", pre_r), ("POST", post_r)):
        sub = ts[ts["group"] == gr]
        assert (sub["residual_silent_s"] == r).all(), f"{gr} residual != {r}"
    expected = ts["lower_bound_s"] + ts["silent_marked_s"] + ts["residual_silent_s"]
    assert (ts["true_stoppage_s"] - expected).abs().max() < 1e-6


# ---- s07 -----------------------------------------------------------------
def test_s07_every_cell_has_n_and_live():
    prod = _load(config.PROCESSED / "productivity.parquet")
    assert prod["n_events"].notna().all()
    assert prod["live_minutes"].notna().all()


# ---- s08 -----------------------------------------------------------------
def test_s08_silent_knob_brackets_headline():
    """IMPL-6: the silent-treatment knob is the headline's sensitivity axis. Crediting more
    silent dead time can only add omitted minutes -> higher mu -> higher P(change), so for every
    (window, lambda conditioning, source) the central X% is monotonic none <= marked <= all -- a
    guard against mis-wiring the silent columns."""
    s = _load(config.PROCESSED / "counterfactual_summary.parquet")
    allg = s[s["group"] == "all"].copy()
    parts = allg["knob_set"].str.split("|", expand=True)
    allg["silent"], allg["cond"], allg["source"] = parts[0], parts[1], parts[2]
    allg["hl"], allg["gw"] = parts[3], parts[4]
    # the geometric-ceiling row AND the stage-source rows (pooled_group/pooled_elim, ADR-0033) are
    # single reported points (silent_marked only), not swept knobs -- drop them so the silent
    # bracket pivot has all three levels per cell.
    allg = allg[allg["gw"].isin(["off", "on"]) &
                allg["source"].isin(["pooled_all", "pooled_post", "pooled_pre", "regime_matched"])]
    assert {"silent_none", "silent_marked", "silent_all"} <= set(allg["silent"])
    piv = allg.pivot_table(index=["window", "cond", "source", "hl", "gw"],
                           columns="silent", values="pct_changed")
    assert (piv["silent_none"] <= piv["silent_marked"] + 1e-9).all()
    assert (piv["silent_marked"] <= piv["silent_all"] + 1e-9).all()


def test_s08_closed_form_p_change():
    """The IMPL-6 metric P(change)=1-exp(-mu): zero when mu=0, strictly increasing in mu, and
    (since mu=lambda*omitted_live with lambda>=0) strictly increasing in omitted_live. Pure unit
    test of the closed form -- no pipeline outputs needed."""
    import numpy as np

    from src.s08_counterfactual import p_change
    assert p_change(0.0) == 0.0
    mu = np.array([0.0, 0.1, 0.5, 1.0, 3.0])
    pc = p_change(mu)
    assert pc[0] == 0.0 and pc[-1] < 1.0
    assert (np.diff(pc) > 0).all()                      # monotonic in mu
    pc_live = p_change(0.08 * np.array([0.0, 1.0, 2.0, 5.0]))  # lambda * omitted_live
    assert pc_live[0] == 0.0
    assert (np.diff(pc_live) > 0).all()                 # monotonic in omitted_live


def test_s08_avg_lambda_decay():
    """IMPL-8 Method A (ADR-0024): the window-average decayed 2H rate. h->inf reproduces the
    observed rail (no decay), h->0 the open-play floor; the average is bounded in [floor, obs],
    monotone INCREASING in the half-life, and monotone DECREASING in the window length T."""
    import numpy as np

    from src.s08_counterfactual import avg_lambda
    obs, floor = 0.0816, 0.0427
    T = np.array([0.5, 1.0, 3.0, 6.0, 12.0])
    assert np.allclose(avg_lambda(T, float("inf"), obs, floor), obs)        # no decay -> obs
    assert np.allclose(avg_lambda(T, 0.0, obs, floor), floor)               # instant decay -> floor
    assert abs(float(avg_lambda(np.array([1e-9]), 4.0, obs, floor)[0]) - obs) < 1e-4  # T->0 -> obs
    prev = None
    for h in (1.0, 2.0, 4.0, 8.0, 16.0):
        v = avg_lambda(T, h, obs, floor)
        assert (v >= floor - 1e-12).all() and (v <= obs + 1e-12).all()      # bounded
        if prev is not None:
            assert (v >= prev - 1e-12).all()                               # larger h -> higher rate
        prev = v
    assert (np.diff(avg_lambda(T, 4.0, obs, floor)) < 0).all()             # longer window -> lower


def test_s08_decay_endpoints():
    """IMPL-8 gate (ADR-0024/0029): the half-life endpoints back out the decay rails. At h=inf
    (no decay, gross-up off) the grid uses the observed lambda with NO ramp toward floor; at h=0
    (instant decay) the 2H window collapses to the open-play floor. 1H+2H at h=0 is NOT the
    open_play 1H+2H (the decay floors only the 2H window, by design). X% is monotone in the
    half-life for the central spec (shorter half-life -> more decay -> lower X%).

    NOTE (re-lock ADR-0031): these rails are the ADOPTED production rails -- Method 2 same-half
    live factors (ls_half/z_half over the whole played half, ADR-0029) AND the PRE-only
    goal-celebration allowance (ADR-0030, residual_silent_pre_s=94.1). The celebration allowance
    credits only the excess over 60s for PRE matches, lowering PRE true_stoppage, so the 'all'
    aggregate rails sit ~0.5 pp BELOW the Method-2-only rails (which were 0.246 / 0.179 / 0.101).
    Refresh these only if same_half_factors, the celebration constants, or the frozen inputs
    change."""
    s = _load(config.PROCESSED / "counterfactual_summary.parquet")
    allg = s[s["group"] == "all"]

    def x(hl, gw, win):
        q = allg[(allg["window"] == win) &
                 (allg["knob_set"] == f"silent_marked|overall|pooled_all|hl={hl}|{gw}")]
        assert not q.empty, f"missing hl={hl}|{gw} {win}"
        return float(q.iloc[0]["pct_changed"])

    # endpoint regression: adopted Method2+celebration rails (ADR-0031). Method-2-only in parens.
    assert abs(x("inf", "off", "1H+2H") - 0.241) < 0.004     # observed rail (Method-2-only 0.246)
    assert abs(x("inf", "off", "2H_only") - 0.175) < 0.004   # (Method-2-only 0.179)
    assert abs(x("0.0", "off", "2H_only") - 0.099) < 0.004   # open_play floor, 2H exact (M2-only 0.101)

    # monotonicity in half-life for the central spec (gross-up on).
    xs = [x(h, "on", "1H+2H") for h in ("0.0", "2.0", "4.0", "8.0", "inf")]
    assert all(b >= a - 1e-9 for a, b in zip(xs, xs[1:])), f"X% not monotone in half-life: {xs}"
