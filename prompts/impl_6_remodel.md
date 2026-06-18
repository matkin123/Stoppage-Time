# IMPL-6 — Remodel the headline counterfactual (first-principles redesign)

**Read `docs/redesign.md` first** — it is the full spec; this prompt executes its "core remodel"
unit. Read `CLAUDE.md §6`: ONE self-contained unit, validate the gate, checkpoint, STOP. Do NOT do
the board/cooling research (separate sessions, `prompts/research_*.md`) and do NOT lock X% (that is
the final session). Upstream is FROZEN: `bip.py`/s03, the s05 estimator (r=0.825) and its constants,
the board=time-played measurement (only being RENAMED), the Nate harness.

## What this session does
Rebuild s08 (and the minimal s07/s09 it needs) to the redesigned model. NO new data sourcing.

### 1. Metric -> any-extra-goal closed form (D1, O1, O2)
- Replace the W/D/L Monte Carlo with: per match `mu = sum_h lambda_h * omitted_live_h`;
  `P(change) = 1 - exp(-mu)`; `X% = mean(P(change))`. Delete the 10k-sim flip logic (the
  `rng_mc.poisson` draws + `new_sign != actual_sign`). Keep the CI bootstrap (Gamma lambda +
  silent_marked estimator-error draw, D4) but compute P(change) analytically per draw.
- CONFIRM with the user before coding: (O1) include 1H stoppage (`mu = mu_1H + mu_2H`,
  "≥1 extra goal anywhere") vs a 2H-only headline; (O2) X% = mean(1-exp(-mu)) [recommended] vs a
  count of matches with mu >= 1.

### 2. Lambda -> drop team_role, default overall, pool PRE+POST (D2, D3)
- `build_lambda_cells`: keep `overall` (+ `tied_nontied` as a documented sensitivity). REMOVE
  `team_role` (level/leading/trailing) and the `_role_of` plumbing it feeds.
- Add a central source `pooled_all` (PRE+POST). Keep pooled_pre / pooled_post / regime_matched as
  sensitivities in the grid.
- ADD a 1H-stoppage lambda (today only 2H exists): from `goals[is_stoppage=="1H"]` and a 1H-stoppage
  live-share.

### 3. 1H window plumbing
- s07: add a `1H_stoppage` phase to `stoppage_live_share.parquet` (live/total within 1H added time),
  alongside the existing `2H_stoppage` / `any_stoppage`.
- s08: compute true_stoppage, played_in_stoppage, omitted, and omitted_live PER HALF (1H and 2H),
  using `period_end_s - 2700` for each half's played time.

### 4. Rename board -> played_in_stoppage (DC2)
- Rename the variable/columns produced by s06a and consumed by s08, plus the s09 ledger labels and
  comments. Add a SEPARATE `board_announced` column (NULL for now; populated in IMPL-7 if R1 finds a
  source). The counterfactual still uses `true_stoppage - played_in_stoppage` (unchanged math).

### 5. Data-consistency (DC1, DC3)
- DC1: make lambda exposure and the productivity ledger use the SAME per-match
  live-minutes-in-stoppage table. Today `build_lambda_cells` (~811 2H team-min) disagrees with the
  ledger (894.5) because matches missing from `live_share` fall to 0 exposure while their goals still
  count. Fix and assert they match.
- DC3: fix `s09:fig_productivity_by_bucket` (f01) to exclude/label extra time so the minute-120
  penalty/ET spike stops implying regulation contamination.

### 6. Re-run + validate
- `python run.py --stage 07` -> `08` -> `09`.
- Update tests: replace `test_s08_silent_knob_brackets_headline`'s flip assertions with the new
  P(change) monotonicity (more omitted live time / more silent credit => higher P(change); keep
  none <= marked <= all). Add a guard that P(change)=0 when mu=0 and is monotonic in omitted_live.

## Gate
- All pytest green. s08 prints the new grid (silent x conditioning x source) as P(change) X% + CI.
- Bring the new grid to the user. **Do NOT lock X%** — that is the final session after IMPL-7.

## Checkpoint
- ADR in `docs/decisions.md` (metric/lambda/rename/1H implemented; new grid numbers; what changed vs
  ADR-0017). Update `next_session.md`: IMPL-6 DONE, point to R1/R2 + IMPL-7. STOP.
