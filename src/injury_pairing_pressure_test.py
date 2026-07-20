"""PHASE 0 pressure test (READ-ONLY) for the s05 injury->ball-drop mis-pairing fix.

Standalone red-team of the proposed change to the LOCKED StatsBomb pipeline (ADR-0035,
24.4%/12.9%). Reads production parquet ONLY; writes nothing to data/processed, params.yaml,
s05_incident.py, tournaments.yaml, or any ADR. Prints a full report and writes an analysis
markdown to docs/injury_pairing_pressure_test.md (an exhibit, NOT decisions.md).

It replicates the s05 union-then-intersect-with-dead machinery (importing the real helpers
from s05_incident so semantics are byte-identical) and recomputes lower_bound_s under three
injury-pairing rules:
    current  = injury -> next Referee Ball-Drop            (cap max_injury_s)   [locked]
    restart  = injury -> next RESTART play_pattern         (cap max_injury_s)   [proposed A]
    earliest = injury -> EARLIEST of {next restart, drop}  (cap max_injury_s)   [proposed B]
    inplay   = injury -> next s03 IN-PLAY segment start    (cap max_injury_s)   [proposed C = user's
               "next live ball-in-play event"; the Opta-calibrated live-ball boundary, not a marker]

Because injury enters lower_bound_s via a UNION intersected with s03 dead, the real estimator
delta is the recomputed union, NOT the raw injury-component change. The residual constants are
mean-anchored to WC2018 Nate `expected`, so any refit is mean-preserving on WC2018 by
construction -- the headline move must come from POST matches whose lb shrinks while the
residual barely moves. We quantify exactly that.

Run: python -m src.injury_pairing_pressure_test
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.lib import config, nate
from src.s05_incident import RESTART, _intersect_total, _next_resume

PRE_TOURS = {"wc_2018", "euro_2020", "euro_2024"}
BALLDROP = "Referee Ball-Drop"
NEARBY_S = 120.0  # "genuine nearby ball-drop" threshold for P1


def _period_components(g, injury_rule: str, celeb_is_pre: bool, p, inplay_starts=None):
    """Replicate s05's per-(match,period) component intervals. Returns (base, restart_excess,
    injury_raw_intervals, dead-independent diagnostics).
    injury_rule in {current, restart, earliest, inplay}. `inplay` brackets to the next s03
    in-play segment start (the Opta-calibrated live-ball boundary), NOT an event-type marker."""
    g = g.sort_values(["period_s", "idx"])
    clocks = g["period_s"].to_numpy()
    patterns = g["play_pattern"].fillna("").to_numpy()
    types = g["type"].fillna("").to_numpy()
    poss = g["possession"].to_numpy()
    cards = g["card"].notna().to_numpy()
    shot_out = g["shot_outcome"].fillna("").to_numpy()

    celeb, sub, card, injury, injraw = [], [], [], [], []
    injury_events = []  # (t0, next_restart, next_balldrop) for diagnostics
    for i in range(len(clocks)):
        t0 = float(clocks[i])
        typ = types[i]
        if (typ == "Shot" and shot_out[i] == "Goal") or typ == "Own Goal For":
            r = _next_resume(clocks, patterns, types, i, want_patterns={"From Kick Off"})
            if r is not None:
                hi = min(r, t0 + p["max_celebration_s"])
                lo = t0 + (p["celebration_normal_s"] if celeb_is_pre else 0.0)
                if hi > lo:
                    celeb.append((lo, hi))
        if typ in ("Player Off", "Substitution"):
            r = _next_resume(clocks, patterns, types, i, want_patterns=RESTART)
            if r is not None:
                sub.append((t0, min(r, t0 + p["max_sub_s"])))
        if cards[i]:
            r = _next_resume(clocks, patterns, types, i, want_patterns=RESTART)
            if r is not None:
                card.append((t0, min(r, t0 + p["max_card_s"])))
        if typ == "Injury Stoppage":
            r_drop = _next_resume(clocks, patterns, types, i, want_type=BALLDROP)
            r_rest = _next_resume(clocks, patterns, types, i, want_patterns=RESTART)
            injury_events.append((t0, r_rest, r_drop))
            if injury_rule == "current":
                r = r_drop
            elif injury_rule == "restart":
                r = r_rest
            elif injury_rule == "earliest":
                cands = [x for x in (r_rest, r_drop) if x is not None]
                r = min(cands) if cands else None
            elif injury_rule == "inplay":
                later = inplay_starts[inplay_starts > t0] if inplay_starts is not None else []
                r = float(later[0]) if len(later) else None
            else:
                raise ValueError(injury_rule)
            if r is not None:
                iv = (t0, min(r, t0 + p["max_injury_s"]))
                injury.append(iv)
                injraw.append(iv)

    allowance = {str(k): float(v) for k, v in p["restart_normal_s"].items()}
    rex = []
    for i in range(len(clocks) - 1):
        if poss[i + 1] != poss[i] and patterns[i + 1] in allowance:
            gap = float(clocks[i + 1]) - float(clocks[i])
            allow = allowance[patterns[i + 1]]
            if gap > allow:
                rex.append((float(clocks[i]) + allow, float(clocks[i + 1])))

    base = celeb + sub + card + injury
    return base, rex, injraw, injury_events


def compute(events, seg, matches, params, injury_rule: str, celeb_mode: str):
    """Per-match lower_bound_s + lower_bound_base_s under an injury rule.
    celeb_mode: 'prod' (is_pre from group) or 'full' (force full-gap celebration, for the
    POST-residual refit basis on WC2018)."""
    p = params["incident"]
    group = matches.set_index("match_id")["group"].to_dict()
    dead_seg = {}
    for (mid, per), gg in seg[~seg["in_play"]].groupby(["match_id", "period"]):
        dead_seg[(int(mid), int(per))] = list(zip(gg["start_s"], gg["end_s"]))
    inplay_start = {}
    for (mid, per), gg in seg[seg["in_play"]].groupby(["match_id", "period"]):
        inplay_start[(int(mid), int(per))] = np.sort(gg["start_s"].to_numpy())

    rows = []
    for mid, grp in events.groupby("match_id"):
        is_pre = group.get(int(mid)) == "PRE"
        celeb_is_pre = is_pre if celeb_mode == "prod" else (celeb_mode == "excess")
        for period, g in grp.groupby("period"):
            if period >= 5:
                continue
            ips = inplay_start.get((int(mid), int(period)), np.array([]))
            base, rex, injraw, _ = _period_components(g, injury_rule, celeb_is_pre, p, ips)
            dead = dead_seg.get((int(mid), int(period)), [])
            rows.append({
                "match_id": int(mid), "period": int(period),
                "lower_bound_base_s": _intersect_total(base, dead),
                "lower_bound_s": _intersect_total(base + rex, dead),
                "injury_raw_s": sum(b - a for a, b in injraw),
                "injury_dead_s": _intersect_total(injraw, dead),
            })
    return pd.DataFrame(rows)


def refit_residual(lbms_min: dict, expected_min: dict) -> float:
    """Mean-anchor residual (seconds) = 60 * (mean Nate expected - mean lbms) over shared ids."""
    ids = sorted(set(lbms_min) & set(expected_min))
    return 60.0 * (np.mean([expected_min[i] for i in ids]) - np.mean([lbms_min[i] for i in ids]))


def rmae(pred_min: dict, expected_min: dict):
    ids = sorted(set(pred_min) & set(expected_min))
    p = np.array([pred_min[i] for i in ids]); t = np.array([expected_min[i] for i in ids])
    return len(ids), float(np.corrcoef(p, t)[0, 1]), float(np.mean(np.abs(p - t)))


def main() -> None:
    params = config.params()
    events = pd.read_parquet(config.INTERIM / "events_norm.parquet")
    seg = pd.read_parquet(config.INTERIM / "bip_segments.parquet")
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    inc_prod = pd.read_parquet(config.INTERIM / "incident_stoppage.parquet")
    ts_prod = pd.read_parquet(config.INTERIM / "true_stoppage.parquet")
    seg["dur"] = seg["end_s"] - seg["start_s"]
    dead_total = seg[~seg["in_play"]].groupby("match_id")["dur"].sum()

    # in-play segment starts per (match, period) -- the Opta-calibrated live-ball boundaries
    # used by the "inplay" rule and the injury-flag-in-dead-vs-live diagnostic.
    inplay_start_m = {}
    for (mid, per), gg in seg[seg["in_play"]].groupby(["match_id", "period"]):
        inplay_start_m[(int(mid), int(per))] = np.sort(gg["start_s"].to_numpy())
    dead_ivs_m = {}
    for (mid, per), gg in seg[~seg["in_play"]].groupby(["match_id", "period"]):
        dead_ivs_m[(int(mid), int(per))] = list(zip(gg["start_s"].to_numpy(), gg["end_s"].to_numpy()))

    tour = matches.set_index("match_id")["tournament"].to_dict()
    group = matches.set_index("match_id")["group"].to_dict()
    is_pre_t = {t: (t in PRE_TOURS) for t in set(tour.values())}

    # silent_marked (invariant to injury rule) per match from locked parquet
    ms_match_s = inc_prod.groupby("match_id")["silent_marked_s"].sum()
    ms_min = {int(m): v / 60.0 for m, v in ms_match_s.items()}
    expected_min = nate.truth_minutes("expected")  # WC2018 Nate `expected`
    wc2018 = set(expected_min)

    out = []  # report lines
    def pr(s=""):
        print(s); out.append(s)

    pr("# s05 injury->ball-drop pairing -- Phase 0 pressure test\n")
    pr(f"Events: {len(events):,}  Injury Stoppage: {(events['type']=='Injury Stoppage').sum():,}  "
       f"Referee Ball-Drop: {(events['type']==BALLDROP).sum():,}  "
       f"(ratio drop/injury = {(events['type']==BALLDROP).sum()/(events['type']=='Injury Stoppage').sum():.2f})\n")

    # ---- recompute lb under the four rules (production celebration) ----
    rules = ["current", "restart", "earliest", "inplay"]
    lb = {r: compute(events, seg, matches, params, r, "prod") for r in rules}

    # self-consistency: current rule must reproduce the locked incident/true_stoppage parquet
    cur = lb["current"].groupby("match_id")[["lower_bound_s", "lower_bound_base_s"]].sum()
    prod = inc_prod.groupby("match_id")[["lower_bound_s", "lower_bound_base_s"]].sum()
    dlb = (cur["lower_bound_s"] - prod["lower_bound_s"]).abs().max()
    dbase = (cur["lower_bound_base_s"] - prod["lower_bound_base_s"]).abs().max()
    pr("## Self-consistency (replication vs locked parquet)")
    pr(f"max |Δ lower_bound_s|      current-rule vs locked: {dlb:.4f}s")
    pr(f"max |Δ lower_bound_base_s| current-rule vs locked: {dbase:.4f}s")

    # residual refit basis: WC2018 lbms under prod (=excess) celeb and full celeb, per rule
    lb_full = {r: compute(events, seg, matches, params, r, "full") for r in rules}

    def lbms(lbdf, ids):
        s = lbdf.groupby("match_id")["lower_bound_s"].sum()
        return {int(m): s[m] / 60.0 + ms_min[int(m)] for m in s.index if int(m) in ids}

    pre_resid = {r: refit_residual(lbms(lb[r], wc2018), expected_min) for r in rules}
    post_resid = {r: refit_residual(lbms(lb_full[r], wc2018), expected_min) for r in rules}
    pr(f"\nrefit PRE residual  (excess celeb, WC2018): "
       + "  ".join(f"{r}={pre_resid[r]:.1f}s" for r in rules)
       + f"   [locked pre={params['silent']['residual_silent_pre_s']}]")
    pr(f"refit POST residual (full celeb,   WC2018): "
       + "  ".join(f"{r}={post_resid[r]:.1f}s" for r in rules)
       + f"   [locked post={params['silent']['residual_silent_s']}]")

    # ---- P4: WC2018 r/MAE under each rule (with its own refit PRE residual) ----
    pr("\n## P4 -- WC2018 calibration (all-PRE) vs Nate `expected`")
    pr("| rule | n | r | MAE (min) | refit pre-resid (s) | mean est (min) | mean nate |")
    pr("|---|---|---|---|---|---|---|")
    mean_nate = np.mean([expected_min[i] for i in wc2018])
    for r in rules:
        lbms_r = lbms(lb[r], wc2018)
        est = {m: lbms_r[m] + pre_resid[r] / 60.0 for m in lbms_r}
        n, rr, mae = rmae(est, expected_min)
        pr(f"| {r} | {n} | {rr:.3f} | {mae:.2f} | {pre_resid[r]:.1f} | "
           f"{np.mean(list(est.values())):.2f} | {mean_nate:.2f} |")
    pr("\n(Refit is mean-preserving by construction, so mean est == mean nate for every rule; "
       "r and MAE are the quality signals.)")

    # ---- true_stoppage per match under each rule, with refit residuals ----
    def true_stop(lbdf, lbdf_full, pre_r, post_r):
        s = lbdf.groupby("match_id")["lower_bound_s"].sum()
        res = {}
        for m in s.index:
            m = int(m)
            resid = pre_r if group.get(m) == "PRE" else post_r
            res[m] = (s[m] + ms_match_s[m] + resid) / 60.0
        return res

    ts = {r: true_stop(lb[r], lb_full[r], pre_resid[r], post_resid[r]) for r in rules}

    # verify current reproduces locked true_stoppage
    ts_prod_min = {int(m): v / 60.0 for m, v in ts_prod.set_index("match_id")["true_stoppage_s"].items()}
    dts = max(abs(ts["current"][m] - ts_prod_min[m]) for m in ts_prod_min)
    pr(f"\nmax |Δ true_stoppage| current-rule vs locked parquet: {dts*60:.3f}s  (validates refit path)")

    # ---- six-tournament pools: mean true_stoppage (owed) old vs new ----
    pr("\n## Projected before->after -- mean true_stoppage (owed), minutes")
    pr("| tournament | era | n | current | restart | earliest | inplay | Δ(earliest) | Δ(inplay) |")
    pr("|---|---|---|---|---|---|---|---|---|")
    def mean_by(ids):
        return {r: np.mean([ts[r][i] for i in ids]) for r in rules}
    def prow(label, era, ids):
        mb = mean_by(ids)
        pr(f"| {label} | {era} | {len(ids)} | {mb['current']:.2f} | {mb['restart']:.2f} | "
           f"{mb['earliest']:.2f} | {mb['inplay']:.2f} | {mb['earliest']-mb['current']:+.2f} | "
           f"{mb['inplay']-mb['current']:+.2f} |")
    for t in ["wc_2018", "euro_2020", "euro_2024", "wc_2022", "copa_america_2024", "afcon_2023"]:
        ids = [m for m in ts["current"] if tour.get(m) == t]
        prow(t, "PRE" if is_pre_t[t] else "POST", ids)
    for era in ("PRE", "POST"):
        ids = [m for m in ts["current"] if (group.get(m) == era)]
        prow(f"**{era} pool**", era, ids)

    # ---- P1: ball-drop presence share ----
    pr("\n## P1 -- Was Referee Ball-Drop ever a workable key?")
    inj = events[events["type"] == "Injury Stoppage"]
    drops = events[events["type"] == BALLDROP]
    drop_by_mp = {k: np.sort(v["period_s"].to_numpy())
                  for k, v in drops.groupby(["match_id", "period"])}
    near = far = none = 0
    gaps = []
    for row in inj.itertuples():
        arr = drop_by_mp.get((row.match_id, row.period))
        if arr is None:
            none += 1; continue
        after = arr[arr >= row.period_s]
        if len(after) == 0:
            none += 1; continue
        gap = after[0] - row.period_s
        gaps.append(gap)
        if gap <= NEARBY_S:
            near += 1
        else:
            far += 1
    tot = len(inj)
    pr(f"Injury events: {tot}.  next ball-drop in SAME period:")
    pr(f"  within {NEARBY_S:.0f}s (genuine pairing): {near} ({near/tot:.1%})")
    pr(f"  present but >{NEARBY_S:.0f}s away (mis-pair risk): {far} ({far/tot:.1%})")
    pr(f"  NO later ball-drop in the period (key absent): {none} ({none/tot:.1%})")
    if gaps:
        gaps = np.array(gaps)
        pr(f"  gap to next drop when present: median {np.median(gaps):.0f}s  "
           f"p90 {np.percentile(gaps,90):.0f}s  max {gaps.max():.0f}s")

    # ---- P2: earliest-of vs plain next-restart ----
    pr("\n## P2 -- earliest-of{restart,drop} vs plain next-restart (overshoot check)")
    diff_cases = 0; drop_earlier = 0; both = 0; rest_only = 0; drop_only = 0; neither = 0
    drop_earlier_gaps = []
    p_inc = params["incident"]
    for mid, grp in events.groupby("match_id"):
        for period, g in grp.groupby("period"):
            if period >= 5:
                continue
            _, _, _, iev = _period_components(g, "current", True, p_inc)
            for t0, r_rest, r_drop in iev:
                if r_rest is not None and r_drop is not None:
                    both += 1
                    if r_drop < r_rest - 0.5:
                        drop_earlier += 1
                        drop_earlier_gaps.append(r_rest - r_drop)
                    if abs(r_drop - r_rest) > 0.5:
                        diff_cases += 1
                elif r_rest is not None:
                    rest_only += 1
                elif r_drop is not None:
                    drop_only += 1
                else:
                    neither += 1
    pr(f"injury events with BOTH markers: {both}; restart-only: {rest_only}; drop-only: {drop_only}; "
       f"neither: {neither}")
    pr(f"  of BOTH: ball-drop strictly earlier than next restart (plain next-restart would "
       f"OVERSHOOT): {drop_earlier} ({drop_earlier/max(both,1):.1%})")
    if drop_earlier_gaps:
        dg = np.array(drop_earlier_gaps)
        pr(f"  overshoot amount when it happens: median {np.median(dg):.0f}s  p90 {np.percentile(dg,90):.0f}s")

    # ---- P3: injury_raw span vs dead-clipped (live play neutralization) ----
    pr("\n## P3 -- resumption windows: live play swept in, then stripped by ∩dead")
    for r in ("restart", "earliest", "inplay"):
        raw = lb[r]["injury_raw_s"].sum()
        dead = lb[r]["injury_dead_s"].sum()
        pr(f"  {r}: Σ raw injury window {raw/60:.1f} min; Σ (window ∩ dead) {dead/60:.1f} min; "
           f"live stripped by ∩dead {(raw-dead)/60:.1f} min ({(raw-dead)/max(raw,1):.1%})")
    pr("  (lower_bound_s uses ∩dead only, so any live span inside a resumption window is removed.)")

    # ---- injury-flag location: dead vs live segment (validity of the inplay rule) ----
    pr("\n## Injury-flag location -- is the ball dead or live when the flag is logged?")
    in_dead = in_live = no_seg = 0
    for row in inj.itertuples():
        if row.period >= 5:
            continue
        divs = dead_ivs_m.get((int(row.match_id), int(row.period)))
        if divs is None:
            no_seg += 1; continue
        t = float(row.period_s)
        if any(a <= t < b for a, b in divs):
            in_dead += 1
        else:
            in_live += 1
    tot_inj = in_dead + in_live + no_seg
    pr(f"  injury flag falls in a DEAD segment: {in_dead} ({in_dead/max(tot_inj,1):.1%})  "
       f"in a LIVE segment: {in_live} ({in_live/max(tot_inj,1):.1%})  no-seg: {no_seg}")
    pr("  (If the flag is already in dead time, 'next in-play start' is the true resumption. If it "
       "is in live time, ∩dead strips the live span so the inplay window still cannot over-credit.)")

    # ---- P5: per-tournament ball-drop presence ----
    pr("\n## P5 -- per-tournament ball-drop presence (data-quality vs football)")
    pr("| tournament | era | injuries | drop ≤120s | share | no-drop-in-period |")
    pr("|---|---|---|---|---|---|")
    for t in ["wc_2018", "euro_2020", "euro_2024", "wc_2022", "copa_america_2024", "afcon_2023"]:
        sub = inj[inj["match_id"].map(tour) == t]
        n = len(sub); nnear = nnone = 0
        for row in sub.itertuples():
            arr = drop_by_mp.get((row.match_id, row.period))
            after = arr[arr >= row.period_s] if arr is not None else np.array([])
            if len(after) == 0:
                nnone += 1
            elif after[0] - row.period_s <= NEARBY_S:
                nnear += 1
        pr(f"| {t} | {'PRE' if is_pre_t[t] else 'POST'} | {n} | {nnear} | {nnear/max(n,1):.1%} | "
           f"{nnone/max(n,1):.1%} |")

    # ---- P6: gate safety ----
    pr("\n## P6 -- s05 gate (lower_bound_s ≤ total dead) under new rules")
    for r in rules:
        pm = lb[r].groupby("match_id")["lower_bound_s"].sum()
        viol = [(int(m), pm[m], float(dead_total.get(m, 0.0)))
                for m in pm.index if pm[m] > float(dead_total.get(m, 0.0)) + 1.0]
        pr(f"  {r}: gate violations = {len(viol)}"
           + ("" if not viol else f"  e.g. {viol[:3]}"))
    # restart_excess / base-minus-injury invariance check: sub+card+celeb+restart_excess identical
    pr("  (sub/card/celebration/restart_excess intervals are identical across rules by "
       "construction -- only the injury interval feeding the union changes.)")

    # ---- P7: edge cases ----
    pr("\n## P7 -- edge cases")
    inj_any = inc_prod.groupby("match_id")["injury_present"].any()
    pr(f"  matches with NO Injury Stoppage event: {int((~inj_any).sum())} / {inj_any.size}")
    et = inj[inj["period"] >= 3]
    pr(f"  injury events in ET periods (3-4): {len(et)}  "
       f"(across {et['match_id'].nunique()} matches)")
    # injury_present true but current rule credits 0 (no ball-drop found) -> new rule recovers
    pr(f"  injury events with NO usable ball-drop key (current rule credits 0 for these): "
       f"{none} of {tot} ({none/tot:.1%}) -> next-restart recovers genuine dead time here.")

    # ---- channel decomposition: residual vs injury/lb (for the recommended 'inplay' rule) ----
    lock_pre, lock_post = 94.1, 24.2
    pr("\n## Channel decomposition -- where does the pool move come from? (rule = inplay)")
    pr("Δ true_stoppage per match = (residual channel, uniform within era) + (lb/injury channel).")
    pr(f"  PRE  residual channel: {(pre_resid['earliest']-lock_pre)/60:+.2f} min (earliest) / "
       f"{(pre_resid['inplay']-lock_pre)/60:+.2f} min (inplay), uniform over 166 PRE matches")
    pr(f"  POST residual channel: {(post_resid['earliest']-lock_post)/60:+.2f} min (earliest) / "
       f"{(post_resid['inplay']-lock_post)/60:+.2f} min (inplay), uniform over 148 POST matches")
    pr("| tournament | era | Δtotal(inplay) | resid-chan | lb/injury-chan |")
    pr("|---|---|---|---|---|")
    for t in ["wc_2018", "euro_2020", "euro_2024", "wc_2022", "copa_america_2024", "afcon_2023"]:
        ids = [m for m in ts["current"] if tour.get(m) == t]
        dtot = np.mean([ts["inplay"][i] - ts["current"][i] for i in ids])
        rchan = ((pre_resid["inplay"] if is_pre_t[t] else post_resid["inplay"])
                 - (lock_pre if is_pre_t[t] else lock_post)) / 60
        pr(f"| {t} | {'PRE' if is_pre_t[t] else 'POST'} | {dtot:+.2f} | {rchan:+.2f} | {dtot-rchan:+.2f} |")

    # ---- floored-POST-residual variant (residual >= 0) ----
    pr("\n## Alternative: floor residual at 0 (a negative 'irreducible remainder' is incoherent)")
    pr("Residual floored at 0 per era; compares the two candidate rules head-to-head.")
    pr("| pool | n | current owed | earliest+floored | inplay+floored | Δ(earl) | Δ(inplay) |")
    pr("|---|---|---|---|---|---|---|")
    lb_earl = lb["earliest"].groupby("match_id")["lower_bound_s"].sum()
    lb_inpl = lb["inplay"].groupby("match_id")["lower_bound_s"].sum()
    for era in ("PRE", "POST"):
        ids = [m for m in ts["current"] if group.get(m) == era]
        re_e = max(pre_resid["earliest"], 0.0) if era == "PRE" else max(post_resid["earliest"], 0.0)
        re_i = max(pre_resid["inplay"], 0.0) if era == "PRE" else max(post_resid["inplay"], 0.0)
        fe = {m: (lb_earl[m] + ms_match_s[m] + re_e) / 60.0 for m in ids}
        fi = {m: (lb_inpl[m] + ms_match_s[m] + re_i) / 60.0 for m in ids}
        mc = np.mean([ts["current"][i] for i in ids])
        me = np.mean([fe[i] for i in ids]); mi = np.mean([fi[i] for i in ids])
        pr(f"| {era} | {len(ids)} | {mc:.2f} | {me:.2f} | {mi:.2f} | {me-mc:+.2f} | {mi-mc:+.2f} |")

    # ---- cap binding frequency ----
    pr("\n## Cap (max_injury_s=600) binding frequency")
    for r in rules:
        n_cap = n_win = 0
        for mid, grp in events.groupby("match_id"):
            for period, g in grp.groupby("period"):
                if period >= 5:
                    continue
                ips = inplay_start_m.get((int(mid), int(period)), np.array([]))
                _, _, injraw, iev = _period_components(g, r, True, p_inc, ips)
                for (t0, hi) in injraw:
                    n_win += 1
                    if abs((hi - t0) - 600.0) < 0.5:
                        n_cap += 1
        pr(f"  {r}: {n_cap}/{n_win} injury windows hit the 600s cap ({n_cap/max(n_win,1):.1%})")

    # ---- worked example: 3939992 (Costa Rica 2-1 Paraguay, Copa 2024) ----
    pr("\n## Worked example -- match 3939992 (Costa Rica 2-1 Paraguay, Copa 2024)")
    for r in rules:
        row = lb[r][lb[r]["match_id"] == 3939992]
        inj_min = row["injury_dead_s"].sum() / 60
        lbm = row["lower_bound_s"].sum() / 60
        pr(f"  {r:9}: injury∩dead {inj_min:5.1f} min   lower_bound {lbm:5.1f} min   "
           f"true_stoppage {ts[r].get(3939992, float('nan')):5.1f} min")

    doc = config.DOCS / "injury_pairing_pressure_test.md"
    doc.write_text("\n".join(out) + "\n")
    print(f"\nwrote {doc}")


if __name__ == "__main__":
    main()
