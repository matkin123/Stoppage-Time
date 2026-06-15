"""Generate the precise time-played board from StatsBomb half-end timestamps.

Item 1 redefined the "board" as the *precise time actually played* in each regulation
half (Nate Silver's "ACTUAL" column), not the fourth-official announced integer. The old
ESPN scrape (``scrape_board_espn.py``) could only ever read added time to the whole minute
-- ESPN freezes its clock at 45:00 / 90:00 during added time and the one feed with real
seconds (broadcast wallclock) is corrupt on ~half the period-boundary markers. Whole-minute
labels over-read Nate by ~1.5 min and cap correlation at r=0.943, so they cannot hit the
Item 1 gate (r>0.95, MAE<0.5).

StatsBomb's ``Half End`` event carries a second-level timestamp at the referee's whistle.
s02 already surfaces it as ``p1_end_s`` / ``p2_end_s`` on matches.parquet, so the precise
played board is just ``period_end_s - 2700`` (regulation half = 2700s). Validated against
Nate's 32 published WC2018 matches: MAE 0.135 min (~8s), bias +0.10 min, r=0.992 -- a
second-level, all-six-tournament, fully local source with no scrape.

Run:  python -m src.board_statsbomb     (writes data/raw/board/board_added_time.csv)
Then: python run.py --stage 06a         (joins onto matches; reference-band check)
"""
from __future__ import annotations

import pandas as pd

from src.lib import config

REG_HALF_S = 2700  # regulation half length; added time = period_end_s - REG_HALF_S


def main() -> None:
    config.ensure_dirs()
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")

    rows = []
    for r in matches.itertuples(index=False):
        for period, end_s in ((1, r.p1_end_s), (2, r.p2_end_s)):
            if pd.isna(end_s):
                continue
            board_min = max(0.0, (end_s - REG_HALF_S) / 60.0)
            rows.append({
                "date": r.date, "home": r.home, "away": r.away,
                "period": period, "board_min": round(board_min, 4), "source": "statsbomb",
            })

    out = pd.DataFrame(rows, columns=["date", "home", "away", "period", "board_min", "source"])
    out.to_csv(config.RAW_BOARD / "board_added_time.csv", index=False)

    per = out.groupby(["date", "home", "away"])["board_min"].sum()
    print(f"  wrote {len(out)} board rows for {len(per)} matches -> "
          f"{config.RAW_BOARD / 'board_added_time.csv'}")
    print(f"  mean total time-played/match: {per.mean():.2f} min")


if __name__ == "__main__":
    main()
