"""Calibration chart vs Nate Silver's WC2018 ground truth (article trust figure).

Standalone (NOT a pipeline stage, NOT a gate) so it can never perturb the deterministic
s09 output. Reads only checkpointed tables + the checked-in Nate CSV via src/lib/nate.py.

Two independent anchors, one figure:
  LEFT   true-stoppage ESTIMATOR vs Nate `expected` (the should-be-added model)  -> r~0.875
  RIGHT  time-PLAYED board       vs Nate `actual`   (what the ref actually added) -> r~0.992

The left r firmed up from 0.825 to 0.875 (MAE 2.44 -> 1.77) once the PRE goal-celebration
allowance landed (ADR-0030) and the headline re-locked at 24.8% (ADR-0031, 2026-06-25).

The left panel is the calibration that the headline counterfactual rests on; the right panel
shows the clock read is near-exact, which is what makes the expected-minus-actual gap credible.

Run: python -m src.fig_nate_calibration
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.lib import config, editorial, nate


def _estimator_minutes() -> dict[int, float]:
    """Per-match true-stoppage estimate (min). true_stoppage.parquet is already a match total."""
    ts = pd.read_parquet(config.INTERIM / "true_stoppage.parquet")
    return {int(m): float(s) / 60.0 for m, s in zip(ts["match_id"], ts["true_stoppage_s"])}


def _panel(ax, pred: dict[int, float], column: str, title: str, color: str, highlight: dict):
    truth = nate.truth_minutes(column)
    ids = sorted(set(pred) & set(truth))
    p = [pred[i] for i in ids]
    t = [truth[i] for i in ids]
    m = nate.metric(pred, truth)

    lim = max(max(p), max(t)) * 1.08
    ax.plot([0, lim], [0, lim], color="#3C4043", lw=1.2, zorder=1)
    ax.scatter(t, p, s=30, alpha=0.7, color=color, linewidths=0, zorder=3)
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_aspect("equal", adjustable="box")
    ax.set_anchor("N")

    # inline diagonal label (no legend), parked low on the line in the empty
    # lower-left triangle so it clears every plotted point on either panel
    ax.text(lim * 0.17, lim * 0.17, "Perfect agreement", rotation=45,
            rotation_mode="anchor", ha="center", va="bottom", fontsize=8.5,
            color="#3C4043", style="italic")

    for label, mid in highlight.items():
        if mid in pred and mid in truth:
            ax.annotate(label, (truth[mid], pred[mid]), textcoords="offset points",
                        xytext=(8, -2), fontsize=8, color=editorial.INK)
            ax.scatter([truth[mid]], [pred[mid]], s=52, facecolor="none",
                       edgecolor=editorial.INK, linewidth=1.1, zorder=4)

    ax.text(0.04, 0.96, f"r = {m['r']:.2f}\nMAE = {m['mae']:.2f}",
            transform=ax.transAxes, va="top", ha="left", fontsize=10,
            color=color, fontweight="bold")
    ax.set_title(title, fontsize=11.5, color=editorial.INK, pad=8, loc="left")
    ax.grid(color="#ECEEEF", lw=0.7, zorder=0)
    editorial.despine(ax, keep=("left", "bottom"))
    return m


def main() -> None:
    config.ensure_dirs()

    with plt.rc_context(editorial.RC):
        fig = plt.figure(figsize=(12.4, 8.2))
        H = fig.get_size_inches()[1]
        content_top = editorial.titleblock(
            fig,
            "My stoppage-time figures match an independent benchmark",
            "Each dot is one of 32 World Cup 2018 matches, comparing my analysis with Nate "
            "Silver’s independent hand-coded figures. The closer to the line, the closer the "
            "agreement — exact on the clock (right), strong on the model (left).",
            "World Cup 2018 — the one tournament with an independent published benchmark "
            "(Nate Silver, FiveThirtyEight). 32 matches.\nSource: StatsBomb open data; "
            "author’s analysis.",
            content_gap_in=0.42)
        ax_bottom = 0.115
        panel_top = content_top - 0.30 / H  # leave room for each panel's title
        h = panel_top - ax_bottom
        # bigger, symmetric panels with a tighter inter-panel gap
        axL = fig.add_axes([0.055, ax_bottom, 0.42, h])
        axR = fig.add_axes([0.525, ax_bottom, 0.42, h])
        mL = _panel(axL, _estimator_minutes(), "expected",
                    "What should have been added", editorial.HILITE, {})
        mR = _panel(axR, nate.board_total_minutes(), "actual",
                    "What was actually played", editorial.SLATE, {})
        axL.set_xlabel("Nate Silver’s estimate (minutes)", fontsize=10.5)
        axL.set_ylabel("My true stoppage-time estimate (minutes)", fontsize=10.5)
        axR.set_xlabel("Nate Silver, actual (minutes)", fontsize=10.5)
        axR.set_ylabel("My measurement (minutes)", fontsize=10.5)

    path = config.FIGURES / "f07_nate_calibration.png"
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {path}")
    print(f"  estimator vs expected: r={mL['r']:.3f} MAE={mL['mae']:.2f}  |  "
          f"board vs actual: r={mR['r']:.3f} MAE={mR['mae']:.2f}")


if __name__ == "__main__":
    main()
