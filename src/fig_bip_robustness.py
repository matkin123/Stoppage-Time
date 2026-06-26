"""Robustness of the single BIP knob (`bip.max_live_gap_s`) — calibration trust figure.

Standalone (NOT a pipeline stage, NOT a gate) so it can never perturb the deterministic
s09 output or any locked table. Reads only interim/events_norm + matches and re-runs the
frozen gap-method segmenter (src/lib/bip.py) at a range of max_live_gap values. The
production value (20s) and all locked numbers are untouched.

Why this exists: BIP rests on ONE global, monotonic knob. The s08 sensitivity grid sweeps
the silent/decay/half-life knobs but NOT this one. This figure closes that gap and shows
(a) the published WC2022 anchor stays inside Opta's +-90s tolerance across a wide band, and
(b) the PRE/POST BIP-share structure the productivity comparison rests on is preserved
across the band — i.e. nothing downstream hinges on the exact knob value.

Two anchors (WC2018 54:50, WC2022 58:04) are the only tournaments with a published Opta
ball-in-play truth; the other four have no free per-tournament BIP and appear for structure
only.

Run: python -m src.fig_bip_robustness
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.lib import bip, config, editorial

# Opta published regulation ball-in-play (seconds/match) — the only external truths.
OPTA_TRUTH_S = {"wc_2018": 54 * 60 + 50, "wc_2022": 58 * 60 + 4}
PRE = {"wc_2018", "euro_2020"}
LABEL = {
    "wc_2018": "2018 World Cup", "euro_2020": "Euro 2020", "wc_2022": "2022 World Cup",
    "euro_2024": "Euro 2024", "copa_america_2024": "Copa 2024", "afcon_2023": "AFCON 2023",
}
SWEEP = [12, 14, 16, 18, 20, 22, 24, 26, 28, 30]
CHOSEN = 20.0


def _mmss(s: float) -> str:
    total = int(round(s))
    return f"{total // 60}:{total % 60:02d}"


def sweep() -> pd.DataFrame:
    """Pooled regulation BIP (mean live s/match) and BIP share per tournament x knob."""
    p = config.params()
    restart = set(p["bip"]["restart_play_patterns"])
    min_gap = float(p["bip"]["min_dead_gap_s"])
    events = pd.read_parquet(config.INTERIM / "events_norm.parquet")
    tmap = (
        pd.read_parquet(config.INTERIM / "matches.parquet")
        .set_index("match_id")["tournament"].to_dict()
    )
    per_match = {mid: grp for mid, grp in events.groupby("match_id")}

    rows: list[dict] = []
    for g in SWEEP:
        agg: dict[str, list[tuple[float, float]]] = {}
        for mid, grp in per_match.items():
            segs = bip.build_segments(grp, restart, min_gap, float(g))
            if segs.empty:
                continue
            segs = segs[segs["period"].isin([1, 2])]
            dur = segs["end_s"] - segs["start_s"]
            live = float(dur[segs["in_play"]].sum())
            total = float(dur.sum())
            agg.setdefault(tmap[mid], []).append((live, total))
        for tour, vals in agg.items():
            live = np.array([v[0] for v in vals])
            total = np.array([v[1] for v in vals])
            rows.append({
                "max_live_gap_s": g, "tournament": tour, "n": len(vals),
                "bip_s": live.mean(), "share": live.sum() / total.sum(),
            })
    return pd.DataFrame(rows)


def figure(df: pd.DataFrame) -> None:
    """Editorial redesign: each World Cup anchor is one colour family (reconstruction line +
    its published benchmark + tolerance band). The chosen threshold is a named reference line.
    Panel B shows the before/after gap is preserved at every threshold — POST is the subject
    (red), PRE neutral slate, both direct-labeled at the line ends, no legend box."""
    with plt.rc_context(editorial.RC):
        fig = plt.figure(figsize=(12.8, 7.3))
        axA = fig.add_axes([0.070, 0.135, 0.40, 0.50])
        axB = fig.add_axes([0.570, 0.135, 0.40, 0.50])

        # --- Panel A: reconstruction vs the two Opta benchmarks ------------------
        # Each tournament is one colour: a climbing SOLID+dots reconstruction, its flat
        # DASHED Opta benchmark, and a shaded ±90s tolerance band. The benchmark is
        # labeled on the dashed line at the LEFT (the solids converge near 59' at the
        # right, so a right-end name label would collide).
        anchors = [("wc_2022", editorial.HILITE), ("wc_2018", editorial.SLATE)]
        for tour, color in anchors:
            truth = OPTA_TRUTH_S[tour]
            d = df[df["tournament"] == tour].sort_values("max_live_gap_s")
            axA.axhspan((truth - 90) / 60, (truth + 90) / 60, color=color, alpha=0.08, zorder=0)
            axA.axhline(truth / 60, ls="--", lw=1.1, color=color, alpha=0.85, zorder=2)
            axA.plot(d["max_live_gap_s"], d["bip_s"] / 60, "-o", ms=4.5, color=color, zorder=3)
            axA.annotate(f"{LABEL[tour]} benchmark · {_mmss(truth)}",
                         (SWEEP[0], truth / 60), textcoords="offset points", xytext=(0, 4),
                         va="bottom", ha="left", fontsize=8.5, color=color, fontweight="bold")
        axA.axvline(CHOSEN, color=editorial.REF, ls=(0, (3, 3)), lw=1.1, zorder=2)
        axA.annotate("Chosen threshold: 20s", (CHOSEN, axA.get_ylim()[0]),
                     textcoords="offset points", xytext=(6, 8), fontsize=8.5,
                     color=editorial.SUBINK)
        axA.text(0.97, 0.05,
                 "Solid line + dots = our reconstruction\nShaded band = ±90-second tolerance",
                 transform=axA.transAxes, ha="right", va="bottom", fontsize=8.5,
                 color=editorial.SUBINK, style="italic")
        axA.set_xlabel("Tuning threshold (seconds)", fontsize=10.5)
        axA.set_ylabel("Live play per match (minutes)", fontsize=10.5)
        axA.set_title("20 seconds lands on the benchmark",
                      fontsize=11.5, color=editorial.INK, pad=8, loc="left")
        axA.set_xlim(SWEEP[0] - 1, SWEEP[-1] + 1)

        # --- Panel B: before/after gap is preserved across the threshold ---------
        label_dy = {"wc_2018": 5, "euro_2020": -5, "copa_america_2024": 6, "afcon_2023": -6}
        shares = df["share"] * 100
        ylo, yhi = shares.min() - 3.0, shares.max() + 2.0
        for tour in LABEL:
            d = df[df["tournament"] == tour].sort_values("max_live_gap_s")
            if d.empty:
                continue
            color = editorial.SLATE if tour in PRE else editorial.HILITE
            axB.plot(d["max_live_gap_s"], d["share"] * 100, "-o", ms=3.5, color=color,
                     zorder=3)
            axB.annotate(LABEL[tour],
                         (d["max_live_gap_s"].iloc[-1], d["share"].iloc[-1] * 100),
                         textcoords="offset points", xytext=(6, label_dy.get(tour, 0)),
                         fontsize=8, color=color, va="center")
        axB.set_ylim(ylo, yhi)
        axB.axvline(CHOSEN, color=editorial.REF, ls=(0, (3, 3)), lw=1.1, zorder=2)
        axB.annotate("Chosen threshold: 20s", (CHOSEN, ylo),
                     textcoords="offset points", xytext=(6, 8), fontsize=8.5,
                     color=editorial.SUBINK)
        axB.text(SWEEP[0], yhi - 0.6, "Before the 2022 directive", fontsize=8.5,
                 color=editorial.SLATE, fontweight="bold", va="top")
        axB.text(SWEEP[0], ylo + 0.6, "After the 2022 directive", fontsize=8.5,
                 color=editorial.HILITE, fontweight="bold", va="bottom")
        axB.set_xlabel("Tuning threshold (seconds)", fontsize=10.5)
        axB.set_ylabel("Live play, share of regulation (%)", fontsize=10.5)
        axB.set_title("And the before / after gap holds at every threshold",
                      fontsize=11.5, color=editorial.INK, pad=8, loc="left")
        axB.set_xlim(SWEEP[0] - 1, SWEEP[-1] + 8)

        for ax in (axA, axB):
            ax.grid(color=editorial.GRID, lw=0.7, zorder=0)
            editorial.despine(ax, keep=("left", "bottom"))

        editorial.titleblock(
            fig,
            "The tuning choice is anchored to an independent benchmark",
            ["Every “live minute” rests on one threshold: how long a gap in play counts as",
             "dead time. The chosen 20 seconds lands the reconstruction on Opta’s published",
             "figure (left), and the before / after gap between tournaments holds at any value (right)."],
            "Live-play reconstruction swept across tuning thresholds; the chosen value is 20 "
            "seconds. A published Opta benchmark exists only for the 2018 & 2022 World Cups "
            "(left).\nSource: StatsBomb open data; Opta (published figures); author’s analysis.")

        out = config.FIGURES / "bip_robustness.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
    print(f"  wrote {out}")


def table(df: pd.DataFrame) -> str:
    """Markdown table: both anchors' BIP and signed error vs Opta across the sweep."""
    lines = [
        "| max_live_gap | WC2018 BIP | Δ vs 54:50 | WC2022 BIP | Δ vs 58:04 | Σ\\|err\\| |",
        "|---|---|---|---|---|---|",
    ]
    for g in SWEEP:
        r18 = df[(df.max_live_gap_s == g) & (df.tournament == "wc_2018")].iloc[0]
        r22 = df[(df.max_live_gap_s == g) & (df.tournament == "wc_2022")].iloc[0]
        e18 = r18.bip_s - OPTA_TRUTH_S["wc_2018"]
        e22 = r22.bip_s - OPTA_TRUTH_S["wc_2022"]
        mark = "  **(chosen)**" if g == CHOSEN else ""
        lines.append(
            f"| {g}s{mark} | {_mmss(r18.bip_s)} | {e18:+.0f}s | "
            f"{_mmss(r22.bip_s)} | {e22:+.0f}s | {abs(e18) + abs(e22):.0f}s |"
        )
    return "\n".join(lines)


def main() -> None:
    df = sweep()
    figure(df)
    tbl = table(df)
    out = config.DOCS / "bip_robustness_table.md"
    out.write_text(
        "# BIP knob robustness sweep (standalone, locked tables untouched)\n\n"
        "This table stops at BIP minutes + the cross-tournament ranking. For the BIP knob "
        "propagated all the way through to the HEADLINE X% (≤0.10 pp across this whole sweep), "
        "see `docs/bip_headline_sensitivity.md` / ADR-0026.\n\n" + tbl + "\n")
    print(f"  wrote {out}\n")
    print(tbl)


if __name__ == "__main__":
    main()
