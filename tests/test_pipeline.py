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


# ---- s07 -----------------------------------------------------------------
def test_s07_every_cell_has_n_and_live():
    prod = _load(config.PROCESSED / "productivity.parquet")
    assert prod["n_events"].notna().all()
    assert prod["live_minutes"].notna().all()
