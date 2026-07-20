# ADR-0040 Phase 0 — silent_marked / lower_bound double-count pressure test
Date: 2026-07-20   Pipeline lock: ADR-0039 (23.3%/12.1%)

## Self-consistency (re-derived vs locked incident_stoppage.parquet)
  max |Δ lower_bound_s|:   0.0000s  (expect ≈0)
  max |Δ silent_marked_s|: 0.0000s  (expect ≈0)

## P1 — Root cause confirmation + fix-location choice

### Smoking gun: Egypt 1-1 Congo DR (mid=3922240) P1
  silent_marked_s (production) = 330s
  lower_bound_s (production)   = 706s
  overlap_s (double-count)     = 306s
  dedup_silent_marked_s        = 24s
  (ADR-0040 spec cited 257s overlap; actual from this run: 306s)

### Overlap distribution across all 314 matches
  Matches with overlap > 30s: 281/314
  Max match overlap: 15.0 min (match 3922242, afcon_2023)

  Tournament                 Era      N   Overlap s/match   Overlap min/match
  ───────────────────────────────────────────────────────────────────────────
  wc_2018                    PRE     64             154.7                2.58
  euro_2020                  PRE     51             179.1                2.99
  euro_2024                  PRE     51             169.6                2.83
  wc_2022                    POST    64             172.8                2.88
  copa_america_2024          POST    32             285.2                4.75
  afcon_2023                 POST    52             331.2                5.52
    ** PRE pool **           PRE    166             166.8                2.78
    ** POST pool **          POST   148             252.8                4.21

### Mechanism
  `silent.py:74` excludes a gap only when `poss[i+1]!=poss[i] AND patterns[i+1] in
  restart_patterns`. An injury window whose RESUME event is 'Goal Keeper', 'Shot',
  or any non-From-... pattern bypasses this check. Since 'Injury Stoppage' IS in
  `out_of_play_types`, the gap lead-edge is marked → the gap lands in silent_marked_s.
  The same gap is ALSO in comp['injury'] → lower_bound_s. Both appear in true_stoppage.

### Fix-location analysis: A (dedup-in-s05) vs B (fix-silent.py)

  **Option A (dedup-in-s05) — RECOMMENDED**
  Credit: `silent_marked_s = _intersect_total(_subtract(silent_iv, all_intervals), dead)`
  `_subtract` removes from silent_iv any seconds already covered by all_intervals.
  - Surgical: only changes credit accounting in s05, nothing else
  - Provably disjoint by construction: lb and sm are now non-overlapping subsets of dead
  - `silent_all` deduped the same way; sm ≤ sa monotonicity preserved (marked ⊆ all)
  - Zero blast radius on BIP/s03

  **Option B (fix-silent.py) — also safe, not recommended**
  Skip a silent gap whose lead-edge event is an incident type (Injury Stoppage /
  Player Off / Substitution / Foul Committed / Bad Behaviour) even when the trailing
  possession lacks a From-... restart pattern.

  bip.py imports silent module: False  |  s03_bip.py: False
  (Confirmed: silent.py is ONLY consumed by s05_incident.py — Fix B cannot affect BIP)
  Fix B is principled but introduces coupling between silent.py and incident event types.
  **Verdict: proceed with Fix A.**

## P2 — WC2018 r/MAE under dedup + residual refit

  WC2018 calibration (all PRE; ADR-0039 uses excess-celeb convention on WC2018)
  Estimator                                 n       r   MAE (min)   pre_resid_s
  ───────────────────────────────────────────────────────────────────────────
  current (ADR-0039)                       32  0.870        1.67          25.9
  dedup Fix A (new refit)                  32  0.836        1.54         204.1

  mean(lb+dedup_sm) WC2018 = 9.76 min/match  (was ~12.73)
  mean Nate expected       = 13.16 min/match

  New PRE residual:  25.9s → 204.1s  (rises to re-anchor WC2018 to Nate)

  POST residual refit (full-gap celeb on WC2018):
    mean(lb_full+dedup_sm_full) = 10.99 min/match
    raw refit = 130.5s
    → POSITIVE (no floor needed). ADR-0039 D2 floor is MOOT under the dedup fix.
    This is the key evidence the fix is correct: the incoherent −47.7s residual
    (which ADR-0039 had to floor) was a SYMPTOM of the double-count.
  New POST residual: 0.0s → 130.5s

