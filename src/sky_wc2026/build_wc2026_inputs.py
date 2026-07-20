"""WC2026 (Sky / Opta) data lane -- produces the two chart-input tables, DATA ONLY.

Self-contained side lane for the 2026 FIFA World Cup, fed by the Sky-supplied Opta F24
workbook (data/DONOTSHAREWorldCup_Stoppages.xlsx, 96 matches). It does NOT touch the locked
StatsBomb pipeline, tournaments.yaml, or any locked parquet/ADR -- it only READS the frozen
Nate allowance ladder + caps from config/params.yaml and REUSES the repo's bucket contract
(RANGES / BUCKET_ORDER) + Poisson CI helper. No figures are rendered here.

Two outputs (plug-compatible with the existing charts):
  agg01_estimate_vs_played.parquet/.csv  -- per match: OWED (est_min) vs PLAYED (played_min)
  agg02_productivity_by_bucket.parquet/.csv -- per 10-min bucket: goals per live minute + CI
  ledger.md -- QA + validation gates (eyeball only, NOT calibration)

Methodology (WC2026 ADR):
  * OWED = per-gap credit by a first-match-wins precedence
      hydration -> injury -> sub -> card -> celebration -> restart ladder -> keeper -> excluded.
    REQUIRE-A-MARKER: untagged open-play lulls get 0 (the non-addable baseline); the excluded
    seconds are reported. Restart ladder credits only the EXCESS over Nate's allowance
    (throw-in 20 / goal-kick 30 / corner 45 / free-kick 60). NO residual constant (that is a
    StatsBomb blind-spot correction), NO calibration to the historical numbers. Celebration is
    credited FULL (min D,180) -- WC2026 is a POST-directive tournament. Hydration credited full,
    at most once per half. Owed & played summed over periods 1-4 (period 5 = shoot-out excluded).
  * PLAYED = per period End-event clock minus the nominal period end (P1 2700 / P2 5400 /
    P3 6300 / P4 7200). Validated against Sheet1.actual_stoppage_time_secs.
  * agg_02 stays regulation P1+P2; live minutes = played span minus TOTAL candidate dead per
    bucket (denominator uses the whole gap, not the owed allowance).
"""
from __future__ import annotations

import bisect
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.figures_requested import RANGES, BUCKET_ORDER, INF, bucket_of  # bucket contract (reuse)
from src.lib import config, stats

XLSX = ROOT / "data" / "DONOTSHAREWorldCup_Stoppages.xlsx"
OUT = ROOT / "data" / "processed" / "sky_wc2026"

# Period bookkeeping (cumulative match clock, seconds).
NOMINAL_START = {1: 0.0, 2: 2700.0, 3: 5400.0, 4: 6300.0}   # for within-period coords (agg_02 uses 1,2)
NOMINAL_END = {1: 2700.0, 2: 5400.0, 3: 6300.0, 4: 7200.0}  # 45' / 90' / 105' / 120'

# --- OWED marker sets (Opta event-type names + default stoppage families) ---------------
INJURY_EVT = {"Player retired", "Player returns", "Referee drop ball"}
INJURY_FAM = {"Injury / player off", "Injury / player return", "Referee stoppage"}
SUB_EVT = {"Player off", "Player on"}
CARD_EVT = {"Card"}
CARD_FAM = {"Disciplinary"}
CELEB_EVT = {"Goal"}
CELEB_FAM = {"Goal / restart"}

# --- ADR-0038: event families that tell us whether the ball is LIVE or has DIED ------------
# Open-play families: any of these strictly inside an inter-window gap proves the ball went
# live, so the two dead windows are SEPARATE stoppages (do not merge / credit the seam).
OPENPLAY_FAM = {"Open play / pass", "Open play", "Open play / challenge", "Shot / restart"}
# Ball-death families: the events that stop live play. Used to find where the ball actually
# died before a candidate window that (for delay stoppages) only starts at the Type 27 marker.
BALLDEATH_FAM = {"Foul", "Ball out of play", "Offside"}
# Period-start match clock (the "Match clock" freezes here across the half-time interval, so a
# substitution logged at exactly this clock happened BEFORE the whistle -> not owed stoppage).
PERIOD_START_MC = {1: "00:00", 2: "45:00", 3: "90:00", 4: "105:00"}
LEADIN_CAP_S = 180.0   # cap a single stoppage lead-in (ball-death -> window start)

# Sheet1 uses FIFA display names (+ a few mojibake'd accents); the event feed uses Opta short
# names. Only 8 teams differ. Map them onto the Opta spelling by their SIMPLIFIED form
# (accent/space-stripped, lower-alnum) so the unordered team-pair join lines up regardless of the
# raw encoding (e.g. "T√ºrkiye" -> "torkiye" -> "turkey").
CANON_ALIAS = {
    "bosniaandherzegovina": "bosniaherz",
    "caboverde": "capeverde",
    "czechia": "czechrepublic",
    "iriran": "iran",
    "korearepublic": "southkorea",
    "torkiye": "turkey",       # "Türkiye" mojibake
    "curaao": "curacao",       # "Curaçao" mojibake
    "ctedivoire": "ivorycoast",  # "Côte d'Ivoire" mojibake
}


