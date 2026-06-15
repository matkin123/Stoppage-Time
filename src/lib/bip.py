"""Ball-in-play reconstruction via the gap method (the s03 keystone).

Dead time = the gap from the last event of a possession to the FIRST event of the next
possession, when that next possession begins with a restart `play_pattern` (From Throw In
/ Corner / Free Kick / Goal Kick / Kick Off / Keeper). Everything else -- intervals
within a possession, and possession changes during live play (Regular Play / From Counter)
-- is in-play.

CRITICAL gotcha: StatsBomb sets `play_pattern` on EVERY event of a possession, not just
its restart. So a restart pattern must only be read at a possession boundary; intra-
possession intervals are always live regardless of the (inherited) pattern label.

We operate on the normalized events of a single match (one row per event, with
`period`, `period_s`, and `possession`). Segments are built per period and never cross
a period boundary.
"""
from __future__ import annotations

import pandas as pd


def build_segments(
    match_events: pd.DataFrame,
    restart_patterns: set[str],
    min_dead_gap_s: float = 0.0,
    max_live_gap_s: float = float("inf"),
) -> pd.DataFrame:
    """One match's normalized events -> contiguous in_play/dead segments per period.

    An interval is dead if EITHER (a) it crosses into a new possession that begins with a
    restart pattern (gap >= min_dead_gap_s), OR (b) the gap is >= max_live_gap_s -- a
    silent stretch too long to be live play (injury / VAR / slow restart within a
    possession), which the restart-pattern rule alone misses.

    Coordinates are within-period seconds (period_s); gaps are always computed within a
    single period, so the absolute offset is irrelevant and phase/bucket logic lines up
    with the 45'/90' marks. Returns columns: period, start_s, end_s, in_play (bool).
    """
    segs: list[dict] = []
    for period, grp in match_events.sort_values(["period", "period_s", "idx"]).groupby(
        "period", sort=True
    ):
        clocks = grp["period_s"].to_numpy()
        patterns = grp["play_pattern"].fillna("").to_numpy()
        poss = grp["possession"].to_numpy()
        if len(clocks) < 2:
            continue
        # Classify each inter-event interval. An interval is dead only at a possession
        # boundary whose NEW possession begins with a restart pattern -- i.e. the ball
        # had gone out of play and is being put back in. Intra-possession intervals and
        # live turnovers (Regular Play / From Counter) are in-play.
        raw: list[tuple[float, float, bool]] = []
        for i in range(len(clocks) - 1):
            t0, t1 = float(clocks[i]), float(clocks[i + 1])
            if t1 <= t0:
                continue
            gap = t1 - t0
            boundary = poss[i + 1] != poss[i]
            is_restart = boundary and patterns[i + 1] in restart_patterns
            dead = (is_restart and gap >= min_dead_gap_s) or (gap >= max_live_gap_s)
            raw.append((t0, t1, not dead))  # in_play = not dead
        # Merge adjacent intervals sharing the same in_play flag.
        for t0, t1, in_play in raw:
            if segs and segs[-1]["period"] == period and segs[-1]["in_play"] == in_play \
                    and abs(segs[-1]["end_s"] - t0) < 1e-6:
                segs[-1]["end_s"] = t1
            else:
                segs.append(
                    {"period": int(period), "start_s": t0, "end_s": t1, "in_play": in_play}
                )
    return pd.DataFrame(segs, columns=["period", "start_s", "end_s", "in_play"])


def phase_of(period_s: float, period: int, params: dict) -> str:
    """Map a within-period position to a phase label.

    {regular, 1H_stoppage (period_s>=45:00 in P1), 2H_stoppage (period_s>=45:00 in P2,
    i.e. the 90' mark), extra_time}. extra_time is added beyond the spec's three labels so
    knockout ET is not misattributed to regulation buckets (logged in docs/decisions.md).
    """
    thr = params["phases"]["half_stoppage_s"]
    if period == 1 and period_s >= thr:
        return "1H_stoppage"
    if period == 2 and period_s >= thr:
        return "2H_stoppage"
    if period >= 3:
        return "extra_time"
    return "regular"


def bucket_of(period_s: float, period: int, params: dict) -> int:
    """Within-period seconds -> non-overlapping 10-min match bucket index.

    P1 -> 0..4 (last is 40-45), P2 -> 5..9 (45-55 .. 85-90), ET -> 10+. Stoppage time
    falls in the trailing bucket of its half but is separated out via `phase`.
    """
    n = params["phases"]["bucket_minutes"] * 60
    within = min(int(period_s // n), 4) if period <= 2 else int(period_s // n)
    base = (period - 1) * 5 if period <= 2 else 10
    return base + within


def allocate_live_seconds(segments: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Split in-play segments (within-period coords) at bucket + phase boundaries; sum
    live seconds. Returns columns: bucket, phase, live_seconds.
    """
    bucket_s = params["phases"]["bucket_minutes"] * 60
    thr = params["phases"]["half_stoppage_s"]
    rows: list[dict] = []
    for s in segments[segments["in_play"]].itertuples(index=False):
        start, end, period = float(s.start_s), float(s.end_s), int(s.period)
        bps = {start, end}
        b = (int(start // bucket_s) + 1) * bucket_s
        while b < end:
            bps.add(float(b))
            b += bucket_s
        if period <= 2 and start < thr < end:
            bps.add(float(thr))
        pts = sorted(bps)
        for a, c in zip(pts[:-1], pts[1:]):
            if c <= a:
                continue
            mid = (a + c) / 2
            rows.append(
                {
                    "bucket": bucket_of(mid, period, params),
                    "phase": phase_of(mid, period, params),
                    "live_seconds": c - a,
                }
            )
    if not rows:
        return pd.DataFrame(columns=["bucket", "phase", "live_seconds"])
    out = pd.DataFrame(rows)
    return out.groupby(["bucket", "phase"], as_index=False)["live_seconds"].sum()
