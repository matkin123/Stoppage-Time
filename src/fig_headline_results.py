"""Editorial table: the headline result on one page (article T3).

Every value is read from processed/counterfactual_summary.parquet (the central knob set,
its bootstrap CIs, the stricter outcome-flip, the 2H-only comparison) and the assumption
band/envelope are recomputed from that same table with the ADR-0025 logic (silent fixed at
the calibrated silent_marked point; legitimate knobs swept one-at-a-time, then jointly).
Nothing is hardcoded.

Standalone (NOT a pipeline stage, NOT a gate). Run: python -m src.fig_headline_results
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import pandas as pd

from src.lib import config, editorial

CENTRAL = "silent_marked|overall|pooled_all|hl=4.0|on"


def _load():
    s = pd.read_parquet(config.PROCESSED / "counterfactual_summary.parquet")
    hw = config.params()["counterfactual"]["headline_window"]
    parts = s["knob_set"].str.split("|", expand=True)
    s = s.assign(silent=parts[0], cond=parts[1], source=parts[2], hl=parts[3], gw=parts[4])

    def row(knob, win):
        q = s[(s["group"] == "all") & (s["window"] == win) & (s["knob_set"] == knob)]
        return q.iloc[0]

    central = row(CENTRAL, hw)
    central_2h = row(CENTRAL, "2H_only")

    # ADR-0025 reported set: silent fixed at silent_marked, gross-up in {off,on}, drop the
    # regression-only half-life endpoints. Joint envelope = min/max over it.
    rep = s[(s["group"] == "all") & (s["window"] == hw) & (s["silent"] == "silent_marked") &
            (s["gw"].isin(["off", "on"])) & (~s["hl"].isin(["hl=inf", "hl=0.0"]))]
    joint_lo, joint_hi = rep["pct_changed"].min(), rep["pct_changed"].max()
    # one-factor-at-a-time lead band: sweep each knob holding the other three central.
    sweeps = pd.concat([
        rep[(rep["source"] == "pooled_all") & (rep["hl"] == "hl=4.0") & (rep["gw"] == "on")],
        rep[(rep["cond"] == "overall") & (rep["hl"] == "hl=4.0") & (rep["gw"] == "on")],
        rep[(rep["cond"] == "overall") & (rep["source"] == "pooled_all") & (rep["gw"] == "on")],
        rep[(rep["cond"] == "overall") & (rep["source"] == "pooled_all") & (rep["hl"] == "hl=4.0")],
    ])
    band_lo, band_hi = sweeps["pct_changed"].min(), sweeps["pct_changed"].max()
    return central, central_2h, band_lo, band_hi, joint_lo, joint_hi


def main() -> None:
    config.ensure_dirs()
    c, c2, band_lo, band_hi, joint_lo, joint_hi = _load()

    def pct(x):
        return f"{x:.1%}"

    def rng(lo, hi):
        return f"{lo:.1%} – {hi:.1%}"

    cell_text = [
        ["Different scoreline — the headline", pct(c["pct_changed"])],
        ["95% confidence interval (sampling)", rng(c["ci_lo"], c["ci_hi"])],
        ["Modeling band — one choice varied at a time", rng(band_lo, band_hi)],
        ["Modeling envelope — all choices varied at once", rng(joint_lo, joint_hi)],
        ["Different result — winner or draw actually changes",
         f"{pct(c['pct_outcome_flip'])}   [{c['flip_ci_lo']:.1%}, {c['flip_ci_hi']:.1%}]"],
        ["Second-half stoppage only (comparison, not the headline)",
         f"{pct(c2['pct_changed'])}   [{c2['ci_lo']:.1%}, {c2['ci_hi']:.1%}]"],
    ]

    editorial.table_figure(
        title="About one match in four would have ended with a different scoreline",
        subtitle=[
            "If stoppage time were measured and awarded per the rulebook. The scoreline figure —",
            "at least one extra goal by either side — is the headline; the stricter result figure,",
            "where the winner or a draw actually changes, is always reported separately.",
        ],
        source=editorial.FOOTER,
        columns=["What changes", "Share of matches"],
        cell_text=cell_text,
        col_widths=[0.66, 0.34],
        aligns=["left", "left"],
        hilite_cells=[(0, 0), (0, 1)],
        bold_cells=[(4, 0), (4, 1)],
        figsize=(11.4, 5.4),
        savepath=config.FIGURES / "t_headline_results.png",
    )


if __name__ == "__main__":
    main()
