"""Guards for the Nate 538 ground truth + validation harness (src/lib/nate.py).

These prove the scaffolding the IMPL sessions depend on is correct BEFORE any of them run:
  1. the 32-match table parses and is internally consistent with 538's printed DIFF,
  2. all 32 reconcile to wc_2018 match_ids (catches any name/orientation drift), and
  3. end-to-end: the harness reproduces the already-validated board-vs-ACTUAL fit (r=0.992,
     MAE 0.135 min from ADR-0011) -- so a green test here means the data, the reconciliation,
     and the metric are all wired correctly.

Tests 1-2 need no pipeline outputs. Test 3 needs interim/played_in_stoppage.parquet; it skips
(rather than fails) if that file is absent, so the harness can be developed without data.
"""
import math

import pytest

from src.lib import nate


def test_table_parses_and_diff_is_consistent():
    df = nate.load_nate()
    assert len(df) == 32
    # 538's printed DIFF = actual - expected (minutes). Confirms we transcribed the right columns.
    for r in df.itertuples():
        recomputed = (r.actual_s - r.expected_s) / 60.0
        assert abs(recomputed - r.diff_min) <= 0.06, f"{r.home}-{r.away}: {recomputed:.2f} vs {r.diff_min}"


def test_expected_mean_is_the_13_2_min_level():
    # Sanity that 'expected' is the estimator target (~13.2 min), not 'actual' (~7 min).
    df = nate.load_nate()
    assert 12.5 <= df["expected_s"].mean() / 60.0 <= 13.9
    assert 6.0 <= df["actual_s"].mean() / 60.0 <= 7.5


def test_all_32_reconcile_to_match_ids():
    rec = nate.reconcile()
    assert len(rec) == 32
    assert rec["match_id"].notna().all()
    assert rec["match_id"].nunique() == 32  # no pair collisions


def test_harness_reproduces_validated_board_fit():
    pytest.importorskip("pandas")
    from src.lib import config

    if not (config.INTERIM / "played_in_stoppage.parquet").exists():
        pytest.skip("played_in_stoppage.parquet not built; run s06a first")
    if not (config.INTERIM / "matches.parquet").exists():
        pytest.skip("matches.parquet not built")

    board = nate.board_total_minutes()
    m = nate.metric(board, nate.truth_minutes("actual"))
    # ADR-0011 validated the board at MAE 0.135 min, r=0.992 vs Nate ACTUAL. Reproduce it.
    assert m["n"] == 32
    assert m["r"] > 0.95, m
    assert m["mae"] < 0.5, m
    assert not math.isnan(m["r"])
