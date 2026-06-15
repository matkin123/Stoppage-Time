"""s01 -- Ingest StatsBomb.

Pulls each tournament's match list from StatsBomb open data and writes a tidy
interim/matches.parquet. Event JSON is NOT pulled here: it is streamed per-match in
s02 (parse -> parquet -> delete) to respect the tight disk budget. We never clone the
open-data repo and we never touch 360 data.

Out: raw/statsbomb/matches_<key>.json (immutable cache), interim/matches.parquet
Gate: match counts per competition equal the tournaments.yaml checksums (115 / 199).
"""
from __future__ import annotations

import json

import pandas as pd
import requests

from src.lib import config

OD_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"


def _fetch_matches(competition_id: int, season_id: int) -> list[dict]:
    url = f"{OD_BASE}/matches/{competition_id}/{season_id}.json"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.json()


def _row(m: dict, t: dict) -> dict:
    return {
        "match_id": m["match_id"],
        "tournament": t["key"],
        "competition": t["name"],
        "competition_id": t["competition_id"],
        "season_id": t["season_id"],
        "group": t["group"],
        "date": m.get("match_date"),
        "home": m["home_team"]["home_team_name"],
        "away": m["away_team"]["away_team_name"],
        "ht_score": None,  # filled from events in s04 if needed
        "ft_score": f'{m.get("home_score")}-{m.get("away_score")}',
        "home_score": m.get("home_score"),
        "away_score": m.get("away_score"),
        "stage": (m.get("competition_stage") or {}).get("name"),
        # period ends are reconstructed from events in s02:
        "p1_end_s": pd.NA,
        "p2_end_s": pd.NA,
    }


def main() -> None:
    config.ensure_dirs()
    tcfg = config.tournaments()
    checks = tcfg["group_checksums"]

    rows: list[dict] = []
    per_tournament: dict[str, int] = {}
    for t in tcfg["tournaments"]:
        matches = _fetch_matches(t["competition_id"], t["season_id"])
        cache = config.RAW_SB / f"matches_{t['key']}.json"
        with open(cache, "w") as f:
            json.dump(matches, f)
        n = len(matches)
        per_tournament[t["key"]] = n
        rows.extend(_row(m, t) for m in matches)
        flag = "OK" if n == t["expected_matches"] else "MISMATCH"
        print(f"  {t['key']:<20} {n:>3} matches (expected {t['expected_matches']}) [{flag}]")

    df = pd.DataFrame(rows).sort_values(["tournament", "match_id"]).reset_index(drop=True)
    out = config.INTERIM / "matches.parquet"
    df.to_parquet(out, index=False)

    # ---- acceptance gate -------------------------------------------------
    errors = []
    for t in tcfg["tournaments"]:
        if per_tournament[t["key"]] != t["expected_matches"]:
            errors.append(
                f"{t['key']}: got {per_tournament[t['key']]}, expected {t['expected_matches']}"
            )
    pre = sum(per_tournament[t["key"]] for t in tcfg["tournaments"] if t["group"] == "PRE")
    post = sum(per_tournament[t["key"]] for t in tcfg["tournaments"] if t["group"] == "POST")
    if pre != checks["PRE"]:
        errors.append(f"PRE total {pre} != {checks['PRE']}")
    if post != checks["POST"]:
        errors.append(f"POST total {post} != {checks['POST']}")

    print(f"\n  PRE={pre} POST={post} TOTAL={pre + post}  -> {out}")
    if errors:
        raise SystemExit("s01 GATE FAILED:\n  " + "\n  ".join(errors))
    print("  s01 gate PASSED (match-count checksums)")


if __name__ == "__main__":
    main()
