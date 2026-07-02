# Turnkey — Team-quality / Elo test for the outcome-flip (settles ADR-0034)

**Open a fresh session and run this whole unit, then stop (CLAUDE.md §6).** Self-contained.

## Role
Sports quant (soccer/football, event data + late-game game-state effects) **and** a data-sourcing
engineer comfortable with free international-football rating feeds (World Football Elo, bookmaker
odds). You reason from first principles and report **honest bands, not points**.

## Objective
Settle a reviewer objection to the outcome-flip secondary metric (locked **13.0% [11.3%, 15.1%]**,
ADR-0031): *the team leading by one at 90' is on average the better team, so the trailing (worse)
team scores fewer than half the omitted-window goals — `p_trail < 0.5` — and P(flip) should be
**less** than half of P(scoreline), not the ~0.52 the model reports.* Read `docs/decisions.md`
**ADR-0034** first — it records the reasoning; this prompt runs the two analyses that decide it.

**Bottom line to keep in view:** the headline **scoreline 24.8% is immune** (it never attributes the
scorer — `p_change(mu)`); only the flip's lead-by-1 branch (`src/s08_counterfactual.py:371`,
`p_change(mu/2)` ⇒ `p_trail = 0.5`) is exposed. So nothing here can move the headline; it can only
move the flip, and only through the `lead_by_1` bucket.

---

