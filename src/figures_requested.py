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

from src.lib import config, stats

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


def render_table_png(tab):
    fig, ax = plt.subplots(figsize=(13, 2.4))
    ax.axis("off")
    disp = tab.copy()
    disp["rate [95% CI]"] = [
        f"{r:.4f} [{lo:.4f}, {hi:.4f}]" if np.isfinite(r) else "n/a"
        for r, lo, hi in zip(tab["goals_per_played_min"], tab["ci_lo"], tab["ci_hi"])]
    disp = disp[["state_at_90", "n_matches", "goals_2H_stoppage",
                 "live_min_2H_stoppage", "rate [95% CI]"]]
    disp.columns = ["state @ 90'", "n matches", "2H-stop goals",
                    "2H-stop played min", "goals/played min [95% CI]"]
    t = ax.table(cellText=disp.values, colLabels=disp.columns,
                 cellLoc="center", loc="center",
                 colWidths=[0.15, 0.12, 0.15, 0.18, 0.30])
    t.auto_set_font_size(False)
    t.set_fontsize(9)
    t.scale(1, 1.6)
    for j in range(len(disp.columns)):
        t[0, j].set_facecolor("#4C72B0")
        t[0, j].set_text_props(color="white", fontweight="bold")
    ax.set_title("2H-stoppage goal productivity by game state at 90' (all tournaments)",
                 fontsize=11, pad=12)
    _save(fig, "t01_gamestate_productivity.png")


# ---------------------------------------------------------------- main
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = load()

    # ---- aggregate single-panel figures ----
    fig, ax = plt.subplots(figsize=(7, 7))
    _scatter(ax, d["scatter"], "All tournaments")
    _save(fig, "agg_01_scatter_lb_vs_played.png")

    fig, ax = plt.subplots(figsize=(7, 7))
    _scatter_estimate(ax, d["scatter_est"], "All tournaments")
    _save(fig, "agg_01_scatter_estimate_vs_played.png")

    fig, ax = plt.subplots(figsize=(10, 5.5))
    _bar_buckets(ax, productivity_by_bucket(d, scope_ids(d, "all")), "All tournaments")
    _save(fig, "agg_02_productivity_by_bucket.png")

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
