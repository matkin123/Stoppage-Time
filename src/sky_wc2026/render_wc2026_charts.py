"""Render the two WC2026 (Sky / Opta) publication charts from the built agg tables.

RENDER-ONLY (ADR-0037 lane). Reads the two tables built by build_wc2026_inputs.py
(data/processed/sky_wc2026/{agg01,agg02}*.parquet) and feeds them to the existing
publication figure builders in src/figures_requested.py, overriding every
StatsBomb-specific text element (title, subtitle, footer means, source) with the
WC2026 numbers. Does NOT rebuild the tables or touch the locked StatsBomb lane; the
StatsBomb charts are byte-identical (the builders' overrides default to their old text).

In:  data/processed/sky_wc2026/agg01_estimate_vs_played.parquet   (est_min vs played_min)
     data/processed/sky_wc2026/agg02_productivity_by_bucket.parquet (goals/live_min by bucket)
Out: figures/sky_wc2026/agg_01_scatter_estimate_vs_played_wide.png
     figures/sky_wc2026/agg_02_productivity_by_bucket_bordered.png
"""
from __future__ import annotations

import pandas as pd

from src import figures_requested as fr
from src.lib import config

SRC = config.PROCESSED / "sky_wc2026"
OUT = config.FIGURES / "sky_wc2026"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sc = pd.read_parquet(SRC / "agg01_estimate_vs_played.parquet")
    prod = pd.read_parquet(SRC / "agg02_productivity_by_bucket.parquet")

    n = len(sc)
    pct_above = (sc["est_min"] > sc["played_min"]).mean()
    owed = sc["est_min"].mean()
    played = sc["played_min"].mean()
    missing = (sc["est_min"] - sc["played_min"]).mean()

    # ---- agg_01: true stoppage estimate vs stoppage actually played (wide) ----
    scat_source = (
        f"Data includes all 96 matches from the 2026 World Cup through the Round of 16.\n"
        f"”Typical” is the median. Mean values are: stoppage owed {owed:.1f} mins, "
        f"played {played:.1f} mins, and nearly {missing:.0f} mins missing.\n"
        "Source: Opta")
    scat_subtitle = [
        f"Each dot is a match from the 2026 World Cup. {pct_above:.0%} of matches "
        "ended too early,",
        "with more stoppage owed than was actually played."]
    fr._scatter_estimate_pub(
        sc,
        out_name="agg_01_scatter_estimate_vs_played_wide.png",
        side_pad_in=0.3, border=True, ax_dx=-0.036,
        title="Stoppage time was under-awarded in every\n2026 World Cup match",
        subtitle=scat_subtitle,
        source=scat_source,
        marker_arrowstyle="-",
        out_dir=OUT)

    # ---- agg_02: goals per live minute by stage of the match (bordered) ----
    bar_source = (
        f"Data includes all 96 matches from the 2026 World Cup through the Round of 16; goals scored in "
        "regulation (first and second half).\nSource: Opta")
    bar_subtitle = [
        "Goals per live minute by stage of the match. Scoring climbs "
        "through each half and spikes in stoppage time (red).",
        "A “live minute” counts only the time the ball is actually in play."]
    bar_annotation = "Goals come nearly twice as fast\nin second-half stoppage time"
    fr._bar_buckets_pub(
        prod,
        out_name="agg_02_productivity_by_bucket_bordered.png",
        side_pad_in=0.3, border=True,
        title="Goal scoring increased dramatically in stoppage time",
        source=bar_source,
        subtitle=bar_subtitle,
        annotation=bar_annotation,
        hilite_labels={"2H stop"},
        out_dir=OUT)

    print("  WC2026 charts complete.")


if __name__ == "__main__":
    main()
