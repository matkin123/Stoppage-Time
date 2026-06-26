"""Tournament-level gap structure + StatsBomb data-quality audit (standalone diagnostic).

NOT a pipeline stage, NOT a gate. Regenerates a checkpointed table and a reference doc
from the interim parquet, so the numbers in docs/statsbomb_data_quality.md trace to a
script + a table (the project standard of proof).

These metrics DESCRIBE the StatsBomb event data itself -- silent-gap prevalence, logging
density, off-camera coverage, injury-event population -- to give readers a feel for the raw
material the gap method reconstructs from. They are INDEPENDENT of the headline
counterfactual (s08), so the ADR-0029 Method-2 migration does NOT touch them.

Definitions (all per match, REGULATION halves P1+P2 only, to match the Opta BIP convention):
  * "silent gap"  = a >= max_live_gap_s (20s) inter-event interval that is NOT a restart-
                    boundary gap. This is the threshold-sensitive imperfection: the stretch
                    where StatsBomb simply stopped logging (injury / VAR / melee / off-camera).
  * "restart gap" = a possession-boundary interval whose new possession opens with a restart
                    play_pattern (throw-in/corner/FK/goal-kick/kick-off/keeper). Normal-flow
                    dead time; counted dead at any length (min_dead_gap_s = 0).
  * "flip band"   = non-restart gaps in [12s, 30s): the gaps that change live<->dead as the
                    BIP threshold is swept 12-30s. Their per-match density is the local slope
                    of reconstructed BIP w.r.t. the threshold -- the sensitivity mass.

Run: python -m src.statsbomb_quality
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.lib import config

RESTART = {"From Throw In", "From Corner", "From Free Kick",
           "From Goal Kick", "From Kick Off", "From Keeper"}
THR = 20.0  # bip.max_live_gap_s -- the silent-gap threshold
FLIP_LO, FLIP_HI = 12.0, 30.0  # the BIP sweep band

ORDER = ["wc_2018", "euro_2020", "wc_2022", "euro_2024",
         "copa_america_2024", "afcon_2023"]
LABEL = {"wc_2018": "WC 2018", "euro_2020": "Euro 2020", "wc_2022": "WC 2022",
         "euro_2024": "Euro 2024", "copa_america_2024": "Copa 2024",
         "afcon_2023": "AFCON 2023"}
REGIME = {"wc_2018": "PRE", "euro_2020": "PRE", "wc_2022": "POST",
          "euro_2024": "POST", "copa_america_2024": "POST", "afcon_2023": "POST"}


def _classify(reg: pd.DataFrame, tour: dict) -> pd.DataFrame:
    """One row per non-live inter-event interval (regulation): match, tournament, kind, gap.
    kind in {restart, silent}; non-restart gaps < THR are live and dropped. flip flags the
    [12,30s) non-restart sweep band (a superset includes the <THR slice that is otherwise live)."""
    recs = []
    for (mid, _per), g in reg.groupby(["match_id", "period"]):
        g = g.sort_values(["period_s", "idx"])
        clk = g["period_s"].to_numpy(float)
        pat = g["play_pattern"].fillna("").to_numpy()
        poss = g["possession"].to_numpy()
        for i in range(len(clk) - 1):
            t0, t1 = clk[i], clk[i + 1]
            if t1 <= t0:
                continue
            gap = t1 - t0
            is_restart = poss[i + 1] != poss[i] and pat[i + 1] in RESTART
            flip = (not is_restart) and (FLIP_LO <= gap < FLIP_HI)
            if is_restart:
                recs.append((mid, tour[mid], "restart", gap, flip))
            elif gap >= THR:
                recs.append((mid, tour[mid], "silent", gap, flip))
            elif flip:
                recs.append((mid, tour[mid], "live_flip", gap, flip))
    return pd.DataFrame(recs, columns=["match_id", "tournament", "kind", "gap", "flip"])


def build() -> pd.DataFrame:
    ev = pd.read_parquet(config.INTERIM / "events_norm.parquet")
    m = pd.read_parquet(config.INTERIM / "matches.parquet")
    tour = m.set_index("match_id")["tournament"].to_dict()
    reg = ev[ev["period"].isin([1, 2])].copy()
    reg["tournament"] = reg["match_id"].map(tour)
    d = _classify(reg, tour)

    dens = (reg.groupby(["match_id", "tournament"])
            .agg(n_events=("idx", "size"),
                 off_cam=("off_camera", lambda s: float(s.fillna(False).astype(bool).sum())))
            .reset_index())
    ends = m.set_index("match_id")[["p1_end_s", "p2_end_s"]]
    dens["reg_clock_s"] = dens["match_id"].map(lambda x: float(ends.loc[x].sum()))
    dens["ev_per_min"] = dens["n_events"] / (dens["reg_clock_s"] / 60.0)

    inj_mids = set(ev[ev["type"] == "Injury Stoppage"]["match_id"].unique())
    n_matches = m.groupby("tournament").size()

    rows = []
    for t in ORDER:
        mids = m[m["tournament"] == t]["match_id"]
        sub = d[d["tournament"] == t]
        sil = sub[sub["kind"] == "silent"]
        res = sub[sub["kind"] == "restart"]
        sil_n = sil.groupby("match_id").size().reindex(mids, fill_value=0)
        sil_sum = sil.groupby("match_id")["gap"].sum().reindex(mids, fill_value=0.0)
        res_n = res.groupby("match_id").size().reindex(mids, fill_value=0)
        res_sum = res.groupby("match_id")["gap"].sum().reindex(mids, fill_value=0.0)
        flip_n = sub[sub["flip"]].groupby("match_id").size().reindex(mids, fill_value=0)
        dd = dens[dens["tournament"] == t]
        rows.append({
            "tournament": t,
            "label": LABEL[t],
            "regime": REGIME[t],
            "matches": int(n_matches[t]),
            "silent_n_per_match": sil_n.mean(),
            "silent_mean_len_s": sil["gap"].mean() if len(sil) else np.nan,
            "silent_med_len_s": sil["gap"].median() if len(sil) else np.nan,
            "silent_total_per_match_s": sil_sum.mean(),
            "silent_max_len_s": sil["gap"].max() if len(sil) else np.nan,
            "silent_share_of_dead": sil_sum.sum() / (sil_sum.sum() + res_sum.sum()),
            "restart_n_per_match": res_n.mean(),
            "restart_total_per_match_s": res_sum.mean(),
            "events_per_match": dd["n_events"].mean(),
            "events_per_min": dd["ev_per_min"].mean(),
            "off_camera_per_match": dd["off_cam"].mean(),
            "pct_matches_with_injury_evt": 100.0 * mids.isin(inj_mids).mean(),
            "flip_band_per_match": flip_n.mean(),
        })
    return pd.DataFrame(rows).set_index("tournament")


def _t(df, cols, fmts, headers):
    """Render a markdown table for the given columns/format strings/headers."""
    out = ["| Tournament | " + " | ".join(headers) + " |",
           "|" + "---|" * (len(headers) + 1)]
    for t in ORDER:
        r = df.loc[t]
        cells = [fmt(r[c]) for c, fmt in zip(cols, fmts)]
        out.append(f"| {r['label']} ({r['regime']}) | " + " | ".join(cells) + " |")
    return "\n".join(out)


def _regime_silent(df, rg):
    sub = df[df["regime"] == rg]
    nm = sub["matches"].sum()
    gpm = (sub["silent_n_per_match"] * sub["matches"]).sum() / nm
    tot = (sub["silent_total_per_match_s"] * sub["matches"]).sum() / nm
    # match-weighted mean length = total silent seconds / total silent gaps
    mean_len = tot / gpm
    return nm, gpm, mean_len, tot


def write_doc(df: pd.DataFrame) -> None:
    s18 = df.loc["wc_2018"]
    post = df[df["regime"] == "POST"]
    post_flip = (post["flip_band_per_match"] * post["matches"]).sum() / post["matches"].sum()
    ratio = s18["flip_band_per_match"] / post_flip
    pre = _regime_silent(df, "PRE")
    pos = _regime_silent(df, "POST")

    doc = f"""# StatsBomb data quality & gap structure, by tournament

