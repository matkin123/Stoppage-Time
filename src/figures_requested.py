"""Standalone requested figures (user ad-hoc, 2026-06-18).

Renders the specific charts the user asked to see, per tournament (small-multiples
over the six tournaments) and across all tournaments (aggregate), plus a game-state
productivity table. Reads ONLY interim/processed parquet (source of truth); writes to
figures/requested/. Deterministic.

Charts (x4), each as an aggregate single-panel figure + a 2x3 per-tournament grid:
  1. incident lower bound vs time played in stoppage (scatter, y=x identity line)
  2. goals per played-minute by custom minute bucket (bar; stoppage bars highlighted)
  3. stoppage-time share of 2H goals vs share of 2H minutes played (2 bars)
  4. dead-ball % per stoppage-time minute vs per regular-time minute (2 bars, 0-100%)
Plus: table of 2H-stoppage productivity by game state at 90' (tied / 1-goal / >1-goal).

In:  interim/{matches,goals,incident_stoppage,played_in_stoppage,bip_segments,
     match_state}.parquet ; processed/stoppage_live_share.parquet
Out: figures/requested/*.png, figures/requested/*.csv, figures/requested/ledger.md
"""
from __future__ import annotations

from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.lib import config, editorial, stats

OUT = config.FIGURES / "requested"

# Tournament display order: PRE first, then POST.
TOURNEYS = [
    ("wc_2018", "World Cup 2018 (PRE)"),
    ("euro_2020", "Euro 2020 (PRE)"),
    ("wc_2022", "World Cup 2022 (POST)"),
    ("euro_2024", "Euro 2024 (POST)"),
    ("copa_america_2024", "Copa America 2024 (POST)"),
    ("afcon_2023", "AFCON 2023 (POST)"),
]

INF = 1e9
# Custom buckets the user specified (mirror around halftime: 1H = four 10s + a 5,
# 2H = a 5 + four 10s). (label, period, lo_s, hi_s). NOTE the pipeline's native 2H
# buckets are 45-55/55-65/... so these are recomputed here, not read from match_minutes.
RANGES = {
    1: [("1-10", 0, 600), ("11-20", 600, 1200), ("21-30", 1200, 1800),
        ("31-40", 1800, 2400), ("41-45", 2400, 2700), ("1H stop", 2700, INF)],
    2: [("45-50", 0, 300), ("51-60", 300, 900), ("61-70", 900, 1500),
        ("71-80", 1500, 2100), ("81-90", 2100, 2700), ("2H stop", 2700, INF)],
}
BUCKET_ORDER = [lab for per in (1, 2) for (lab, _, _) in RANGES[per]]
STOPPAGE_LABELS = {"1H stop", "2H stop"}
REG_COLOR, STOP_COLOR = "#4C72B0", "#C44E52"


def bucket_of(period: int, period_s: float) -> str | None:
    if period not in RANGES:
        return None
    for lab, lo, hi in RANGES[period]:
        if lo <= period_s < hi:
            return lab
    return None


def allocate_live_custom(seg: pd.DataFrame) -> pd.DataFrame:
    """Per (match_id, bucket) live seconds, splitting in-play segments at custom bounds."""
    acc: dict[tuple, float] = defaultdict(float)
    live = seg[seg["in_play"]]
    for r in live.itertuples(index=False):
        per = int(r.period)
        if per not in RANGES:
            continue
        s, e = float(r.start_s), float(r.end_s)
        for lab, lo, hi in RANGES[per]:
            ov = min(e, hi) - max(s, lo)
            if ov > 0:
                acc[(r.match_id, lab)] += ov
    return (pd.Series(acc, name="live_s").rename_axis(["match_id", "bucket"])
            .reset_index())


def regular_dead_seconds(seg: pd.DataFrame) -> pd.DataFrame:
    """Per match: total & live seconds in the [0,45:00) regulation portion of P1+P2."""
    tot: dict = defaultdict(float)
    liv: dict = defaultdict(float)
    for r in seg.itertuples(index=False):
        per = int(r.period)
        if per not in (1, 2):
            continue
        s, e = float(r.start_s), float(r.end_s)
        ov = min(e, 2700.0) - max(s, 0.0)
        if ov <= 0:
            continue
        tot[r.match_id] += ov
        if r.in_play:
            liv[r.match_id] += ov
    rows = [{"match_id": m, "reg_total_s": tot[m], "reg_live_s": liv.get(m, 0.0)}
            for m in tot]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- data prep
