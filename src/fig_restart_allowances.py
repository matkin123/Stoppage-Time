"""Editorial table: the routine-restart time-wasting allowances (article T1).

Renders the allowance ladder the owed-stoppage estimator uses: a routine restart is
free up to a normal duration, and only the seconds beyond it count as owed stoppage.
Values are read from config/params.yaml (bip.restart_normal_s) -- the single source --
not hardcoded. Adopted unchanged from Nate Silver's 2018 World Cup stopwatch study.

Standalone (NOT a pipeline stage, NOT a gate). Run: python -m src.fig_restart_allowances
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

from src.lib import config, editorial

# params key -> plain-English label, in the ascending-allowance order Nate uses.
DISPLAY = [
    ("From Throw In", "Throw-in"),
    ("From Goal Kick", "Goal kick"),
    ("From Corner", "Corner kick"),
    ("From Free Kick", "Free kick"),
]


def main() -> None:
    config.ensure_dirs()
    allowances = config.params()["incident"]["restart_normal_s"]

    cell_text = [[label, f"{int(allowances[key])} sec"] for key, label in DISPLAY]

    editorial.plain_table_figure(
        title="A restart only owes time once it drags past these limits",
        source=("Allowances applied to every routine restart across all 314 matches; the "
                "excess over each is credited as owed stoppage.\nSource: Nate Silver / "
                "FiveThirtyEight (2018 World Cup stopwatch study); author’s analysis."),
        columns=["Routine restart", "Normal allowance"],
        cell_text=cell_text,
        col_widths=[0.62, 0.38],
        aligns=["left", "center"],
        left_in=0.42,
        figsize=(9.6, 3.4),
        savepath=config.FIGURES / "t_restart_allowances.png",
    )


if __name__ == "__main__":
    main()
