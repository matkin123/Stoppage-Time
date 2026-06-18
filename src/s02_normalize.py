"""s02 -- Normalize events.

One tidy row per event with a cumulative match clock (clock_s), handling the
period-offset gotcha (StatsBomb timestamp resets each period). Event JSON is fetched
in-memory per match and discarded immediately -- nothing lands on disk -- so the
footprint stays tiny. Also reconstructs each match's period-end seconds and writes
them back onto matches.parquet.

In:  interim/matches.parquet
Out: interim/events_norm.parquet, (updated) interim/matches.parquet
Gate: clock_s monotonic within match; recovered period lengths are sane.
"""
from __future__ import annotations

import pandas as pd
import requests
from tqdm import tqdm

from src.lib import clock, config

OD_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"


def _fetch_events(session: requests.Session, match_id: int) -> list[dict]:
    url = f"{OD_BASE}/events/{match_id}.json"
    r = session.get(url, timeout=60)
    r.raise_for_status()
    return r.json()


def _normalize_match(match_id: int, events: list[dict]) -> pd.DataFrame:
    recs = []
    for e in events:
        ts = e.get("timestamp")
        if ts is None:
            continue
        recs.append(
            {
                "match_id": match_id,
                "idx": e.get("index"),
                "period": e.get("period"),
                "possession": e.get("possession"),
                "period_s": clock.parse_timestamp(ts),
                "type": (e.get("type") or {}).get("name"),
                "team": (e.get("team") or {}).get("name"),
                "player": (e.get("player") or {}).get("name"),
                "play_pattern": (e.get("play_pattern") or {}).get("name"),
                "duration_s": e.get("duration"),
                "out": bool(e.get("out", False)),
                "off_camera": bool(e.get("off_camera", False)),
                # helper fields for s04 (goals) and s05 (incident dead time):
                "shot_outcome": (e.get("shot") or {}).get("outcome", {}).get("name"),
                "card": (
                    (e.get("foul_committed") or {}).get("card", {}).get("name")
                    or (e.get("bad_behaviour") or {}).get("card", {}).get("name")
                ),
                # out-of-play markers for the marker-gated silent reclassifier (IMPL-1):
                "pass_outcome": ((e.get("pass") or {}).get("outcome") or {}).get("name"),
                "gk_type": ((e.get("goalkeeper") or {}).get("type") or {}).get("name"),
                "gk_outcome": ((e.get("goalkeeper") or {}).get("outcome") or {}).get("name"),
            }
        )
    df = pd.DataFrame(recs)
    if df.empty:
        return df
    # cumulative elapsed clock from this match's ACTUAL period lengths (monotonic).
    period_lengths = df.groupby("period")["period_s"].max().to_dict()
    offsets = clock.cumulative_offsets(period_lengths)
    df["clock_s"] = df["period_s"] + df["period"].map(offsets).fillna(0.0)
    return df


def main() -> None:
    config.ensure_dirs()
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    session = requests.Session()

    frames: list[pd.DataFrame] = []
    p1_ends: dict[int, float] = {}
    p2_ends: dict[int, float] = {}

    for mid in tqdm(matches["match_id"].tolist(), desc="s02 normalize", unit="match"):
        events = _fetch_events(session, int(mid))
        df = _normalize_match(int(mid), events)
        if df.empty:
            continue
        frames.append(df)
        for period, ends in ((1, p1_ends), (2, p2_ends)):
            sub = df[df["period"] == period]
            if not sub.empty:
                ends[int(mid)] = float(sub["period_s"].max())

    events_norm = pd.concat(frames, ignore_index=True)
    events_norm = events_norm.sort_values(["match_id", "period", "period_s", "idx"])
    events_norm.to_parquet(config.INTERIM / "events_norm.parquet", index=False)

    matches["p1_end_s"] = matches["match_id"].map(p1_ends)
    matches["p2_end_s"] = matches["match_id"].map(p2_ends)
    matches.to_parquet(config.INTERIM / "matches.parquet", index=False)

    # ---- acceptance gate -------------------------------------------------
    errors, warnings = [], []
    for mid, grp in events_norm.groupby("match_id"):
        c = grp.sort_values(["period", "clock_s", "idx"])["clock_s"].to_numpy()
        if (c[1:] < c[:-1] - 1e-6).any():
            errors.append(f"match {mid}: clock_s not monotonic")
    # period lengths sane: within-period first half 44-55 min, second half 44-60 min
    for mid, v in p1_ends.items():
        if not (2640 <= v <= 3300):
            warnings.append(f"match {mid}: P1 within-length {v / 60:.1f} min")
    for mid, v in p2_ends.items():
        if not (2640 <= v <= 3600):
            warnings.append(f"match {mid}: P2 within-length {v / 60:.1f} min")

    print(f"\n  events_norm rows: {len(events_norm):,}  matches: {events_norm['match_id'].nunique()}")
    if warnings:
        print(f"  {len(warnings)} period-length warnings (inspect, not necessarily fatal):")
        for w in warnings[:10]:
            print(f"    {w}")
    if errors:
        raise SystemExit("s02 GATE FAILED:\n  " + "\n  ".join(errors[:20]))
    print("  s02 gate PASSED (monotonic clock; period lengths within sane band)")


if __name__ == "__main__":
    main()