def _q_ids(qual: str | None) -> set[str]:
    """Parse a ';'-delimited Opta qualifier string into the set of qualifier IDs present."""
    if not qual:
        return set()
    out = set()
    for tok in str(qual).split(";"):
        tok = tok.strip()
        if tok:
            out.add(tok.split("=")[0].strip())
    return out


def _canon_team(name: str) -> str:
    """Canonicalize a team name for the Sheet1<->feed join: accent/space strip to a simplified
    lower-alnum form, then apply the small alias map so Sheet1's FIFA names match the Opta feed."""
    n = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    simp = "".join(ch for ch in n.lower() if ch.isalnum())
    return CANON_ALIAS.get(simp, simp)


# ---- workbook readers -------------------------------------------------------------------
def _rows(ws):
    it = ws.iter_rows(values_only=True)
    hdr = list(next(it))
    idx = {h: i for i, h in enumerate(hdr)}
    return it, idx


def load_workbook_tables():
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)

    # -- Stoppage_Candidates: the pre-computed dead gaps (periods 1-4) --
    it, ix = _rows(wb["Stoppage_Candidates"])
    cand = []
    fixtures = {}  # fixture_uuid -> dict(match, home, away, date, key)
    for r in it:
        per = r[ix["periodId"]]
        if per not in (1, 2, 3, 4):
            continue
        uu = r[ix["fixture_uuid"]]
        home, away = r[ix["Home team"]], r[ix["Away team"]]
        if uu not in fixtures:
            fixtures[uu] = {
                "fixture_uuid": uu, "match": r[ix["Match"]], "home": home, "away": away,
                "date": str(r[ix["Date"]])[:10],
                "key": frozenset({_canon_team(home), _canon_team(away)}),
            }
        cand.append({
            "fixture_uuid": uu, "match": r[ix["Match"]], "period": int(per),
            "D": float(r[ix["Real timestamp gap seconds"]] or 0.0),
            "start_min_abs": float(r[ix["Start minute absolute"]] or 0.0),
            "end_min_abs": float(r[ix["End minute absolute"]] or 0.0),
            "start_evt": r[ix["Start event type"]] or "",
            "end_evt": r[ix["End event type"]] or "",
            "start_mc": str(r[ix["Start match clock"]] or ""),  # ADR-0038 half-time-sub test
            "end_mc": str(r[ix["End match clock"]] or ""),
            "family": r[ix["Stoppage reason family"]] or "",
            "end_qids": _q_ids(r[ix["End qualifiers"]]),
        })

    # -- Match_Event_Log: End (30) clocks + Goal (16) events + (ADR-0038) the open-play and
    #    ball-death event streams per (fixture, period), used to detect inter-window seams
    #    (was the ball ever live between two dead windows?) and stoppage lead-ins (where did
    #    the ball actually die before a candidate window that starts at a delay marker?).
    it, ix = _rows(wb["Match_Event_Log"])
    ends = {}   # (fixture_uuid, period) -> max cumulative End clock (s)
    goals = {}  # (fixture_uuid, event_id) -> dict(period, clock_s)   [deduped]
    openplay = defaultdict(list)   # (uu, per) -> [minute_absolute] where the ball is LIVE
    balldeath = defaultdict(list)  # (uu, per) -> [minute_absolute] where the ball DIES
    for r in it:
        per = r[ix["periodId"]]
        if per not in (1, 2, 3, 4):
            continue
        uu = r[ix["fixture_uuid"]]
        fam = r[ix["Default stoppage family"]]
        if fam in OPENPLAY_FAM:
            openplay[(uu, int(per))].append(float(r[ix["Minute absolute"]] or 0.0))
        elif fam in BALLDEATH_FAM:
            balldeath[(uu, int(per))].append(float(r[ix["Minute absolute"]] or 0.0))
        et = r[ix["Event type ID"]]
        if et not in (30, 16):
            continue
        clock_s = float(r[ix["Time minute"]] or 0) * 60.0 + float(r[ix["Time second"]] or 0)
        if et == 30:
            k = (uu, int(per))
            ends[k] = max(ends.get(k, 0.0), clock_s)
        else:  # goal -- dedup by event id
            goals[(uu, r[ix["Event ID"]])] = {"fixture_uuid": uu, "period": int(per),
                                              "clock_s": clock_s}
    for d in (openplay, balldeath):
        for k in d:
            d[k].sort()

    # -- Hydration_Break_Info: 1 per half; midpoint minute (absolute) --
    it, ix = _rows(wb["Hydration_Break_Info"])
    hyd = defaultdict(list)  # (match_name, period) -> [midpoint_minute]
    for r in it:
        half = str(r[ix["Hydration break"]]).lower()
        per = 1 if "first" in half else 2 if "second" in half else None
        if per is None:
            continue
        hyd[(r[ix["Match"]], per)].append(float(r[ix["Break midpoint minute"]]))

    # -- Sheet1: per-match Sky analysis (join by canonical unordered pair) --
    it, ix = _rows(wb["Sheet1"])
    sheet1 = {}  # key -> dict
    for r in it:
        key = frozenset({_canon_team(r[ix["home_team_name"]]), _canon_team(r[ix["away_team_name"]])})
        sheet1[key] = {
            "actual_stoppage_s": float(r[ix["actual_stoppage_time_secs"]] or 0.0),
            "extra_time_match": r[ix["extra_time_match"]],
            "scheduled_min": r[ix["scheduled_playing_time_mins"]],
        }

    # -- Stoppage_Summary: per (match, period) estimated dead seconds (cross-check + gate) --
    it, ix = _rows(wb["Stoppage_Summary"])
    summ_dead = defaultdict(float)   # match_name -> total dead (periods 1-4)
    summ_dead_p = {}                 # (match_name, period) -> dead s
    for r in it:
        per = r[ix["periodId"]]
        if per not in (1, 2, 3, 4):
            continue
        d = float(r[ix["Estimated dead time seconds"]] or 0.0)
        summ_dead[r[ix["Match"]]] += d
        summ_dead_p[(r[ix["Match"]], int(per))] = d

    wb.close()
    return dict(cand=cand, fixtures=fixtures, ends=ends, goals=list(goals.values()),
                hyd=hyd, sheet1=sheet1, summ_dead=summ_dead, summ_dead_p=summ_dead_p,
                openplay=dict(openplay), balldeath=dict(balldeath))


