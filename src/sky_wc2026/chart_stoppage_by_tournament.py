"""Non-hydration stoppage time per tournament -- publication figure.

Per-tournament mean non-hydration stoppage time actually played:
- StatsBomb (WC2018, Euro2020, WC2022, Euro2024, Copa2024, AFCON2023):
  played_in_stoppage_min summed over P1+P2 per match.
- WC2026 (Opta / Sky): played_reg_min minus per-match total drink-break-related
  dead time from Sheet1.drink_break_delays_mmss (includes the break itself plus
  surrounding dead time: players walking, referee organising). This is wider than
  the pure break duration in Hydration_Break_Info (~5 min/match) and averages
  ~7 min/match. Sheet1 stores these as Excel [MM]:SS cells; openpyxl reads them
  as datetime.time where .hour = minutes and .minute = seconds of the duration
  (see _load_wc2026 for the conversion).

Out: figures/sky_wc2026/stoppage_by_tournament_bordered.png
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.lib import config, editorial

XLSX = ROOT / "data" / "DONOTSHAREWorldCup_Stoppages.xlsx"
OUT = config.FIGURES / "sky_wc2026"

# Chronological order; None key = WC2026 (Opta lane)
TOURNAMENTS = [
    ("wc_2018",           "WC 2018",     "PRE"),
    ("euro_2020",         "Euro 2020",   "PRE"),
    ("wc_2022",           "WC 2022",     "POST"),
    ("afcon_2023",        "AFCON 2023",  "POST"),
    ("euro_2024",         "Euro 2024*",  "PRE"),
    ("copa_america_2024", "Copa 2024",   "POST"),
    (None,                "WC 2026",     "NEW"),
]

# Two distinct greys for PRE / POST; same red used in agg_01 and agg_02 for WC2026
COLOR_PRE  = "#C5CBD2"          # light grey
COLOR_POST = "#4D5560"          # dark grey -- clearly different from PRE
COLOR_NEW  = editorial.HILITE   # #D4322C -- same red as agg_01 / agg_02


def _load_statsbomb() -> dict[str, float]:
    pis = pd.read_parquet(config.INTERIM / "played_in_stoppage.parquet")
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    per_match = (pis.groupby("match_id")["played_in_stoppage_min"].sum()
                 .reset_index()
                 .merge(matches[["match_id", "tournament"]], on="match_id"))
    return per_match.groupby("tournament")["played_in_stoppage_min"].mean().to_dict()


_CANON_ALIAS = {
    "bosniaandherzegovina": "bosniaherz", "caboverde": "capeverde",
    "czechia": "czechrepublic", "iriran": "iran", "korearepublic": "southkorea",
    "torkiye": "turkey", "curaao": "curacao", "ctedivoire": "ivorycoast",
}


def _canon_team(name: str) -> str:
    n = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    s = "".join(c for c in n.lower() if c.isalnum())
    return _CANON_ALIAS.get(s, s)


def _load_wc2026() -> tuple[float, float, int]:
    """Return (mean_nonhyd_min, mean_drink_delays_min, n_reg_matches).

    Uses Sheet1.drink_break_delays_mmss (total drink-break-related dead time:
    break duration + surrounding context) rather than the pure Hydration_Break_Info
    duration. Sheet1 stores [MM]:SS durations; openpyxl reads them as datetime.time
    where .hour = minutes and .minute = seconds of the duration.
    """
    agg01 = pd.read_parquet(
        config.PROCESSED / "sky_wc2026" / "agg01_estimate_vs_played.parquet")
    reg = agg01[agg01["extra_time_match"] == "No"].copy()

    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)

    # Build match_name -> canonical frozenset from Stoppage_Candidates
    ws_sc = wb["Stoppage_Candidates"]
    it = ws_sc.iter_rows(values_only=True)
    hdr = list(next(it))
    ix = {h: i for i, h in enumerate(hdr)}
    match_key: dict[str, frozenset] = {}
    for r in it:
        m = r[ix["Match"]]
        if m and m not in match_key:
            match_key[m] = frozenset({_canon_team(r[ix["Home team"]]),
                                      _canon_team(r[ix["Away team"]])})

    # Build canonical frozenset -> drink_delays_s from Sheet1
    ws_s1 = wb["Sheet1"]
    it = ws_s1.iter_rows(values_only=True)
    hdr = list(next(it))
    ix = {h: i for i, h in enumerate(hdr)}
    s1_drink: dict[frozenset, float] = {}
    for r in it:
        key = frozenset({_canon_team(r[ix["home_team_name"]]),
                         _canon_team(r[ix["away_team_name"]])})
        t = r[ix["drink_break_delays_mmss"]]
        # [MM]:SS cell: openpyxl .hour holds minutes, .minute holds seconds
        s1_drink[key] = float(t.hour * 60 + t.minute) if hasattr(t, "hour") else 0.0

    wb.close()

    reg = reg.copy()
    reg["drink_delays_min"] = (
        reg["match"]
        .map(lambda m: s1_drink.get(match_key.get(m, frozenset()), 0.0))
        / 60.0
    )
    reg["nonhyd_min"] = reg["played_reg_min"] - reg["drink_delays_min"]
    return float(reg["nonhyd_min"].mean()), float(reg["drink_delays_min"].mean()), len(reg)


def build_chart(out_name: str = "stoppage_by_tournament_bordered.png") -> Path:
    OUT.mkdir(parents=True, exist_ok=True)

    sb = _load_statsbomb()
    wc26_val, hyd_mean, n_wc26 = _load_wc2026()

    values, labels, colors = [], [], []
    for key, label, regime in TOURNAMENTS:
        values.append(wc26_val if key is None else sb[key])
        labels.append(label)
        colors.append({"PRE": COLOR_PRE, "POST": COLOR_POST, "NEW": COLOR_NEW}[regime])
    values = np.array(values)
    x = np.arange(len(values))

    y_max = max(values) * 1.22

    with plt.rc_context(editorial.RC):
        fig = plt.figure(figsize=(10.2, 6.4))
        ax = fig.add_axes([0.085, 0.24, 0.885, 0.50])

        # Axis limits first
        ax.set_ylim(0, y_max)
        ax.set_xlim(-0.6, len(values) - 0.4)
        ax.set_ylabel("Minutes per match", fontsize=11, labelpad=6)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}"))
        ax.grid(axis="y", color=editorial.GRID, lw=0.8, zorder=0)
        ax.set_axisbelow(True)
        for sp in ("top", "right", "left"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(length=0)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=10.5)

        # Bars
        ax.bar(x, values, color=colors, width=0.72, zorder=3)

        # Value labels -- INK for the grey bars, HILITE for WC2026
        for xi, v, c in zip(x, values, colors):
            label_col = editorial.HILITE if c == COLOR_NEW else editorial.INK
            ax.text(xi, v + 0.18, f"{v:.1f}",
                    ha="center", va="bottom",
                    fontsize=10.5, fontweight="bold", color=label_col)

        # Legend ON the chart with white background (blocks gridlines)
        legend_handles = [
            mpatches.Patch(facecolor=COLOR_PRE,  label="PRE-directive"),
            mpatches.Patch(facecolor=COLOR_POST, label="POST-directive (2022+)"),
            mpatches.Patch(facecolor=COLOR_NEW,  label="WC 2026"),
        ]
        leg = ax.legend(
            handles=legend_handles,
            loc="upper right",
            frameon=True,
            facecolor="white",
            edgecolor="#CCCCCC",
            framealpha=1.0,
            fontsize=9.5,
            handlelength=1.1,
            handleheight=1.1,
            borderpad=0.65,
            labelspacing=0.45,
        )
        leg.set_zorder(10)
        # Style legend text to match editorial INK
        for txt in leg.get_texts():
            txt.set_color(editorial.INK)

        # Title block
        title = "Without water breaks, WC 2026 stoppage time fell below pre-directive levels"
        subtitle = [
            "Average non-hydration stoppage time per match. The 2022 FIFA/Collina directive"
            " almost doubled added time in the tournaments that followed.",
            "Total hydration dead time (~7 min per match) is subtracted"
            " to allow fair comparison across tournaments.",
        ]
        source = (
            f"Data: all matches from the 2018 & 2022 World Cups, Euro 2020 & 2024,"
            f" Copa America 2024 and AFCON 2023 (regulation halves only),\n"
            f"plus all 96 WC 2026 matches through the Round of 16 (regulation halves only).\n"
            f"*UEFA opted out of the 2022 FIFA/Collina directive; Euro 2024 is classified as PRE.\n"
            f"Source: Opta (WC 2026); StatsBomb open data (all other tournaments)."
        )
        editorial.titleblock(fig, title, subtitle, source)

    out_path = OUT / out_name
    editorial.save_padded(fig, out_path, side_pad_in=0.3, border=True, dpi=130)
    print(f"  wrote {out_path}")
    return out_path


if __name__ == "__main__":
    build_chart()