def load():
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    goals = pd.read_parquet(config.INTERIM / "goals.parquet")
    inc = pd.read_parquet(config.INTERIM / "incident_stoppage.parquet")
    pis = pd.read_parquet(config.INTERIM / "played_in_stoppage.parquet")
    seg = pd.read_parquet(config.INTERIM / "bip_segments.parquet")
    state = pd.read_parquet(config.INTERIM / "match_state.parquet")
    ls = pd.read_parquet(config.PROCESSED / "stoppage_live_share.parquet")
    ts = pd.read_parquet(config.INTERIM / "true_stoppage.parquet")

    tour = matches.set_index("match_id")["tournament"]

    # per-match scatter table
    lb = inc.groupby("match_id")["lower_bound_s"].sum() / 60
    played = pis.groupby("match_id")["played_in_stoppage_min"].sum()
    scatter = pd.DataFrame({"lb_min": lb, "played_min": played}).dropna()
    scatter["tournament"] = tour
    scatter = scatter.reset_index().rename(columns={"index": "match_id"})

    # per-match scatter table -- y = full model estimate (true_stoppage_s, the
    # silent_marked-calibrated estimator: lower_bound + marker-gated silent + residual)
    est = ts.set_index("match_id")["true_stoppage_s"] / 60
    scatter_est = pd.DataFrame({"est_min": est, "played_min": played}).dropna()
    scatter_est["tournament"] = tour
    scatter_est = scatter_est.reset_index().rename(columns={"index": "match_id"})

    # goals -> custom bucket (regulation periods only)
    g = goals[goals["period"].isin([1, 2])].copy()
    g["bucket"] = [bucket_of(p, s) for p, s in zip(g["period"], g["period_s"])]
    g = g.dropna(subset=["bucket"])
    g["tournament"] = g["match_id"].map(tour)

    # live minutes -> custom bucket
    live = allocate_live_custom(seg)
    live["tournament"] = live["match_id"].map(tour)

    # dead% inputs
    reg = regular_dead_seconds(seg)
    reg["tournament"] = reg["match_id"].map(tour)
    stop = ls[ls["phase"] == "any_stoppage"][
        ["match_id", "tournament", "stoppage_seconds", "live_seconds"]].copy()

    state = state.merge(matches[["match_id", "tournament"]], on="match_id", how="left")
    return dict(matches=matches, tour=tour, scatter=scatter, scatter_est=scatter_est,
                goals=g, live=live, reg=reg, stop=stop, state=state)


def scope_ids(d, key):
    if key == "all":
        return set(d["matches"]["match_id"])
    return set(d["matches"].loc[d["matches"]["tournament"] == key, "match_id"])


# ---------------------------------------------------------------- per-scope metrics
def productivity_by_bucket(d, ids):
    g = d["goals"][d["goals"]["match_id"].isin(ids)]
    lv = d["live"][d["live"]["match_id"].isin(ids)]
    goals_b = g.groupby("bucket").size()
    live_b = lv.groupby("bucket")["live_s"].sum() / 60
    rows = []
    for b in BUCKET_ORDER:
        n = float(goals_b.get(b, 0))
        lm = float(live_b.get(b, 0.0))
        rate, lo, hi = stats.poisson_rate_ci(n, lm) if lm > 0 else (np.nan, np.nan, np.nan)
        rows.append({"bucket": b, "goals": n, "live_min": lm,
                     "rate": rate, "ci_lo": lo, "ci_hi": hi})
    return pd.DataFrame(rows)


def two_h_shares(d, ids):
    g = d["goals"]
    g2 = g[(g["period"] == 2) & g["match_id"].isin(ids)]
    goals_stop = (g2["bucket"] == "2H stop").sum()
    goals_2h = len(g2)
    lv = d["live"][d["live"]["match_id"].isin(ids)]
    lv2 = lv[lv["bucket"].isin(["45-50", "51-60", "61-70", "71-80", "81-90", "2H stop"])]
    live_stop = lv2.loc[lv2["bucket"] == "2H stop", "live_s"].sum()
    live_2h = lv2["live_s"].sum()
    return {
        "goals_share": goals_stop / goals_2h if goals_2h else np.nan,
        "minutes_share": live_stop / live_2h if live_2h else np.nan,
        "goals_stop": int(goals_stop), "goals_2h": int(goals_2h),
        "live_stop_min": live_stop / 60, "live_2h_min": live_2h / 60,
    }


