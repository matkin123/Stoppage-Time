# LOCK — the headline X% + CI + band (final session, HUMAN CHECKPOINT)

**This is the last modeling unit. Nothing left to BUILD — you only SELECT.** The full sensitivity grid,
the productivity-DECAY band, and the z-corrected in-stoppage gross-up are already produced (**ADR-0024,
2026-06-19**). This session decides the single modeled claim with the user, eyes open, and fills the
paused `ADR-XXXX — HEADLINE NUMBER` template in `docs/decisions.md` — **renumber it to ADR-0025**
(ADR-0024 is the decay/z-correction build). **Do NOT re-build, re-tune, or re-run s08 to "improve"
anything.** (CLAUDE.md §4/§6: the s08 grid is the second of the two human checkpoints.)

## This is a decision session, not an autonomous one
The headline is THE one modeled claim of the article. **Bring the grid to the user and decide together.**
Present the options, give a recommendation with the tradeoff, and let the user choose the rails. Do not
silently pick numbers and write them in. X% ships as a BAND with a CI and a sensitivity table — never a
bare point (CLAUDE.md §1).

## Read first (source of truth — not chat history)
- `processed/counterfactual_summary.parquet` — the grid (group=all). Columns: `window, knob_set,
  pct_changed, pct_outcome_flip, ci_lo, ci_hi, flip_ci_lo, flip_ci_hi, n_matches`. **knob_set is 5-part:
  `{silent}|{cond}|{source}|hl={h}|{gw}`** — the `hl=` slot is the decay half-life (min), `gw ∈
  {off, on, geometric}`. Central row = `silent_marked|overall|pooled_all|hl=4.0|on`.
- `docs/numbers_ledger.md` — the human-readable bands (Headline, Productivity-decay half-life band,
  O3 gross-up rails, Outcome-flip, Assumption-vs-sampling, A.2 — all written by s09).
- `docs/decisions.md` — **ADR-0024** (the CURRENT model: decay + gross-up central ON + z-correction +
  silent-as-a-POINT), **ADR-0021** (metric framing + band direction), **ADR-0019/0018 D1–D4** (remodel:
  metric, drop team_role, pool λ, silent central). The template to fill is the
  `## ADR-XXXX — HEADLINE NUMBER (PAUSED …)` block near the bottom.
- Optionally re-run `python run.py --stage 08` to reprint the grid + the DECAY HALF-LIFE BAND /
  GROSS-UP RAILS lines (deterministic; only the CI bootstrap uses the seed). Do NOT change knobs.

## The numbers as built (central = `silent_marked|overall|pooled_all|hl=4.0|on`; ADR-0024)
- **Headline (different SCORELINE, ≥1 extra goal), 1H+2H window:** central **23.6% [CI 20.6%, 27.4%]**;
  2H_only 16.0%.
- **Productivity-DECAY half-life band (the committed sensitivity, gross-up ON):** 1H+2H **22.2% (h=2) ..
  23.6% (h=4 central) .. 24.9% (h=8)**; 2H_only **14.4% .. 16.0% .. 17.4%**. The decay REPLACES the old
  observed/open-play rails — they are the h=∞ / h=0 endpoints (gross-up OFF backs them out byte-close:
  h=inf 1H+2H 23.8% / 2H_only 17.1%; h=0 2H_only 9.7%). live_share cancels in μ.
- **O3 in-stoppage gross-up (z=0.382 corrected; central is ON):** 1H+2H off 21.1% → **on 23.6%
  (central)** → geometric ceiling 24.2%; 2H_only off 14.1% → on 16.0% → geom 16.4%. NOTE: the geometric
  tail is now TIGHT (just above ON) — the z-correction (only the genuine-stoppage fraction z=0.382 of
  dead time recurs, not the full dead share) fixed the old `1/live_share` blow-up to 34%.
- **Outcome-flip secondary (stricter "different OUTCOME"):** **12.1% [10.6%, 14.2%]** (1H+2H) /
  8.2% (2H_only).
