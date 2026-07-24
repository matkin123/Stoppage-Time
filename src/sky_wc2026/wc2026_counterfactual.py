"""WC2026 counterfactual: headline scoreline/result-flip probabilities.

Applies the same closed-form Poisson model as the StatsBomb s08 pipeline to the
96 WC2026 matches from the Opta/Sky workbook, using 7-tournament pooled goal rates
(6 StatsBomb + WC2026).

Key differences from the locked StatsBomb s08:
  - "True stoppage" = Opta owed estimator (ADR-0037/0038) per half, NOT s05 incident_stoppage
  - Goal rates pooled across all 7 tournaments (StatsBomb productivity.parquet + agg02)
  - State at 90' derived from Match_Event_Log goal events (own goals handled via qualifier 28)
  - No estimator-error CI draw (Opta is direct wall-clock measurement, not the s05 estimator)
  - Regulation only (P1+P2); ET periods excluded even for ET matches

Central spec mirrors s08 central: 1H+2H window, halflife=4.0 min, gross-up ON.

Outputs (separate pathway; does NOT touch locked StatsBomb pipeline):
  data/processed/sky_wc2026/wc2026_cf_per_match.parquet
  data/processed/sky_wc2026/wc2026_cf_summary.parquet
  data/processed/sky_wc2026/wc2026_cf_ledger.md
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sky_wc2026.build_wc2026_inputs import (
    XLSX,
    NOMINAL_END,
    INJURY_EVT, INJURY_FAM,
    SUB_EVT, CARD_EVT, CARD_FAM,
    CELEB_EVT, CELEB_FAM,
    DELAY_EVT, PERIOD_START_MC, LEADIN_CAP_S, STITCH_TOL_S,
    resolve_restart,
    _stitch_windows, _has_openplay, _last_openplay_before, _first_balldeath_in,
    _q_ids,
    load_workbook_tables,
)
from src.lib import config

OUT = ROOT / "data" / "processed" / "sky_wc2026"

HALFLIFE = 4.0          # decay halflife for 2H rate (same as StatsBomb central)
SEED = 20260722
N_BOOTSTRAP = 1000
OWN_GOAL_QUALIFIER = "28"  # Opta qualifier ID for own goals (reverses team_side attribution)
REGULATION_CLOCK_S = 5400.0  # 90 * 60 -- goals at or before this are "before 90+'"


# ---- mathematical model helpers (same formulas as s08) ----------------------------------

def p_change(mu):
    return 1.0 - np.exp(-mu)


def avg_lambda(T_min, halflife_min, obs_rate, floor_rate):
    """Window-average decayed 2H goal rate (IMPL-8/ADR-0024, vectorized over per-match T)."""
    obs = np.asarray(obs_rate, dtype=float)
    floor = np.asarray(floor_rate, dtype=float)
    T = np.asarray(T_min, dtype=float)
    if math.isinf(halflife_min):
        return obs + 0.0 * T
    if halflife_min <= 0.0:
        return np.where(T > 0.0, floor, obs)
    k = math.log(2.0) / halflife_min
    kT = k * T
    ramp = np.where(kT > 1e-12, -np.expm1(-kT) / np.where(kT > 1e-12, kT, 1.0), 1.0)
    return floor + (obs - floor) * ramp


# ---- XLSX readers -----------------------------------------------------------------------

def _goals_with_teams(wb):
    """Read Match_Event_Log: goals (type 16) with team_side and own-goal flag.

    Returns a list of dicts: {fixture_uuid, period, clock_s, team_side_benefiting}
    where team_side_benefiting is adjusted for own goals (qualifier 28 flips home<->away).
    Only periods 1 and 2 (regulation) are returned.
    """
    ws = wb["Match_Event_Log"]
    it = ws.iter_rows(values_only=True)
    hdr = list(next(it))
    ix = {h: i for i, h in enumerate(hdr)}

    goals = []
    for r in it:
        if r[ix["Event type ID"]] != 16:
            continue
        per = r[ix["periodId"]]
        if per not in (1, 2):
            continue
        side = r[ix["Team side"]]  # "home" or "away"
        q_ids = _q_ids(r[ix["Qualifiers"]])
        if OWN_GOAL_QUALIFIER in q_ids:
            # OG: the credit goes to the OPPONENT of the team that scored the OG
            side = "away" if side == "home" else "home"
        clock_s = float(r[ix["Time minute"]] or 0) * 60.0 + float(r[ix["Time second"]] or 0)
        goals.append({
            "fixture_uuid": r[ix["fixture_uuid"]],
            "period": int(per),
            "clock_s": clock_s,
            "team_side": side,
        })
    return goals


def _dead_per_period(wb):
    """Stoppage_Summary: estimated dead seconds per (match_name, period) for P1 and P2."""
    ws = wb["Stoppage_Summary"]
    it = ws.iter_rows(values_only=True)
    hdr = list(next(it))
    ix = {h: i for i, h in enumerate(hdr)}
    dead = {}
    for r in it:
        per = r[ix["periodId"]]
        if per not in (1, 2):
            continue
        dead[(r[ix["Match"]], int(per))] = float(r[ix["Estimated dead time seconds"]] or 0.0)
    return dead


# ---- per-half owed (regulation only) ----------------------------------------------------

def compute_owed_per_half(T):
    """Modified compute_owed that accumulates by (fixture_uuid, period) for P1 and P2 only.

    Returns dict: (uu, per) -> {"owed_s": float, "seam_s": float, "leadin_s": float}
    Mirrors the full ADR-0038 ladder from build_wc2026_inputs.compute_owed, with the
    accumulation key changed from fixture_uuid to (fixture_uuid, period).
    """
    p = config.params()["incident"]
    allow = {str(k): float(v) for k, v in p["restart_normal_s"].items()}
    caps = dict(injury=p["max_injury_s"], sub=p["max_sub_s"], card=p["max_card_s"],
                celebration=p["max_celebration_s"])
    COMP = ["hydration", "injury", "sub", "card", "celebration",
            "throw-in", "goal-kick", "corner", "free-kick", "delay", "seam", "leadin"]

    owed = defaultdict(lambda: {c: 0.0 for c in COMP})
    hyd_used = set()

    by_mp = defaultdict(list)
    for g in T["cand"]:
        if g["period"] not in (1, 2):
            continue
        by_mp[(g["fixture_uuid"], g["period"])].append(g)

    for (uu, per), gaps in by_mp.items():
        acc = owed[(uu, per)]           # per-half accumulator (the only key change vs compute_owed)
        op = T["openplay"].get((uu, per), [])
        bd = T["balldeath"].get((uu, per), [])
        ps_mc = PERIOD_START_MC.get(per, "")
        prev_end = None

        for w in _stitch_windows(gaps):
            w_start, w_end = w[0]["start_min_abs"], w[-1]["end_min_abs"]

            if prev_end is not None and (w_start - prev_end) * 60.0 > STITCH_TOL_S \
                    and not _has_openplay(op, prev_end, w_start):
                acc["seam"] += (w_start - prev_end) * 60.0

            op0 = _last_openplay_before(op, w_start)
            if op0 is not None and (prev_end is None or op0 > prev_end):
                bdt = _first_balldeath_in(bd, op0, w_start)
                if bdt is not None:
                    leadin_s = min((w_start - bdt) * 60.0, LEADIN_CAP_S)
                    if leadin_s > 0:
                        acc["leadin"] += leadin_s

            prev_end = w_end

            if any(g["start_evt"] in DELAY_EVT or g["end_evt"] in DELAY_EVT for g in w):
                acc["delay"] += sum(g["D"] for g in w)
                continue

            for g in w:
                D, fam = g["D"], g["family"]
                sET, eET, qids = g["start_evt"], g["end_evt"], g["end_qids"]

                mids = T["hyd"].get((g["match"], per), [])
                if mids and any(g["start_min_abs"] <= m <= g["end_min_abs"] for m in mids):
                    if (g["match"], per) not in hyd_used:
                        acc["hydration"] += D
                        hyd_used.add((g["match"], per))
                    continue
                if sET in INJURY_EVT or eET in INJURY_EVT or fam in INJURY_FAM:
                    acc["injury"] += min(D, caps["injury"]); continue
                if sET in SUB_EVT or eET in SUB_EVT or fam.startswith("Substitution"):
                    pre_whistle = ((sET in SUB_EVT and g["start_mc"] == ps_mc)
                                   or (eET in SUB_EVT and g["end_mc"] == ps_mc))
                    if pre_whistle:
                        continue   # half-time sub: 0 owed (ADR-0038)
                    acc["sub"] += min(D, caps["sub"]); continue
                if sET in CARD_EVT or eET in CARD_EVT or fam in CARD_FAM:
                    acc["card"] += min(D, caps["card"]); continue
                if sET in CELEB_EVT or fam in CELEB_FAM:
                    acc["celebration"] += min(D, caps["celebration"]); continue
                rtype, a = resolve_restart(qids, fam, allow)
                if rtype in ("throw-in", "goal-kick", "corner", "free-kick"):
                    acc[rtype] += max(0.0, D - a); continue

    result = {}
    for (uu, per), acc in owed.items():
        total = sum(acc[c] for c in COMP)
        result[(uu, per)] = {
            "owed_s": total,
            "seam_s": acc["seam"],
            "leadin_s": acc["leadin"],
        }
    return result


# ---- state at 90' -----------------------------------------------------------------------

def state_at_90_per_match(goals_team, fixtures):
    """Regulation state (tied / lead_by_1 / lead_by_2plus) for each match.

    Uses goals where clock_s <= 5400 (at or before 90:00), periods 1-2, with own-goal
    qualifier 28 already flipped in goals_team. ET matches have all their regulation goals
    captured here; the state is what it was before 2H stoppage was played.
    """
    home_g = defaultdict(int)
    away_g = defaultdict(int)
    for g in goals_team:
        if g["clock_s"] <= REGULATION_CLOCK_S:
            uu = g["fixture_uuid"]
            if g["team_side"] == "home":
                home_g[uu] += 1
            else:
                away_g[uu] += 1
    state = {}
    for uu in fixtures:
        diff = abs(home_g.get(uu, 0) - away_g.get(uu, 0))
        if diff == 0:
            state[uu] = "tied"
        elif diff == 1:
            state[uu] = "lead_by_1"
        else:
            state[uu] = "lead_by_2plus"
    return state


# ---- 7-tournament pooled rates ----------------------------------------------------------

def pool_7tournament_rates(prod_path, agg02_path):
    """Pool 6 StatsBomb tournaments (productivity.parquet) with WC2026 (agg02_productivity_by_bucket).

    Returns dict with keys: n_1H, exp_1H, n_2H, exp_2H, n_floor, exp_floor
    (goals counts and live-minute exposures for each of the three rate cells).
    """
    prod = pd.read_parquet(prod_path)
    agg02 = pd.read_parquet(agg02_path)

    def _sb(phase_label):
        row = prod[(prod["scope"] == "pooled") & (prod["dimension"] == "phase")
                   & (prod["phase_or_bucket"] == phase_label) & (prod["metric"] == "goals")]
        if row.empty:
            return 0.0, 0.0
        r = row.iloc[0]
        return float(r["n_events"]), float(r["live_minutes"])

    sb_n1H, sb_e1H = _sb("1H_stoppage")
    sb_n2H, sb_e2H = _sb("2H_stoppage")
    sb_nreg, sb_ereg = _sb("regular")

    wc_1H = agg02[agg02["bucket"] == "1H stop"].iloc[0]
    wc_2H = agg02[agg02["bucket"] == "2H stop"].iloc[0]
    reg_buckets = agg02[~agg02["bucket"].isin(["1H stop", "2H stop"])]

    wc_n1H, wc_e1H = float(wc_1H["goals"]), float(wc_1H["live_min"])
    wc_n2H, wc_e2H = float(wc_2H["goals"]), float(wc_2H["live_min"])
    wc_nreg = float(reg_buckets["goals"].sum())
    wc_ereg = float(reg_buckets["live_min"].sum())

    return {
        "n_1H": sb_n1H + wc_n1H,   "exp_1H": sb_e1H + wc_e1H,
        "n_2H": sb_n2H + wc_n2H,   "exp_2H": sb_e2H + wc_e2H,
        "n_floor": sb_nreg + wc_nreg, "exp_floor": sb_ereg + wc_ereg,
        "sb_n1H": sb_n1H, "sb_e1H": sb_e1H, "sb_n2H": sb_n2H, "sb_e2H": sb_e2H,
        "sb_nreg": sb_nreg, "sb_ereg": sb_ereg,
        "wc_n1H": wc_n1H, "wc_e1H": wc_e1H, "wc_n2H": wc_n2H, "wc_e2H": wc_e2H,
        "wc_nreg": wc_nreg, "wc_ereg": wc_ereg,
    }


# ---- per-match model arrays -------------------------------------------------------------

def build_match_arrays(T, dead_per_period, owed_per_half, goals_team):
    """Compute per-match static arrays for the Poisson model.

    Returns a list of dicts, one per fixture, containing all pre-computed values
    that don't change across bootstrap draws (omitted live minutes, live share, decay
    horizon T2, state_at_90). Only regulation P1+P2.
    """
    state90 = state_at_90_per_match(goals_team, T["fixtures"])
    rows = []
    for uu, fx in T["fixtures"].items():
        match_name = fx["match"]

        # --- per-half played seconds ---
        played_1H = max(0.0, T["ends"].get((uu, 1), NOMINAL_END[1]) - NOMINAL_END[1])
        played_2H = max(0.0, T["ends"].get((uu, 2), NOMINAL_END[2]) - NOMINAL_END[2])

        # --- per-half owed seconds ---
        oh1 = owed_per_half.get((uu, 1), {"owed_s": 0.0, "seam_s": 0.0, "leadin_s": 0.0})
        oh2 = owed_per_half.get((uu, 2), {"owed_s": 0.0, "seam_s": 0.0, "leadin_s": 0.0})
        owed_1H, seam_1H, leadin_1H = oh1["owed_s"], oh1["seam_s"], oh1["leadin_s"]
        owed_2H, seam_2H, leadin_2H = oh2["owed_s"], oh2["seam_s"], oh2["leadin_s"]

        # --- dead seconds per half (broad: Stoppage_Summary + seam + leadin) ---
        raw_dead_1H = dead_per_period.get((match_name, 1), 0.0)
        raw_dead_2H = dead_per_period.get((match_name, 2), 0.0)
        dead_1H = raw_dead_1H + seam_1H + leadin_1H
        dead_2H = raw_dead_2H + seam_2H + leadin_2H

        # --- period durations (45 min nominal + played stoppage) ---
        dur_1H = 2700.0 + played_1H
        dur_2H = 2700.0 + played_2H

        # --- live share per half ---
        ls_1H = max(0.0, min(1.0, (dur_1H - dead_1H) / dur_1H)) if dur_1H > 0 else 0.0
        ls_2H = max(0.0, min(1.0, (dur_2H - dead_2H) / dur_2H)) if dur_2H > 0 else 0.0

        # --- gross-up z_half (genuine owed / total dead) ---
        z_1H = min(1.0, owed_1H / dead_1H) if dead_1H > 0 else 0.0
        z_2H = min(1.0, owed_2H / dead_2H) if dead_2H > 0 else 0.0

        # --- gross-up live factor (ADR-0024): ls * (1 + z*(1-ls)) ---
        fl_1H = ls_1H * (1.0 + z_1H * (1.0 - ls_1H))
        fl_2H = ls_2H * (1.0 + z_2H * (1.0 - ls_2H))

        # --- omitted clock and live minutes per half ---
        omit_1H = max(0.0, owed_1H / 60.0 - played_1H / 60.0)
        omit_2H = max(0.0, owed_2H / 60.0 - played_2H / 60.0)
        omit_live_1H = omit_1H * fl_1H
        omit_live_2H = omit_2H * fl_2H

        # --- 2H decay horizon T2 = grossed omitted clock = omit_live / live_share ---
        T2 = (omit_live_2H / ls_2H) if ls_2H > 0 else 0.0

        rows.append({
            "fixture_uuid": uu, "match": match_name,
            "home": fx["home"], "away": fx["away"],
            "owed_1H_s": owed_1H, "owed_2H_s": owed_2H,
            "played_1H_s": played_1H, "played_2H_s": played_2H,
            "dead_1H_s": dead_1H, "dead_2H_s": dead_2H,
            "ls_1H": ls_1H, "ls_2H": ls_2H,
            "z_1H": z_1H, "z_2H": z_2H,
            "fl_1H": fl_1H, "fl_2H": fl_2H,
            "omit_1H_min": omit_1H, "omit_2H_min": omit_2H,
            "omit_live_1H_min": omit_live_1H, "omit_live_2H_min": omit_live_2H,
            "T2_min": T2,
            "state_at_90": state90.get(uu, "unknown"),
        })
    return rows


# ---- Poisson model ----------------------------------------------------------------------

def run_model(match_rows, rates, n_bootstrap=N_BOOTSTRAP, seed=SEED):
    """Run the central Poisson model and bootstrap CI.

    Central spec: 1H+2H window, halflife=4.0 min, gross-up ON (per build_match_arrays).

    Bootstrap: Jeffreys-Gamma draws on 3 lambda cells (1H, 2H, floor). No estimator-error
    draw (Opta data is direct wall-clock measurement, not the StatsBomb s05 estimator).

    Returns (per_match_df, summary_dict).
    """
    n = len(match_rows)
    omit_live_1H = np.array([r["omit_live_1H_min"] for r in match_rows])
    omit_live_2H = np.array([r["omit_live_2H_min"] for r in match_rows])
    ls_2H = np.array([r["ls_2H"] for r in match_rows])
    T2 = np.array([r["T2_min"] for r in match_rows])
    state90 = np.array([r["state_at_90"] for r in match_rows])
    tied90 = state90 == "tied"
    lead1_90 = state90 == "lead_by_1"

    r1H_central = rates["n_1H"] / rates["exp_1H"]
    r2H_central = rates["n_2H"] / rates["exp_2H"]
    rfloor_central = rates["n_floor"] / rates["exp_floor"]

    def _mu(r1H, r2H, rfloor):
        avg2 = avg_lambda(T2, HALFLIFE, r2H, rfloor)
        mu_1H = r1H * omit_live_1H
        mu_2H = avg2 * omit_live_2H
        return {"1H+2H": mu_1H + mu_2H, "2H_only": mu_2H}

    def _flip(mu_arr):
        pf = np.zeros(n)
        pf[tied90] = p_change(mu_arr[tied90])
        pf[lead1_90] = p_change(mu_arr[lead1_90] / 2.0)
        return pf

    # --- central (deterministic) ---
    mu_central = _mu(r1H_central, r2H_central, rfloor_central)
    per_match_rows = []
    for i, r in enumerate(match_rows):
        mu_tot = float(mu_central["1H+2H"][i])
        per_match_rows.append({
            **{k: r[k] for k in ["fixture_uuid", "match", "home", "away", "state_at_90",
                                  "owed_1H_s", "owed_2H_s", "played_1H_s", "played_2H_s",
                                  "omit_1H_min", "omit_2H_min",
                                  "omit_live_1H_min", "omit_live_2H_min",
                                  "ls_1H", "ls_2H", "z_1H", "z_2H", "T2_min"]},
            "mu_1H2H": mu_tot,
            "p_score_change": float(p_change(mu_tot)),
            "p_flip": float(_flip(mu_central["1H+2H"])[i]),
        })

    # --- bootstrap ---
    rng = np.random.default_rng(seed)
    exp_1H = rates["exp_1H"]
    exp_2H = rates["exp_2H"]
    exp_fl = rates["exp_floor"]

    boot = {w: {"score": np.empty(n_bootstrap), "flip": np.empty(n_bootstrap)}
            for w in ("1H+2H", "2H_only")}

    for b in range(n_bootstrap):
        b_r1H = rng.gamma(rates["n_1H"] + 0.5, 1.0 / exp_1H)
        b_r2H = rng.gamma(rates["n_2H"] + 0.5, 1.0 / exp_2H)
        b_rfl = rng.gamma(rates["n_floor"] + 0.5, 1.0 / exp_fl)
        mu_b = _mu(b_r1H, b_r2H, b_rfl)
        for w in ("1H+2H", "2H_only"):
            pc_b = p_change(mu_b[w])
            boot[w]["score"][b] = float(pc_b.mean())
            boot[w]["flip"][b] = float(_flip(mu_b[w]).mean())

    summary = {}
    pc_central_2h = float(p_change(mu_central["2H_only"]).mean())
    for w in ("1H+2H", "2H_only"):
        pc_central = float(p_change(mu_central[w]).mean())
        pf_central = float(_flip(mu_central[w]).mean())
        s, f = boot[w]["score"], boot[w]["flip"]
        summary[w] = {
            "window": w, "n_matches": n,
            "pct_changed": pc_central,
            "ci_lo": float(np.quantile(s, 0.025)),
            "ci_hi": float(np.quantile(s, 0.975)),
            "pct_flip": pf_central,
            "flip_ci_lo": float(np.quantile(f, 0.025)),
            "flip_ci_hi": float(np.quantile(f, 0.975)),
        }
    return pd.DataFrame(per_match_rows), summary


# ---- ledger -----------------------------------------------------------------------------

def write_ledger(per_match, summary, rates, out_path):
    L = ["# WC2026 counterfactual ledger", "",
         "Self-contained Poisson model on 96 WC2026 matches (Opta/Sky workbook).",
         "Separate pathway -- does NOT modify the locked StatsBomb pipeline.",
         "Central spec: 1H+2H window, halflife=4.0 min, gross-up ON.", ""]

    # --- 7-tournament rate table ---
    L += ["## 7-tournament pooled goal rates", "",
          "| cell | n_goals | live_min | rate |", "|---|---|---|---|"]
    for label, nk, ek in [
        ("1H stoppage (SB 6 tourn.)", "sb_n1H", "sb_e1H"),
        ("1H stoppage (WC2026)", "wc_n1H", "wc_e1H"),
        ("1H stoppage (7-pool)", "n_1H", "exp_1H"),
        ("2H stoppage (SB 6 tourn.)", "sb_n2H", "sb_e2H"),
        ("2H stoppage (WC2026)", "wc_n2H", "wc_e2H"),
        ("2H stoppage (7-pool)", "n_2H", "exp_2H"),
        ("regular/floor (SB 6 tourn.)", "sb_nreg", "sb_ereg"),
        ("regular/floor (WC2026)", "wc_nreg", "wc_ereg"),
        ("regular/floor (7-pool)", "n_floor", "exp_floor"),
    ]:
        n, e = rates.get(nk, 0), rates.get(ek, 0)
        r = n / e if e > 0 else float("nan")
        L.append(f"| {label} | {n:.0f} | {e:.1f} | {r:.5f} |")
    L.append("")

    # --- headline ---
    L += ["## Headline", ""]
    for w, s in summary.items():
        L.append(f"### {w}")
        L.append(f"- **scoreline change**: {s['pct_changed']:.1%} "
                 f"[{s['ci_lo']:.1%}, {s['ci_hi']:.1%}]")
        L.append(f"- **result flip**: {s['pct_flip']:.1%} "
                 f"[{s['flip_ci_lo']:.1%}, {s['flip_ci_hi']:.1%}]")
        L.append(f"- n_matches: {s['n_matches']}")
        L.append("")

    # --- per-match summary ---
    L += ["## Per-match summary", ""]
    pm = per_match.copy()
    pm["owed_reg_min"] = (pm["owed_1H_s"] + pm["owed_2H_s"]) / 60
    pm["played_reg_min"] = (pm["played_1H_s"] + pm["played_2H_s"]) / 60
    pm["omit_total_min"] = pm["omit_1H_min"] + pm["omit_2H_min"]
    L.append(f"- mean owed (regulation): {pm['owed_reg_min'].mean():.2f} min")
    L.append(f"- mean played (regulation): {pm['played_reg_min'].mean():.2f} min")
    L.append(f"- mean omitted: {pm['omit_total_min'].mean():.2f} min")
    L.append(f"- mean P(scoreline change): {pm['p_score_change'].mean():.3f}")
    L.append(f"- mean P(flip): {pm['p_flip'].mean():.3f}")
    L.append("")
    L += ["### State at 90' distribution", ""]
    for s, cnt in pm["state_at_90"].value_counts().items():
        L.append(f"- {s}: {cnt} matches ({cnt/len(pm):.1%})")
    L.append("")

    # --- top 10 matches by omitted time ---
    L += ["### Top 10 matches by omitted stoppage (min)", ""]
    L += ["| match | owed_reg | played_reg | omitted | p_change | p_flip | state_90 |",
          "|---|---|---|---|---|---|---|"]
    for _, r in pm.nlargest(10, "omit_total_min").iterrows():
        L.append(f"| {r['match']} | {r['owed_reg_min']:.1f} | {r['played_reg_min']:.1f} | "
                 f"{r['omit_total_min']:.1f} | {r['p_score_change']:.3f} | {r['p_flip']:.3f} | "
                 f"{r['state_at_90']} |")
    L.append("")

    out_path.write_text("\n".join(L) + "\n")
    print(f"  wrote {out_path}")


# ---- main -------------------------------------------------------------------------------

def main():
    OUT.mkdir(parents=True, exist_ok=True)

    print(f"loading workbook tables from {XLSX.name} ...")
    T = load_workbook_tables()
    print(f"  fixtures={len(T['fixtures'])}  candidate gaps(P1-2)="
          f"{sum(1 for g in T['cand'] if g['period'] in (1,2))}")

    print("loading goals with team attribution ...")
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    goals_team = _goals_with_teams(wb)
    dead_per_period = _dead_per_period(wb)
    wb.close()
    print(f"  regulation goals (P1+P2): {len(goals_team)}")

    print("computing per-half owed (regulation P1+P2) ...")
    owed_per_half = compute_owed_per_half(T)
    print(f"  owed entries: {len(owed_per_half)}")

    print("building per-match arrays ...")
    match_rows = build_match_arrays(T, dead_per_period, owed_per_half, goals_team)

    print("pooling 7-tournament rates ...")
    prod_path = ROOT / "data" / "processed" / "productivity.parquet"
    agg02_path = ROOT / "data" / "processed" / "sky_wc2026" / "agg02_productivity_by_bucket.parquet"
    rates = pool_7tournament_rates(prod_path, agg02_path)
    r1H = rates["n_1H"] / rates["exp_1H"]
    r2H = rates["n_2H"] / rates["exp_2H"]
    rfl = rates["n_floor"] / rates["exp_floor"]
    print(f"  7-pool rates: 1H={r1H:.5f}  2H={r2H:.5f}  floor={rfl:.5f}")
    print(f"  (SB: 1H={rates['sb_n1H']/rates['sb_e1H']:.5f}  "
          f"2H={rates['sb_n2H']/rates['sb_e2H']:.5f})")
    print(f"  (WC2026: 1H={rates['wc_n1H']/rates['wc_e1H']:.5f}  "
          f"2H={rates['wc_n2H']/rates['wc_e2H']:.5f})")

    print(f"running model ({len(match_rows)} matches, n_bootstrap={N_BOOTSTRAP}) ...")
    per_match_df, summary = run_model(match_rows, rates)

    # --- output ---
    per_match_df.to_parquet(OUT / "wc2026_cf_per_match.parquet", index=False)
    per_match_df.to_csv(OUT / "wc2026_cf_per_match.csv", index=False)
    summary_df = pd.DataFrame(list(summary.values()))
    summary_df.to_parquet(OUT / "wc2026_cf_summary.parquet", index=False)
    summary_df.to_csv(OUT / "wc2026_cf_summary.csv", index=False)
    write_ledger(per_match_df, summary, rates, OUT / "wc2026_cf_ledger.md")

    print("\n" + "=" * 70)
    hl = summary["1H+2H"]
    print(f"  HEADLINE (1H+2H window, 7-tournament pooled rates, n={hl['n_matches']}):")
    print(f"  Scoreline change: {hl['pct_changed']:.1%}  "
          f"[95% CI {hl['ci_lo']:.1%} – {hl['ci_hi']:.1%}]")
    print(f"  Result flip:      {hl['pct_flip']:.1%}  "
          f"[95% CI {hl['flip_ci_lo']:.1%} – {hl['flip_ci_hi']:.1%}]")
    h2 = summary["2H_only"]
    print(f"  (2H only:  scoreline {h2['pct_changed']:.1%}  flip {h2['pct_flip']:.1%})")
    print("=" * 70)
    print(f"\n  wrote wc2026_cf_per_match.parquet, wc2026_cf_summary.parquet, "
          f"wc2026_cf_ledger.md -> {OUT}")


if __name__ == "__main__":
    main()
