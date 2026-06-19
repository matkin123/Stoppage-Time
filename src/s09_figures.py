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

from src.lib import config


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
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.bar(sub["state"], sub["rate"],
           yerr=[sub["rate"] - sub["ci_lo"], sub["ci_hi"] - sub["rate"]], capsize=4)
    ax.set_ylabel("goals per live-minute (2H stoppage)")
    ax.set_title("2H-stoppage goal productivity by state at 90'")
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
    (the central spec's per-match grossed omitted-2H clock + obs/floor rates) and avg_lambda (s08)."""
    import numpy as np

    from src.s08_counterfactual import avg_lambda
    path = config.PROCESSED / "decay_profile.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    obs = float(df["obs_rate"].iloc[0])
    floor = float(df["floor_rate"].iloc[0])
    T = df["omitted_2h_clock_min"].to_numpy()
    T = T[np.isfinite(T)]
    tmax = max(12.0, float(np.nanmax(T)) if len(T) else 12.0)
    curves = [(2.0, "tab:red"), (4.0, "tab:blue"), (8.0, "tab:orange")]

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 5))

    # left: per-marginal-minute lambda(t) = floor + (obs-floor)*0.5**(t/h)
    t = np.linspace(0.0, tmax, 240)
    axhL = axL.twinx()
    axhL.hist(T, bins=24, color="0.88", zorder=0)
    axhL.set_ylabel("matches (omitted-2H clock)")
    axhL.set_zorder(axL.get_zorder() - 1)
    axL.patch.set_visible(False)
    for h, c in curves:
        lab = f"h={h:g} min" + ("  (CENTRAL)" if h == 4.0 else "")
        axL.plot(t, floor + (obs - floor) * 0.5 ** (t / h), color=c, lw=2, label=lab)
    axL.axhline(obs, ls="--", color="k", lw=1, label=f"observed 2H-stoppage ({obs:.4f})")
    axL.axhline(floor, ls=":", color="gray", lw=1.2, label=f"open-play floor ({floor:.4f})")
    axL.set_xlabel("marginal omitted 2H minute t")
    axL.set_ylabel(r"goals per live-minute  $\lambda(t)$")
    axL.set_title("Per-minute productivity decay")
    axL.set_xlim(0, tmax)
    axL.legend(fontsize=7, loc="upper right")

    # right: effective window-average rate avg_lambda(T,h) a match actually gets
    Tg = np.linspace(0.02, tmax, 240)
    axhR = axR.twinx()
    axhR.hist(T, bins=24, color="0.88", zorder=0)
    axhR.set_ylabel("matches (omitted-2H clock)")
    axhR.set_zorder(axR.get_zorder() - 1)
    axR.patch.set_visible(False)
    for h, c in curves:
        lab = f"h={h:g} min" + ("  (CENTRAL)" if h == 4.0 else "")
        axR.plot(Tg, avg_lambda(Tg, h, obs, floor), color=c, lw=2, label=lab)
    axR.axhline(obs, ls="--", color="k", lw=1)
    axR.axhline(floor, ls=":", color="gray", lw=1.2)
    if len(T):
        meanT = float(np.nanmean(T))
        axR.axvline(meanT, color="green", lw=1.2, label=f"mean T = {meanT:.1f} min")
    axR.set_xlabel("total omitted 2H clock minutes T (grossed)")
    axR.set_ylabel(r"effective average  $\overline{\lambda}(T)$")
    axR.set_title("Effective rate a match actually gets")
    axR.set_xlim(0, tmax)
    axR.legend(fontsize=7, loc="upper right")

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
        # regression-only hl endpoints (inf/0.0) and the geometric ceiling row are excluded.
        reported = s[(s["group"] == "all") & (s["window"] == hw) &
                     (s["silent"] == "silent_marked") &
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
