# IMPL-7 — Board-announced distortions + cooling breaks

**DEPENDS ON** `prompts/research_board.md` (R1, DONE/ADR-0020). R2 (`prompts/research_cooling.md`) is
DONE and **Part B is DE-SCOPED (ADR-0022)** — this session is now **Part A (board_announced
under-allocation) + Part C (band-building)** only. Read `docs/redesign.md`. `CLAUDE.md §6`: one unit,
validate, STOP. This runs AFTER IMPL-6 (the core remodel). Upstream FROZEN as in IMPL-6.

## A. Board-announced distortions (uses R1 findings)
- If R1 found a free source for the 4th-official announced board: populate `board_announced` (per
  half, per match; partial coverage is fine — flag which tournaments are covered).
- Compute two distortions and add them to the s09 ledger:
  1. **Under-allocation at 90'** = `true_stoppage - board_announced` (ref put too little on the board).
     DESCRIPTIVE only (separate from the X% counterfactual).
  2. **Time-wasting within stoppage** = `played_in_stoppage - played_in_stoppage * live_share` (dead
     ball during the played added time). Needs NO board data. This also yields the time-wasting RATE
     that feeds the Part C gross-up (ADR-0021 O3), so compute it here and carry the rate forward.

## B. Cooling breaks as pure stoppage — DE-SCOPED (ADR-0022, 2026-06-18). DO NOT BUILD.
R2 ran the "if it does NOT improve r, do not ship it" check ahead of time (read-only, against the
processed tables) and the hypothesis was REJECTED — so this part is dropped:
- The s05 estimator already credits **~73%** of a cooling break via `restart_excess` (measured on
  AFCON2023, where every match had breaks: clear break gaps avg 168s, ~122s already credited, ~46s
  missed). The "uncounted silent gap" premise is ≤27% true.
- On WC2018 (the only Nate-validated set; baseline r=0.825) a naive "+3 min/break" DEGRADES r (→0.780,
  MAE +1.07) by double-counting; the careful "missed-remainder only" add is within noise (sign flips
  with the detection threshold). Breaks concentrate in POST, which has no Nate ground truth.
- See `prompts/research_cooling_findings.md` + ADR-0022. If a reviewer insists on representing cooling,
  do it ONLY as a labeled POST-only sensitivity (~46s/break × detected breaks ≈ ~1.5 min/match on
  AFCON), shown as a band, never calibrated into the headline — NOT as an estimator-accuracy change.

## C. Counterfactual band finalization (ADR-0021 — build these so the lock just SELECTS)
These are small, well-specified s08/s09 changes. The headline ships as a BAND, not a point.
1. **Productivity-premium band.** Add a knob for the λ applied to OMITTED time: UPPER = observed
   stoppage λ (today); LOWER = open-play (regular) λ = `productivity[phase=regular]` (~0.0427
   goals/live-min) applied to omitted minutes. Expected: 1H+2H ~23.8% (upper) / ~16.3% (lower);
   2H-only 17.1% / 9.7%. Report both rails + the silent band in the ledger. (Reminder: `live_share`
   cancels in mu, so this band is the λ choice, not a live-share knob — see ADR-0021.)
2. **O3 time-wasting gross-up.** Using the rate from A.2, gross up omitted CLOCK time for the
   in-stoppage time-wasting that added time itself generates, then apply productivity to the live
   portion. The user has signed off that this RAISES X% — measure faithfully, no agenda.
3. **Outcome-flip secondary metric.** Alongside the any-extra-goal headline (different SCORELINE),
   compute and report the stricter "different OUTCOME" cut (winner/draw flips; tied + lead-by-1
   matches; per-team half-rate split) — ~12.7% illustrative. Headline stays scorelines.
4. **Do NOT** add the pre-first-goal λ re-fit unless trivially cheap — the open-play floor already
   brackets it (ADR-0021 #4).

## Gate + checkpoint
- pytest green. (Part B dropped — no r-vs-Nate re-validation needed; the estimator is unchanged.)
  The full sensitivity band (silent × productivity-premium rails, + outcome-flip secondary) printed
  by s08 and in the s09 ledger.
- ADR in `docs/decisions.md` with results. Update `next_session.md`. STOP.
- After this, the FINAL session locks X% + CI + band (the paused ADR-XXXX headline template).