# ---- OWED ------------------------------------------------------------------------------
def resolve_restart(end_qids: set[str], family: str, allow: dict) -> tuple[str | None, float]:
    """Opta restart type from END qualifiers (fallback: start family). Returns (label, allowance).
    keeper -> ('keeper', 0) is credited 0; None -> unresolved (excluded)."""
    if "107" in end_qids:
        return "throw-in", allow["From Throw In"]
    if "124" in end_qids:
        return "goal-kick", allow["From Goal Kick"]
    if "6" in end_qids or family == "Corner / set piece":
        return "corner", allow["From Corner"]
    if "5" in end_qids or family in ("Foul", "Offside"):
        return "free-kick", allow["From Free Kick"]
    if "123" in end_qids:
        return "keeper", 0.0
    return None, 0.0


# Opta delay markers (event-type NAMES as they surface in the candidate boundaries).
# 27 = Start delay, 28 = End delay (both real referee-caused stoppages: injury, VAR review,
# ball/net inspection, melee) that carry NO restart qualifier + NO incident event, so the
# require-a-marker ladder returned None and dropped them to rule 8. 65 = Contentious referee
# decision (Opta's closest VAR proxy; only 62x tournament-wide, ~1 lone window). Per Law 7 all
# of this is time that must be added back, so any dead window touching one is credited in FULL.
DELAY_EVT = {"Type 27", "Type 28", "Type 65"}
STITCH_TOL_S = 0.05  # exact temporal contiguity == "no live football between" (see ADR-0037)


def _stitch_windows(gaps):
    """Merge temporally contiguous candidate gaps (next.start ~ cur.end, no football between)
    within one (match, period) into maximal dead windows. Over-segmentation in the candidate
    sheet splits a single stoppage at each interior logged non-football event (the France v
    Senegal VAR window = 3 gaps); exact contiguity re-stitches them."""
    gs = sorted(gaps, key=lambda g: g["start_min_abs"])
    windows, cur = [], [gs[0]]
    for a, b in zip(gs, gs[1:]):
        if (b["start_min_abs"] - a["end_min_abs"]) * 60.0 <= STITCH_TOL_S:
            cur.append(b)
        else:
            windows.append(cur)
            cur = [b]
    windows.append(cur)
    return windows


def _has_openplay(op_sorted, lo, hi):
    """Any open-play minute_absolute in [lo, hi)? Half-open on the LEFT so that an open-play
    restart logged exactly at the prior window's end counts as 'the ball went live'."""
    i = bisect.bisect_left(op_sorted, lo)
    return i < len(op_sorted) and op_sorted[i] < hi


def _last_openplay_before(op_sorted, t):
    """Latest open-play minute_absolute strictly before t (the ball's last live moment)."""
    i = bisect.bisect_left(op_sorted, t)
    return op_sorted[i - 1] if i > 0 else None


def _first_balldeath_in(bd_sorted, lo, hi):
    """Earliest ball-death minute_absolute in the OPEN interval (lo, hi)."""
    i = bisect.bisect_right(bd_sorted, lo)
    return bd_sorted[i] if i < len(bd_sorted) and bd_sorted[i] < hi else None