def dead_pct(d, ids):
    reg = d["reg"][d["reg"]["match_id"].isin(ids)]
    stop = d["stop"][d["stop"]["match_id"].isin(ids)]
    reg_total, reg_live = reg["reg_total_s"].sum(), reg["reg_live_s"].sum()
    st_total, st_live = stop["stoppage_seconds"].sum(), stop["live_seconds"].sum()
    return {
        "dead_regular": 1 - reg_live / reg_total if reg_total else np.nan,
        "dead_stoppage": 1 - st_live / st_total if st_total else np.nan,
    }


# ---------------------------------------------------------------- plotting
def _bar_buckets(ax, prod, title, ylabel=True):
    colors = [STOP_COLOR if b in STOPPAGE_LABELS else REG_COLOR for b in prod["bucket"]]
    x = range(len(prod))
    ax.bar(x, prod["rate"], color=colors)
    ax.set_xticks(list(x))
    ax.set_xticklabels(prod["bucket"], rotation=60, ha="right", fontsize=7)
    if ylabel:
        ax.set_ylabel("goals per played minute")
    ax.set_title(title, fontsize=9)


def _scatter(ax, sc, title):
    ax.scatter(sc["played_min"], sc["lb_min"], s=14, alpha=0.55, color=REG_COLOR)
    if len(sc):
        lim = max(sc["played_min"].max(), sc["lb_min"].max()) + 1
        above = int((sc["lb_min"] > sc["played_min"]).sum())
        pct_above = above / len(sc)
    else:
        lim, above, pct_above = 1, 0, float("nan")
    ax.plot([0, lim], [0, lim], "k--", lw=1, label="played = proven dead time")
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_xlabel("time played in stoppage (min)")
    ax.set_ylabel("incident lower bound (min)")
    ax.set_title(title, fontsize=9)
    ax.legend(fontsize=6, loc="upper left")
    ax.text(0.97, 0.04,
            f"{pct_above:.0%} of matches above the line\n"
            f"(proven stoppage > time played)\nn={above}/{len(sc)}",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=7,
            bbox=dict(boxstyle="round", fc="white", ec="0.6", alpha=0.85))


def _scatter_estimate(ax, sc, title):
    ax.scatter(sc["played_min"], sc["est_min"], s=14, alpha=0.55, color=REG_COLOR)
    if len(sc):
        lim = max(sc["played_min"].max(), sc["est_min"].max()) + 1
        above = int((sc["est_min"] > sc["played_min"]).sum())
        pct_above = above / len(sc)
    else:
        lim, above, pct_above = 1, 0, float("nan")
    ax.plot([0, lim], [0, lim], "k--", lw=1, label="played = estimated stoppage")
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_xlabel("time played in stoppage (min)")
    ax.set_ylabel("estimated stoppage time (model, min)")
    ax.set_title(title, fontsize=9)
    ax.legend(fontsize=6, loc="upper left")
    ax.text(0.97, 0.04,
            f"{pct_above:.0%} of matches above the line\n"
            f"(estimated stoppage > time played)\nn={above}/{len(sc)}",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=7,
            bbox=dict(boxstyle="round", fc="white", ec="0.6", alpha=0.85))


def _shares(ax, sh, title):
    ax.bar(["share of\n2H goals", "share of 2H\nminutes played"],
           [sh["goals_share"], sh["minutes_share"]], color=[STOP_COLOR, REG_COLOR])
    ax.set_ylim(0, max(0.05, sh["goals_share"], sh["minutes_share"]) * 1.25)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_title(title, fontsize=9)
    for i, v in enumerate([sh["goals_share"], sh["minutes_share"]]):
        if np.isfinite(v):
            ax.text(i, v, f"{v:.1%}", ha="center", va="bottom", fontsize=7)


def _deadpct(ax, dp, title):
    ax.bar(["stoppage-time\nminute", "regular-time\nminute"],
           [dp["dead_stoppage"], dp["dead_regular"]], color=[STOP_COLOR, REG_COLOR])
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_title(title, fontsize=9)
    for i, v in enumerate([dp["dead_stoppage"], dp["dead_regular"]]):
        if np.isfinite(v):
            ax.text(i, v, f"{v:.1%}", ha="center", va="bottom", fontsize=7)


