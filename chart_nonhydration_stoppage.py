"""Ad-hoc figure: non-hydration played stoppage per tournament, 7 tournaments,
chronological x-axis, coloured by policy regime. Reads the same sources as
nonhydration_played_stoppage_by_tournament.csv."""
import csv
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch

CSV_2026 = "/Users/michaelatkin/Downloads/2026 WC Delays.csv"

# --- prior 6: regulation (1H+2H) played added time == non-hydration (no formal breaks) ---
pis = pd.read_parquet("data/interim/played_in_stoppage.parquet")
per = pis.groupby(["tournament", "match_id"])["played_in_stoppage_min"].sum()
prior = per.groupby("tournament").mean()

# --- 2026 from the Sky delays CSV, excluding the 6 extra-time knockouts ---
rows = list(csv.DictReader(open(CSV_2026)))
sec = lambda t: int(t.split(":")[0]) * 60 + int(t.split(":")[1])
reg = [r for r in rows if sec(r["Match Time (MM:SS)"]) <= 120 * 60]
v2026 = sum(((sec(r["Match Time (MM:SS)"]) - 90 * 60) - sec(r["Drink Break Delays (MM:SS)"])) / 60
            for r in reg) / len(reg)

# chronological by first match date; Euro 2024* = PRE (UEFA opted out of the 2022 directive)
BARS = [
    ("WC 2018",    prior["wc_2018"],           "PRE"),
    ("Euro 2020",  prior["euro_2020"],         "PRE"),
    ("WC 2022",    prior["wc_2022"],           "POST"),
    ("AFCON 2023", prior["afcon_2023"],        "POST"),
    ("Euro 2024*", prior["euro_2024"],         "PRE"),
    ("Copa 2024",  prior["copa_america_2024"], "POST"),
    ("WC 2026",    v2026,                       "NEW"),
]
COLOR = {"PRE": "#4C78A8", "POST": "#F58518", "NEW": "#54A24B"}
LEGEND = {"PRE": "PRE directive", "POST": "POST directive", "NEW": "New (2026)"}

labels = [b[0] for b in BARS]
vals = [b[1] for b in BARS]
colors = [COLOR[b[2]] for b in BARS]

fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.bar(labels, vals, color=colors, width=0.72, zorder=3)
for rect, val in zip(bars, vals):
    ax.text(rect.get_x() + rect.get_width() / 2, val + 0.15, f"{val:.1f}",
            ha="center", va="bottom", fontsize=11, fontweight="bold")

ax.set_title("Non-hydration stoppage time per tournament", fontsize=15, fontweight="bold", pad=14,
             loc="left")
ax.set_ylabel("Minutes per match")
ax.set_ylim(0, max(vals) + 1.4)
ax.margins(x=0.02)
ax.spines[["top", "right"]].set_visible(False)
ax.yaxis.grid(True, color="#E6E6E6", zorder=0)
ax.set_axisbelow(True)

handles = [Patch(facecolor=COLOR[k], label=LEGEND[k]) for k in ["PRE", "POST", "NEW"]]
ax.legend(handles=handles, title="Stoppage-time regime", frameon=False, loc="upper right")

fig.text(0.065, 0.015,
         "*Euro 2024 refereed under PRE-directive rules (UEFA opted out of the 2022 FIFA/Collina directive).   "
         "WC 2026 is live/partial (90 regulation matches thru Round of 16; 6 extra-time knockouts excluded).",
         fontsize=7.5, color="#555555")

fig.tight_layout(rect=[0, 0.04, 1, 1])
out = "figures/nonhydration_stoppage_by_tournament.png"
fig.savefig(out, dpi=200, bbox_inches="tight")
print("wrote", out)
print("\n".join(f"{l:12s} {v:6.2f}  {r}" for (l, v, r), _ in zip(BARS, vals)))