## Analysis A — Exact state-decomposition of the locked 13.0% flip
**Goal:** replace the equal-μ back-of-envelope with the real per-state split, and show how much of
the flip is even `p_trail`-sensitive (bounds the objection's maximum bite).

1. Reuse the s08 central-knob machinery (pattern: `src/flip_split_sensitivity.py` /
   `src/s08_counterfactual.py` `outcome_flip()` — both READ production parquet). Central knob
   `silent_marked|overall|pooled_all|hl=4.0|on`.
2. **Faithfulness gate FIRST:** reproduce the locked `pct_outcome_flip = 0.12976` (== production
   `processed/counterfactual.parquet`) before decomposing. If it doesn't match, stop and fix the
   harness.
3. For each of the 314 eligible matches, key on `state_at_90` (`interim/match_state.parquet`) and
   sum the per-match flip mass by state:
   - `tied` (98): `1 − exp(−μ)` — `p_trail`-immune (any goal flips).
   - `lead_by_1` (121): `1 − exp(−μ·0.5)` — `p_trail`-sensitive.
   - `lead_by_2plus` (95): 0 — unflippable.
4. **Report:** total flip = `X` pp from tied + `Y` pp from lead_by_1 (+0). The `p_trail`-sensitive
   share `Y/(X+Y)`. The **tied-only floor** `X` as a fraction of the 24.8% scoreline (the ratio the
   flip can never fall below, even at `p_trail=0`). The exact `flip/scoreline` ratio and its
   decomposition — confirm the "≈ half" is a state-census result, not a `p_trail` artifact.

---

## Analysis B — Elo-conditioned `p_trail` (explanatory power + crossover + covariance)
**Goal:** measure whether the aggregate `p_trail` is really < 0.5, whether quality has explanatory
power, test the user's crossover hypothesis, and measure the one channel the pooled mean misses.

**B1 — Quality proxy (sourcing).**
- **Primary: World Football Elo (eloratings.net)** — pre-match rating for both teams on match date,
  all 314 matches. Match-level, free (see memory `reference_external_datasets`). Cache raw pulls to
  `data/raw/` (immutable). Join by national-team name + date; reuse the name-normalization pattern
  in `src/lib/nate.py`.
- **Robustness alts (only if cheap):** pre-match bookmaker win-prob (gold standard for "better on the
  day"); FIFA ranking as a *coarse* robustness check — NOT primary (annually sticky, 2018 methodology
  break).

**B2 — Signed gap.** For each `lead_by_1` match, `Δ = Elo(trailing@90') − Elo(leading@90')`
(`Δ < 0` ⟺ leader stronger = the objection's case). Trailing/leading identity from `match_state` /
`score_{home,away}_after`.

**B3 — Regression (explanatory power + crossover).**
- Outcome: observed indicator "trailing team scored in the added-time/late window" among `lead_by_1`
  situations. Reconstruct the pre-goal margin from `score_after` exactly as
  `src/flip_split_sensitivity.py` does (reuse it); use its cuts (2H stoppage; late-window >75'/80').
- Model: `logit(trailing_scored) ~ Δ + Δ² + minute + competition`. `β₁` = the explanatory power the
  reviewer asked for; the `Δ²` term tests the **crossover** (chase wins at narrow `Δ`, quality at
  wide `Δ`). Report `β₁`, pseudo-R², the crossover `Δ*` where predicted `p_trail = 0.5`, calibration,
  and where the bulk of the `lead_by_1` population sits relative to `Δ*`.
- **Sample-size note:** `lead_by_1` stoppage goals are few (n≈31, ADR-0032). If power is inadequate,
  BORROW a larger international-match sample (Elo + late-goal scorer + game state) to fit `p_trail(Δ)`,
  then APPLY the curve to the 314. Flag any external-sample caveat (competition mix, era).

**B4 — Covariance (the first-order channel).** Measure `corr(signed Δ, μ_omitted)` across the 121
`lead_by_1` matches (μ = the s08 closed-form omitted-goal mean), then the **μ-weighted mean `p_trail`
vs unweighted**. Per-match `p_trail` heterogeneity washes out (Jensen, O(μ²)); a `p_trail`×μ
covariance does not — if the highest-omitted-time `lead_by_1` matches are the biggest mismatches, the
μ-weighted mean sits below 0.5 and the flip drops linearly.

**B5 — Re-weight and compare.** Swap the flat `p_trail = 0.5` for per-match predicted `p_trail(Δ)` in
the `lead_by_1` branch; recompute the aggregate flip; compare to the locked 13.0%. **Report a band.**
- **GUARDRAIL:** the regression is on OBSERVED scorers (the chase effect is already baked in). Do NOT
  replace production `p_trail` with an Elo-*implied* value derived from open-play scoring rates — that
  double-counts against the chase and biases the flip low. Elo TESTS residual signal; it does not SET
  the base rate.

---

## Deliverables
- New exhibit `docs/team_quality_flip_test.md`: Analysis-A decomposition table; the `Δ` regression
  (slope, `Δ*`, pseudo-R²); the covariance + μ-weighted vs unweighted `p_trail`; the re-weighted flip
  band vs 13.0%.
- Append the outcome to **ADR-0034** (or open ADR-0035 *only* if a human checkpoint adopts a change).
- Update `next_session.md` pointer. Run the README §7 pass (expected: no change — the 0.548 pre-empt
  already stands in the README results section).

## Guardrails (CLAUDE.md §6)
- **ANALYSIS ONLY.** Standalone script (e.g. `src/team_quality_flip.py`) that READS production parquet
  and writes a report. Do NOT overwrite `processed/counterfactual*.parquet`, the s08 grid, figures, or
  `params.yaml`. Pattern to copy: `src/flip_split_sensitivity.py`, `src/bip_headline_sensitivity.py`.
- Add an s08 sensitivity row **only if** the re-weighted flip moves **> 0.5 pp**; otherwise it is a
  Substack pre-empt, lock UNCHANGED.
- If the re-weight moves materially (> 0.5 pp, or leaves the flip CI [11.3%, 15.1%]), **STOP** and bring
  to a human checkpoint before any lock change. The headline 24.8% is untouched either way.

## Constants / paths (read live values; don't hard-code)
- Central knob `silent_marked|overall|pooled_all|hl=4.0|on`; windows 1H+2H (headline) + 2H_only.
- State census: **tied 98 / lead_by_1 121 / lead_by_2plus 95** (of 314).
- Locked flip to reproduce: `pct_outcome_flip = 0.12976`. `p_trail` leverage (ADR-0032):
  `[0.40,0.60] → flip 12.0%–13.9%`; measured `0.548 → ~13.4%`.
- Files: `interim/{match_state,incident_stoppage}.parquet`; `processed/counterfactual.parquet`;
  helpers in `src/s08_counterfactual.py` (`outcome_flip`, closed form). ADR-0032 exhibit:
  `docs/flip_split_sensitivity.md`; margin reconstruction: `src/flip_split_sensitivity.py`.
- Elo: eloratings.net (per-date ratings + downloadable history).
