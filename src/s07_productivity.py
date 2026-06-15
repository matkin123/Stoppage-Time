"""s07 -- Productivity & descriptive tables.

Productivity = events per live-minute, with exact Poisson 95% CIs on every cell:
  - goals / shots / shots-on-target per live-minute, by 10-min bucket and by phase
    (stoppage phases separate), per tournament / per group / pooled.
  - 2H-stoppage productivity by state_at_90 (tied / non-tied / overall).
Also writes the measured stoppage live-share (feeds s08) and, if board data exists,
PRE-vs-POST board descriptives.

In:  interim/{events_norm,goals,match_minutes,bip_segments,match_state,matches}.parquet
     interim/board_added_time.parquet (optional)
Out: processed/productivity.parquet, processed/stoppage_live_share.parquet,
     processed/board_descriptive.parquet (if board data present)
Gate: every productivity cell reports n_events and live_minutes alongside the rate.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.lib import bip, config, stats

ON_TARGET = {"Goal", "Saved", "Saved To Post"}


def _scope_frames(df, matches):
    """Yield (scope_label, sub_df) for pooled, each group, each tournament."""
    t = matches.set_index("match_id")[["tournament", "group"]]
    d = df.merge(t, left_on="match_id", right_index=True, how="left")
    yield "pooled", d
    for grp, sub in d.groupby("group"):
        yield f"group:{grp}", sub
    for tr, sub in d.groupby("tournament"):
        yield f"tournament:{tr}", sub


def _rows_for(scope, dim_col, counts, live_min, state="all"):
    """Build productivity rows joining event counts to live-minutes on a dim key.

    `counts` is a dict metric -> Series(index=dim key, value=count).
    """
    rows = []
    keys = set(live_min.index)
    for s in counts.values():
        keys |= set(s.index)
    for k in sorted(keys, key=str):
        lm = float(live_min.get(k, 0.0))
        for metric in ("goals", "shots", "shots_on_target"):
            n = float(counts[metric].get(k, 0.0))
            rate, lo, hi = stats.poisson_rate_ci(n, lm) if lm > 0 else (np.nan, np.nan, np.nan)
            rows.append({
                "scope": scope, "dimension": dim_col, "phase_or_bucket": str(k),
                "state": state, "metric": metric, "n_events": n,
                "live_minutes": lm, "rate": rate, "ci_lo": lo, "ci_hi": hi,
            })
    return rows


def _counts_by(df, key):
    g = df[df["type"] == "Shot"].copy()
    goals = df[((df["type"] == "Shot") & (df["shot_outcome"] == "Goal")) |
               (df["type"] == "Own Goal For")]
    sot = g[g["shot_outcome"].isin(ON_TARGET)]
    return {
        "goals": goals.groupby(key).size(),
        "shots": g.groupby(key).size(),
        "shots_on_target": sot.groupby(key).size(),
    }


def main() -> None:
    config.ensure_dirs()
    events = pd.read_parquet(config.INTERIM / "events_norm.parquet")
    mm = pd.read_parquet(config.INTERIM / "match_minutes.parquet")
    seg = pd.read_parquet(config.INTERIM / "bip_segments.parquet")
    state = pd.read_parquet(config.INTERIM / "match_state.parquet")
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    p = config.params()

    ev = events[events["period"] < 5].copy()
    ev["bucket"] = [bip.bucket_of(s, per, p) for s, per in zip(ev["period_s"], ev["period"])]
    ev["phase"] = [bip.phase_of(s, per, p) for s, per in zip(ev["period_s"], ev["period"])]

    rows = []
    # --- by bucket and by phase, across scopes ---
    for dim in ("bucket", "phase"):
        for scope, sub_ev in _scope_frames(ev, matches):
            counts = _counts_by(sub_ev, dim)
            mm_scope = next(s for lbl, s in _scope_frames(mm, matches) if lbl == scope)
            live_min = mm_scope.groupby(dim)["live_seconds"].sum() / 60
            rows += _rows_for(scope, dim, counts, live_min)

    # --- 2H-stoppage productivity by state_at_90 ---
    ev2 = ev[ev["phase"] == "2H_stoppage"].merge(
        state[["match_id", "state_at_90"]], on="match_id", how="left"
    )
    ev2["state_grp"] = np.where(ev2["state_at_90"] == "tied", "tied", "non_tied")
    mm2 = mm[mm["phase"] == "2H_stoppage"].merge(
        state[["match_id", "state_at_90"]], on="match_id", how="left"
    )
    mm2["state_grp"] = np.where(mm2["state_at_90"] == "tied", "tied", "non_tied")
    for scope, sub_ev in _scope_frames(ev2, matches):
        mm_scope = next(s for lbl, s in _scope_frames(mm2, matches) if lbl == scope)
        for st in ("tied", "non_tied", "all"):
            e = sub_ev if st == "all" else sub_ev[sub_ev["state_grp"] == st]
            m = mm_scope if st == "all" else mm_scope[mm_scope["state_grp"] == st]
            counts = _counts_by(e, "phase")
            live_min = m.groupby("phase")["live_seconds"].sum() / 60
            rows += _rows_for(scope, "state_2H_stoppage", counts, live_min, state=st)

    productivity = pd.DataFrame(rows)
    productivity.to_parquet(config.PROCESSED / "productivity.parquet", index=False)

    # --- measured stoppage live-share (feeds s08) ---
    seg["dur"] = seg["end_s"] - seg["start_s"]
    seg["tournament"] = seg["match_id"].map(matches.set_index("match_id")["tournament"])
    share_rows = []
    for (mid,), g in seg.groupby(["match_id"]):
        for phase_label, mask in (
            ("2H_stoppage", g["phase"] == "2H_stoppage"),
            ("any_stoppage", g["phase"].isin(["1H_stoppage", "2H_stoppage"])),
        ):
            gg = g[mask]
            tot = gg["dur"].sum()
            live = gg[gg["in_play"]]["dur"].sum()
            share_rows.append({
                "match_id": mid, "tournament": g["tournament"].iloc[0],
                "phase": phase_label, "stoppage_seconds": tot,
                "live_seconds": live,
                "live_share": (live / tot) if tot > 0 else np.nan,
            })
    live_share = pd.DataFrame(share_rows)
    live_share.to_parquet(config.PROCESSED / "stoppage_live_share.parquet", index=False)
    pooled_share = live_share[live_share["phase"] == "2H_stoppage"]["live_share"].mean()
    print(f"\n  measured 2H-stoppage live-share (pooled mean): {pooled_share:.3f}")

    # --- board descriptive (optional) ---
    board_path = config.INTERIM / "board_added_time.parquet"
    if board_path.exists():
        board = pd.read_parquet(board_path)
        per_match = board.groupby(["match_id", "group"])["board_min"].sum().reset_index()
        desc = per_match.groupby("group")["board_min"].agg(["mean", "median", "count"])
        desc.to_parquet(config.PROCESSED / "board_descriptive.parquet")
        print("  board added time PRE vs POST (min/match):")
        print(desc.to_string())
    else:
        print("  (board data absent -- run s06a to add PRE/POST board descriptives)")

    # ---- gate ------------------------------------------------------------
    bad = productivity[productivity["n_events"].isna() | productivity["live_minutes"].isna()]
    print(f"\n  productivity rows: {len(productivity)}")
    if len(bad):
        raise SystemExit(f"s07 GATE FAILED: {len(bad)} cells missing n_events/live_minutes")
    print("  s07 gate PASSED (every cell reports n_events and live_minutes)")


if __name__ == "__main__":
    main()
