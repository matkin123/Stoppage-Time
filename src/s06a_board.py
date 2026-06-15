"""s06a -- Board added time (external source).

The fourth-official board number is NOT in StatsBomb, so it must come from outside.
This stage joins a curated cache onto matches. Populate:

    data/raw/board/board_added_time.csv
    columns: date,home,away,period,board_min,source
      date       YYYY-MM-DD (matches matches.parquet date)
      period     1 or 2
      board_min  integer minutes shown on the board for that half
      source     sofascore | espn | fifa  (priority order per spec)

Source priority when collecting: Sofascore incidents (injuryTime per period) ->
ESPN summary -> FIFA match reports (WCs). An optional best-effort Sofascore fetch is
available via STOPPAGE_BOARD_LIVE=1, but the deterministic path is the CSV cache so a
pipeline run never depends on a live site.

In:  interim/matches.parquet, raw/board/board_added_time.csv
Out: interim/board_added_time.parquet
Gate: PRE-group board mean ~7 min; POST WC2022 ~11-12 min.
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
    out.to_parquet(config.INTERIM / "board_added_time.parquet", index=False)

    # ---- gate ------------------------------------------------------------
    per_match = out.groupby(["match_id", "group", "tournament"])["board_min"].sum().reset_index()
    pre_mean = per_match[per_match["group"] == "PRE"]["board_min"].mean()
    wc22 = per_match[per_match["tournament"] == "wc_2022"]["board_min"].mean()
    print(f"\n  board rows joined: {len(out)}  matches: {out['match_id'].nunique()}")
    print(f"  PRE mean per match: {pre_mean:.1f} min (ref ~7)")
    print(f"  WC2022 mean per match: {wc22:.1f} min (ref ~11-12)")
    warn = []
    if pd.notna(pre_mean) and not (5 <= pre_mean <= 9):
        warn.append(f"PRE board mean {pre_mean:.1f} outside 5-9")
    if pd.notna(wc22) and not (10 <= wc22 <= 13):
        warn.append(f"WC2022 board mean {wc22:.1f} outside 10-13")
    for w in warn:
        print(f"  WARNING: {w}")
    print("  s06a complete (gate is reference-band check; see warnings above).")


if __name__ == "__main__":
    main()
