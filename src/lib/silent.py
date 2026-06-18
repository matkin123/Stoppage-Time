"""Marker-gated silent-gap classifier (IMPL-2) -- the shared live/dead refinement.

A "silent gap" is a long inter-event interval with NO restart `play_pattern` at its
trailing edge. Timing alone can't tell a real stoppage (injury, VAR, melee) from sparse
logging of live play (slow build-up, keeper holding under no pressure, an off-camera
stretch). The old rule credited every gap >= `max_live_gap_s` as dead, which systematically
inflated low-injury matches (Germany-Sweden et al.).

The fix: a silent gap is DEAD only when its LEAD edge event carries a StatsBomb
ball-out-of-play marker -- the discrete signal that the ball actually left play. Otherwise
it is live-but-sparsely-logged and credited as in-play. This module supplies the marker test;
`src/lib/bip.build_segments` consumes it as the one live/dead classifier feeding BOTH s03 BIP
and the s05 true-stoppage estimator.

Markers (any one, on the lead-edge event):
  - `out=True`                            (ball flagged out on a Pass/Carry/Shot/Clearance/...)
  - `pass_outcome` in out-of-play set     ("Out", "Injury Clearance")
  - `shot_outcome` in out-of-play set     ("Off T", "Saved Off Target", "Wayward", "Blocked", "Goal")
  - `type` in out-of-play set             ("Foul Committed", "Offside", "Bad Behaviour",
                                           "Substitution", "Player Off", "Injury Stoppage",
                                           "Referee Ball-Drop", "Half End")

Special case (B), applied in bip.build_segments: a keeper-held event
(`gk_type` in {"Collected","Smother","Pick-up"}) with NO `out` on the next touch is the
keeper legally holding a LIVE ball (6-second rule) -- the gap stays live regardless of markers.
"""
from __future__ import annotations

import pandas as pd


def lead_edge_out_of_play(events: pd.DataFrame, cfg: dict) -> pd.Series:
    """Boolean Series (aligned to `events`): does each event carry an out-of-play marker?"""
    out = events["out"].fillna(False).astype(bool)
    pass_out = events["pass_outcome"].isin(cfg["out_of_play_pass_outcomes"])
    shot_out = events["shot_outcome"].isin(cfg["out_of_play_shot_outcomes"])
    type_out = events["type"].isin(cfg["out_of_play_types"])
    return out | pass_out | shot_out | type_out


def gk_holding(events: pd.DataFrame, cfg: dict) -> pd.Series:
    """Boolean Series (aligned to `events`): is each event a keeper holding the ball?"""
    return events["gk_type"].isin(cfg["gk_hold_types"])


def _silent_intervals(
    period_events: pd.DataFrame, restart_patterns: set[str], cfg: dict, require_marker: bool
) -> list[tuple[float, float]]:
    """Silent gaps for ONE period's events (period_s coords).

    A "silent gap" is a >= `min_silent_gap_s` inter-event interval that is NOT a restart-
    boundary gap (its trailing possession does not begin with a restart pattern). With
    `require_marker=True` (the IMPL-3 estimator / `silent_marked` knob) a gap is credited
    ONLY when its LEAD edge carries an out-of-play marker -- the discrete signal the ball
    really left play -- EXCEPT a keeper legally holding a LIVE ball (a gk-hold event whose
    next touch is not flagged `out`); the unmarked gaps are dropped because they are a flat,
    non-addable ~8.4 min/match baseline (crediting them is the over-count). With
    `require_marker=False` (the `silent_all` upper-bound knob) EVERY silent gap is credited
    -- the old over-counter, kept only so s08 can show the headline's sensitivity to this.
    """
    g = period_events.sort_values(["period_s", "idx"])
    clocks = g["period_s"].to_numpy()
    patterns = g["play_pattern"].fillna("").to_numpy()
    poss = g["possession"].to_numpy()
    marker = lead_edge_out_of_play(g, cfg).to_numpy()
    gkhold = gk_holding(g, cfg).to_numpy()
    outflag = g["out"].fillna(False).astype(bool).to_numpy()
    ivals: list[tuple[float, float]] = []
    for i in range(len(clocks) - 1):
        t0, t1 = float(clocks[i]), float(clocks[i + 1])
        gap = t1 - t0
        if gap < cfg["min_silent_gap_s"]:
            continue
        if poss[i + 1] != poss[i] and patterns[i + 1] in restart_patterns:
            continue  # restart-boundary gap -> normal-flow dead, not a silent gap
        if require_marker:
            if gkhold[i] and not outflag[i + 1]:
                continue  # keeper holding a live ball (6-second rule) -> stays live
            if not marker[i]:
                continue
        ivals.append((t0, t1))
    return ivals


def marked_silent_intervals(
    period_events: pd.DataFrame, restart_patterns: set[str], cfg: dict
) -> list[tuple[float, float]]:
    """Marker-gated silent gaps (IMPL-3 estimator / `silent_marked` knob). See _silent_intervals."""
    return _silent_intervals(period_events, restart_patterns, cfg, require_marker=True)


def all_silent_intervals(
    period_events: pd.DataFrame, restart_patterns: set[str], cfg: dict
) -> list[tuple[float, float]]:
    """ALL silent gaps, ungated (`silent_all` upper-bound knob). See _silent_intervals."""
    return _silent_intervals(period_events, restart_patterns, cfg, require_marker=False)