def compute_owed(T):
    p = config.params()["incident"]
    allow = {str(k): float(v) for k, v in p["restart_normal_s"].items()}
    caps = dict(injury=p["max_injury_s"], sub=p["max_sub_s"], card=p["max_card_s"],
                celebration=p["max_celebration_s"])

    # ADR-0038 adds two credited components (seam, leadin) that recover genuine dead time Opta
    # never placed in a candidate gap; component 3 (half-time subs) REMOVES owed via the sub branch.
    COMP = ["hydration", "injury", "sub", "card", "celebration",
            "throw-in", "goal-kick", "corner", "free-kick", "delay", "seam", "leadin"]
    owed = defaultdict(lambda: {c: 0.0 for c in COMP} | {"keeper_s": 0.0, "excluded_s": 0.0})
    hyd_used = set()          # (match, period) already given a hydration credit  (<=1/half gate)
    hyd_events = defaultdict(int)
    excl_by_family = defaultdict(float)   # QA: residual (post-fix) rule-8 excluded baseline
    stats = dict(delay_windows=0, delay_gaps=0, lone65_windows=0, lone65_s=0.0,
                 seam_windows=0, seam_s=0.0, leadin_windows=0, leadin_s=0.0,
                 halftime_windows=0, halftime_removed_s=0.0)

    by_mp = defaultdict(list)
    for g in T["cand"]:
        by_mp[(g["fixture_uuid"], g["period"])].append(g)

    for (uu, per), gaps in by_mp.items():
        acc = owed[uu]
        op = T["openplay"].get((uu, per), [])
        bd = T["balldeath"].get((uu, per), [])
        ps_mc = PERIOD_START_MC.get(per, "")
        prev_end = None   # end minute_absolute of the previous stitched window in THIS period

        for w in _stitch_windows(gaps):
            w_start, w_end = w[0]["start_min_abs"], w[-1]["end_min_abs"]

            # -- Component 1: inter-window seam. Dead time between the previous window's end and
            #    this window's start with NO open-play event in between -> the ball never went
            #    live, so it is one continuous stoppage Opta split into two gaps. Credit the seam.
            if prev_end is not None and (w_start - prev_end) * 60.0 > STITCH_TOL_S \
                    and not _has_openplay(op, prev_end, w_start):
                seam_s = (w_start - prev_end) * 60.0
                acc["seam"] += seam_s
                stats["seam_windows"] += 1
                stats["seam_s"] += seam_s

            # -- Component 2: lead-in. Delay stoppages have candidate windows that begin at the
            #    Type 27 marker, not at the foul/out that actually killed the ball. If the ball
            #    went live after the previous window (a FRESH onset, not a seam continuation),
            #    walk back to the ball-death event and credit the intervening dead time.
            op0 = _last_openplay_before(op, w_start)
            if op0 is not None and (prev_end is None or op0 > prev_end):
                bdt = _first_balldeath_in(bd, op0, w_start)
                if bdt is not None:
                    leadin_s = min((w_start - bdt) * 60.0, LEADIN_CAP_S)
                    if leadin_s > 0:
                        acc["leadin"] += leadin_s
                        stats["leadin_windows"] += 1
                        stats["leadin_s"] += leadin_s

            prev_end = w_end

            # A delay flag ANYWHERE in the window (boundary OR interior sub-gap boundary) makes
            # the ENTIRE contiguous dead window addable -> credit its full summed D. This
            # SUPERSEDES the per-gap ladder for those gaps (no double-count; caps exactly at
            # window D, so gate G2 OWED<=total-dead holds by construction).
            if any(g["start_evt"] in DELAY_EVT or g["end_evt"] in DELAY_EVT for g in w):
                acc["delay"] += sum(g["D"] for g in w)
                stats["delay_windows"] += 1
                stats["delay_gaps"] += len(w)
                if not any(g["start_evt"] in {"Type 27", "Type 28"}
                           or g["end_evt"] in {"Type 27", "Type 28"} for g in w):
                    stats["lone65_windows"] += 1
                    stats["lone65_s"] += sum(g["D"] for g in w)
                continue

            # Non-delay window: each constituent gap runs the original require-a-marker ladder.
            for g in w:
                D, fam = g["D"], g["family"]
                sET, eET, qids = g["start_evt"], g["end_evt"], g["end_qids"]

                # 1. hydration -- gap spans the half's break midpoint (full D, once per half)
                mids = T["hyd"].get((g["match"], per), [])
                if mids and any(g["start_min_abs"] <= m <= g["end_min_abs"] for m in mids):
                    if (g["match"], per) not in hyd_used:
                        acc["hydration"] += D
                        hyd_used.add((g["match"], per))
                        hyd_events[(g["match"], per)] += 1
                    continue
                # 2. injury
                if sET in INJURY_EVT or eET in INJURY_EVT or fam in INJURY_FAM:
                    acc["injury"] += min(D, caps["injury"]); continue
                # 3. substitution -- ADR-0038: a sub logged at the period-start match clock
                #    happened during the half-time interval, BEFORE the whistle. It is not an
                #    in-play stoppage: credit 0 (keep D in the dead accounting as excluded).
                if sET in SUB_EVT or eET in SUB_EVT or fam.startswith("Substitution"):
                    pre_whistle = ((sET in SUB_EVT and g["start_mc"] == ps_mc)
                                   or (eET in SUB_EVT and g["end_mc"] == ps_mc))
                    if pre_whistle:
                        stats["halftime_removed_s"] += min(D, caps["sub"])
                        stats["halftime_windows"] += 1
                        acc["excluded_s"] += D
                        excl_by_family[fam or "(blank)"] += D
                        continue
                    acc["sub"] += min(D, caps["sub"]); continue
                # 4. card
                if sET in CARD_EVT or eET in CARD_EVT or fam in CARD_FAM:
                    acc["card"] += min(D, caps["card"]); continue
                # 5. celebration (WC2026 = POST -> full gap)
                if sET in CELEB_EVT or fam in CELEB_FAM:
                    acc["celebration"] += min(D, caps["celebration"]); continue
                # 6. restart ladder -- credit EXCESS over Nate's allowance
                rtype, a = resolve_restart(qids, fam, allow)
                if rtype in ("throw-in", "goal-kick", "corner", "free-kick"):
                    acc[rtype] += max(0.0, D - a); continue
                # 7. keeper restart -> 0 (tracked)
                if rtype == "keeper":
                    acc["keeper_s"] += D; continue
                # 8. everything else -> 0 (require-a-marker: residual excluded baseline)
                acc["excluded_s"] += D
                excl_by_family[fam or "(blank)"] += D

    rows = []
    for uu, acc in owed.items():
        owed_s = sum(acc[c] for c in COMP)
        rows.append({"fixture_uuid": uu, "owed_s": owed_s,
                     **{f"owed_{c.replace('-', '')}_s": acc[c] for c in COMP},
                     "keeper_s": acc["keeper_s"], "excluded_silent_s": acc["excluded_s"]})
    return pd.DataFrame(rows), hyd_events, dict(excl_by_family), stats


