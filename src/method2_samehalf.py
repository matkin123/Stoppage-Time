"""Method 2 (same-half live share + same-half gross-up z) -- ANALYSIS ONLY (next_session.md / ADR-0027).

Tests the user's preferred fix for the s08 gross-up asymmetry: instead of converting omitted
added-time CLOCK -> omitted LIVE minutes with a match/window-specific live share `lsw` but a POOLED
whole-match scalar z=0.382, assume the OMITTED minutes look like the average SAME-HALF minute -- that
half's REGULAR play PLUS that half's PLAYED stoppage combined -- for BOTH the live share AND the
gross-up z. Both factors then come from the same reference period (the whole played half), so:

    ls_half[m,h] = sum dur(in_play) / sum dur          over ALL period-h segments (NOT clipped at 2700)
    z_half[m,h]  = (lower_bound_s + silent_marked_s) / sum dur(NOT in_play)   over the whole half
    flw          = ls_half * (1 + z_half * (1 - ls_half))        (replaces lsw*(1+z_genuine*(1-lsw)))
    olive_h      = max(0, true_stoppage_h - played_h) * flw      (true_stoppage + played UNCHANGED)
    T2 (horizon) = olive_2H / ls_half[2H]                        (replaces olive_2H / lsw_2H)
    avg2         = avg_lambda(T2, 4.0, obs2, floor2)             (lambda cells UNCHANGED -- pooled)
    mu, P, X%, outcome-flip                                       (closed form, central knob_set only)

The lambda population rates (lam1, obs2, floor2) STAY the pooled cells s08 uses -- Method 2 changes
only the CLOCK->LIVE conversion + the decay horizon, NOT the goals-per-live-minute rates. In
particular the lambda-EXPOSURE live share is still the stoppage-window live-minutes in
build_lambda_cells, so Method 2 deliberately breaks the live-share cancellation (ADR-0026).

Standalone, NOT a stage, NOT a gate, NOT a lock. READS the production parquet; writes only a small
report (print + docs/method2_samehalf.md). Touches NO processed parquet, NO s08 grid, NO figure, NO
params (pattern: src/bip_headline_sensitivity.py; guardrail: ADR-0025 lock + CLAUDE.md sec 6).

Run: python -m src.method2_samehalf
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.lib import config
from src.s08_counterfactual import (
    avg_lambda,
    build_lambda_cells,
    genuine_stoppage_share,
    p_change,
    regular_lambda_cells,
    two_h_addable_share,
)

CENTRAL = "silent_marked|overall|pooled_all|hl=4.0|on"
HALFLIFE = 4.0
# Locked references (ADR-0025 / ADR-0027) for the comparison lines.
LOCKED = {"scoreline_1H+2H": 0.236, "scoreline_2H_only": 0.160, "flip_1H+2H": 0.121}
LOCKED_SE = {"scoreline": 0.196, "flip": 0.103}   # Spain-England central
M1_HEADLINE = 0.234                                # Method 1 (ADR-0027)
M1_SE = {"scoreline": 0.178, "flip": 0.093}        # Method 1 Spain-England (ADR-0027)
GROSSUP_BAND = (0.211, 0.242)                      # off .. geometric, h=4 (ADR-0024)


def same_half_factors(seg, incident):
    """ls_half[(mid,'1H'|'2H')] and z_half[(mid,'1H'|'2H')] over the WHOLE played half.

    ls_half = in-play share of ALL period-h segments (regulation + played added time; NOT clipped at
    2700). z_half = counted addable stoppage (lower_bound + marked silent, EXCLUDING the frozen
    residual constant, matching the pooled z definition) / total dead time, over that whole half.
    Returns dicts keyed (match_id, window)."""
    s = seg.copy()
    s["dur"] = s["end_s"] - s["start_s"]
    half = s[s["period"].isin([1, 2])]
    tot = half.groupby(["match_id", "period"])["dur"].sum()
    live = half[half["in_play"]].groupby(["match_id", "period"])["dur"].sum()
    dead = half[~half["in_play"]].groupby(["match_id", "period"])["dur"].sum()
    counted = (incident.assign(c=incident["lower_bound_s"] + incident["silent_marked_s"])
               .query("period in [1, 2]").set_index(["match_id", "period"])["c"])
    wmap = {1: "1H", 2: "2H"}
    ls_half, z_half = {}, {}
    for (mid, per), t in tot.items():
        w = wmap[per]
        ls_half[(mid, w)] = float(live.get((mid, per), 0.0) / t) if t > 0 else 0.0
        d = float(dead.get((mid, per), 0.0))
        z_half[(mid, w)] = float(counted.get((mid, per), 0.0) / d) if d > 0 else 0.0
    return ls_half, z_half


def main() -> None:
    p = config.params()
    cfg, sil = p["counterfactual"], p["silent"]
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    goals = pd.read_parquet(config.INTERIM / "goals.parquet")
    state = pd.read_parquet(config.INTERIM / "match_state.parquet")
    incident = pd.read_parquet(config.INTERIM / "incident_stoppage.parquet")
    seg = pd.read_parquet(config.INTERIM / "bip_segments.parquet")
    live_share = pd.read_parquet(config.PROCESSED / "stoppage_live_share.parquet")
    prod = pd.read_parquet(config.PROCESSED / "productivity.parquet")
    pis = pd.read_parquet(config.INTERIM / "played_in_stoppage.parquet")

    # --- per-(match,window) inputs, exactly as s08 main() builds them -----------------------
    pmap = {"1H_stoppage": "1H", "2H_stoppage": "2H"}
    live_min, ls_ratio = {}, {}
    for r in live_share.itertuples(index=False):
        w = pmap.get(r.phase)
        if w is None:
            continue
        live_min[(r.match_id, w)] = r.live_seconds / 60.0
        ls_ratio[(r.match_id, w)] = r.live_share          # stoppage-window live share lsw (central)
    played = {}
    for r in pis.itertuples(index=False):
        if r.period in (1, 2):
            played[(r.match_id, "1H" if r.period == 1 else "2H")] = float(r.played_in_stoppage_min)
    inc = {}
    for r in incident.itertuples(index=False):
        if r.period in (1, 2):
            inc[(r.match_id, "1H" if r.period == 1 else "2H")] = (
                float(r.lower_bound_s), float(r.silent_marked_s), float(r.silent_all_s))

    f2 = two_h_addable_share(incident)
    f1 = 1.0 - f2
    fshare = {"1H": f1, "2H": f2}
    z_genuine = genuine_stoppage_share(incident, seg)     # pooled scalar (central uses this)
    residual_s = float(sil["residual_silent_s"])

    def ts_window_min(mid, window):
        """central silent_marked true_stoppage minutes for one window (UNCHANGED by Method 2)."""
        lb, sm, _sa = inc.get((mid, window), (0.0, 0.0, 0.0))
        return (lb + sm + residual_s * fshare[window]) / 60.0

    # pooled lambda cells (central: pooled_all, overall) + the open-play floor cell.
    cells = build_lambda_cells(matches, goals, state, live_min)
    for coh, ce in regular_lambda_cells(prod).items():
        cells[("__regular__", coh)] = ce

    def cell_rate(key):
        c, e = cells[key]
        return c / e if e > 0 else 0.0

    lam1 = cell_rate(("all", "1H", "overall", "all"))     # pooled 1H stoppage rate
    obs2 = cell_rate(("all", "2H", "overall", "all"))     # pooled 2H stoppage rate (decay START)
    floor2 = cell_rate(("__regular__", "all"))            # pooled open-play rate (decay FLOOR)

    eligible = [m for m in matches["match_id"] if (m, "2H") in played]
    n = len(eligible)
    st_dict = state.set_index("match_id").to_dict("index")
    s90 = np.array([st_dict[m]["state_at_90"] for m in eligible])
    tied90, lead1_90 = s90 == "tied", s90 == "lead_by_1"

    def outcome_flip(mu_arr):
        pf = np.zeros(n)
        pf[tied90] = p_change(mu_arr[tied90])
        pf[lead1_90] = p_change(mu_arr[lead1_90] / 2.0)
        return pf

    # same-half factors (Method 2)
    ls_half, z_half = same_half_factors(seg, incident)

    # --- compute olive/T2/mu for a given live-share + z provider -----------------------------
    def run(get_ls, get_z, label):
        out = {}
        olive = {}
        ls2_arr = np.nan_to_num(np.array([get_ls(m, "2H") for m in eligible]), nan=0.0)
        for window in ("1H", "2H"):
            tsw = np.array([ts_window_min(m, window) for m in eligible])
            plw = np.array([played.get((m, window), 0.0) for m in eligible])
            # nan_to_num matches s08: a window with zero added time has NaN live_share (0/0).
            lsw = np.nan_to_num(np.array([get_ls(m, window) for m in eligible]), nan=0.0)
            zw = np.nan_to_num(np.array([get_z(m, window) for m in eligible]), nan=0.0)
            flw = lsw * (1.0 + zw * (1.0 - lsw))           # gross-up ON
            olive[window] = np.maximum(0.0, tsw - plw) * flw
            out[f"omit_clock_{window}"] = np.maximum(0.0, tsw - plw)
            out[f"olive_{window}"] = olive[window]
            out[f"ls_{window}"] = lsw
            out[f"z_{window}"] = zw
        ls2_safe = np.where(ls2_arr > 0, ls2_arr, 1.0)
        T2 = np.where(ls2_arr > 0, olive["2H"] / ls2_safe, 0.0)
        avg2 = avg_lambda(T2, HALFLIFE, obs2, floor2)
        mu = {"1H+2H": lam1 * olive["1H"] + avg2 * olive["2H"],
              "2H_only": avg2 * olive["2H"]}
        for w in mu:
            out[f"P_{w}"] = p_change(mu[w])
            out[f"flip_{w}"] = outcome_flip(mu[w])
            out[f"X_{w}"] = float(p_change(mu[w]).mean())
            out[f"flipX_{w}"] = float(outcome_flip(mu[w]).mean())
        out["label"] = label
        return out

    def get_lsw(m, w):
        return ls_ratio.get((m, w), 0.0)

    def get_lshalf(m, w):
        return ls_half.get((m, w), ls_ratio.get((m, w), 0.0))

    central = run(get_lsw, lambda m, w: z_genuine, "central (locked)")
    m2 = run(get_lshalf, lambda m, w: z_half.get((m, w), 0.0), "Method 2 (same-half)")
    # channel decomposition: A isolates the live-share swap (breaks the cancellation), B isolates z.
    chanA = run(get_lshalf, lambda m, w: z_genuine, "A: ls_half + pooled z")
    chanB = run(get_lsw, lambda m, w: z_half.get((m, w), 0.0), "B: lsw + z_half")

    # --- harness check: central must reproduce the locked artifact ---------------------------
    cf = pd.read_parquet(config.PROCESSED / "counterfactual.parquet")
    locked = {w: float(cf[(cf.window == w) & (cf.knob_set == CENTRAL)].p_change.mean())
              for w in ("1H+2H", "2H_only")}
    print("HARNESS CHECK (central must reproduce processed/counterfactual.parquet):")
    for w in ("1H+2H", "2H_only"):
        print(f"  {w:<8} my central X={central[f'X_{w}']:.5f}  locked={locked[w]:.5f}  "
              f"d={abs(central[f'X_{w}'] - locked[w]):.2e}")
    assert abs(central["X_1H+2H"] - locked["1H+2H"]) < 1e-9, "central harness drift -- abort"

    # --- diagnostics -------------------------------------------------------------------------
    def mean_over(d, w):
        return float(np.mean([d.get((m, w), np.nan) for m in eligible]))
    diag = {}
    for w in ("1H", "2H"):
        diag[f"ls_half_{w}"] = mean_over(ls_half, w)
        diag[f"lsw_{w}"] = float(np.nanmean([ls_ratio.get((m, w), np.nan) for m in eligible]))
        diag[f"z_half_{w}"] = mean_over(z_half, w)
    z_all = np.array([z_half.get((m, w), np.nan) for m in eligible for w in ("1H", "2H")])
    ls_all = np.array([ls_half.get((m, w), np.nan) for m in eligible for w in ("1H", "2H")])
    ok = np.isfinite(z_all) & np.isfinite(ls_all)
    corr = float(np.corrcoef(ls_all[ok], z_all[ok])[0, 1])
    z_half_pooledmean = float(np.nanmean(z_all))

    # --- Spain-England (Euro 2024 final) -----------------------------------------------------
    se_mid = matches[(matches.tournament == "euro_2024") & (matches.stage == "Final")].iloc[0].match_id
    se_i = eligible.index(se_mid)

    def se_row(d):
        return {
            "omit_clock_min": float(d["omit_clock_1H"][se_i] + d["omit_clock_2H"][se_i]),
            "olive_min": float(d["olive_1H"][se_i] + d["olive_2H"][se_i]),
            "P_scoreline": float(d["P_1H+2H"][se_i]),
            "P_flip": float(d["flip_1H+2H"][se_i]),
            "ls_2H": float(d["ls_2H"][se_i]), "z_2H": float(d["z_2H"][se_i]),
        }
    se_c, se_m = se_row(central), se_row(m2)

    # ---------------------------- report -----------------------------------------------------
    band_lo, band_hi = GROSSUP_BAND
    inband = band_lo <= m2["X_1H+2H"] <= band_hi
    L = []
    L.append("# Method 2 (same-half live share + same-half gross-up z) -- ANALYSIS, NOT A LOCK")
    L.append("")
    L.append("Standalone test of the user's preferred fix for the s08 gross-up live-share / z "
             "asymmetry (ADR-0027). Omitted added-time minutes are assumed to look like the average "
             "SAME-HALF minute (that half's regular play + played stoppage) for BOTH the live share "
             "and the gross-up z. READS production parquet; no locked artifact touched. Central spec "
             f"`{CENTRAL}`, gross-up ON, decay h={HALFLIFE}.")
    L.append("")
    L.append("## Headline X% (deterministic central point)")
    L.append("")
    L.append("| window | locked (ADR-0025) | Method 1 (ADR-0027) | **Method 2** |")
    L.append("|---|---|---|---|")
    L.append(f"| scoreline 1H+2H | {LOCKED['scoreline_1H+2H']*100:.1f}% | ~{M1_HEADLINE*100:.1f}% | "
             f"**{m2['X_1H+2H']*100:.2f}%** |")
    L.append(f"| scoreline 2H_only | {LOCKED['scoreline_2H_only']*100:.1f}% | -- | "
             f"**{m2['X_2H_only']*100:.2f}%** |")
    L.append(f"| outcome-flip 1H+2H | {LOCKED['flip_1H+2H']*100:.1f}% | -- | "
             f"**{m2['flipX_1H+2H']*100:.2f}%** |")
    L.append(f"| outcome-flip 2H_only | -- | -- | **{m2['flipX_2H_only']*100:.2f}%** |")
    L.append("")
    L.append(f"Gross-up rail band (ADR-0024, h=4): **[{band_lo*100:.1f}%, {band_hi*100:.1f}%]** "
             f"(off .. geometric). Method 2 scoreline 1H+2H = **{m2['X_1H+2H']*100:.2f}%** -> "
             f"**{'INSIDE' if inband else 'OUTSIDE'}** the band.")
    L.append("")
    L.append("## Spain-England (Euro 2024 final), state@90 = lead_by_1")
    L.append("")
    L.append("| quantity | locked central | Method 1 | **Method 2** |")
    L.append("|---|---|---|---|")
    L.append(f"| omitted clock (min) | {se_c['omit_clock_min']:.2f} | (same) | "
             f"{se_m['omit_clock_min']:.2f} |")
    L.append(f"| omitted LIVE (min) | {se_c['olive_min']:.2f} | -- | {se_m['olive_min']:.2f} |")
    L.append(f"| P scoreline | {LOCKED_SE['scoreline']*100:.1f}% | {M1_SE['scoreline']*100:.1f}% | "
             f"**{se_m['P_scoreline']*100:.2f}%** |")
    L.append(f"| P flip | {LOCKED_SE['flip']*100:.1f}% | {M1_SE['flip']*100:.1f}% | "
             f"**{se_m['P_flip']*100:.2f}%** |")
    L.append(f"| 2H live share used | {se_c['ls_2H']:.3f} (lsw) | -- | {se_m['ls_2H']:.3f} (ls_half) |")
    L.append(f"| 2H z used | {se_c['z_2H']:.3f} (pooled) | 0.008 (window) | {se_m['z_2H']:.3f} (z_half) |")
    L.append("")
    L.append("## Channel decomposition (1H+2H scoreline X%)")
    L.append("")
    dA = (chanA["X_1H+2H"] - central["X_1H+2H"]) * 100
    dB = (chanB["X_1H+2H"] - central["X_1H+2H"]) * 100
    dtot = (m2["X_1H+2H"] - central["X_1H+2H"]) * 100
    L.append(f"- central -> Method 2: **{dtot:+.2f} pp** ({central['X_1H+2H']*100:.2f}% -> "
             f"{m2['X_1H+2H']*100:.2f}%).")
    L.append(f"- **A: live-share swap** (ls_half, pooled z) = {chanA['X_1H+2H']*100:.2f}% "
             f"(**{dA:+.2f} pp**) -- this is the BROKEN-CANCELLATION channel.")
    L.append(f"- **B: z swap** (lsw, z_half) = {chanB['X_1H+2H']*100:.2f}% (**{dB:+.2f} pp**).")
    L.append(f"- interaction = {dtot - dA - dB:+.2f} pp. BOTH channels push the headline UP and are "
             f"comparable in size (live-share {dA:+.2f} pp, z_half {dB:+.2f} pp).")
    L.append("")
    L.append("## Diagnostics")
    L.append("")
    L.append(f"- pooled-mean live share -- **1H**: ls_half {diag['ls_half_1H']:.3f} vs lsw "
             f"{diag['lsw_1H']:.3f}; **2H**: ls_half {diag['ls_half_2H']:.3f} vs lsw {diag['lsw_2H']:.3f}.")
    L.append(f"- pooled-mean z_half -- **1H** {diag['z_half_1H']:.3f}, **2H** {diag['z_half_2H']:.3f}, "
             f"**overall** {z_half_pooledmean:.3f} vs pooled scalar z={z_genuine:.3f}.")
    L.append(f"- corr(ls_half, z_half) over all (match,half) = **{corr:+.3f}**.")
    L.append(f"- lambda rates UNCHANGED (pooled): lam1={lam1:.4f}, obs2={obs2:.4f}, floor2={floor2:.4f}.")
    L.append("")
    L.append("**Cancellation caveat.** The locked headline is robust partly because live share scales "
             "BOTH omitted-live AND lambda-exposure (mu ~= G*omitted/total, ADR-0026). Method 2 changes "
             "the omitted-live live share but NOT the lambda-exposure live share (still stoppage-window "
             "live-minutes in build_lambda_cells), so it deliberately breaks that cancellation.")
    out = config.DOCS / "method2_samehalf.md"
    out.write_text("\n".join(L) + "\n")

    # ---- console echo ----
    print("\n===== METHOD 2 HEADLINE =====")
    print(f"  scoreline 1H+2H : {m2['X_1H+2H']*100:6.2f}%   (locked {LOCKED['scoreline_1H+2H']*100:.1f}%, "
          f"M1 ~{M1_HEADLINE*100:.1f}%)   band [{band_lo*100:.1f},{band_hi*100:.1f}] -> "
          f"{'INSIDE' if inband else 'OUTSIDE'}")
    print(f"  scoreline 2H_only: {m2['X_2H_only']*100:6.2f}%   (locked {LOCKED['scoreline_2H_only']*100:.1f}%)")
    print(f"  flip 1H+2H      : {m2['flipX_1H+2H']*100:6.2f}%   (locked {LOCKED['flip_1H+2H']*100:.1f}%)")
    print(f"  flip 2H_only    : {m2['flipX_2H_only']*100:6.2f}%")
    print("\n===== CHANNEL DECOMPOSITION (1H+2H scoreline) =====")
    print(f"  central {central['X_1H+2H']*100:.2f}% -> M2 {m2['X_1H+2H']*100:.2f}% "
          f"({(m2['X_1H+2H']-central['X_1H+2H'])*100:+.2f} pp)")
    print(f"  A live-share (ls_half, pooled z): {chanA['X_1H+2H']*100:.2f}% "
          f"({(chanA['X_1H+2H']-central['X_1H+2H'])*100:+.2f} pp) <- broken cancellation")
    print(f"  B z swap     (lsw, z_half):       {chanB['X_1H+2H']*100:.2f}% "
          f"({(chanB['X_1H+2H']-central['X_1H+2H'])*100:+.2f} pp)")
    print("\n===== SPAIN-ENGLAND =====")
    print(f"  omitted clock {se_c['omit_clock_min']:.2f}min (unchanged); "
          f"omitted LIVE {se_c['olive_min']:.2f} -> {se_m['olive_min']:.2f}min")
    print(f"  P scoreline {LOCKED_SE['scoreline']*100:.1f}% -> {se_m['P_scoreline']*100:.2f}%  "
          f"(M1 {M1_SE['scoreline']*100:.1f}%)")
    print(f"  P flip      {LOCKED_SE['flip']*100:.1f}% -> {se_m['P_flip']*100:.2f}%  "
          f"(M1 {M1_SE['flip']*100:.1f}%)")
    print(f"  2H ls_half {se_m['ls_2H']:.3f} (vs lsw {se_c['ls_2H']:.3f}); "
          f"2H z_half {se_m['z_2H']:.3f} (vs pooled {se_c['z_2H']:.3f})")
    print("\n===== DIAGNOSTICS =====")
    print(f"  ls_half vs lsw  1H {diag['ls_half_1H']:.3f}/{diag['lsw_1H']:.3f}  "
          f"2H {diag['ls_half_2H']:.3f}/{diag['lsw_2H']:.3f}")
    print(f"  z_half  1H {diag['z_half_1H']:.3f}  2H {diag['z_half_2H']:.3f}  "
          f"overall {z_half_pooledmean:.3f}  (pooled scalar {z_genuine:.3f})")
    print(f"  corr(ls_half, z_half) = {corr:+.3f}")
    print(f"\n  wrote {out}")


if __name__ == "__main__":
    main()
