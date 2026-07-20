"""Compare ball-in-play across the six StatsBomb tournaments + live 2026 WC (Sky Sports).

Six tournaments: gap-method segments (s03), regulation only (periods 1-2), to match the
Opta 58:04 calibration convention. 2026 WC: Sky Sports per-match BIP export.

Raw   = mean in-play minutes per match.
Pct   = pooled in-play share = sum(in_play_s) / sum(total_s).

2026 knockout matches that went to extra time inflate raw min/match, so the regulation-
comparable row excludes them (match clock > 120 min); an all-matches variant is also written.

Out: bip_by_tournament_2026_compare.csv
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SKY_CSV = Path.home() / "Downloads" / "2026 WC Delays.csv"
OUT = ROOT / "bip_by_tournament_2026_compare.csv"

TOURNEY_LABEL = {
    "wc_2018": "WC 2018",
    "euro_2020": "Euro 2020",
    "euro_2024": "Euro 2024",
    "wc_2022": "WC 2022",
    "copa_america_2024": "Copa America 2024",
    "afcon_2023": "AFCON 2023",
}
# PRE/POST per the locked ADR-0035 reclassification (Euro 2024 -> PRE).
GROUP = {
    "wc_2018": "PRE", "euro_2020": "PRE", "euro_2024": "PRE",
    "wc_2022": "POST", "copa_america_2024": "POST", "afcon_2023": "POST",
}


def mmss_to_min(s: str) -> float:
    m, sec = str(s).strip().split(":")
    return int(m) + int(sec) / 60.0


# ---- six StatsBomb tournaments: regulation gap-method BIP ---------------------
seg = pd.read_parquet(ROOT / "data/interim/bip_segments.parquet")
matches = pd.read_parquet(ROOT / "data/interim/matches.parquet")[["match_id", "tournament"]]

seg = seg[seg["period"] <= 2].copy()          # regulation only (match calibration)
seg["dur"] = seg["end_s"] - seg["start_s"]
seg = seg.merge(matches, on="match_id", how="left")

per_match = seg.groupby(["tournament", "match_id"]).apply(
    lambda g: pd.Series({
        "total_s": g["dur"].sum(),
        "inplay_s": g.loc[g["in_play"], "dur"].sum(),
    })
).reset_index()

rows = []
for tk, grp in per_match.groupby("tournament"):
    total = grp["total_s"].sum()
    inplay = grp["inplay_s"].sum()
    rows.append({
        "tournament": TOURNEY_LABEL.get(tk, tk),
        "group": GROUP.get(tk, ""),
        "source": "StatsBomb gap-method (regulation)",
        "n_matches": len(grp),
        "mean_match_min": grp["total_s"].mean() / 60.0,
        "bip_raw_min_per_match": grp["inplay_s"].mean() / 60.0,
        "bip_pct": 100.0 * inplay / total,
    })

six = pd.DataFrame(rows)
# order PRE then POST, then by BIP%
six["_g"] = six["group"].map({"PRE": 0, "POST": 1})
six = six.sort_values(["_g", "tournament"]).drop(columns="_g")

# pooled PRE / POST / all-six rows
def pooled(df, label, group):
    return {
        "tournament": label, "group": group,
        "source": "StatsBomb gap-method (regulation)",
        "n_matches": int(df["n_matches"].sum()),
        # weight per-match means by n_matches to recover the true grand mean
        "mean_match_min": (df["mean_match_min"] * df["n_matches"]).sum() / df["n_matches"].sum(),
        "bip_raw_min_per_match": (df["bip_raw_min_per_match"] * df["n_matches"]).sum() / df["n_matches"].sum(),
        "bip_pct": None,  # filled below from segment totals for exactness
    }

# exact pooled % straight from segments
def pooled_pct(tks):
    sub = per_match[per_match["tournament"].isin(tks)]
    return 100.0 * sub["inplay_s"].sum() / sub["total_s"].sum()

pre_keys = [k for k, v in GROUP.items() if v == "PRE"]
post_keys = [k for k, v in GROUP.items() if v == "POST"]

pre_row = pooled(six[six["group"] == "PRE"], "— PRE pooled —", "PRE")
pre_row["bip_pct"] = pooled_pct(pre_keys)
post_row = pooled(six[six["group"] == "POST"], "— POST pooled —", "POST")
post_row["bip_pct"] = pooled_pct(post_keys)
all6_row = pooled(six, "— all six pooled —", "ALL")
all6_row["bip_pct"] = pooled_pct(list(GROUP))

# ---- 2026 WC (Sky Sports) ----------------------------------------------------
sky = pd.read_csv(SKY_CSV)
sky["match_min"] = sky["Match Time (MM:SS)"].map(mmss_to_min)
sky["inplay_min"] = sky["In Play (MM:SS)"].map(mmss_to_min)
sky["is_et"] = sky["match_min"] > 120.0     # extra-time knockouts

def sky_row(df, label, note):
    return {
        "tournament": label, "group": "2026",
        "source": f"Sky Sports ({note})",
        "n_matches": len(df),
        "mean_match_min": df["match_min"].mean(),
        "bip_raw_min_per_match": df["inplay_min"].mean(),
        "bip_pct": 100.0 * df["inplay_min"].sum() / df["match_min"].sum(),
    }

sky_reg = sky_row(sky[~sky["is_et"]], "WC 2026 (regulation)", "excl. extra-time matches")
sky_all = sky_row(sky, "WC 2026 (all matches)", "incl. extra-time matches")

# ---- assemble ----------------------------------------------------------------
cols = ["tournament", "group", "source", "n_matches",
        "mean_match_min", "bip_raw_min_per_match", "bip_pct"]
out = pd.DataFrame(
    six.to_dict("records") + [pre_row, post_row, all6_row, sky_reg, sky_all]
)[cols]

for c in ["mean_match_min", "bip_raw_min_per_match", "bip_pct"]:
    out[c] = out[c].astype(float).round(2)

out.to_csv(OUT, index=False)
print(out.to_string(index=False))
print(f"\nwrote {OUT}")
print(f"\n2026 extra-time matches excluded from regulation row: {int(sky['is_et'].sum())}")
