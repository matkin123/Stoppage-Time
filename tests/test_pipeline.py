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
    """true_stoppage = lower_bound + marked silent + frozen residual, for every match."""
    ts = _load(config.INTERIM / "true_stoppage.parquet")
    r = float(P["silent"]["residual_silent_s"])
    expected = ts["lower_bound_s"] + ts["silent_marked_s"] + r
    assert (ts["residual_silent_s"] == r).all()
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
    assert {"silent_none", "silent_marked", "silent_all"} <= set(allg["silent"])
    piv = allg.pivot_table(index=["window", "cond", "source"], columns="silent",
                           values="pct_changed")
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
