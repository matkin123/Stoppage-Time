"""Nate Silver / 538 WC-2018 ground truth + the shared validation harness.

This is the external cross-check the whole silent-component effort hinges on (CLAUDE.md S6:
validate upstream against EXTERNAL ground truth, not just internal gates). The 32-match table
is checked in at data/raw/nate_2018/nate_wc2018.csv. Three independent arms, three project
quantities -- DO NOT mix them up:

    Nate column   ->  project quantity            ->  used by
    -----------------------------------------------------------------
    bip           ->  s03 regulation ball-in-play ->  IMPL-2 promote-gate (r >= 0.94)
    expected      ->  true-stoppage estimator     ->  IMPL-3 gate (beat r 0.73-0.77)
    actual        ->  precise time-played board   ->  already validated (r=0.992); regression guard

`expected` is the "how much SHOULD be added" model (mean ~13.2 min) -- the estimator target.
`actual` is what the ref actually added -- the board target. The headline counterfactual is
expected-vs-actual. Getting these two columns crossed silently breaks everything downstream.

Reconciliation gotcha: 538's home/away orientation and a few names differ from StatsBomb
(e.g. 538 "Iceland-Nigeria" is StatsBomb "Nigeria-Iceland"; 538 "S. Korea" is "South Korea").
So we reconcile on the UNORDERED, name-normalized team pair within wc_2018 -- never on order.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.lib import config

# 538 spelling -> StatsBomb spelling. Extend here if a future transcription adds a mismatch.
NAME_FIX = {"S. Korea": "South Korea"}

# The diagnostic matches from the silent-component problem statement, as unordered pairs.
# LOW = few injuries, fat silent bucket -> estimator currently OVER-counts; correction must shrink.
# HIGH = injury-dominated -> estimator already accurate; correction must NOT break these.
DIAGNOSTIC_LOW = [("Germany", "Sweden"), ("Russia", "Egypt"), ("Uruguay", "Saudi Arabia")]
DIAGNOSTIC_HIGH = [("Belgium", "Panama"), ("Tunisia", "England")]


def _norm(name: str) -> str:
    return NAME_FIX.get(name.strip(), name.strip())


def _pair(a: str, b: str) -> frozenset:
    return frozenset((_norm(a), _norm(b)))


def _mmss_to_s(v: str) -> float:
    m, s = str(v).strip().split(":")
    return int(m) * 60 + int(s)


def load_nate() -> pd.DataFrame:
    """The 32-match ground truth, with seconds parsed and an unordered-pair reconciliation key.

    Columns added: bip_s, expected_s, actual_s (seconds) and `pair` (frozenset of normalized
    team names). Raw mm:ss strings are kept for traceability.
    """
    df = pd.read_csv(config.RAW / "nate_2018" / "nate_wc2018.csv", comment="#")
    if len(df) != 32:
        raise ValueError(f"nate_wc2018.csv must have 32 rows, found {len(df)}")
    df["bip_s"] = df["bip"].map(_mmss_to_s)
    df["expected_s"] = df["expected"].map(_mmss_to_s)
    df["actual_s"] = df["actual"].map(_mmss_to_s)
    df["pair"] = [_pair(h, a) for h, a in zip(df["home"], df["away"])]
    return df


def reconcile(nate: pd.DataFrame | None = None, matches: pd.DataFrame | None = None) -> pd.DataFrame:
    """Attach StatsBomb `match_id` to each Nate row via the unordered, normalized team pair.

    Raises if any of the 32 fails to reconcile -- a hard guard so a silent name/orientation
    drift can never let the harness validate against the wrong (or zero) matches.
    """
    nate = load_nate() if nate is None else nate
    if matches is None:
        matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    wc = matches[matches["tournament"] == "wc_2018"]
    pair_to_id: dict[frozenset, int] = {}
    for mid, h, a in zip(wc["match_id"], wc["home"], wc["away"]):
        pair_to_id.setdefault(_pair(h, a), int(mid))
    out = nate.copy()
    out["match_id"] = out["pair"].map(pair_to_id)
    missing = out[out["match_id"].isna()]
    if not missing.empty:
        rows = ", ".join(f"{r.home}-{r.away}" for r in missing.itertuples())
        raise ValueError(f"{len(missing)} Nate matches did not reconcile to a wc_2018 match_id: {rows}")
    out["match_id"] = out["match_id"].astype(int)
    return out


def truth_minutes(column: str) -> dict[int, float]:
    """match_id -> Nate value in MINUTES for column in {'bip','expected','actual'}."""
    col = {"bip": "bip_s", "expected": "expected_s", "actual": "actual_s"}[column]
    rec = reconcile()
    return {int(m): float(s) / 60.0 for m, s in zip(rec["match_id"], rec[col])}


def metric(pred_min: dict[int, float], truth_min: dict[int, float]) -> dict:
    """Pearson r + MAE (minutes) over the match_ids present in both dicts."""
    ids = sorted(set(pred_min) & set(truth_min))
    if len(ids) < 2:
        return {"n": len(ids), "r": float("nan"), "mae": float("nan")}
    p = np.array([pred_min[i] for i in ids], float)
    t = np.array([truth_min[i] for i in ids], float)
    return {"n": len(ids), "r": float(np.corrcoef(p, t)[0, 1]), "mae": float(np.mean(np.abs(p - t)))}


# ---- per-match project quantities (templates the IMPL sessions reuse) --------------------

def regulation_bip_minutes() -> dict[int, float]:
    """Per-match regulation (periods 1-2) ball-in-play minutes from s03 bip_segments."""
    seg = pd.read_parquet(config.INTERIM / "bip_segments.parquet")
    seg = seg[seg["period"].isin([1, 2]) & seg["in_play"]].copy()
    seg["dur"] = seg["end_s"] - seg["start_s"]
    return {int(m): float(v) / 60.0 for m, v in seg.groupby("match_id")["dur"].sum().items()}


def board_total_minutes() -> dict[int, float]:
    """Per-match total board (both regulation halves summed) from interim/board_added_time."""
    b = pd.read_parquet(config.INTERIM / "board_added_time.parquet")
    b = b[b["period"].isin([1, 2])]
    return {int(m): float(v) for m, v in b.groupby("match_id")["board_min"].sum().items()}


def report(pred_min: dict[int, float], column: str, label: str) -> dict:
    """Print an r/MAE report for one arm plus the low/high diagnostic, and return the metric.

    `column` selects the Nate truth column ('bip'|'expected'|'actual'); `pred_min` is the
    project quantity per match_id, in minutes.
    """
    truth = truth_minutes(column)
    m = metric(pred_min, truth)
    print(f"\n  [{label}] vs Nate '{column}'  n={m['n']}  r={m['r']:.3f}  MAE={m['mae']:.2f} min")
    rec = reconcile().set_index("pair")["match_id"].to_dict()
    print("    diagnostic (pred / nate, minutes):")
    for group, pairs in (("LOW (must shrink)", DIAGNOSTIC_LOW), ("HIGH (must hold)", DIAGNOSTIC_HIGH)):
        for a, b in pairs:
            mid = rec.get(_pair(a, b))
            pv = pred_min.get(mid, float("nan"))
            tv = truth.get(mid, float("nan"))
            print(f"      {group:18} {a}-{b:14} pred={pv:5.1f}  nate={tv:5.1f}  err={pv - tv:+5.1f}")
    return m
