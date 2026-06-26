"""Stage robustness chart: 2H-stoppage goal productivity, group stage vs elimination.

Standalone (NOT a pipeline stage, NOT a gate) so it can never perturb the deterministic
s09 output. Reads only checkpointed interim tables. Reproduces the ADR-0025 robustness note
(decisions.md): stoppage-time scoring does not differ between group-stage and knockout
matches, so the headline keeps a single pooled lambda rather than a stage term.

  group     56 goals / 660.8 live-min = 0.0847 [0.064, 0.110]
  elim      17 goals / 233.7 live-min = 0.0727 [0.042, 0.117]
  pooled    73 goals / 894.5 live-min = 0.0816 ; rate ratio group/elim = 1.17 (binomial p=0.69)

Run: python -m src.fig_stage_productivity
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.lib import config, editorial
from src.lib.stats import poisson_rate_ci


def _stage_rates() -> dict[str, dict]:
    """2H-stoppage goals / live-minutes split by stage, from checkpointed interim tables."""
    m = pd.read_parquet(config.INTERIM / "matches.parquet")[["match_id", "stage"]]
    m["cls"] = m["stage"].apply(lambda s: "group" if s == "Group Stage" else "elim")

    goals = pd.read_parquet(config.INTERIM / "goals.parquet")
    g2h = goals[goals["is_stoppage"] == "2H"].merge(m, on="match_id")

    mins = pd.read_parquet(config.INTERIM / "match_minutes.parquet")
    lm2h = mins[mins["phase"] == "2H_stoppage"].merge(m, on="match_id")

    out = {}
    for cls in ("group", "elim"):
        n = int((g2h["cls"] == cls).sum())
        lm = float(lm2h.loc[lm2h["cls"] == cls, "live_seconds"].sum()) / 60.0
        r, lo, hi = poisson_rate_ci(n, lm)
        out[cls] = {"n": n, "lm": lm, "rate": r, "lo": lo, "hi": hi}
    n = sum(out[c]["n"] for c in out)
    lm = sum(out[c]["lm"] for c in out)
    r, lo, hi = poisson_rate_ci(n, lm)
    out["pooled"] = {"n": n, "lm": lm, "rate": r, "lo": lo, "hi": hi}
    return out


def main() -> None:
    config.ensure_dirs()
    d = _stage_rates()

    labels = ["Group stage", "Knockout"]
    keys = ["group", "elim"]
    rates = [d[k]["rate"] for k in keys]
    lo = [d[k]["rate"] - d[k]["lo"] for k in keys]
    hi = [d[k]["hi"] - d[k]["rate"] for k in keys]
    pooled = d["pooled"]["rate"]

    with plt.rc_context(editorial.RC):
        fig = plt.figure(figsize=(8.4, 6.6))
        ax = fig.add_axes([0.115, 0.135, 0.83, 0.585])
        x = [0, 1]
        # Both groups neutral: the finding is that they're the SAME, so the colour
        # carries no contrast. The pooled rate (red) is the reference that matters.
        ax.bar(x, rates, width=0.52, color=editorial.NEUTRAL, zorder=3)
        ax.errorbar(x, rates, yerr=[lo, hi], fmt="none", ecolor="#3C4043",
                    capsize=7, lw=1.3, zorder=4)

        ax.axhline(pooled, ls=(0, (4, 3)), color=editorial.HILITE, lw=1.4, zorder=2)
        ax.text(1.46, pooled, f"Pooled rate  {pooled:.3f}", ha="right", va="bottom",
                fontsize=9, color=editorial.HILITE, fontweight="bold")

        for xi, k in zip(x, keys):
            c = d[k]
            ax.text(xi, c["hi"] + 0.006, f"{c['rate']:.3f}", ha="center", va="bottom",
                    fontsize=13, fontweight="bold", color=editorial.INK)
            ax.text(xi, 0.005, f"{c['n']} goals\n{c['lm']:.0f} live min", ha="center",
                    va="bottom", fontsize=9, color="#44484E")

        ax.annotate("The gap is not statistically significant\n(p = 0.69)",
                    xy=(0.5, pooled), xytext=(0.5, pooled * 0.40),
                    ha="center", va="center", fontsize=9.5, color=editorial.SUBINK,
                    arrowprops=dict(arrowstyle="-", color="#C6CACE", lw=1.0))

        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=11)
        ax.set_ylabel("Goals per live minute", fontsize=11)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.02f}"))
        ax.set_ylim(0, max(d[k]["hi"] for k in keys) * 1.20)
        ax.set_xlim(-0.6, 1.6)
        ax.grid(axis="y", color=editorial.GRID, lw=0.8, zorder=0)
        editorial.despine(ax, keep=("bottom",))

        editorial.titleblock(
            fig,
            "Knockout pressure doesn’t change stoppage-time scoring",
            ["Goals per live minute in second-half stoppage, group games versus knockout",
             "games. The two rates are within sampling noise of each other."],
            "Second-half stoppage only, across all 314 matches from six tournaments, "
            "2018–2024.\nSource: StatsBomb open data; author’s analysis.")

    path = config.FIGURES / "f08_stage_productivity.png"
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {path}")
    for k in ("group", "elim", "pooled"):
        c = d[k]
        print(f"  {k}: n={c['n']} live-min={c['lm']:.1f} "
              f"rate={c['rate']:.4f} [{c['lo']:.3f}, {c['hi']:.3f}]")


if __name__ == "__main__":
    main()