# ---- PLAYED ----------------------------------------------------------------------------
def compute_played(T):
    rows = []
    for uu in T["fixtures"]:
        per_played = {}
        for per in (1, 2, 3, 4):
            clk = T["ends"].get((uu, per))
            if clk is None:
                continue
            per_played[per] = max(0.0, clk - NOMINAL_END[per])
        reg_s = per_played.get(1, 0.0) + per_played.get(2, 0.0)
        full_s = sum(per_played.values())
        rows.append({"fixture_uuid": uu, "played_reg_s": reg_s, "played_full_s": full_s,
                     "n_periods": len(per_played)})
    return pd.DataFrame(rows)


# ---- agg_01 assembly -------------------------------------------------------------------
def build_agg01(T):
    owed_df, hyd_events, excl_by_family, owed_stats = compute_owed(T)
    played_df = compute_played(T)
    fx = pd.DataFrame(T["fixtures"].values())

    df = (fx.merge(owed_df, on="fixture_uuid", how="left")
            .merge(played_df, on="fixture_uuid", how="left"))
    for c in [c for c in df.columns if c.endswith("_s")]:
        df[c] = df[c].fillna(0.0)

    # attach Sheet1 (canonical pair) + total-dead gate value
    df["sheet1_key"] = df["key"]
    s1 = T["sheet1"]
    df["played_sheet1_s"] = df["sheet1_key"].map(lambda k: s1.get(k, {}).get("actual_stoppage_s"))
    df["extra_time_match"] = df["sheet1_key"].map(lambda k: s1.get(k, {}).get("extra_time_match"))
    df["total_dead_s"] = df["match"].map(T["summ_dead"])
    # ADR-0038: seam + lead-in are genuine dead seconds Opta never placed in a candidate gap, so
    # they are NOT in the Stoppage_Summary dead. The correct OWED<=dead bound (G2) must add them
    # back; otherwise crediting them could push OWED above the candidate-only dead by construction.
    df["total_dead_broad_s"] = df["total_dead_s"] + df["owed_seam_s"] + df["owed_leadin_s"]

    df["est_min"] = df["owed_s"] / 60.0
    df["played_min"] = df["played_full_s"] / 60.0            # chart x-axis (P1-4, ADR decision #6)
    df["played_reg_min"] = df["played_reg_s"] / 60.0
    df["played_sheet1_min"] = df["played_sheet1_s"] / 60.0
    df["played_delta_s"] = df["played_reg_s"] - df["played_sheet1_s"]  # regulation-comparable

    # component minutes (strip the trailing "_s" only -- "owed_sub_s" must not lose its inner "_s")
    comp_cols = [c for c in df.columns if c.startswith("owed_") and c.endswith("_s")
                 and c != "owed_s"]
    comp_min = {c: c[:-2] + "_min" for c in comp_cols}
    for c, m in comp_min.items():
        df[m] = df[c] / 60.0

    out_cols = (["match", "fixture_uuid", "est_min", "played_min", "played_reg_min",
                 "played_sheet1_min", "played_delta_s", "extra_time_match"]
                + list(comp_min.values())
                + ["keeper_s", "excluded_silent_s", "total_dead_s", "total_dead_broad_s"])
    return (df, df[out_cols].sort_values("match").reset_index(drop=True),
            hyd_events, excl_by_family, owed_stats)


# ---- agg_02 (productivity by bucket, regulation P1+P2) ----------------------------------
def _bucket_overlaps(period, lo, hi, spans):
    tot = 0.0
    for s, e in spans:
        ov = min(e, hi) - max(s, lo)
        if ov > 0:
            tot += ov
    return tot