def _save(fig, name):
    path = OUT / name
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {path}")


# ================================================================ publication figures
# Two charts (agg_01 scatter, agg_02 bar) are redesigned to the editorial style guide
# (docs/editorial_graphics_style_guide.md). These use dedicated render functions so the
# per-tournament small-multiples (which share _scatter_estimate/_bar_buckets) are untouched.
# Shared styling (palette, title block, footer) lives in src/lib/editorial.py.

PUB_RC = editorial.RC
HILITE = editorial.HILITE
NEUTRAL = editorial.NEUTRAL
NEUTRAL_PT = editorial.NEUTRAL_PT
INK = editorial.INK
SUBINK = editorial.SUBINK
FOOTER = editorial.FOOTER
_titleblock = editorial.titleblock


# ------- agg_02: goals per live minute, by stage of the match -------
BUCKET_PUB = {
    "1-10": "0–10", "11-20": "10–20", "21-30": "20–30", "31-40": "30–40",
    "41-45": "40–45", "1H stop": "45'+",
    "45-50": "45–50", "51-60": "50–60", "61-70": "60–70", "71-80": "70–80",
    "81-90": "80–90", "2H stop": "90'+",
}


def _bar_buckets_pub(prod):
    prod = prod.set_index("bucket").reindex(BUCKET_ORDER).reset_index()
    reg = prod[~prod["bucket"].isin(STOPPAGE_LABELS)]
    baseline = reg["goals"].sum() / reg["live_min"].sum()
    rates = prod["rate"].to_numpy()
    is_stop = prod["bucket"].isin(STOPPAGE_LABELS).to_numpy()

    with plt.rc_context(PUB_RC):
        fig = plt.figure(figsize=(10.2, 6.4))
        ax = fig.add_axes([0.085, 0.205, 0.885, 0.545])
        x = np.arange(len(prod))
        colors = [HILITE if s else NEUTRAL for s in is_stop]
        ax.bar(x, rates, color=colors, width=0.78, zorder=3)

        # regular-play average reference line (label parked over the short early bars)
        ax.axhline(baseline, color="#6B7178", lw=1.0, ls=(0, (4, 3)), zorder=2)
        ax.text(-0.35, baseline + 0.0016, "Regular-play average",
                ha="left", va="bottom", fontsize=8.5, color="#6B7178", style="italic")

        # value labels on the two highlighted (added-time) bars
        for xi, r, s in zip(x, rates, is_stop):
            if s:
                ax.text(xi, r + 0.0016, f"{r:.3f}", ha="center", va="bottom",
                        fontsize=9, fontweight="bold", color=HILITE)

        # hero insight annotation -> tip lands just left of the "0.082" data label,
        # vertically centred on it and above the red bar
        ax.annotate(
            "Goals come nearly twice as fast\nin second-half added time",
            xy=(10.5, rates[-1] + 0.0033), xytext=(7.3, rates[-1] * 0.93),
            ha="center", va="top", fontsize=10, color=INK, fontweight="bold",
            arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.2,
                            connectionstyle="arc3,rad=-0.2"))

        ax.set_xticks(x)
        ax.set_xticklabels([BUCKET_PUB[b] for b in prod["bucket"]], fontsize=8.6)
        ax.set_ylim(0, max(rates) * 1.16)
        ax.set_ylabel("Goals per live minute", fontsize=11)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.02f}"))
        ax.margins(x=0.01)
        ax.grid(axis="y", color="#E6E8EA", lw=0.8, zorder=0)
        ax.set_axisbelow(True)
        for sp in ("top", "right", "left"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(length=0)

        # half-group structure beneath the axis
        ax.axvline(5.5, color="#D7DADE", lw=1.0, ymin=-0.16, ymax=1.0,
                   clip_on=False, zorder=1)
        for xc, lab in ((2.5, "F I R S T   H A L F"), (8.5, "S E C O N D   H A L F")):
            ax.text(xc, -0.16, lab, transform=ax.get_xaxis_transform(),
                    ha="center", va="top", fontsize=9, color="#6B7178",
                    fontweight="bold")

        _titleblock(
            fig,
            "Goal scoring increases dramatically in stoppage time",
            ["Goals per live minute by stage of the match. Scoring climbs through each "
             "half and spikes in added time (red).",
             "A “live minute” counts only the time the ball is actually in play."],
            FOOTER)
    _save(fig, "agg_02_productivity_by_bucket.png")


# ------- agg_01: true stoppage-time estimate vs stoppage time actually played -------
def _scatter_estimate_pub(sc):
    played = sc["played_min"].to_numpy()
    est = sc["est_min"].to_numpy()
    n = len(sc)
    above = est > played
    pct_above = above.mean()
    lim = max(played.max(), est.max()) + 1.5
    med_played, med_est = float(np.median(played)), float(np.median(est))

    with plt.rc_context(PUB_RC):
        # Wide canvas for side whitespace: the plot is a square and height-limited,
        # so the extra width does NOT change its physical size — it just becomes
        # margin, and the symmetric box + anchor "N" keep the plot centred.
        fig = plt.figure(figsize=(11.4, 9.1))
        ax = fig.add_axes([0.10, 0.15, 0.80, 0.64])
        ax.set_anchor("N")

        # identity (fairness) line
        ax.plot([0, lim], [0, lim], color="#3C4043", lw=1.3, zorder=2)
        # points: red above the line (cut short), grey below (played extra)
        ax.scatter(played[above], est[above], s=20, color=HILITE, alpha=0.55,
                   linewidths=0, zorder=3)
        ax.scatter(played[~above], est[~above], s=20, color=NEUTRAL_PT, alpha=0.7,
                   linewidths=0, zorder=3)

        # "typical match" marker -> the ~2x story, made concrete
        ax.scatter([med_played], [med_est], s=95, color=INK, marker="D",
                   zorder=5, edgecolors="white", linewidths=1.1)
        ax.annotate(
            f"Typical match\n~{med_played:.0f} min played,\n~{med_est:.0f} min owed",
            xy=(med_played, med_est), xytext=(med_played + 12.5, med_est - 5.5),
            fontsize=9.5, color=INK, ha="left", va="top",
            arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.1,
                            connectionstyle="arc3,rad=0.2"))

        # inline label for the diagonal (replaces the legend)
        ax.text(lim * 0.74, lim * 0.74, "Played = estimate", rotation=45,
                rotation_mode="anchor", ha="center", va="bottom", fontsize=9.5,
                color="#3C4043", style="italic")
        ax.text(lim * 0.755, lim * 0.74, "clock stopped on time", rotation=45,
                rotation_mode="anchor", ha="center", va="top", fontsize=8,
                color="#8A8F96", style="italic")

        # region cue: what being above the line means (parked in the clear upper-
        # right white space so it doesn't sit on top of the dot cloud)
        ax.text(0.47, 0.965, "Above the line:\nmatch ended too early",
                transform=ax.transAxes, ha="left", va="top", fontsize=9.5,
                color=HILITE, fontweight="bold")

        ax.set_xlim(0, lim)
        ax.set_ylim(0, lim)
        ax.set_aspect("equal")
        ax.set_xlabel("Stoppage time actually played (minutes)", fontsize=11, labelpad=6)
        ax.set_ylabel("True stoppage-time estimate (minutes)", fontsize=11, labelpad=6)
        ax.grid(color="#ECEEEF", lw=0.7, zorder=0)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(length=0, labelsize=9.5)

        source = (FOOTER.split("\n")[0] +
                  "\nSource: StatsBomb open data; author’s analysis, calibrated to "
                  "Nate Silver at r = 0.88, MAE = 1.77 mins")
        _titleblock(
            fig,
            "Matches play about half the stoppage time they’re owed",
            [f"Each red dot is one of {n} matches. {pct_above:.0%} of matches ended too early,",
             "with more stoppage owed than was actually played."],
            source, left_in=1.7)
    _save(fig, "agg_01_scatter_estimate_vs_played.png")


