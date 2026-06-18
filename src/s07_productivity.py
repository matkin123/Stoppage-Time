"""s07 -- Productivity & descriptive tables.

Productivity = events per live-minute, with exact Poisson 95% CIs on every cell:
  - goals / shots / shots-on-target per live-minute, by 10-min bucket and by phase
    (stoppage phases separate), per tournament / per group / pooled.
  - 2H-stoppage productivity by state_at_90 (tied / non-tied / overall).
Also writes the measured stoppage live-share (feeds s08) and, if board data exists,
PRE-vs-POST board descriptives.

In:  interim/{events_norm,goals,match_minutes,bip_segments,match_state,matches}.parquet
     interim/played_in_stoppage.parquet (optional)
Out: processed/productivity.parquet, processed/stoppage_live_share.parquet,
     processed/played_in_stoppage_descriptive.parquet (if data present)
Gate: every productivity cell reports n_events and live_minutes alongside the rate;
      stoppage live-share (1H + 2H) equals the match_minutes ledger live-seconds (DC1).
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


def stoppage_live_share(seg, tour_of, thr):
    """Per-match live/total seconds in each added-time window {1H_stoppage, 2H_stoppage,
    any_stoppage}, splitting each segment at the 45:00/90:00 boundary so a segment straddling
    the mark contributes only its post-mark portion. This mirrors bip.allocate_live_seconds
    (which feeds the productivity ledger via match_minutes), so the live-seconds here equal the
    match_minutes stoppage live-seconds -- ONE exposure table for both lambda and productivity
    (DC1). The old version keyed on the segment-START phase label, which mis-assigned every
    boundary-straddling segment and undercounted 2H live (811 vs 894.5 team-min)."""
    rows = []
    for mid, g in seg.groupby("match_id"):
        acc = {"1H_stoppage": [0.0, 0.0], "2H_stoppage": [0.0, 0.0]}  # [total_s, live_s]
        for s in g.itertuples(index=False):
            per = int(s.period)
            if per not in (1, 2) or float(s.end_s) <= thr:
                continue
            dur = float(s.end_s) - max(float(s.start_s), thr)
            if dur <= 0:
                continue
            win = "1H_stoppage" if per == 1 else "2H_stoppage"
            acc[win][0] += dur
            if s.in_play:
                acc[win][1] += dur
        a1, a2 = acc["1H_stoppage"], acc["2H_stoppage"]
        for win, (tot, live) in (
            ("1H_stoppage", a1), ("2H_stoppage", a2),
            ("any_stoppage", [a1[0] + a2[0], a1[1] + a2[1]]),
        ):
            rows.append({
                "match_id": mid, "tournament": tour_of.get(mid),
                "phase": win, "stoppage_seconds": tot, "live_seconds": live,
                "live_share": (live / tot) if tot > 0 else np.nan,
            })
    return pd.DataFrame(rows)


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

    # --- measured stoppage live-share (feeds s08), split at the half boundary (DC1) ---
    thr = p["phases"]["half_stoppage_s"]
    tour_of = matches.set_index("match_id")["tournament"].to_dict()
    live_share = stoppage_live_share(seg, tour_of, thr)
    live_share.to_parquet(config.PROCESSED / "stoppage_live_share.parquet", index=False)

    # DC1: lambda exposure (live_share live-seconds) and productivity (match_minutes
    # live-seconds) must come from ONE table. Assert they agree per (match, stoppage window).
    canon = (live_share[live_share["phase"].isin(["1H_stoppage", "2H_stoppage"])]
             .set_index(["match_id", "phase"])["live_seconds"])
    ledger = (mm[mm["phase"].isin(["1H_stoppage", "2H_stoppage"])]
              .groupby(["match_id", "phase"])["live_seconds"].sum())
    keys = set(canon.index) | set(ledger.index)
    max_diff = max((abs(float(canon.get(k, 0.0)) - float(ledger.get(k, 0.0))) for k in keys),
                   default=0.0)
    if max_diff > 1e-6:
        raise SystemExit(
            f"s07 DC1 FAILED: stoppage live-seconds disagree with match_minutes by {max_diff:.4f}s"
        )
    for win in ("1H_stoppage", "2H_stoppage"):
        pooled = live_share[live_share["phase"] == win]["live_share"].mean()
        print(f"\n  measured {win} live-share (pooled mean): {pooled:.3f}")
    print(f"  DC1 OK: stoppage live-seconds == match_minutes ledger (max diff {max_diff:.2e}s)")

    # --- played-in-stoppage descriptive (optional; DC2 rename of "board") ---
    pis_path = config.INTERIM / "played_in_stoppage.parquet"
    if pis_path.exists():
        pis = pd.read_parquet(pis_path)
        per_match = (pis.groupby(["match_id", "group"])["played_in_stoppage_min"]
                     .sum().reset_index())
        desc = per_match.groupby("group")["played_in_stoppage_min"].agg(["mean", "median", "count"])
        desc.to_parquet(config.PROCESSED / "played_in_stoppage_descriptive.parquet")
        print("  played-in-stoppage PRE vs POST (min/match):")
        print(desc.to_string())
    else:
        print("  (played-in-stoppage data absent -- run s06a to add PRE/POST descriptives)")

    # ---- gate ------------------------------------------------------------
    bad = productivity[productivity["n_events"].isna() | productivity["live_minutes"].isna()]
    print(f"\n  productivity rows: {len(productivity)}")
    if len(bad):
        raise SystemExit(f"s07 GATE FAILED: {len(bad)} cells missing n_events/live_minutes")
    print("  s07 gate PASSED (every cell reports n_events and live_minutes)")


if __name__ == "__main__":
    main()