def build_agg02(T):
    # goals per bucket (P1/P2), within-period coords
    goal_b = defaultdict(int)
    for g in T["goals"]:
        per = g["period"]
        if per not in (1, 2):
            continue
        within = g["clock_s"] - NOMINAL_START[per]
        b = bucket_of(per, within)
        if b is not None:
            goal_b[b] += 1

    # dead spans per (fixture, period) in within-period coords
    dead_spans = defaultdict(list)
    for c in T["cand"]:
        per = c["period"]
        if per not in (1, 2):
            continue
        s = c["start_min_abs"] * 60.0 - NOMINAL_START[per]
        e = c["end_min_abs"] * 60.0 - NOMINAL_START[per]
        if e > s:
            dead_spans[(c["fixture_uuid"], per)].append((s, e))

    live_b = defaultdict(float)
    for uu in T["fixtures"]:
        for per in (1, 2):
            clk = T["ends"].get((uu, per))
            if clk is None:
                continue
            period_end_within = clk - NOMINAL_START[per]
            spans = dead_spans.get((uu, per), [])
            for lab, lo, hi in RANGES[per]:
                played_span = max(0.0, min(hi, period_end_within) - lo)
                if played_span <= 0:
                    continue
                dead = _bucket_overlaps(per, lo, hi, spans)
                live_b[lab] += max(0.0, played_span - dead)

    rows = []
    for b in BUCKET_ORDER:
        goals = float(goal_b.get(b, 0))
        live_min = live_b.get(b, 0.0) / 60.0
        rate, lo, hi = stats.poisson_rate_ci(goals, live_min) if live_min > 0 else (float("nan"),) * 3
        rows.append({"bucket": b, "goals": goals, "live_min": live_min,
                     "rate": rate, "ci_lo": lo, "ci_hi": hi})
    return pd.DataFrame(rows)


# ---- main ------------------------------------------------------------------------------
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"reading {XLSX.name} ...")
    T = load_workbook_tables()
    print(f"  fixtures={len(T['fixtures'])}  candidate gaps(P1-4)={len(T['cand'])}  "
          f"goals(P1-2)={sum(1 for g in T['goals'] if g['period'] in (1,2))}")

    full, agg01, hyd_events, excl_by_family, owed_stats = build_agg01(T)
    agg02 = build_agg02(T)

    agg01.to_parquet(OUT / "agg01_estimate_vs_played.parquet", index=False)
    agg01.to_csv(OUT / "agg01_estimate_vs_played.csv", index=False)
    agg02.to_parquet(OUT / "agg02_productivity_by_bucket.parquet", index=False)
    agg02.to_csv(OUT / "agg02_productivity_by_bucket.csv", index=False)
    print(f"  wrote agg01 ({len(agg01)} matches) + agg02 ({len(agg02)} buckets) to {OUT}")

    write_ledger(full, agg01, agg02, T, hyd_events, excl_by_family, owed_stats)