_Regenerate with `python -m src.statsbomb_quality` (writes this file and
`data/processed/statsbomb_quality_by_tournament.parquet`). Standalone diagnostic — NOT a
pipeline stage. These are **descriptive metrics of the StatsBomb event feed**, independent
of the headline counterfactual, so they are unaffected by the ADR-0029 Method-2 migration._

This is the reference for "how good is the raw data, and how does it differ across the six
tournaments?" — useful background for the methodology/Substack writeups. All figures are
**per match, regulation halves (P1+P2) only**, to match Opta's 90-minute ball-in-play
convention.

## How the gap threshold works (so the numbers below mean something)

The ball-in-play reconstruction (`s03`, `src/lib/bip.py`) walks consecutive events and labels
each inter-event interval `[last_event, next_event]` dead or live. An interval is **dead** if
**either**:

1. **restart boundary** — the next possession opens with a restart `play_pattern` (throw-in,
   corner, free kick, goal kick, kick-off, keeper); counted dead at any length
   (`min_dead_gap_s = 0`); **or**
2. **silent gap** — `gap ≥ max_live_gap_s` (**20s**), regardless of pattern: the stretch where
   StatsBomb simply stopped logging (injury, VAR, melee, off-camera, slow restart).

**The threshold is a classifier, not a deductible — and crediting is whole-gap, binary.** A 25s
silent gap against a 20s threshold contributes the **full 25s** of dead time, not 5s. Raise the
threshold to 30s and that same gap flips to **fully live** (0s). There is no partial crediting.

**Dead time ≠ stoppage.** `s03` measures *total* dead time; the stoppage estimate (`s05`) is the
*addable* **subset**, built component-by-component, so most dead time is never stoppage:

