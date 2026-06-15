"""Match-clock helpers.

Two distinct time coordinates, kept separate on purpose:

* period_s  -- seconds elapsed WITHIN a period (StatsBomb timestamp parsed directly).
              Phase, bucket and stoppage logic key off this, so "45:00" (period_s >= 2700
              in P1) and "90:00" (period_s >= 2700 in P2) map correctly no matter how long
              the first half actually ran.
* clock_s   -- cumulative ELAPSED match time = period_s + sum of the actual lengths of all
              prior periods. Strictly monotonic across the whole match; used for global
              ordering and the s02 monotonic gate. NOT used for the 45/90 thresholds (a
              long first half would otherwise push the elapsed clock past 45:00 before the
              second half even starts -- the period-offset gotcha).
"""
from __future__ import annotations

HALF_STOPPAGE_S = 2700  # 45:00 within a half == the 45'/90' marks


def parse_timestamp(ts: str) -> float:
    """'HH:MM:SS.mmm' (period-relative) -> seconds within the period."""
    h, m, rest = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def cumulative_offsets(period_lengths: dict[int, float]) -> dict[int, float]:
    """{period: within-period length} -> {period: cumulative seconds before it started}."""
    offsets: dict[int, float] = {}
    running = 0.0
    for period in sorted(period_lengths):
        offsets[period] = running
        running += period_lengths[period]
    return offsets
