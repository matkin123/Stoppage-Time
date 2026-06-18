# IMPL-4 — Make the silent term a sensitivity knob; propagate estimator error; lock X% (HUMAN CHECKPOINT)

**Read first:** `CLAUDE.md` (§6, and §4 acceptance gates), `prompts/silent_component_findings.md`,
and ADR-0015 in `docs/decisions.md`. Prereq: IMPL-3 done (marker-gated s05 estimator built +
validated vs Nate `expected`; residual constant frozen). This is the second human checkpoint —
the headline X% is locked here, eyes open. Do ONLY this unit.

## Framing (this is the real payoff — read before coding)
We cannot measure the silent component perfectly with free data; the marker-gated estimator tops
out around r≈0.77 (ADR-0014/0015). So instead of shipping one silent estimate and pretending it is
exact, we make the **silent treatment an explicit dimension of the s08 sensitivity grid** and ask
the decisive question: **does the headline X% even depend on it?**
- If X% is robust across the silent knob → the residual silent uncertainty does not matter for the
  claim, and we say so. We are done.
- If X% swings across the knob → we report the band honestly as part of the sensitivity table.
Either way the irreducible silent uncertainty flows into the published CI instead of hiding inside
a point estimate.

## Handoff — what IMPL-3 left in place (data + plumbing you build on)
**Data (already materialized, all six tournaments):**
- `interim/incident_stoppage.parquet`, per `(match_id, period)` — the columns you need are
  `lower_bound_s`, `silent_marked_s` (marker-gated central term), `silent_all_s` (ungated upper
  bound), `injury_present`, `var_s`. `test_s05_silent_marked_within_all` guards
  `silent_marked_s <= silent_all_s` per row.
- `interim/true_stoppage.parquet`, per match (FULL-MATCH totals) — `lower_bound_s`,
  `silent_marked_s`, `residual_silent_s`, `true_stoppage_s`. This is the IMPL-3 estimator output
  used for the Nate validation; it is NOT the per-period frame s08 consumes (see gotcha 1).
- `config/params.yaml:silent` — `residual_silent_s: 114.0` (frozen, fit on 2018),
  `estimator_pearson_r: 0.768`, `estimator_mae_min: 2.75` (full-match residuals vs Nate `expected`).

**Plumbing to rewire (s08):** the three silent settings map directly onto the columns above.
- `src/s08_counterfactual.py:true_stoppage_minutes()` (~line 134) currently switches on the OLD
  knob names (`lower_bound` / `lower_bound_plus_injury` / `full_measure_538`) and reads only
  `lower_bound_s`. Replace its body so each new knob sums the right column at **period 2**:
  `silent_none → lb`, `silent_marked → lb + silent_marked_s`, `silent_all → lb + silent_all_s`
  (+ the calibrated residual where appropriate — see gotcha 1).
- `config/params.yaml:counterfactual.true_stoppage_knobs` is the list the grid iterates
  (`src/s08_counterfactual.py` ~line 207). Swap it to `[silent_none, silent_marked, silent_all]`.
  The other two grid dimensions (`lambda_conditioning_knobs`, `lambda_source_knobs`) are unchanged.

## Gotchas (read before coding — these are the landmines)
1. **s08 is a 2H-only (period 2) frame, but the residual/MAE were fit on full-match totals.**
   `true_stoppage_minutes` slices `incident[incident["period"]==2]`; `board2`/`ls2`/`mlive`
   (~lines 200–218) are all period-2. The IMPL-3 `residual_silent_s` (114s) and `estimator_mae_min`
   (2.75) were calibrated against Nate `expected`, which is a FULL-MATCH number. Do NOT bolt the
   full 114s / 2.75 onto the 2H frame unchanged — decide and document: scale to the 2H share, or
   re-derive a 2H-specific residual/sigma. This is the single most likely source of a silent bug.
2. **Estimator-error propagation must reach `mlive`.** The bootstrap (~lines 249–256) currently
   samples only lambda (Jeffreys Gamma). To widen the too-tight `[2.6–2.8%]` band, add a per-match
   draw on the stoppage minutes (`ts_min[m]` / `mlive`) using the per-match sigma from gotcha 1.
   Only tied / 1-goal matches can flip, so accuracy there dominates the CI.
3. **`silent_all` is genuinely large** (~2837 min total vs ~1344 marked across all matches) — it is
   the old over-counter, kept ONLY as the upper rail of the band. Expect X% to move under it; that
   movement IS the sensitivity result, not a bug to suppress.

## Task
1. **Add the silent-treatment knob to s08** (three settings, run end-to-end at each), wired to the
   columns above:
   - `silent_none` — credit zero silent dead time (hard lower bound on stoppage).
   - `silent_marked` — the IMPL-3 marker-gated silent term (`silent_marked_s`, the central estimate).
   - `silent_all` — credit all ≥threshold silent gaps (`silent_all_s`, the over-counting upper bound).
   Report X% at each setting so the headline's sensitivity to the silent assumption is visible.
2. **Propagate the per-match estimator error** (`estimator_mae_min`, ~±2.75 min full-match — scale
   to the 2H frame per gotcha 1) into the s08 bootstrap so the headline CI reflects estimator
   uncertainty, not just sampling. The current `[2.6–2.8%]` band is too tight. Only close (tied /
   1-goal) matches flip the outcome — prioritise estimator accuracy and error propagation there.
3. Re-run downstream in order: `python run.py --stage 07` → `--stage 08` → `--stage 09`.

## Gate (CLAUDE.md §4)
- **s07:** every productivity cell reports `n_events` AND `live_minutes` alongside the rate.
- **s08:** the full sensitivity grid — including the silent-treatment knob above — is produced.
  **READ it before locking X%** (do not commit to a single number until you have seen the grid and
  judged whether X% is robust to the silent treatment).
- **s09:** deterministic figures + numbers ledger; every figure traces to a script + a
  checkpointed table + a documented assumption.

## Lock, then STOP
- With the user, lock the headline **X% + confidence interval + sensitivity band** in
  `docs/decisions.md`, eyes open. State explicitly how sensitive X% is to the silent knob. This is
  the one modeled claim — it ships with the CI and the sensitivity table, never as a bare point
  estimate.
- ADR in `docs/decisions.md`; update `next_session.md` (silent-component work complete).
- End the session.