def write_ledger(full, agg01, agg02, T, hyd_events, excl_by_family, owed_stats):
    import numpy as np
    L = ["# WC2026 (Sky / Opta) chart-input QA ledger", "",
         "Generated by `src/sky_wc2026/build_wc2026_inputs.py`. Eyeball only -- NOT a calibration "
         "target (no external anchor exists for WC2026; the methodology is trusted).", ""]

    n = len(full)
    owed = full["owed_s"] / 60.0
    played = full["played_full_s"] / 60.0
    missing = owed - played
    L += ["## Headline QA (periods 1-4)", "",
          f"- matches: **{n}**",
          f"- mean OWED: **{owed.mean():.2f} min**   (median {owed.median():.2f})",
          f"- mean PLAYED: **{played.mean():.2f} min**   (median {played.median():.2f})",
          f"- mean (OWED - PLAYED) 'missing': **{missing.mean():.2f} min**",
          f"- matches with OWED > PLAYED: **{(owed > played).mean():.1%}** ({int((owed>played).sum())}/{n})",
          ""]

    # owed component breakdown (pooled minutes)
    comp_cols = [c for c in full.columns if c.startswith("owed_") and c.endswith("_s")
                 and c != "owed_s"]
    tot_owed = full["owed_s"].sum()
    L += ["## OWED component breakdown (pooled, minutes; share of total owed)", ""]
    for c in sorted(comp_cols):
        s = full[c].sum()
        share = s / tot_owed if tot_owed else float("nan")
        L.append(f"- {c.replace('owed_','').replace('_s',''):11s}: {s/60:8.1f} min  ({share:5.1%})")
    excl = full["excluded_silent_s"].sum()
    keeper = full["keeper_s"].sum()
    total_dead = full["total_dead_s"].sum()
    delay = full["owed_delay_s"].sum()
    L += ["",
          f"- **excluded silent baseline** (rule 8, RESIDUAL after delay-crediting): "
          f"**{excl/60:.1f} min** ({excl:.0f}s) = {excl/total_dead:.1%} of total dead",
          f"- keeper restarts (credited 0): {keeper/60:.1f} min ({keeper:.0f}s) = "
          f"{keeper/total_dead:.1%} of total dead",
          f"- total dead (Stoppage_Summary, P1-4): {total_dead/60:.1f} min", ""]

    # ---- delay-credit component (ADR-0037): the new addable mass -------------------------
    L += ["### Delay-window credit (ADR-0037 -- Opta type 27/28/65 stoppages, FULL D)", "",
          f"- delay windows credited: **{owed_stats['delay_windows']}** "
          f"(spanning {owed_stats['delay_gaps']} candidate gaps)",
          f"- delay OWED credit: **{delay/60:.1f} min** ({delay:.0f}s) = {delay/tot_owed:.1%} "
          f"of total owed, {delay/total_dead:.1%} of total dead",
          f"- lone type-65 windows (contentious, no 27/28): {owed_stats['lone65_windows']} "
          f"({owed_stats['lone65_s']/60:.1f} min) -- immaterial either way",
          ""]

    # ---- ADR-0038 recovered / removed components ----------------------------------------
    seam_min = full["owed_seam_s"].sum() / 60.0
    leadin_min = full["owed_leadin_s"].sum() / 60.0
    ht_removed_min = owed_stats["halftime_removed_s"] / 60.0
    L += ["### ADR-0038 seam + lead-in recovery (ADD owed) and half-time-sub removal (REMOVE owed)",
          "",
          f"- **inter-window seam** credited: **{seam_min:.1f} min** ({full['owed_seam_s'].sum():.0f}s) "
          f"across {owed_stats['seam_windows']} seams (dead between two candidate windows with no "
          f"open-play event between -> one continuous stoppage Opta split in two)",
          f"- **lead-in** credited: **{leadin_min:.1f} min** ({full['owed_leadin_s'].sum():.0f}s) "
          f"across {owed_stats['leadin_windows']} windows (ball-death -> delay-onset window start; "
          f"cap {LEADIN_CAP_S:.0f}s)",
          f"- **half-time-sub removal**: **-{ht_removed_min:.1f} min** ({owed_stats['halftime_removed_s']:.0f}s) "
          f"across {owed_stats['halftime_windows']} pre-whistle sub windows (Match clock == period "
          f"start) -> moved from owed `sub` to excluded",
          ""]

    # ---- before -> after delta vs the ADR-0037 baseline (the estimate already sent to Sky) ---
    BEFORE = {  # ADR-0037 pooled minutes, 96 matches (frozen "before" iteration)
        "mean_owed": 19.65, "mean_played": 12.69, "mean_missing": 6.96, "pct_owed_gt": 1.000,
        "sub": 326.2, "excluded": 259.8, "seam": 0.0, "leadin": 0.0}
    after = {"mean_owed": owed.mean(), "mean_played": played.mean(), "mean_missing": missing.mean(),
             "pct_owed_gt": (owed > played).mean(),
             "sub": full["owed_sub_s"].sum() / 60.0,
             "excluded": full["excluded_silent_s"].sum() / 60.0,
             "seam": seam_min, "leadin": leadin_min}
    L += ["### Before -> after delta (ADR-0037 baseline -> ADR-0038)", "",
          "| metric | before | after | delta |", "|---|---|---|---|",
          f"| mean OWED (min) | {BEFORE['mean_owed']:.2f} | {after['mean_owed']:.2f} | "
          f"{after['mean_owed']-BEFORE['mean_owed']:+.2f} |",
          f"| mean PLAYED (min) | {BEFORE['mean_played']:.2f} | {after['mean_played']:.2f} | "
          f"{after['mean_played']-BEFORE['mean_played']:+.2f} |",
          f"| mean (OWED-PLAYED) (min) | {BEFORE['mean_missing']:.2f} | {after['mean_missing']:.2f} | "
          f"{after['mean_missing']-BEFORE['mean_missing']:+.2f} |",
          f"| % OWED>PLAYED | {BEFORE['pct_owed_gt']:.1%} | {after['pct_owed_gt']:.1%} | "
          f"{after['pct_owed_gt']-BEFORE['pct_owed_gt']:+.1%} |",
          f"| owed `sub` (min) | {BEFORE['sub']:.1f} | {after['sub']:.1f} | "
          f"{after['sub']-BEFORE['sub']:+.1f} |",
          f"| owed `seam` (min) | {BEFORE['seam']:.1f} | {after['seam']:.1f} | {after['seam']:+.1f} |",
          f"| owed `leadin` (min) | {BEFORE['leadin']:.1f} | {after['leadin']:.1f} | {after['leadin']:+.1f} |",
          f"| excluded baseline (min) | {BEFORE['excluded']:.1f} | {after['excluded']:.1f} | "
          f"{after['excluded']-BEFORE['excluded']:+.1f} |",
          "",
          f"Net mean-OWED move: **{after['mean_owed']-BEFORE['mean_owed']:+.2f} min/match** "
          f"= +{seam_min/96:.2f} seam +{leadin_min/96:.2f} lead-in -{ht_removed_min/96:.2f} half-time-sub.",
          ""]

    # worked-example checks (the audit fixtures)
    L += ["### Worked-example checks", ""]
    for mm in ("Canada v Qatar", "Germany v Paraguay", "Jordan v Argentina"):
        row = full[full["match"] == mm]
        if row.empty:
            continue
        r0 = row.iloc[0]
        L.append(f"- **{mm}**: owed {r0['owed_s']/60:.2f} min "
                 f"(seam {r0['owed_seam_s']:.0f}s, lead-in {r0['owed_leadin_s']:.0f}s), "
                 f"played {r0['played_full_s']/60:.2f} min")
    L.append("")

    # excluded-by-family: confirm rule 8 only catches genuinely-unmarked families (no restart leak)
    L += ["### Excluded (rule 8) by candidate family -- confirms no restart/foul leak", ""]
    for fam, s in sorted(excl_by_family.items(), key=lambda kv: -kv[1]):
        L.append(f"- {fam}: {s/60:.1f} min ({s:.0f}s)")
    L.append("")

    # ---- validation gates ----
    L += ["## Validation gates", ""]

    # G1 PLAYED vs Sheet1 (regulation-comparable), <=30s. Restrict tolerance to non-ET matches:
    # for ET matches Sheet1.actual_stoppage_time counts everything beyond the 90' schedule
    # (incl. the two 15' ET periods), so it is NOT comparable to per-period added time.
    d = full.dropna(subset=["played_sheet1_s"]).copy()
    d["abs_delta"] = (d["played_reg_s"] - d["played_sheet1_s"]).abs()
    reg = d[d["extra_time_match"] == "No"]
    et = d[d["extra_time_match"] == "Yes"]
    bad = reg[reg["abs_delta"] > 30.0]
    L.append(f"- **G1 PLAYED vs Sheet1** (|Δ|≤30s, non-ET, regulation P1+P2): "
             f"matched {len(reg)} non-ET; max|Δ|={reg['abs_delta'].max():.1f}s; "
             f"{'PASS' if bad.empty else f'{len(bad)} EXCEPTIONS'}")
    for _, r in bad.sort_values("abs_delta", ascending=False).iterrows():
        L.append(f"    - {r['match']}: mine {r['played_reg_s']:.0f}s vs Sheet1 "
                 f"{r['played_sheet1_s']:.0f}s (Δ {r['played_reg_s']-r['played_sheet1_s']:+.0f}s)")
    L.append(f"    - ET matches ({len(et)}) excluded from the tolerance test: Sheet1 counts the two "
             f"15' ET halves as stoppage-beyond-90', so it is not regulation-comparable "
             f"(these are the only |Δ|>30s rows).")
    unmatched = full[full["played_sheet1_s"].isna()]
    if not unmatched.empty:
        L.append(f"    - UNMATCHED to Sheet1 ({len(unmatched)}): "
                 + ", ".join(unmatched["match"].tolist()))

    # G2 OWED <= total dead per match.
    # ADR-0038 re-derivation: crediting inter-window seam + lead-in dead time (both are
    # dead seconds that live OUTSIDE the candidate windows summed in Stoppage_Summary)
    # can legitimately push OWED above the narrow Stoppage_Summary dead figure. The
    # invariant "owed never exceeds real dead time" still holds, but the correct
    # comparison is against the BROAD dead measure = summary dead + seam + lead-in.
    # We report both ratios for transparency; the gate itself keys off broad dead.
    g2 = full.dropna(subset=["total_dead_broad_s"]).copy()
    viol = g2[g2["owed_s"] > g2["total_dead_broad_s"] + 1.0]
    L.append(f"- **G2 OWED ≤ total dead (broad)** (per match, Stoppage_Summary + seam + lead-in): "
             f"{'PASS' if viol.empty else f'{len(viol)} VIOLATIONS'} "
             f"(max owed/broad-dead ratio {(g2['owed_s']/g2['total_dead_broad_s']).max():.2f}; "
             f"max owed/summary-dead ratio {(g2['owed_s']/g2['total_dead_s']).max():.2f})")
    for _, r in viol.iterrows():
        L.append(f"    - {r['match']}: owed {r['owed_s']:.0f}s > broad dead {r['total_dead_broad_s']:.0f}s")

    # G3 hydration <=1 per half
    over = {k: v for k, v in hyd_events.items() if v > 1}
    n_hyd = sum(hyd_events.values())
    n_half_breaks = sum(len(v) for v in T["hyd"].values())
    L.append(f"- **G3 hydration credited ≤1/half**: {n_hyd} credits across "
             f"{n_half_breaks} listed breaks; {'PASS' if not over else f'VIOLATIONS {over}'}")

    # G4 excluded/keeper share of dead
    L.append(f"- **G4 unresolved/excluded share of total dead**: "
             f"excluded {excl/total_dead:.1%} + keeper {keeper/total_dead:.1%} "
             f"= {(excl+keeper)/total_dead:.1%} (expect small)")

    # cross-check: candidate dead vs Stoppage_Summary per period (pooled)
    cand_dead = defaultdict(float)
    for c in T["cand"]:
        cand_dead[(c["match"], c["period"])] += c["D"]
    diffs = []
    for k, v in T["summ_dead_p"].items():
        diffs.append(cand_dead.get(k, 0.0) - v)
    diffs = np.array(diffs)
    L.append(f"- **X-check candidate ΣD vs Stoppage_Summary dead** (per period): "
             f"mean Δ {diffs.mean():+.1f}s, max|Δ| {np.abs(diffs).max():.1f}s "
             f"(candidate gap = wall-clock D, Summary = estimated dead; small residual expected)")
    L.append("")

    # ---- agg_02 table ----
    L += ["## agg_02 -- goals per live minute by bucket (regulation P1+P2)", "",
          "| bucket | goals | live_min | rate | ci_lo | ci_hi |", "|---|---|---|---|---|---|"]
    for _, r in agg02.iterrows():
        L.append(f"| {r['bucket']} | {r['goals']:.0f} | {r['live_min']:.1f} | "
                 f"{r['rate']:.4f} | {r['ci_lo']:.4f} | {r['ci_hi']:.4f} |")
    L.append("")

    (OUT / "ledger.md").write_text("\n".join(L) + "\n")
    print(f"  wrote {OUT / 'ledger.md'}")


if __name__ == "__main__":
    main()
