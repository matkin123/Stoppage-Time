"""READ-ONLY audit: top-N StatsBomb matches by owed (true) stoppage.

Ranks the six-tournament matches by `true_stoppage_s`, then for each match
re-derives every window the s05 estimator attributes as stoppage
(celebration / sub / card / injury / restart_excess / silent_marked),
intersects each with the independent s03 BIP dead-time, and prints the
raw match-log events inside each window, sorted largest -> smallest.

Purpose: let a human eyeball whether each credited window is a TRUE stoppage.
Writes NOTHING; reads production parquet only. Mirrors src/s05_incident.py
logic exactly (post ADR-0039 injury rule) so the windows match the lock.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.lib import config, silent

RESTART = {
    "From Throw In", "From Corner", "From Free Kick",
    "From Goal Kick", "From Kick Off", "From Keeper",
}

TYPE_GLOSS = {
    "Injury Stoppage": "referee stops play for an injury",
    "Substitution": "substitution recorded",
    "Player Off": "player leaving the pitch (sub/injury)",
    "Player On": "player entering the pitch",
    "Foul Committed": "foul (card if flagged)",
    "Bad Behaviour": "off-ball misconduct card (no foul)",
    "Referee Ball-Drop": "dropped-ball restart",
    "Half End": "end of half (ball dead)",
    "Half Start": "start of half",
    "Offside": "offside (ball dead)",
    "Shot": "shot",
    "Own Goal For": "own goal (credited to this team)",
    "Own Goal Against": "own goal conceded",
    "Goal Keeper": "goalkeeper action",
    "Substitution ": "substitution",
}


def _next_resume(clocks, patterns, types, i, want_patterns=None, want_type=None):
    for j in range(i + 1, len(clocks)):
        if want_type is not None and types[j] == want_type:
            return j
        if want_patterns is not None and patterns[j] in want_patterns:
            return j
    return None


def _merge(intervals):
    if not intervals:
        return []
    intervals = sorted(intervals)
    out = [list(intervals[0])]
    for s, e in intervals[1:]:
        if s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]


def _intersect_total(a, b):
    a, b = _merge(a), _merge(b)
    total, i, j = 0.0, 0, 0
    while i < len(a) and j < len(b):
        lo = max(a[i][0], b[j][0])
        hi = min(a[i][1], b[j][1])
        if hi > lo:
            total += hi - lo
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return total


def mmss(t):
    t = max(0.0, float(t))
    return f"{int(t) // 60:02d}:{int(t) % 60:02d}"


def interpret(row):
    typ = row["type"]
    g = TYPE_GLOSS.get(typ, "")
    extra = []
    if typ == "Shot" and row.get("shot_outcome") == "Goal":
        g = "GOAL"
    if typ == "Pass" and row.get("pass_outcome") == "Out":
        extra.append("ball out (pass)")
    if bool(row.get("out")):
        extra.append("out=True")
    if pd.notna(row.get("card")) and row.get("card"):
        extra.append(f"card={row['card']}")
    pp = row.get("play_pattern")
    if pp in RESTART:
        extra.append(f"RESTART:{pp}")
    if pd.notna(row.get("shot_outcome")) and row.get("shot_outcome"):
        extra.append(f"shot={row['shot_outcome']}")
    if pd.notna(row.get("pass_outcome")) and row.get("pass_outcome") and typ == "Pass":
        extra.append(f"pass={row['pass_outcome']}")
    txt = g
    if extra:
        txt = (g + " | " if g else "") + ", ".join(extra)
    return txt


def period_windows(g, dead, ips, p, allowance, restart_set, sil, is_pre):
    """Return list of window dicts for one (match, period). Mirrors s05 main()."""
    g = g.sort_values(["period_s", "idx"])
    clocks = g["period_s"].to_numpy()
    patterns = g["play_pattern"].fillna("").to_numpy()
    types = g["type"].fillna("").to_numpy()
    poss = g["possession"].to_numpy()
    cards = g["card"].notna().to_numpy()
    shot_out = g["shot_outcome"].fillna("").to_numpy()
    idxs = g["idx"].to_numpy()

    wins = []

    def add(comp, lo, hi, trig_i, resume_i=None, resume_note=None):
        wins.append({
            "comp": comp, "lo": float(lo), "hi": float(hi),
            "trig_idx": int(idxs[trig_i]) if trig_i is not None else None,
            "trig_pos": trig_i,
            "resume_idx": int(idxs[resume_i]) if resume_i is not None else None,
            "resume_note": resume_note,
        })

    for i in range(len(clocks)):
        t0 = float(clocks[i])
        typ = types[i]
        if (typ == "Shot" and shot_out[i] == "Goal") or typ == "Own Goal For":
            j = _next_resume(clocks, patterns, types, i, want_patterns={"From Kick Off"})
            if j is not None:
                hi = min(clocks[j], t0 + p["max_celebration_s"])
                lo = t0 + (p["celebration_normal_s"] if is_pre else 0.0)
                if hi > lo:
                    add("celebration", lo, hi, i, j, "next kick-off")
        if typ in ("Player Off", "Substitution"):
            j = _next_resume(clocks, patterns, types, i, want_patterns=RESTART)
            if j is not None:
                add("sub", t0, min(clocks[j], t0 + p["max_sub_s"]), i, j, "next restart")
        if cards[i]:
            j = _next_resume(clocks, patterns, types, i, want_patterns=RESTART)
            if j is not None:
                add("card", t0, min(clocks[j], t0 + p["max_card_s"]), i, j, "next restart")
        if typ == "Injury Stoppage":
            later = ips[ips > t0]
            if len(later):
                r = float(later[0])
                add("injury", t0, min(r, t0 + p["max_injury_s"]), i, None,
                    f"next in-play start @ {mmss(r)}")

    for i in range(len(clocks) - 1):
        if poss[i + 1] != poss[i] and patterns[i + 1] in allowance:
            gap = float(clocks[i + 1]) - float(clocks[i])
            allow = allowance[patterns[i + 1]]
            if gap > allow:
                add("restart_excess", clocks[i] + allow, clocks[i + 1], i, i + 1,
                    f"restart {patterns[i+1]} (allow {allow:.0f}s)")

    # marker-gated silent windows
    for (lo, hi) in silent.marked_silent_intervals(g, restart_set, sil):
        # find the lead-edge event (last event at or before lo)
        pos = int(np.searchsorted(clocks, lo, side="right")) - 1
        add("silent_marked", lo, hi, pos if pos >= 0 else None, None, "marker-gated silent gap")

    # attach credited (intersect-with-dead) seconds per window
    for w in wins:
        w["credited"] = _intersect_total([(w["lo"], w["hi"])], dead)
        w["raw"] = w["hi"] - w["lo"]
    return wins, g


def main(topn=5, ctx=1):
    params = config.params()
    p = params["incident"]
    sil = params["silent"]
    restart_set = set(params["bip"]["restart_play_patterns"])
    allowance = {str(k): float(v) for k, v in p["restart_normal_s"].items()}

    events = pd.read_parquet(config.INTERIM / "events_norm.parquet")
    seg = pd.read_parquet(config.INTERIM / "bip_segments.parquet")
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    ts = pd.read_parquet(config.INTERIM / "true_stoppage.parquet")

    meta = matches.set_index("match_id")
    group = meta["group"].to_dict()

    dead_seg = {}
    for (mid, per), gg in seg[~seg["in_play"]].groupby(["match_id", "period"]):
        dead_seg[(int(mid), int(per))] = list(zip(gg["start_s"], gg["end_s"]))
    inplay_start = {}
    for (mid, per), gg in seg[seg["in_play"]].groupby(["match_id", "period"]):
        inplay_start[(int(mid), int(per))] = np.sort(gg["start_s"].to_numpy())

    top = ts.sort_values("true_stoppage_s", ascending=False).head(topn)
    print(f"\n{'='*90}\nTOP {topn} STATSBOMB MATCHES BY OWED (TRUE) STOPPAGE  [true_stoppage_s]\n{'='*90}")
    for rank, (_, r) in enumerate(top.iterrows(), 1):
        mid = int(r["match_id"])
        m = meta.loc[mid]
        print(f"{rank}. {m['home']} {m['ft_score']} {m['away']}  ({m['tournament']}, {m['group']})  "
              f"mid={mid}  owed={r['true_stoppage_s']/60:.2f} min  "
              f"[lb={r['lower_bound_s']/60:.2f} + silent_marked={r['silent_marked_s']/60:.2f} "
              f"+ residual={r['residual_silent_s']:.0f}s]")

    for rank, (_, r) in enumerate(top.iterrows(), 1):
        mid = int(r["match_id"])
        m = meta.loc[mid]
        is_pre = group.get(mid) == "PRE"
        grp = events[events["match_id"] == mid]
        print(f"\n\n{'#'*90}")
        print(f"# RANK {rank}: {m['home']} {m['ft_score']} {m['away']}  "
              f"({m['tournament']}, {m['group']}, {group.get(mid)})  mid={mid}")
        print(f"# owed(true_stoppage) = {r['true_stoppage_s']/60:.2f} min | "
              f"lower_bound = {r['lower_bound_s']/60:.2f} | silent_marked = {r['silent_marked_s']/60:.2f} "
              f"| residual = {r['residual_silent_s']:.0f}s ({group.get(mid)})")
        print('#'*90)

        allw = []
        gper = {}
        for period, g in grp.groupby("period"):
            if period >= 5:
                continue
            dead = dead_seg.get((mid, int(period)), [])
            ips = inplay_start.get((mid, int(period)), np.array([]))
            wins, gsorted = period_windows(g, dead, ips, p, allowance, restart_set, sil, is_pre)
            gper[int(period)] = gsorted
            for w in wins:
                w["period"] = int(period)
                allw.append(w)

        allw.sort(key=lambda w: w["credited"], reverse=True)
        for k, w in enumerate(allw, 1):
            per = w["period"]
            clockoff = 45 * (per - 1)
            def clk(t):
                return f"{mmss(t)} (~{mmss(t + clockoff*60)})"
            print(f"\n  [{k:>2}] {w['comp']:<15} P{per}  window {mmss(w['lo'])}->{mmss(w['hi'])}  "
                  f"raw={w['raw']:.0f}s  credited(dead∩)={w['credited']:.0f}s  "
                  f"resume: {w['resume_note']}")
            g = gper[per]
            lo, hi = w["lo"], w["hi"]
            sub = g[(g["period_s"] >= lo - ctx) & (g["period_s"] <= hi + ctx)]
            # keep it readable: cap to ~14 rows, prefer non-Pressure/Carry noise if long
            show = sub
            if len(sub) > 16:
                keepmask = ~sub["type"].isin(["Pressure", "Carry", "Ball Receipt*"])
                show = pd.concat([sub[keepmask], sub[~keepmask].head(2)]).sort_values(["period_s", "idx"])
                if len(show) > 16:
                    show = show.head(16)
            for _, e in show.iterrows():
                flag = ""
                if e["period_s"] < lo - 1e-6:
                    flag = "  <lead-edge"
                elif e["period_s"] > hi + 1e-6:
                    flag = "  <resume"
                print(f"        P{per} {mmss(e['period_s'])}  idx={int(e['idx']):>5}  "
                      f"{str(e['type'])[:18]:<18} {interpret(e)}{flag}")


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    main(topn=n)