## P3 — Six-tournament before->after (mean owed/true_stoppage, min/match)

  Tournament                 Era      N      Curr     Dedup         Δ
  ─────────────────────────────────────────────────────────────────
  wc_2018                    PRE     64     12.69     13.09     +0.39
  euro_2020                  PRE     51     14.04     14.02     -0.02
  euro_2024                  PRE     51     14.00     14.15     +0.14
  wc_2022                    POST    64     16.51     15.81     -0.71
  copa_america_2024          POST    32     22.94     20.36     -2.58
  afcon_2023                 POST    52     25.22     21.87     -3.35
  ─────────────────────────────────────────────────────────────────
    ** PRE pool **           PRE    166     13.51     13.70     +0.19
    ** POST pool **          POST   148     20.96     18.92     -2.04
    ** pooled **             all    314     17.02     16.16     -0.86

  PRE pool:  13.51 → 13.70 (+0.19 min/match)
  POST pool: 20.96 → 18.92 (-2.04 min/match)
  PRE/POST owed gap (POST−PRE): 7.45 → 5.22 min/match  (narrows 2.23 min)

  POST-concentration is a DATA-QUALITY correction (AFCON/Copa restart tags looser than
  WCs/Euros), not a new bias. PRE barely changes because the residual re-anchors to Nate.

  NOTE: These owed projections are MEAN-BASED. The headline X% must come from the
  regenerated s08 grid (omitted = max(0, owed−played) per half; nonlinear; P(≥1 goal)
  saturates). Expect scoreline to move DOWN ~1–3 pp; exact magnitude requires s08.

## P4 — Gate interactions

  lb + dedup_sm > dead (new gate, should be 0 by construction): 0
  dedup_sm > dedup_sa monotonicity violations (should be 0):    0
  lb > dead (existing ADR-0039 gate, should be 0):               0
  lb + sm (pre-fix) > dead violations: 0  ← MISSING gate Phase 1 will add

  By construction after Fix A: silent_iv and all_intervals are now disjoint subsets
  of dead, so lb ⊂ dead and dedup_sm ⊂ dead and lb ∩ dedup_sm = ∅ → lb+dedup_sm ≤ dead.

## P5 — Expert flags

  ET periods (3-4) in data: 58 rows across 29 matches
    ET overlap > 0: 18 matches, mean 1.9 min/match
    Fix A applies equally to ET periods (all_intervals and silent_iv work in period_s coords)
  Matches with zero overlap: 18/314
  Production sa < sm violations (should be 0): 0
  Dedup sa < sm violations (should be 0):      0
  Matches retaining positive dedup_sm: 223/314
  Mean dedup_sm: 0.83 min/match  (was 4.28 min/match)
  → legitimate incremental silent time (non-incident-driven) is PRESERVED; only the
    seconds already credited by incident windows are removed.

  Max-overlap match: 3922242 (afcon_2023)
    overlap_s = 15.0 min
    sm_s = 15.4 min → dedup_sm_s = 0.4 min

## Go / No-Go

  PRE residual:  25.9s → 204.1s  (positive, coherent)
  POST residual: 0.0s → 130.5s  (POSITIVE — D2 floor MOOT)
  r/MAE: 0.870/1.67 → 0.836/1.54  (calibration changed)
  Gate violations (dedup): 0 lb+sm>dead, 0 sm>sa

  **VERDICT: GO.**
  - Double-count confirmed; mechanism clear; fix (A) is surgical and zero-BIP-risk.
  - Both residuals refit to coherent positive values; incoherent ADR-0039 D2 floor resolved.
  - POST-concentration is a data-quality correction, not a new bias.
  - Gate analysis shows dedup is conservative by construction (lb+sm ≤ dead).
  - Headline will move DOWN ~1–3 pp (exact from s08 grid); '>1 pp → human' guardrail applies.
  - Phase 1 may proceed after human sign-off.
