"""Editorial table: the sensitivity grid (article T4).

Shows that the 24.8% headline barely moves as each defensible modeling choice is swept.
Every level, spread, and band is read from / recomputed against
processed/counterfactual_summary.parquet (ADR-0025 reported set: silent fixed at the
calibrated silent_marked point). Plain-English labels map onto the internal knob names;
the numbers are never hardcoded.

Standalone (NOT a pipeline stage, NOT a gate). Run: python -m src.fig_sensitivity_grid
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import pandas as pd

from src.lib import config, editorial

# Central knob set fields: silent | cond | source | hl | gw
CEN = dict(silent="silent_marked", cond="overall", source="pooled_all", hl="hl=4.0", gw="on")

# Each swept axis: (display label, field, [(level label, value, is_central), ...])
AXES = [
    ("Where the goal rate comes from", "source",
     [("all-pooled", "pooled_all", True), ("POST-only", "pooled_post", False),
      ("regime-matched", "regime_matched", False), ("PRE-only", "pooled_pre", False)]),
    ("In-stoppage time-wasting", "gw",
     [("off", "off", False), ("on", "on", True), ("geometric", "geometric", False)]),
    ("How fast the late rate cools", "hl",
     [("2-min half-life", "hl=2.0", False), ("4-min", "hl=4.0", True),
      ("8-min", "hl=8.0", False)]),
    ("Score at 90 minutes", "cond",
     [("split level/decided", "tied_nontied", False), ("overall", "overall", True)]),
]


def main() -> None:
    config.ensure_dirs()
    s = pd.read_parquet(config.PROCESSED / "counterfactual_summary.parquet")
    hw = config.params()["counterfactual"]["headline_window"]
    g = s[(s["group"] == "all") & (s["window"] == hw)].set_index("knob_set")

    def value(field, level):
        f = dict(CEN, **{field: level})
        knob = f"{f['silent']}|{f['cond']}|{f['source']}|{f['hl']}|{f['gw']}"
        return float(g.loc[knob, "pct_changed"])

    cell_text, dim_cells, hilite_cells = [], [], []
    for axis_label, field, levels in AXES:
        vals = [value(field, lv) for _, lv, _ in levels]
        central = next(value(field, lv) for _, lv, ic in levels if ic)
        alts = " · ".join(f"{lab} {value(field, lv) * 100:.1f}"
                          for lab, lv, ic in levels if not ic)
        spread = (max(vals) - min(vals)) * 100
        r = len(cell_text)
        hilite_cells.append((r, 1))
        cell_text.append([axis_label, f"{central:.1%}", alts, f"{spread:.1f} pts"])

    # Assumption band (one-at-a-time) and joint envelope, recomputed from the reported set.
    rep = g.reset_index()
    parts = rep["knob_set"].str.split("|", expand=True)
    rep = rep.assign(silent=parts[0], cond=parts[1], source=parts[2], hl=parts[3], gw=parts[4])
    rep = rep[(rep["silent"] == "silent_marked") & (rep["gw"].isin(["off", "on"])) &
              (~rep["hl"].isin(["hl=inf", "hl=0.0"]))]
    joint_lo, joint_hi = rep["pct_changed"].min(), rep["pct_changed"].max()
    sweeps = pd.concat([
        rep[(rep["source"] == "pooled_all") & (rep["hl"] == "hl=4.0") & (rep["gw"] == "on")],
        rep[(rep["cond"] == "overall") & (rep["hl"] == "hl=4.0") & (rep["gw"] == "on")],
        rep[(rep["cond"] == "overall") & (rep["source"] == "pooled_all") & (rep["gw"] == "on")],
        rep[(rep["cond"] == "overall") & (rep["source"] == "pooled_all") & (rep["hl"] == "hl=4.0")],
    ])
    band_lo, band_hi = sweeps["pct_changed"].min(), sweeps["pct_changed"].max()
    cen = g.loc["silent_marked|overall|pooled_all|hl=4.0|on"]
    samp = float(cen["ci_hi"] - cen["ci_lo"])
    band_w = (band_hi - band_lo) * 100
    joint_w = (joint_hi - joint_lo) * 100

    base = len(cell_text)
    for i, (lab, lo, hi, w) in enumerate([
        ("One choice varied at a time", band_lo, band_hi, band_w),
        ("All choices varied jointly", joint_lo, joint_hi, joint_w),
    ]):
        ratio = (hi - lo) / samp
        cell_text.append([lab, "—", f"{lo:.1%} – {hi:.1%}", f"{w:.1f} pts ≈ {ratio:.1f}× sampling"])
        dim_cells.append((base + i, 1))

    editorial.table_figure(
        title="The headline doesn’t hinge on any single modeling choice",
        subtitle=[
            "Each assumption swept across its defensible range; the central choice is shown in red.",
            "Varying one choice at a time moves the result about as much as ordinary sampling noise,",
            "and varying all of them at once only modestly more.",
        ],
        source=("Scoreline counterfactual over all 314 matches, headline window (first- and "
                "second-half added time); silent treatment fixed at its calibrated value.\n"
                "Source: StatsBomb open data; author’s analysis."),
        columns=["Modeling choice", "Central", "X% at each alternative setting", "Spread"],
        cell_text=cell_text,
        col_widths=[0.24, 0.10, 0.45, 0.21],
        aligns=["left", "center", "left", "left"],
        hilite_cells=hilite_cells,
        dim_cells=dim_cells,
        figsize=(13.6, 5.4),
        savepath=config.FIGURES / "t_sensitivity_grid.png",
    )


if __name__ == "__main__":
    main()
