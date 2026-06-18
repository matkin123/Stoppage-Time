"""s06a -- Played-in-stoppage time (RENAMED from "board"; ADR-0011/0019, DC2).

The quantity in the raw cache is the time the half was ACTUALLY PLAYED past 45:00/90:00
(period_end_s - 2700), produced by `board_statsbomb.py`. It was historically mislabeled
"board"; the announced fourth-official board is a DIFFERENT number we have not sourced yet
(see prompts/research_board.md / R1). This stage renames the measurement to
`played_in_stoppage_min` and reserves a NULL `board_announced` column for that future input.
The raw CSV keeps its original column name (`board_min`) as the immutable measurement layer.

    data/raw/board/board_added_time.csv
    columns: date,home,away,period,board_min,source
      date       YYYY-MM-DD (matches matches.parquet date)
      period     1 or 2
      board_min  minutes actually played past 45:00/90:00 for that half (time-played)
      source     statsbomb | sofascore | espn | fifa

In:  interim/matches.parquet, raw/board/board_added_time.csv
Out: interim/played_in_stoppage.parquet
       columns: ..., played_in_stoppage_min (= raw board_min), board_announced (NULL for now)
Gate: PRE-group played-in-stoppage mean ~7 min; POST WC2022 ~11-12 min.
"""
from __future__ import annotations

import pandas as pd

from src.lib import config

CSV = config.RAW_BOARD / "board_added_time.csv"
TEMPLATE_COLS = ["date", "home", "away", "period", "board_min", "source"]


def _write_template() -> None:
    pd.DataFrame(columns=TEMPLATE_COLS).to_csv(CSV, index=False)


def main() -> None:
    config.ensure_dirs()
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")

    if not CSV.exists():
        _write_template()
        raise SystemExit(
            f"s06a: no board data yet. Wrote a template to {CSV}.\n"
            "  Fill it (date,home,away,period,board_min,source) from Sofascore/ESPN/FIFA,\n"
            "  then re-run s06a. This is the one unavoidable external input."
        )

    board = pd.read_csv(CSV)
    missing = set(TEMPLATE_COLS) - set(board.columns)
    if missing:
        raise SystemExit(f"s06a: board CSV missing columns {missing}")
    if board.empty:
        raise SystemExit(f"s06a: {CSV} is empty -- populate it and re-run.")

    # join on date + teams to recover match_id, tournament, group
    key = matches[["match_id", "tournament", "group", "date", "home", "away"]].copy()
    merged = board.merge(key, on=["date", "home", "away"], how="left")
    unmatched = merged[merged["match_id"].isna()]
    if len(unmatched):
        print(f"  WARNING: {len(unmatched)} board rows did not join to a match (check team spellings):")
        for r in unmatched.head(10).itertuples(index=False):
            print(f"    {r.date} {r.home} vs {r.away}")
    merged = merged.dropna(subset=["match_id"])
    merged["match_id"] = merged["match_id"].astype(int)

    out = merged[
        ["match_id", "tournament", "group", "period", "board_min", "source"]
    ].sort_values(["match_id", "period"])
    # DC2 rename: the measured quantity is time PLAYED in stoppage, not the announced board.
    out = out.rename(columns={"board_min": "played_in_stoppage_min"})
    # board_announced = the true fourth-official number; not sourced yet (R1). NULL placeholder
    # so downstream under-allocation work (IMPL-7) has a column to populate without a schema change.
    out["board_announced"] = pd.NA
    out = out[
        ["match_id", "tournament", "group", "period",
         "played_in_stoppage_min", "board_announced", "source"]
    ]
    out.to_parquet(config.INTERIM / "played_in_stoppage.parquet", index=False)

    # ---- gate ------------------------------------------------------------
    per_match = (out.groupby(["match_id", "group", "tournament"])["played_in_stoppage_min"]
                 .sum().reset_index())
    pre_mean = per_match[per_match["group"] == "PRE"]["played_in_stoppage_min"].mean()
    wc22 = per_match[per_match["tournament"] == "wc_2022"]["played_in_stoppage_min"].mean()
    print(f"\n  played-in-stoppage rows joined: {len(out)}  matches: {out['match_id'].nunique()}")
    print(f"  PRE mean per match: {pre_mean:.1f} min (ref ~7)")
    print(f"  WC2022 mean per match: {wc22:.1f} min (ref ~11-12)")
    warn = []
    if pd.notna(pre_mean) and not (5 <= pre_mean <= 9):
        warn.append(f"PRE played-in-stoppage mean {pre_mean:.1f} outside 5-9")
    if pd.notna(wc22) and not (10 <= wc22 <= 13):
        warn.append(f"WC2022 played-in-stoppage mean {wc22:.1f} outside 10-13")
    for w in warn:
        print(f"  WARNING: {w}")
    print("  s06a complete (gate is reference-band check; see warnings above).")


if __name__ == "__main__":
    main()