- **Silent band (the dominant, irreducible axis):** none 10.8–16.0% / marked 18.6–27.3% /
  all 25.8–37.3% across all other knobs. Central uses `silent_marked` + propagated estimator error;
  none/all are definitional guardrails, NEVER calibration targets. Full reported grid range 10.8–37.3%.
- **Assumption-vs-sampling:** central CI width 6.7%; with silent FIXED at marked the assumption spread
  is **1.3× sampling** (incl. silent it is 4.0×) — name the silent axis as the headline's biggest
  uncertainty.

## Decisions to make WITH THE USER (SELECT from the grid — most are already framed by ADR-0024)
1. **Window** — headline `1H+2H` (≥1 extra goal anywhere in omitted added time) vs `2H_only` comparison.
   Default 1H+2H (ADR-0019).
2. **Decay half-life band** — ADR-0024 already fixed central h=4, band [2,8] → 1H+2H ≈22–25%. Confirm the
   headline ships this band (lead number = h=4 central 23.6%).
3. **Gross-up** — ADR-0024 flipped central to ON (the directive must compensate for stoppage within
   added time). Confirm; report OFF (21.1%) as a conservative rail and geometric (24.2%) as the ceiling.
4. **λ source** — central `pooled_all`; report `pooled_pre`/`pooled_post`/`regime_matched` as
   sensitivities (D3: no first-principles pre/post λ difference; data agrees within Poisson noise).
5. **Conditioning** — central `overall`; `tied_nontied` as a sensitivity (D2: within noise).
6. **Silent** — central `silent_marked` (a POINT, ADR-0024); none/all are bounds only. Decide how
   prominently to surface the silent band (it is the dominant uncertainty).
7. **Outcome-flip** — confirm reported alongside as the stricter cut (~12.1%); headline stays scorelines.

## Red-team MUST-FIX framing (numbers refreshed to ADR-0024)
The pre-IMPL-8 red-team block in `next_session.md` lists three must-fix items written against the OLD
numbers (23.8% point, band ≈16–24%, flip 12.2%). The CURRENT equivalents the lock must LEAD with:
1. **Lead with the BAND, not a point.** The decay band is ≈22–25%, but the SILENT axis (10.8%→37.3%) is
   the dominant uncertainty and must be named. Do not present 23.6% as a bare point.
2. **Separate scoreline from outcome.** "≥1 extra goal in ~24%" vs "result actually flips in ~12%".
   `lead_by_2plus` matches cannot flip — "ended differently" attached to the scoreline number is the
   most attackable sentence.
3. **Carry the COVERAGE caveat verbatim.** Nate validates WC2018 only; POST is validated only indirectly
   (frozen-2018 estimator constants + the WC2022 Opta BIP point). This flag must survive into the ADR.

## Fill the ADR-0025 HEADLINE template
Replace the paused `ADR-XXXX — HEADLINE NUMBER` block with the locked values: X% + 95% CI, window, the
central knob_set `silent_marked|overall|pooled_all|hl=4.0|on`, the decay band rails (h2..h8), the
silent/conditioning/source sensitivities, the gross-up OFF/ON/geometric rails, the outcome-flip
secondary. Carry the **caveats** verbatim: irreducible silent band (ADR-0017); 1H counterfactual
independence (O1); thin PRE counts; Nate validates WC2018 only; board_announced under-allocation Δ (A.1)
is still DEFERRED and DESCRIPTIVE-only — never in X% (`prompts/scrape_board_announced.md`).

## Gate + checkpoint
- The locked ADR states a BAND + CI + sensitivity table, not a bare point (CLAUDE.md §1).
- `pytest` stays green (no code changes expected; if you re-run s08, the summary is unchanged).
- Update `next_session.md`: headline LOCKED; the only optional remaining unit is the deferred
  board_announced scrape (descriptive). The modeling pipeline is DONE.
- STOP.
