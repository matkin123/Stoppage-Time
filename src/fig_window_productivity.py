"""Editorial table: goals per live minute by match window (article T2).

The objection the model is built around: scoring is not even across a match. Second-half
added time is the most productive window on the pitch. Rates, goal counts and live minutes
are read from processed/productivity.parquet (scope=pooled, dimension=phase) -- the source
of truth -- never hardcoded.

Standalone (NOT a pipeline stage, NOT a gate). Run: python -m src.fig_window_productivity
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import pandas as pd

from src.lib import config, editorial

# phase key in productivity.parquet -> plain-English window label, in article order
# (peak first, floor last).
ROWS = [
    ("2H_stoppage", "Second-half added time"),
    ("1H_stoppage", "First-half added time"),
    ("regular", "Regulation open play"),
]


def _phase_rates() -> dict[str, dict]:
    prod = pd.read_parquet(config.PROCESSED / "productivity.parquet")
    sub = prod[(prod["scope"] == "pooled") & (prod["dimension"] == "phase") &
               (prod["metric"] == "goals")].set_index("phase_or_bucket")
    return {k: sub.loc[k].to_dict() for k, _ in ROWS}


def main() -> None:
    config.ensure_dirs()
    rates = _phase_rates()

    cell_text = []
    for key, label in ROWS:
        r = rates[key]
        cell_text.append([
            label,
            f"{int(round(r['n_events']))}",
            f"{r['live_minutes']:,.0f}",
            f"{r['rate']:.4f}   [{r['ci_lo']:.4f}, {r['ci_hi']:.4f}]",
        ])

    editorial.plain_table_figure(
        columns=["Match window", "Goals (n)", "Live minutes",
                 "Goals per live minute (95% CI)"],
        cell_text=cell_text,
        col_widths=[0.34, 0.12, 0.16, 0.38],
        aligns=["left", "center", "center", "left"],
        bold_rows=[0],
        figsize=(11.6, 2.2),
        savepath=config.FIGURES / "t_window_productivity.png",
    )


if __name__ == "__main__":
    main()
