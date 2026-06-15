"""s03 -- Ball-in-play reconstruction (the keystone).

Segments each match into in-play / dead intervals via the gap method (see src/lib/bip.py),
tags phase and 10-min bucket, and allocates live seconds per bucket/phase/match.

In:  interim/events_norm.parquet
Out: interim/bip_segments.parquet, interim/match_minutes.parquet
GATE (calibration -- do not proceed until green): pooled WC2022 reconstructed
regulation ball-in-play within +-90s of Opta's 58:04. If it fails, tune
params.yaml:bip.min_dead_gap_s before trusting anything downstream. Secondary:
pooled in-play share ~55-60%.
"""
from __future__ import annotations

import pandas as pd

from src.lib import bip, config


def main() -> None:
    config.ensure_dirs()
    p = config.params()
    restart = set(p["bip"]["restart_play_patterns"])
    min_gap = float(p["bip"]["min_dead_gap_s"])
    max_live_gap = float(p["bip"]["max_live_gap_s"])

    events = pd.read_parquet(config.INTERIM / "events_norm.parquet")
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    tourn = matches.set_index("match_id")["tournament"].to_dict()

    seg_frames: list[pd.DataFrame] = []
    minute_frames: list[pd.DataFrame] = []

    for mid, grp in events.groupby("match_id"):
        segs = bip.build_segments(grp, restart, min_gap, max_live_gap)
        if segs.empty:
            continue
        segs.insert(0, "match_id", mid)
        segs["phase"] = [
            bip.phase_of(s, per, p) for s, per in zip(segs["start_s"], segs["period"])
        ]
        segs["bucket"] = [
            bip.bucket_of(s, per, p) for s, per in zip(segs["start_s"], segs["period"])
        ]
        seg_frames.append(segs)

        mins = bip.allocate_live_seconds(segs, p)
        mins.insert(0, "match_id", mid)
        minute_frames.append(mins)

    bip_segments = pd.concat(seg_frames, ignore_index=True)
    match_minutes = pd.concat(minute_frames, ignore_index=True)
    bip_segments.to_parquet(config.INTERIM / "bip_segments.parquet", index=False)
    match_minutes.to_parquet(config.INTERIM / "match_minutes.parquet", index=False)

    # ---- calibration gate ------------------------------------------------
    seg = bip_segments.copy()
    seg["dur"] = seg["end_s"] - seg["start_s"]
    seg["tournament"] = seg["match_id"].map(tourn)

    # Regulation only (periods 1-2) to match Opta's 90-min ball-in-play convention.
    reg = seg[seg["period"].isin([1, 2])]
    wc22 = reg[reg["tournament"] == "wc_2022"]
    n_wc22 = wc22["match_id"].nunique()
    inplay_per_match = (
        wc22[wc22["in_play"]].groupby("match_id")["dur"].sum().reindex(
            wc22["match_id"].unique(), fill_value=0.0
        )
    )
    pooled_bip = float(inplay_per_match.mean()) if n_wc22 else float("nan")

    total_per_match = wc22.groupby("match_id")["dur"].sum()
    inplay_share = float(
        wc22[wc22["in_play"]]["dur"].sum() / wc22["dur"].sum()
    ) if not wc22.empty else float("nan")

    target = p["bip"]["calibration_target_s"]
    tol = p["bip"]["calibration_tolerance_s"]
    print(f"\n  WC2022 matches: {n_wc22}")
    print(f"  pooled regulation ball-in-play: {pooled_bip:.0f}s ({pooled_bip / 60:.2f} min)")
    print(f"  Opta target: {target}s ({target / 60:.2f} min)  tolerance +-{tol}s")
    print(f"  pooled in-play share: {inplay_share:.3f} (sane {p['bip']['inplay_share_sane_lo']}-{p['bip']['inplay_share_sane_hi']})")

    if abs(pooled_bip - target) > tol:
        raise SystemExit(
            f"s03 CALIBRATION GATE FAILED: |{pooled_bip:.0f}-{target}| = "
            f"{abs(pooled_bip - target):.0f}s > {tol}s. "
            f"Tune params.yaml:bip.min_dead_gap_s and re-run. STOP -- do not proceed."
        )
    if not (p["bip"]["inplay_share_sane_lo"] <= inplay_share <= p["bip"]["inplay_share_sane_hi"]):
        print("  WARNING: in-play share outside sane band -- inspect before trusting s07+.")
    print("  s03 CALIBRATION GATE PASSED. Confirm the number yourself before continuing.")


if __name__ == "__main__":
    main()
