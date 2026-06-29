"""Editorial table: the sensitivity grid (article T4).

Shows that the 24.8% headline barely moves as each defensible modeling choice is swept.
Every level, spread, and band is read from / recomputed against
processed/counterfactual_summary.parquet (ADR-0025 reported set: silent fixed at the
calibrated silent_marked point; stage-source rows ADR-0033). Plain-English labels map
onto the internal knob names; the numbers are never hardcoded.

Bare black-and-white table for Substack (no colour, no title/footer): the article prose
supplies all context. Knobs are listed in the order they are introduced in the piece —
decay, score at 90, knockout vs group, PRE vs POST goal-rate source, in-stoppage
time-wasting — then the one-at-a-time band and the full joint envelope.

Standalone (NOT a pipeline stage, NOT a gate). Run: python -m src.fig_sensitivity_grid
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import pandas as pd

from src.lib import config, editorial

# Central knob set fields: silent | cond | source | hl | gw
CEN = dict(silent="silent_marked", cond="overall", source="pooled_all", hl="hl=4.0", gw="on")

# The four lambda sources that constitute the reported one-at-a-time band / joint envelope.
# The stage cohorts (pooled_group / pooled_elim) are a SEPARATE robustness row (ADR-0033) and
# are deliberately excluded from the band/envelope, like the geometric ceiling.
BAND_SOURCES = ["pooled_all", "pooled_post", "pooled_pre", "regime_matched"]

# Each swept axis, IN THE ORDER INTRODUCED IN THE ARTICLE:
#   (display label, field, [(level label, value, is_central), ...])
AXES = [
    ("Decay of the late-game premium", "hl",
     [("2-min half-life", "hl=2.0", False), ("4-min", "hl=4.0", True),
      ("8-min", "hl=8.0", False)]),
    ("Score at 90 minutes", "cond",
     [("split level/decided", "tied_nontied", False), ("overall", "overall", True)]),
    ("Knockout vs group stage", "source",
     [("all matches", "pooled_all", True), ("group stage", "pooled_group", False),
      ("knockout", "pooled_elim", False)]),
    ("Goal-rate source (PRE vs POST)", "source",
     [("all-pooled", "pooled_all", True), ("POST-only", "pooled_post", False),
      ("regime-matched", "regime_matched", False), ("PRE-only", "pooled_pre", False)]),
    ("In-stoppage time-wasting", "gw",
     [("off", "off", False), ("on", "on", True), ("geometric", "geometric", False)]),
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

    cell_text = []
    for axis_label, field, levels in AXES:
        vals = [value(field, lv) for _, lv, _ in levels]
        central = next(value(field, lv) for _, lv, ic in levels if ic)
        alts = " · ".join(f"{lab} {value(field, lv) * 100:.1f}"
                          for lab, lv, ic in levels if not ic)
        spread = (max(vals) - min(vals)) * 100
        cell_text.append([axis_label, f"{central:.1%}", alts, f"{spread:.1f} pts"])

    # Assumption band (one-at-a-time) and joint envelope, recomputed from the reported set.
    # Restrict to the calibrated silent point, the four band sources, single-pass gross-up
    # (off/on), and finite half-lives -- this excludes the geometric ceiling AND the
    # stage-source rows (ADR-0033) so neither re-centres the headline.
    rep = g.reset_index()
    parts = rep["knob_set"].str.split("|", expand=True)
    rep = rep.assign(silent=parts[0], cond=parts[1], source=parts[2], hl=parts[3], gw=parts[4])
    rep = rep[(rep["silent"] == "silent_marked") & (rep["source"].isin(BAND_SOURCES)) &
              (rep["gw"].isin(["off", "on"])) & (~rep["hl"].isin(["hl=inf", "hl=0.0"]))]
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

    for lab, lo, hi, w in [
        ("One choice varied at a time", band_lo, band_hi, band_w),
        ("All choices varied jointly", joint_lo, joint_hi, joint_w),
    ]:
        ratio = (hi - lo) / samp
        cell_text.append([lab, "—", f"{lo:.1%} – {hi:.1%}", f"{w:.1f} pts ≈ {ratio:.1f}× sampling"])

    editorial.plain_table_figure(
        columns=["Modeling choice", "Central", "X% at each alternative setting", "Spread"],
        cell_text=cell_text,
        col_widths=[0.28, 0.10, 0.42, 0.20],
        aligns=["left", "center", "left", "left"],
        bold_rows=[len(cell_text) - 2, len(cell_text) - 1],
        figsize=(12.6, 3.6),
        savepath=config.FIGURES / "t_sensitivity_grid.png",
    )


if __name__ == "__main__":
    main()
