"""s09 -- Figures & numbers ledger.

Renders the final figures from processed tables and writes docs/numbers_ledger.md,
mapping each article claim to the producing table/cell. Deterministic: no randomness,
re-running yields identical output.

In:  processed/*.parquet, interim/*.parquet
Out: figures/*.png, docs/numbers_ledger.md
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.lib import config, editorial


def _save(fig, name):
    path = config.FIGURES / name
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {path}")
    return path


def fig_productivity_by_bucket(prod):
    sub = prod[(prod["dimension"] == "bucket") & (prod["scope"] == "pooled") &
               (prod["metric"] == "goals")].copy()
    sub["b"] = sub["phase_or_bucket"].astype(int)
    # DC3: drop extra-time buckets (>=10). They produced a spurious minute-120 spike from
    # ET/penalty goals that read as if penalties contaminate regulation scoring. The figure is
    # a REGULATION productivity curve (buckets 0-9 = P1 0-45, P2 45-90); ET is out of scope.
    sub = sub[sub["b"] < 10].sort_values("b")
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.errorbar(sub["b"] * 10, sub["rate"],
                yerr=[sub["rate"] - sub["ci_lo"], sub["ci_hi"] - sub["rate"]],
                fmt="o-", capsize=3)
    ax.set_xlabel("match minute (bucket start)")
    ax.set_ylabel("goals per live-minute")
    ax.set_title("Goal productivity per live-minute by 10-min bucket (pooled, regulation only)")
    return _save(fig, "f01_productivity_by_bucket.png")


def fig_stoppage_by_state(prod):
    sub = prod[(prod["dimension"] == "state_2H_stoppage") & (prod["scope"] == "pooled") &
               (prod["metric"] == "goals")]
    if sub.empty:
        return None
    order = ["tied", "non_tied", "all"]
    label = {"tied": "Level at 90'", "non_tied": "One side ahead", "all": "All matches"}
    rows = {r["state"]: r for _, r in sub.iterrows()}
    rows = [rows[s] for s in order if s in rows]
    rates = [r["rate"] for r in rows]
    lo = [r["rate"] - r["ci_lo"] for r in rows]
    hi = [r["ci_hi"] - r["rate"] for r in rows]
    # "All matches" is the reference (red); the two score states are neutral — the
    # point is that the score at 90' barely moves the rate.
    colors = [editorial.HILITE if r["state"] == "all" else editorial.NEUTRAL for r in rows]

    with plt.rc_context(editorial.RC):
        fig = plt.figure(figsize=(8.0, 6.6))
        ax = fig.add_axes([0.12, 0.135, 0.82, 0.585])
        x = range(len(rows))
        ax.bar(x, rates, width=0.6, color=colors, zorder=3)
        ax.errorbar(x, rates, yerr=[lo, hi], fmt="none", ecolor="#3C4043",
                    capsize=7, lw=1.3, zorder=4)
        for xi, r in zip(x, rows):
            ax.text(xi, r["ci_hi"] + 0.004, f"{r['rate']:.3f}", ha="center",
                    va="bottom", fontsize=12, fontweight="bold", color=editorial.INK)
        ax.set_xticks(list(x))
        ax.set_xticklabels([label[r["state"]] for r in rows], fontsize=11)
        ax.set_ylabel("Goals per live minute", fontsize=11)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.02f}"))
        ax.set_ylim(0, max(r["ci_hi"] for r in rows) * 1.18)
        ax.grid(axis="y", color=editorial.GRID, lw=0.8, zorder=0)
        editorial.despine(ax, keep=("bottom",))
        editorial.titleblock(
            fig,
            "Whatever the score, stoppage time scores the same",
            ["Goals per live minute in second-half stoppage, by the score when the 90th",
             "minute is reached. Leading, trailing or level, the rate barely moves."],
            "Second-half stoppage only, across all 314 matches from six tournaments, "
            "2018–2024.\nSource: StatsBomb open data; author’s analysis.")
    return _save(fig, "f02_stoppage_by_state.png")


def fig_board_pre_post():
    path = config.PROCESSED / "played_in_stoppage_descriptive.parquet"
    if not path.exists():
        return None
    desc = pd.read_parquet(path)
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.bar(desc.index.astype(str), desc["mean"])
    ax.set_ylabel("time played in stoppage per match (min)")
    ax.set_title("Time played in stoppage: PRE vs POST")
    return _save(fig, "f03_board_pre_post.png")


def fig_lb_vs_board():
    inc_path = config.INTERIM / "incident_stoppage.parquet"
    pis_path = config.INTERIM / "played_in_stoppage.parquet"
    if not pis_path.exists():
        return None
    inc = pd.read_parquet(inc_path)
    pis = pd.read_parquet(pis_path)
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    lb = inc.groupby("match_id")["lower_bound_s"].sum() / 60
    played = pis.groupby("match_id")["played_in_stoppage_min"].sum()
    grp = matches.set_index("match_id")["group"]
    df = pd.DataFrame({"lb": lb, "played": played, "group": grp}).dropna()
    fig, ax = plt.subplots(figsize=(6, 6))
    for g, c in (("PRE", "tab:blue"), ("POST", "tab:orange")):
        d = df[df["group"] == g]
        ax.scatter(d["played"], d["lb"], s=14, alpha=0.6, label=g, color=c)
    lim = max(df["played"].max(), df["lb"].max()) + 1
    ax.plot([0, lim], [0, lim], "k--", lw=1, label="y=x")
    ax.set_xlabel("time played in stoppage (min)")
    ax.set_ylabel("incident lower bound (min)")
    ax.set_title("Lower bound vs time played in stoppage")
    ax.legend()
    return _save(fig, "f04_lb_vs_board.png")


def fig_sensitivity():
    path = config.PROCESSED / "counterfactual_summary.parquet"
    if not path.exists():
        return None
    hw = config.params()["counterfactual"]["headline_window"]
    s = pd.read_parquet(path)
    # LOCK (ADR-0025): silent is a calibrated POINT (silent_marked), NOT a plotted sensitivity axis;
    # silent_none/all are known-wrong bounds excluded from all reported figures. The reported band is
    # over the LEGITIMATE knobs. This panel fixes the central conditioning/source (overall|pooled_all)
    # -- those barely move X% (ADR-0019) and would clutter -- and shows the decay-half-life {2,4,8} x
    # gross-up {off,on} band. Regression-only endpoints (hl=inf/0.0) and the geometric row are dropped.
    parts = s["knob_set"].str.split("|", expand=True)
    s = s.assign(silent=parts[0], cond=parts[1], source=parts[2], hl=parts[3], gw=parts[4])
    s = s[(s["group"] == "all") & (s["window"] == hw) &
          (s["silent"] == "silent_marked") &
          (s["cond"] == "overall") & (s["source"] == "pooled_all") &
          (s["gw"].isin(["off", "on"])) & (~s["hl"].isin(["hl=inf", "hl=0.0"]))].copy()
    s["label"] = s["hl"] + " | grossup=" + s["gw"]
    s = s.sort_values("pct_changed")
    xerr_lo = (s["pct_changed"] - s["ci_lo"]).clip(lower=0)
    xerr_hi = (s["ci_hi"] - s["pct_changed"]).clip(lower=0)
    fig, ax = plt.subplots(figsize=(8, max(4, 0.34 * len(s))))
    ax.errorbar(s["pct_changed"], range(len(s)), xerr=[xerr_lo, xerr_hi], fmt="o", capsize=3)
    ax.set_yticks(range(len(s)))
    ax.set_yticklabels(s["label"], fontsize=7)
    ax.set_xlabel("P(>=1 extra goal) -- share of matches")
    ax.set_title(f"Counterfactual band, window={hw}, silent_marked|overall|pooled_all (95% CI)")
    return _save(fig, "f05_sensitivity_grid.png")


def fig_productivity_decay():
    """Promote the IMPL-8 prototype to a permanent figure (ADR-0024). Traces to decay_profile.parquet
    (the central spec's per-match grossed omitted-2H clock + obs/floor rates).

    Editorial redesign: the central 4-min half-life is the SUBJECT (red); the 2- and 8-min
    bounds are neutral context. Reference lines (observed stoppage rate, open-play floor) are
    named in white space. The three half-life curves are keyed in a small legend parked in the
    top-right white space, just below the stoppage-time scoring-rate line, where the curves have
    decayed toward the floor and left the corner clear."""
    import numpy as np

    path = config.PROCESSED / "decay_profile.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    obs = float(df["obs_rate"].iloc[0])
    floor = float(df["floor_rate"].iloc[0])
    R = obs - floor

    tmax = 30.0  # full decay window: by 30 unplayed minutes every curve has cooled to the floor

    # (half-life, colour, lineweight, linestyle, label) — central is the red highlight (solid);
    # the two neutral bounds share the same grey, distinguished by pattern (fades fast dotted,
    # fades slow dashed). All three are keyed in a boxed legend rather than on the curves.
    grey = "#92969B"  # editorial.NEUTRAL (#B7BCC2) darkened ~20% for the two neutral bounds
    curves = [(2.0, grey, 1.6, ":", "Fades fast (2 min)"),
              (4.0, editorial.HILITE, 2.6, "-", "Central: 4-min half-life"),
              (8.0, grey, 1.6, "--", "Fades slow (8 min)")]

    with plt.rc_context(editorial.RC):
        fig = plt.figure(figsize=(9.8, 6.6))
        H = fig.get_size_inches()[1]
        content_top = editorial.titleblock(
            fig,
            "The model assumes that stoppage time scoring decays in omitted minutes",
            "If we add more time, teams won’t keep scoring at the same rate. The model’s "
            "central choice is a 4-minute half-life, bracketed by a faster and slower "
            "alternative.",
            "Built from second-half stoppage scoring across all 314 matches, 2018–2024. "
            "Central spec: 4-minute half-life.\nSource: StatsBomb open data; author’s analysis.",
            content_gap_in=0.42)
        ax_bottom = 0.155
        ax_top = content_top - 0.30 / H  # leave room for the axes (sub)title
        ax = fig.add_axes([0.08, ax_bottom, 0.885, ax_top - ax_bottom])
        ylim = (floor - R * 0.18, obs + R * 0.24)

        # per-marginal-minute lambda(t) = floor + (obs-floor)*0.5**(t/h)
        t = np.linspace(0.0, tmax, 300)
        handles = []
        for h, c, lw, ls, lab in curves:
            y = floor + R * 0.5 ** (t / h)
            line, = ax.plot(t, y, color=c, lw=lw, ls=ls, label=lab, zorder=3)
            handles.append(line)

        # Legend keyed in the top-right white space, parked just below the stoppage-time
        # scoring-rate line. Sits in a solid-white, dark-grey-bordered box (opaque, drawn above
        # the gridlines). Each label is coloured to its curve; the central spec is bold.
        leg_order = list(reversed(curves))  # legend reads top→bottom: slow, central, fast
        leg = ax.legend(handles=list(reversed(handles)), loc="upper right",
                        bbox_to_anchor=(0.985, 0.77), frameon=True, fancybox=False,
                        facecolor="white", edgecolor="#3C4043", framealpha=1.0,
                        handlelength=2.6, handletextpad=0.7, labelspacing=0.6, fontsize=8.5,
                        borderaxespad=0.0)
        leg.set_zorder(6)
        leg.get_frame().set_linewidth(0.9)
        for txt, (h, _c, _lw, _ls, _lab) in zip(leg.get_texts(), leg_order):
            txt.set_color(_c)
            txt.set_fontweight("bold" if h == 4.0 else "normal")

        # reference lines, named in clear white space, both left-aligned to minute 1 — drawn
        # SOLID as the two "walls" that bound the estimates (stoppage rate above, open play below)
        ax.axhline(obs, ls="-", color="#3C4043", lw=1.1, zorder=2)
        ax.axhline(floor, ls="-", color="#3C4043", lw=1.2, zorder=2)
        ax.annotate("Stoppage time scoring rate", (1, obs), textcoords="offset points",
                    xytext=(0, 3), ha="left", va="bottom", fontsize=8.5, style="italic",
                    color="#3C4043")
        ax.annotate("Open play scoring rate", (1, floor), textcoords="offset points",
                    xytext=(0, -3), ha="left", va="top", fontsize=8.5, style="italic",
                    color="#3C4043")

        ax.set_xlabel("Minutes into the unplayed stoppage time", fontsize=10.5)
        ax.set_ylabel("Goals per live minute", fontsize=10.5)
        ax.set_title("Decayed goal-scoring rate for each hypothetical added minute",
                     fontsize=11.5, color=editorial.INK, pad=8, loc="left")
        ax.set_xlim(0, tmax)
        ax.set_ylim(*ylim)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.02f}"))
        ax.grid(color=editorial.GRID, lw=0.7, zorder=0)
        editorial.despine(ax, keep=("left", "bottom"))

    return _save(fig, "f06_productivity_decay.png")


def write_ledger(prod):
    lines = ["# Numbers ledger", "",
             "Every article figure -> producing table + cell. Regenerated by s09.", ""]

    def cell(scope, dim, metric, key, state="all"):
        m = prod[(prod["scope"] == scope) & (prod["dimension"] == dim) &
                 (prod["metric"] == metric) & (prod["phase_or_bucket"] == str(key)) &
                 (prod["state"] == state)]
        if m.empty:
            return "n/a"
        r = m.iloc[0]
        return f"{r['rate']:.4f} [{r['ci_lo']:.4f}, {r['ci_hi']:.4f}] (n={r['n_events']:.0f}, live_min={r['live_minutes']:.1f})"

    lines += [
        "## Productivity (goals per live-minute, pooled)",
        f"- 2H stoppage: `{cell('pooled','phase','goals','2H_stoppage')}` "
        "-> processed/productivity.parquet (scope=pooled,dimension=phase,phase=2H_stoppage,metric=goals)",
        f"- regular play: `{cell('pooled','phase','goals','regular')}` -> same table, phase=regular",
        f"- 2H stoppage, tied at 90: `{cell('pooled','state_2H_stoppage','goals','2H_stoppage','tied')}`",
        f"- 2H stoppage, non-tied: `{cell('pooled','state_2H_stoppage','goals','2H_stoppage','non_tied')}`",
        "",
    ]

    cf = config.PROCESSED / "counterfactual_summary.parquet"
    if cf.exists():
        hw = config.params()["counterfactual"]["headline_window"]
        s = pd.read_parquet(cf)
        parts = s["knob_set"].str.split("|", expand=True)
        s = s.assign(silent=parts[0], cond=parts[1], source=parts[2], hl=parts[3], gw=parts[4])
        # LOCK (ADR-0025): silent is a SINGLE calibrated estimate (silent_marked, calibrated to Nate
        # WC2018 ground truth), reported as a POINT -- NOT a sensitivity knob. silent_none/all are
        # known-wrong bounds kept ONLY as internal monotonicity guardrails in the grid; they are
        # NEVER reported as a range. The reported assumption range is over the LEGITIMATE knobs
        # (conditioning x source x decay-half-life x gross-up) with silent FIXED at silent_marked;
        # regression-only hl endpoints (inf/0.0), the geometric ceiling row, and the stage-source
        # rows (pooled_group/pooled_elim, ADR-0033) are excluded -- the last are a separate
        # robustness row that must not re-centre the reported band/envelope.
        band_sources = ["pooled_all", "pooled_post", "pooled_pre", "regime_matched"]
        reported = s[(s["group"] == "all") & (s["window"] == hw) &
                     (s["silent"] == "silent_marked") & (s["source"].isin(band_sources)) &
                     (s["gw"].isin(["off", "on"])) & (~s["hl"].isin(["hl=inf", "hl=0.0"]))].copy()
        allg = reported
        joint_lo, joint_hi = allg["pct_changed"].min(), allg["pct_changed"].max()
        central = "silent_marked|overall|pooled_all|hl=4.0|on"
        cen_cond, cen_src, cen_hl, cen_gw = "overall", "pooled_all", "hl=4.0", "on"

        def per_knob_band(frame):
            # One-factor-at-a-time: sweep EACH legitimate knob while holding the other three
            # at central. This is the LEAD band (ADR-0025) -- a defensible "vary one assumption
            # at a time" range, distinct from (and narrower than) the full joint min-max envelope.
            sweeps = pd.concat([
                frame[(frame["source"] == cen_src) & (frame["hl"] == cen_hl) & (frame["gw"] == cen_gw)],
                frame[(frame["cond"] == cen_cond) & (frame["hl"] == cen_hl) & (frame["gw"] == cen_gw)],
                frame[(frame["cond"] == cen_cond) & (frame["source"] == cen_src) & (frame["gw"] == cen_gw)],
                frame[(frame["cond"] == cen_cond) & (frame["source"] == cen_src) & (frame["hl"] == cen_hl)],
            ])
            return sweeps["pct_changed"].min(), sweeps["pct_changed"].max()

        band_lo, band_hi = per_knob_band(reported)

        def row(knob, win=hw):
            q = s[(s["group"] == "all") & (s["window"] == win) & (s["knob_set"] == knob)]
            return q.iloc[0] if not q.empty else None

        c = row(central)
        c2 = row(central, "2H_only")
        lines += [
            "## Headline counterfactual (X% = mean P[>=1 extra goal in omitted stoppage])",
            "- metric: mu = sum_h lambda_h * omitted_live_h; P(change)=1-exp(-mu); "
            "X%=mean over matches (s08, ADR-0019). No Monte Carlo.",
            f"- headline window: {hw}  (>=1 extra goal anywhere in omitted added time).",
            "- LOCKED ADR-0025 (2026-06-19). Framing: if stoppage time were measured and awarded "
            "per the rulebook, X% of matches would have ended with a DIFFERENT SCORELINE.",
            f"- **HEADLINE BAND (lead): {band_lo:.1%} - {band_hi:.1%}** -- one-factor-at-a-time over the "
            "legitimate knobs (conditioning x source x decay-half-life x gross-up), each swept while the "
            "other three sit at central; silent FIXED at calibrated silent_marked.",
        ]
        if c is not None:
            lines.append(
                f"- central point ({central}): {c['pct_changed']:.1%} "
                f"[95% CI {c['ci_lo']:.1%}, {c['ci_hi']:.1%}]")
        lines.append(
            f"- full JOINT min-max envelope (all legitimate knobs varied together): "
            f"{joint_lo:.1%} - {joint_hi:.1%} "
            "-> processed/counterfactual_summary.parquet (group=all, window=" + hw + ")")
        if c2 is not None:
            lines.append(f"- same knob, 2H_only window (comparison): {c2['pct_changed']:.1%}")
        lines.append(
            "- SILENT treatment is a SINGLE CALIBRATED ESTIMATE (silent_marked, calibrated to Nate "
            "WC2018 ground truth), reported as a POINT -- NOT a sensitivity knob. silent_none/all are "
            "known-wrong bounds kept ONLY as internal monotonicity guardrails in the grid; they are "
            "NOT reported as a range, in the headline or the sensitivity table (ADR-0025).")

        # IMPL-8 (ADR-0024): the decay half-life sweep REPLACES the old productivity-premium rails.
        def hrow(hlf, gw, win):
            return row(f"silent_marked|overall|pooled_all|hl={hlf}|{gw}", win)
        lines += [
            "",
            "## Productivity-decay half-life band (ADR-0024; silent_marked|overall|pooled_all, gross-up ON)",
            "- replaces the old observed/open-play rails: the 2H lambda DECAYS from the observed "
            "2H-stoppage rate toward the open-play floor over the omitted window; half-life h is the "
            "swept band parameter. Reported band = h in [2,8]min; central h=4. live_share cancels in mu.",
        ]
        for win in (hw, "2H_only"):
            fl, mid, ce = hrow("2.0", "on", win), hrow("4.0", "on", win), hrow("8.0", "on", win)
            if mid is not None and fl is not None and ce is not None:
                lines.append(
                    f"- {win}: h2 FLOOR {fl['pct_changed']:.1%} "
                    f"[CI {fl['ci_lo']:.1%}, {fl['ci_hi']:.1%}]  ..  h4 CENTRAL {mid['pct_changed']:.1%} "
                    f"[CI {mid['ci_lo']:.1%}, {mid['ci_hi']:.1%}]  ..  h8 CEIL {ce['pct_changed']:.1%} "
                    f"[CI {ce['ci_lo']:.1%}, {ce['ci_hi']:.1%}]")
        lines += [
            "- endpoint regression (gross-up OFF): h=inf backs out the OLD `observed` rail, h=0 the "
            "OLD `open_play` floor (2H_only exact; 1H+2H differs because the decay floors only 2H).",
        ]
        for win in (hw, "2H_only"):
            no_decay, instant = hrow("inf", "off", win), hrow("0.0", "off", win)
            if no_decay is not None and instant is not None:
                lines.append(f"  - {win}: h=inf(=observed) {no_decay['pct_changed']:.1%} .. "
                             f"h=0(=open_play) {instant['pct_changed']:.1%}")
        lines += [
            "",
            "## O3 in-stoppage time-wasting gross-up (ADR-0024; central=ON, h=4, silent_marked)",
            "- grosses up omitted CLOCK for the stoppage WITHIN added time, then applies the decayed "
            "lambda to the live portion; central is gross-up ON (one pass). Only the genuine-stoppage "
            "fraction z of dead time recurs (refs compensate stoppage, not normal flow), so one pass "
            "adds z*(1-live_share) of the clock and the geometric limit is ls/(1-z*(1-ls)) -- just "
            "above ON, NOT the old 1/live_share (ADR-0024 z-correction; z=0.38 from regulation dead "
            "vs counted stoppage).",
        ]
        for win in (hw, "2H_only"):
            off, on = hrow("4.0", "off", win), hrow("4.0", "on", win)
            geom = row("silent_marked|overall|pooled_all|hl=4.0|geometric", win)
            if off is not None and on is not None:
                gtxt = f" -> geometric ceiling {geom['pct_changed']:.1%}" if geom is not None else ""
                lines.append(f"- {win}: gross-up off {off['pct_changed']:.1%} -> on(CENTRAL) "
                             f"{on['pct_changed']:.1%}{gtxt}")
        lines += [
            "",
            "## Stage-source robustness: group stage vs knockout (ADR-0033)",
            "- recompute the headline X% sourcing EVERY match's goal rates from a single stage cohort "
            "(group-stage-only / knockout-only lambda), the stage analogue of pooled_pre/pooled_post. "
            "Per-match omitted-live minutes + decay horizon are lambda-source independent (reused from "
            "the central spec); only the cohort rates swap in. Point estimate only -- a REPORTED "
            "robustness row, EXCLUDED from the band/envelope (like the geometric ceiling).",
        ]
        for win in (hw, "2H_only"):
            grp = row(f"silent_marked|overall|pooled_group|hl=4.0|on", win)
            elim = row(f"silent_marked|overall|pooled_elim|hl=4.0|on", win)
            allm = row(central, win)
            if grp is not None and elim is not None and allm is not None:
                lines.append(f"- {win}: group stage {grp['pct_changed']:.1%} .. all matches "
                             f"{allm['pct_changed']:.1%} (CENTRAL) .. knockout {elim['pct_changed']:.1%}")
        lines += [
            "",
            "## Outcome-flip secondary metric (ADR-0021 #1; stricter 'different OUTCOME')",
            "- winner/draw status flips: tied matches flip on any extra goal; lead_by_1 flip when "
            "the trailing team (half rate) equalizes+; lead_by_2plus treated as unflippable.",
        ]
        if c is not None:
            lines.append(f"- central ({hw}): outcome-flip {c['pct_outcome_flip']:.1%} "
                         f"[CI {c['flip_ci_lo']:.1%}, {c['flip_ci_hi']:.1%}] "
                         f"(vs scoreline headline {c['pct_changed']:.1%})")
        if c2 is not None:
            lines.append(f"- central (2H_only): outcome-flip {c2['pct_outcome_flip']:.1%} "
                         f"[CI {c2['flip_ci_lo']:.1%}, {c2['flip_ci_hi']:.1%}]")
        # assumption-vs-sampling (ADR-0025): silent is FIXED at the calibrated silent_marked point,
        # so the reported assumption spread is over the LEGITIMATE knobs only (conditioning x source
        # x decay x gross-up). none/all are known-wrong and not reported, so there is no
        # "incl. silent" ratio.
        samp = float(c["ci_hi"] - c["ci_lo"]) if c is not None else float("nan")
        band_width = float(band_hi - band_lo)
        asm_joint = float(allg["pct_changed"].max() - allg["pct_changed"].min())
        lock_line = (
            f"- LOCKED in docs/decisions.md ADR-0025 (2026-06-19): X% = central "
            f"{c['pct_changed']:.1%} [95% CI {c['ci_lo']:.1%}, {c['ci_hi']:.1%}], window {hw}, "
            f"knob_set {central}." if c is not None
            else "- LOCKED in docs/decisions.md ADR-0025 (2026-06-19).")
        lines += [
            "",
            "## Assumption-vs-sampling uncertainty (ADR-0025)",
            f"- central 95% CI width (sampling): {samp:.1%}.",
            f"- LEAD assumption band, one-factor-at-a-time over the legitimate knobs (silent FIXED at "
            f"calibrated silent_marked): {band_lo:.1%} - {band_hi:.1%}, width {band_width:.1%} "
            f"-> ratio {band_width / samp:.1f}x sampling.",
            f"- full JOINT envelope (all legitimate knobs varied together): {joint_lo:.1%} - "
            f"{joint_hi:.1%}, width {asm_joint:.1%} -> ratio {asm_joint / samp:.1f}x sampling.",
            "- silent treatment is reported as a single calibrated POINT, NOT a sensitivity axis: "
            "silent_none/all are known-wrong and excluded from all reported ranges (ADR-0025). The "
            "reported model uncertainty is sampling (CI) + the legitimate assumption knobs "
            "(lambda-source, decay half-life, gross-up, conditioning).",
            lock_line,
            "",
        ]
    else:
        lines += ["## Headline counterfactual", "- (run s08 first)", ""]

    # A.2 time-wasting within played stoppage (IMPL-7 Part A.2)
    tw_path = config.PROCESSED / "timewasting_descriptive.parquet"
    if tw_path.exists():
        tw = pd.read_parquet(tw_path)
        per = tw.groupby(["match_id", "group"])["timewaste_min"].sum()
        grp = per.groupby("group").mean()
        pooled_rate = tw["timewaste_min"].sum() / tw["played_min"].sum()
        lines += [
            "## A.2 time-wasting within played stoppage (descriptive; IMPL-7 Part A)",
            f"- dead-ball minutes during the added time that WAS played = played * (1 - live_share). "
            f"-> processed/timewasting_descriptive.parquet",
            f"- pooled rate (dead / played): {pooled_rate:.1%}; mean min/match "
            f"PRE {grp.get('PRE', float('nan')):.2f} / POST {grp.get('POST', float('nan')):.2f}.",
            "- the gross-up (above) does NOT recur this full rate: only the genuine-stoppage "
            "fraction z=0.38 of dead time is compensable (ADR-0024 z-correction).",
            "- (board_announced under-allocation Delta = true_stoppage - board_announced is DEFERRED: "
            "needs the SofaScore scrape; board_announced still NULL.)",
            "",
        ]

    (config.DOCS / "numbers_ledger.md").write_text("\n".join(lines))
    print(f"  wrote {config.DOCS / 'numbers_ledger.md'}")


def main() -> None:
    config.ensure_dirs()
    prod = pd.read_parquet(config.PROCESSED / "productivity.parquet")
    fig_productivity_by_bucket(prod)
    fig_stoppage_by_state(prod)
    fig_board_pre_post()
    fig_lb_vs_board()
    fig_sensitivity()
    fig_productivity_decay()
    write_ledger(prod)
    print("  s09 complete.")


if __name__ == "__main__":
    main()