| Dead-gap type | Credited to stoppage |
|---|---|
| Incident window (goal celebration, sub, card, injury) | the **whole window** (clipped to a max, ∩ measured dead) |
| Routine restart gap | **only the excess over an allowance** — throw-in 20s, goal-kick 30s, corner 45s, FK 60s; kick-off & keeper excluded |
| Silent gap (≥20s, non-restart) | **marked → whole gap; unmarked → nothing** (unmarked silent gaps are a flat ~8.4 min/match non-addable baseline) |
| — | plus a frozen residual constant (24.2s/match) |

## Silent gaps — the threshold-sensitive imperfection

The long no-event stretches the 20s threshold governs. Prevalence and length vary sharply by
tournament; **WC 2018 is the outlier** ({s18['silent_n_per_match']:.1f} silent gaps/match, ~2×
any other, and {s18['silent_share_of_dead']*100:.0f}% of its dead time is silent vs 16–21%
elsewhere — though its gaps are the *shortest*).

{_t(df,
    ["silent_n_per_match", "silent_mean_len_s", "silent_med_len_s",
     "silent_total_per_match_s", "silent_max_len_s", "silent_share_of_dead"],
    [lambda v: f"{v:.1f}", lambda v: f"{v:.0f}", lambda v: f"{v:.0f}",
     lambda v: f"{v:.0f}s ({v/60:.1f}m)", lambda v: f"{v:.0f}", lambda v: f"{v*100:.0f}%"],
    ["Silent gaps/match", "Mean len (s)", "Median (s)", "Silent dead/match",
     "Max gap (s)", "Silent % of dead"])}

**PRE vs POST:** PRE ({pre[0]} matches) {pre[1]:.1f} silent gaps/match, mean {pre[2]:.0f}s,
{pre[3]:.0f}s/match ({pre[3]/60:.1f} min). POST ({pos[0]} matches) {pos[1]:.1f} gaps/match,
mean {pos[2]:.0f}s, {pos[3]:.0f}s/match ({pos[3]/60:.1f} min).

## Restart-boundary dead time — normal-flow stoppages (contrast)

The bulk of dead time, and legitimate ball-out-of-play the rulebook would *not* add back. Far
more uniform across tournaments than silent gaps, which is why the silent slice is the
interesting one.

{_t(df,
    ["restart_n_per_match", "restart_total_per_match_s"],
    [lambda v: f"{v:.0f}", lambda v: f"{v:.0f}s ({v/60:.1f}m)"],
    ["Restart gaps/match", "Restart dead/match"])}

## StatsBomb logging quality

Direct signals of how thickly each tournament was logged. **AFCON 2023 and Copa 2024 are the
thinnest** (lowest event density, AFCON the most off-camera and the longest silent gaps). **WC
2018 is the only tournament with zero off-camera flags** — that field was not populated in that
era's data, so 2018's silent gaps are invisible to the off-camera signal. The `Injury Stoppage`
event type is populated inconsistently (93.8%–100% of matches), which is why `s05` falls back to
marker-gated silent gaps rather than trusting that event type.

{_t(df,
    ["events_per_match", "events_per_min", "off_camera_per_match", "pct_matches_with_injury_evt"],
    [lambda v: f"{v:,.0f}", lambda v: f"{v:.1f}", lambda v: f"{v:.1f}", lambda v: f"{v:.0f}%"],
    ["Events/match", "Events/min", "Off-camera/match", "% matches w/ Injury evt"])}

> **Only 2 of 6 tournaments have an external truth.** Opta published regulation ball-in-play only
> for WC 2018 (54:50) and WC 2022 (58:04); the 20s threshold is calibrated against those. Euro
> 2020/2024, Copa, and AFCON inherit a threshold tuned on the World Cups.

## Why one global threshold can't fit every tournament

The gaps that **flip** live↔dead as the threshold sweeps 12→30s are the non-restart gaps in
that band. Their per-match density is the local slope of reconstructed BIP w.r.t. the threshold.
**WC 2018 carries {s18['flip_band_per_match']:.1f} flip-band gaps/match vs ~{post_flip:.1f} for
the POST tournaments — a {ratio:.2f}× ratio.** Roughly twice the flip-mass means 2018's
reconstructed ball-in-play responds ~{ratio:.1f}× more steeply to the threshold, so no single
global value sits at every tournament's true point at once — the residual is tournament-specific,
not an offset one knob could remove.

{_t(df, ["flip_band_per_match"], [lambda v: f"{v:.1f}"], ["Flip-band gaps/match [12,30s)"])}

_Source: `src/statsbomb_quality.py` over `data/interim/events_norm.parquet` (+ `matches.parquet`).
Checkpointed table: `data/processed/statsbomb_quality_by_tournament.parquet`._
"""
    out = config.DOCS / "statsbomb_data_quality.md"
    out.write_text(doc)
    return out


def main() -> None:
    df = build()
    pq = config.PROCESSED / "statsbomb_quality_by_tournament.parquet"
    df.reset_index().to_parquet(pq, index=False)
    out = write_doc(df)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    pd.set_option("display.float_format", lambda x: f"{x:,.2f}")
    print(df.drop(columns=["label"]))
    print(f"\n  wrote {pq}")
    print(f"  wrote {out}")


if __name__ == "__main__":
    main()
