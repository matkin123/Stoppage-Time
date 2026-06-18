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
    # Focus the band figure on the central conditioning/source (overall|pooled_all): the Part C
    # axes that the lock SELECTS are silent {none,marked,all} x premium {observed,open_play} x
    # gross-up {off,on}. The conditioning/source sensitivities barely move X% (ADR-0019) and would
    # make the panel unreadable at 96 rows.
    parts = s["knob_set"].str.split("|", expand=True)
    s = s.assign(silent=parts[0], cond=parts[1], source=parts[2], prem=parts[3], gw=parts[4])
    s = s[(s["group"] == "all") & (s["window"] == hw) &
          (s["cond"] == "overall") & (s["source"] == "pooled_all")].copy()
    s["label"] = s["silent"] + " | " + s["prem"] + " | grossup=" + s["gw"]
    s = s.sort_values("pct_changed")
    xerr_lo = (s["pct_changed"] - s["ci_lo"]).clip(lower=0)
    xerr_hi = (s["ci_hi"] - s["pct_changed"]).clip(lower=0)
    fig, ax = plt.subplots(figsize=(8, max(4, 0.34 * len(s))))
    ax.errorbar(s["pct_changed"], range(len(s)), xerr=[xerr_lo, xerr_hi], fmt="o", capsize=3)
    ax.set_yticks(range(len(s)))
    ax.set_yticklabels(s["label"], fontsize=7)
    ax.set_xlabel("P(>=1 extra goal) -- share of matches")
    ax.set_title(f"Counterfactual band, window={hw}, overall|pooled_all (95% CI)")
    return _save(fig, "f05_sensitivity_grid.png")


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
        s = s.assign(silent=parts[0], cond=parts[1], source=parts[2], prem=parts[3], gw=parts[4])
        allg = s[(s["group"] == "all") & (s["window"] == hw)].copy()
        lo, hi = allg["pct_changed"].min(), allg["pct_changed"].max()
        central = "silent_marked|overall|pooled_all|observed|off"

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
            f"- full grid range: {lo:.1%} - {hi:.1%} "
            "-> processed/counterfactual_summary.parquet (group=all, window=" + hw + ")",
        ]
        if c is not None:
            lines.append(
                f"- central ({central}): {c['pct_changed']:.1%} "
                f"[CI {c['ci_lo']:.1%}, {c['ci_hi']:.1%}]")
        if c2 is not None:
            lines.append(f"- same knob, 2H_only window (comparison): {c2['pct_changed']:.1%}")
        lines.append("- X% by silent treatment (min-max across all other knobs):")
        for lvl in ("silent_none", "silent_marked", "silent_all"):
            sub = allg[allg["silent"] == lvl]
            if not sub.empty:
                lines.append(f"  - {lvl}: {sub['pct_changed'].min():.1%} - {sub['pct_changed'].max():.1%}")

        # ADR-0021 Part C: productivity-premium band, O3 gross-up, outcome-flip secondary
        def band(silent):
            out = {}
            for win in (hw, "2H_only"):
                lo_r = row(f"{silent}|overall|pooled_all|open_play|off", win)
                hi_r = row(f"{silent}|overall|pooled_all|observed|off", win)
                gu_r = row(f"{silent}|overall|pooled_all|observed|on", win)
                out[win] = (lo_r, hi_r, gu_r)
            return out
        b = band("silent_marked")
        lines += [
            "",
            "## Productivity-premium band (ADR-0021 #2; silent_marked|overall|pooled_all)",
            "- rails over the lambda applied to OMITTED minutes; live_share cancels in mu, so this "
            "is a lambda choice, not a live-share knob.",
        ]
        for win in (hw, "2H_only"):
            lo_r, hi_r, _ = b[win]
            if lo_r is not None and hi_r is not None:
                lines.append(
                    f"- {win}: OPEN-PLAY floor {lo_r['pct_changed']:.1%} "
                    f"[CI {lo_r['ci_lo']:.1%}, {lo_r['ci_hi']:.1%}]  ..  OBSERVED-stoppage "
                    f"{hi_r['pct_changed']:.1%} [CI {hi_r['ci_lo']:.1%}, {hi_r['ci_hi']:.1%}]")
        lines += [
            "",
            "## O3 in-stoppage time-wasting gross-up (ADR-0021 #3; observed lambda, silent_marked)",
            "- grosses up omitted CLOCK by (1 + time-wasting_rate) then applies productivity to the "
            "live portion; RAISES X% (faithful, no agenda).",
        ]
        for win in (hw, "2H_only"):
            _, hi_r, gu_r = b[win]
            if hi_r is not None and gu_r is not None:
                lines.append(f"- {win}: gross-up off {hi_r['pct_changed']:.1%} -> on {gu_r['pct_changed']:.1%}")
        lines += [
            "",
            "## Outcome-flip secondary metric (ADR-0021 #1; stricter 'different OUTCOME')",
            "- winner/draw status flips: tied matches flip on any extra goal; lead_by_1 flip when "
            "the trailing team (half rate) equalizes+; lead_by_2plus treated as unflippable.",
        ]
        if c is not None:
            lines.append(f"- central ({hw}): outcome-flip {c['pct_outcome_flip']:.1%} "
                         f"(vs scoreline headline {c['pct_changed']:.1%})")
        if c2 is not None:
            lines.append(f"- central (2H_only): outcome-flip {c2['pct_outcome_flip']:.1%}")
        lines += [
            "",
            "- X% is highly sensitive to the silent treatment + productivity premium -> ships as a "
            "BAND, not a point.",
            "- NOT YET LOCKED: the final session SELECTS the rails + CI in docs/decisions.md.",
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
            "- this same rate feeds the s08 O3 gross-up (above).",
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
    write_ledger(prod)
    print("  s09 complete.")


if __name__ == "__main__":
    main()