def small_multiples(d, plot_fn, metric_fn, fname, suptitle):
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    for ax, (key, label) in zip(axes.ravel(), TOURNEYS):
        ids = scope_ids(d, key)
        plot_fn(ax, metric_fn(d, ids), label)
    fig.suptitle(suptitle, fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    _save(fig, fname)


# ---------------------------------------------------------------- game-state table
STATE_LABELS = [("tied", "Tied"), ("lead_by_1", "1-goal diff"),
                ("lead_by_2plus", ">1-goal diff")]


def game_state_table(d):
    g = d["goals"]
    g2 = g[(g["period"] == 2) & (g["bucket"] == "2H stop")].merge(
        d["state"][["match_id", "state_at_90"]], on="match_id", how="left")
    lv = d["live"]
    lv2 = lv[lv["bucket"] == "2H stop"].merge(
        d["state"][["match_id", "state_at_90"]], on="match_id", how="left")
    rows = []
    for code, lab in STATE_LABELS:
        n_matches = int((d["state"]["state_at_90"] == code).sum())
        n_goals = int((g2["state_at_90"] == code).sum())
        live_min = lv2.loc[lv2["state_at_90"] == code, "live_s"].sum() / 60
        rate, lo, hi = (stats.poisson_rate_ci(n_goals, live_min)
                        if live_min > 0 else (np.nan, np.nan, np.nan))
        rows.append({"state_at_90": lab, "n_matches": n_matches,
                     "goals_2H_stoppage": n_goals, "live_min_2H_stoppage": round(live_min, 2),
                     "goals_per_played_min": round(rate, 4),
                     "ci_lo": round(lo, 4), "ci_hi": round(hi, 4)})
    return pd.DataFrame(rows)


STATE_PLAIN = {"Tied": "Level", "1-goal diff": "Within one goal",
               ">1-goal diff": "Two or more goals apart"}


def render_table_png(tab):
    cols = ["Score at 90 min", "Matches", "Stoppage goals", "Live minutes",
            "Goals per live minute (95% CI)"]
    aligns = ["left", "center", "center", "center", "left"]
    cell_text = []
    for _, r in tab.iterrows():
        rate = r["goals_per_played_min"]
        ci = (f"{rate:.3f}   [{r['ci_lo']:.3f}, {r['ci_hi']:.3f}]"
              if np.isfinite(rate) else "n/a")
        cell_text.append([STATE_PLAIN.get(r["state_at_90"], r["state_at_90"]),
                          f"{int(r['n_matches'])}", f"{int(r['goals_2H_stoppage'])}",
                          f"{r['live_min_2H_stoppage']:.0f}", ci])

    with plt.rc_context(PUB_RC):
        fig = plt.figure(figsize=(12.0, 4.3))
        # table occupies a fixed band; bbox=[0,0,1,1] makes it fill the axes exactly
        # (equal row heights, no overflow into the title or footer).
        ax = fig.add_axes([0.035, 0.20, 0.93, 0.40])
        ax.axis("off")
        widths = [0.25, 0.11, 0.17, 0.16, 0.31]
        t = ax.table(cellText=cell_text, colLabels=cols, colWidths=widths,
                     bbox=[0, 0, 1, 1])
        t.auto_set_font_size(False)
        t.set_fontsize(11)
        ncol = len(cols)
        for (row, col), cell in t.get_celld().items():
            cell.set_edgecolor("none")
            cell.PAD = 0.04
            ha = aligns[col]
            if row == 0:  # header: bottom rule only, bold ink, metric col in red
                cell.visible_edges = "B"
                cell.set_edgecolor(INK)
                cell.set_linewidth(1.2)
                cell.set_text_props(fontweight="bold", ha=ha,
                                    color=HILITE if col == ncol - 1 else INK)
            else:  # faint row separators; the metric column carries weight
                cell.visible_edges = "B"
                cell.set_edgecolor(editorial.GRID)
                cell.set_linewidth(0.8)
                cell.set_text_props(ha=ha, color=INK,
                                    fontweight="bold" if col == ncol - 1 else "normal")

        editorial.titleblock(
            fig,
            "Whatever the score, stoppage time scores the same",
            ["Second-half stoppage-time scoring by the score when the 90th minute is",
             "reached. The rate hardly shifts between level and decided matches."],
            FOOTER, left_in=0.42)
    _save(fig, "t01_gamestate_productivity.png")


# ---------------------------------------------------------------- main
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = load()

    # ---- aggregate single-panel figures ----
    fig, ax = plt.subplots(figsize=(7, 7))
    _scatter(ax, d["scatter"], "All tournaments")
    _save(fig, "agg_01_scatter_lb_vs_played.png")

    _scatter_estimate_pub(d["scatter_est"])

    _bar_buckets_pub(productivity_by_bucket(d, scope_ids(d, "all")))

    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    _shares(ax, two_h_shares(d, scope_ids(d, "all")), "All tournaments")
    _save(fig, "agg_03_2H_shares.png")

    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    _deadpct(ax, dead_pct(d, scope_ids(d, "all")), "All tournaments")
    _save(fig, "agg_04_dead_pct.png")

    # ---- per-tournament small-multiples ----
    small_multiples(d, _scatter, _scatter_data,
                    "tour_01_scatter_lb_vs_played.png",
                    "Incident lower bound vs time played in stoppage (per tournament)")
    small_multiples(d, _scatter_estimate, _scatter_est_data,
                    "tour_01_scatter_estimate_vs_played.png",
                    "Estimated stoppage time (model) vs time played in stoppage (per tournament)")
    small_multiples(d, _bar_buckets, productivity_by_bucket,
                    "tour_02_productivity_by_bucket.png",
                    "Goals per played minute by match bucket (per tournament)")
    small_multiples(d, _shares, two_h_shares, "tour_03_2H_shares.png",
                    "Stoppage-time share of 2H goals vs 2H minutes played (per tournament)")
    small_multiples(d, _deadpct, dead_pct, "tour_04_dead_pct.png",
                    "Dead-ball % per stoppage vs regular minute (per tournament)")

    # ---- game-state table ----
    tab = game_state_table(d)
    tab.to_csv(OUT / "t01_gamestate_productivity.csv", index=False)
    render_table_png(tab)

    write_ledger(d, tab)
    print("  requested figures complete.")


def _scatter_data(d, ids):
    return d["scatter"][d["scatter"]["match_id"].isin(ids)]


def _scatter_est_data(d, ids):
    return d["scatter_est"][d["scatter_est"]["match_id"].isin(ids)]


def write_ledger(d, tab):
    lines = ["# Requested figures - numbers ledger", "",
             "Generated by `src/figures_requested.py` from interim/processed parquet.", "",
             "## Aggregate (all tournaments)", ""]
    allids = scope_ids(d, "all")
    sh = two_h_shares(d, allids)
    dp = dead_pct(d, allids)
    lines += [
        f"- 2H-stoppage share of 2H goals: **{sh['goals_share']:.1%}** "
        f"({sh['goals_stop']}/{sh['goals_2h']} goals)",
        f"- 2H-stoppage share of 2H minutes played: **{sh['minutes_share']:.1%}** "
        f"({sh['live_stop_min']:.1f}/{sh['live_2h_min']:.1f} live-min)",
        f"- dead-ball % per stoppage-time minute: **{dp['dead_stoppage']:.1%}**",
        f"- dead-ball % per regular-time minute: **{dp['dead_regular']:.1%}**", "",
        "## Productivity by bucket (all tournaments) -- goals per played minute", ""]
    prod = productivity_by_bucket(d, allids)
    for _, r in prod.iterrows():
        flag = " (stoppage)" if r["bucket"] in STOPPAGE_LABELS else ""
        lines.append(f"- {r['bucket']}{flag}: {r['rate']:.4f}  "
                     f"(n={r['goals']:.0f}, live_min={r['live_min']:.1f})")
    lines += ["", "## Game-state table (2H-stoppage productivity at 90')", "",
              "| state at 90' | n matches | 2H-stop goals | 2H-stop played min | goals/played min [95% CI] |",
              "|---|---|---|---|---|"]
    for _, r in tab.iterrows():
        lines.append(
            f"| {r['state_at_90']} | {r['n_matches']} | {r['goals_2H_stoppage']} | "
            f"{r['live_min_2H_stoppage']:.2f} | {r['goals_per_played_min']:.4f} "
            f"[{r['ci_lo']:.4f}, {r['ci_hi']:.4f}] |")
    lines += ["", "## Per-tournament aggregates", "",
              "| tournament | 2H goal share | 2H min share | dead% stoppage | dead% regular |",
              "|---|---|---|---|---|"]
    for key, label in TOURNEYS:
        ids = scope_ids(d, key)
        s, p = two_h_shares(d, ids), dead_pct(d, ids)
        lines.append(f"| {label} | {s['goals_share']:.1%} | {s['minutes_share']:.1%} | "
                     f"{p['dead_stoppage']:.1%} | {p['dead_regular']:.1%} |")
    (OUT / "ledger.md").write_text("\n".join(lines) + "\n")
    print(f"  wrote {OUT / 'ledger.md'}")


if __name__ == "__main__":
    main()
