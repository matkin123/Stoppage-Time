"""Unit tests for the shared libraries (no network, no data files needed)."""
import math

import pandas as pd
import pytest

from src.lib import bip, clock, config, stats


# ---- config --------------------------------------------------------------
def test_tournament_checksums_consistent():
    t = config.tournaments()
    pre = sum(x["expected_matches"] for x in t["tournaments"] if x["group"] == "PRE")
    post = sum(x["expected_matches"] for x in t["tournaments"] if x["group"] == "POST")
    assert pre == t["group_checksums"]["PRE"] == 115
    assert post == t["group_checksums"]["POST"] == 199
    assert pre + post == t["group_checksums"]["TOTAL"] == 314


def test_params_load():
    p = config.params()
    assert p["counterfactual"]["n_bootstrap"] == 1000
    assert p["counterfactual"]["headline_window"] == "1H+2H"
    assert set(p["bip"]["restart_play_patterns"]) >= {"From Throw In", "From Corner"}


# ---- clock ---------------------------------------------------------------
def test_parse_timestamp():
    assert clock.parse_timestamp("00:00:00.000") == 0
    assert clock.parse_timestamp("00:01:30.000") == 90
    assert clock.parse_timestamp("01:02:03.500") == 3723.5


def test_cumulative_offsets_from_actual_lengths():
    # first half ran 56 min (3360s); second half offset should be 3360, not nominal 2700
    offsets = clock.cumulative_offsets({1: 3360.0, 2: 3000.0})
    assert offsets[1] == 0.0
    assert offsets[2] == 3360.0  # monotonic: P2 starts after P1's real end


# ---- bip -----------------------------------------------------------------
def _toy_match():
    # possession 1 (kick off) runs live 0->10; ball goes out; possession 2 restarts from
    # a throw-in at 25 (so 10->25 is dead) and continues live to 30.
    return pd.DataFrame({
        "match_id": [1] * 4,
        "idx": [1, 2, 3, 4],
        "period": [1, 1, 1, 1],
        "possession": [1, 1, 2, 2],
        "period_s": [0.0, 10.0, 25.0, 30.0],
        "play_pattern": ["From Kick Off", "From Kick Off", "From Throw In", "From Throw In"],
    })


def test_build_segments_marks_dead_gap():
    segs = bip.build_segments(_toy_match(), {"From Throw In", "From Kick Off"}, 0.0)
    # interval 10->25 leads into a throw-in => dead
    dead = segs[~segs["in_play"]]
    assert len(dead) == 1
    assert dead.iloc[0]["start_s"] == 10.0 and dead.iloc[0]["end_s"] == 25.0


def test_phase_of():
    p = config.params()
    assert bip.phase_of(100, 1, p) == "regular"      # within-period seconds
    assert bip.phase_of(2800, 1, p) == "1H_stoppage"  # >=45:00 in P1
    assert bip.phase_of(2800, 2, p) == "2H_stoppage"  # >=45:00 in P2 == 90' mark
    assert bip.phase_of(100, 3, p) == "extra_time"


def test_bucket_of_no_half_overlap():
    p = config.params()
    # late first half and early second half must NOT share a bucket index
    assert bip.bucket_of(2500, 1, p) == 4          # 40-45 of P1
    assert bip.bucket_of(100, 2, p) == 5           # first bucket of P2 (45-55)
    assert bip.bucket_of(2500, 2, p) == 9          # 85-90


def test_allocate_splits_on_bucket_boundary():
    segs = pd.DataFrame({
        "period": [1], "start_s": [550.0], "end_s": [650.0], "in_play": [True],
    })
    out = bip.allocate_live_seconds(segs, config.params())
    # 550-600 in bucket 0, 600-650 in bucket 1
    assert set(out["bucket"]) == {0, 1}
    assert math.isclose(out["live_seconds"].sum(), 100.0)


# ---- stats ---------------------------------------------------------------
def test_poisson_rate_ci_basic():
    rate, lo, hi = stats.poisson_rate_ci(10, 5.0)
    assert math.isclose(rate, 2.0)
    assert lo < rate < hi


def test_poisson_rate_ci_zero_count():
    rate, lo, hi = stats.poisson_rate_ci(0, 5.0)
    assert rate == 0.0 and lo == 0.0 and hi > 0.0


def test_poisson_rate_ci_zero_exposure_is_nan():
    rate, lo, hi = stats.poisson_rate_ci(3, 0.0)
    assert math.isnan(rate)
