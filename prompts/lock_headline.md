# LOCK — the headline X% + CI + band (final session, HUMAN CHECKPOINT)

**This is the last unit. Nothing left to BUILD — you only SELECT.** The full sensitivity grid and the
band are already produced (IMPL-6 ADR-0019; IMPL-7 A.2+C ADR-0023). This session decides the single
modeled claim with the user, eyes open, and fills the paused `ADR-XXXX — HEADLINE NUMBER` template in
`docs/decisions.md`. **Do NOT re-build, do NOT re-tune, do NOT re-run s08 to "improve" anything.**
(CLAUDE.md §4/§6: the s08 grid is the second of the two human checkpoints.)

## This is a decision session, not an autonomous one
The headline is THE one modeled claim of the article. **Bring the grid to the user and decide together.**
Present the options, give a recommendation with the tradeoff, and let the user choose the rails. Do not
silently pick numbers and write them in. X% ships as a BAND with a CI and a sensitivity table — never a
bare point (CLAUDE.md §1).

## Read first (source of truth — not chat history)
- `processed/counterfactual_summary.parquet` — the grid (group=all). Columns: `window, knob_set,
  pct_changed, pct_outcome_flip, ci_lo, ci_hi`. knob_set is 5-part:
  `{silent}|{cond}|{source}|{prem}|{gw}`.
- `docs/numbers_ledger.md` — the human-readable band (Productivity-premium band, O3 gross-up,
  Outcome-flip, A.2 sections already written by s09).
- `docs/decisions.md` — **ADR-0021** (metric framing + band DIRECTION), **ADR-0023** (what was built),
  **ADR-0018 D1–D4** (metric, drop team_role, pool λ, silent central). The template to fill is the
  `## ADR-XXXX — HEADLINE NUMBER (PAUSED …)` block.
- Optionally re-run `python run.py --stage 08` to reprint the grid + the PRODUCTIVITY-PREMIUM BAND /
  O3 lines (deterministic; only the CI bootstrap uses the seed). Do not change knobs.

## The numbers as built (central = `silent_marked|overall|pooled_all|observed|off`)
- **Headline (different SCORELINE, ≥1 extra goal), 1H+2H window:** central **23.8% [CI 20.3%, 28.0%]**.
- **Productivity-premium band (the committed sensitivity):** 1H+2H **16.3% (open-play floor) ..
  23.8% (observed stoppage λ)**; 2H_only **9.7% .. 17.1%**. (live_share cancels in μ → this is the λ
  choice, not a live-share knob — ADR-0021 #2.)
- **O3 in-stoppage time-wasting gross-up (faithful, RAISES X%):** 1H+2H 23.8 → **31.6%**; 2H_only
  17.1 → **23.6%**. Report as a sensitivity (base = off).
- **Outcome-flip secondary (stricter "different OUTCOME"):** **12.2%** (1H+2H) / 8.8% (2H_only).
- **Silent band (the irreducible axis):** none 9.0–19.9% / marked 15.9–34.4% / all 22.5–47.1% across
  all other knobs. Central uses `silent_marked` + propagated estimator error (D4); none/all are
  definitional guardrails, never calibration targets.

## Decisions to make WITH THE USER (SELECT from the grid)
1. **Window** — headline = `1H+2H` (≥1 extra goal anywhere in omitted added time) vs `2H_only`
   comparison. (Default 1H+2H per ADR-0019.)
2. **Productivity-premium rail** — ship the BAND (open-play floor → observed) as the headline, or lead
   with one rail? ADR-0021 says band ≈16–24%, truth nearer the top (omitted minutes are end-of-half,
   same game state); 16.3% is the zero-premium floor. Recommend: headline = band, lead number = observed.
3. **λ source** — central `pooled_all`; report `pooled_pre`/`pooled_post`/`regime_matched` as
   sensitivities (D3: no first-principles pre/post λ difference; data agrees within Poisson noise).
4. **Conditioning** — central `overall`; `tied_nontied` as a sensitivity (D2: within noise).
5. **O3 gross-up** — confirm it ships as a clearly-labeled sensitivity (raises to ~31.6%), not the
   central, even though it's faithful (no agenda; ADR-0021 #3).
6. **Outcome-flip** — confirm reported alongside as the stricter cut (~12.2%), headline stays scorelines.

## Fill the ADR-XXXX HEADLINE template (and renumber it, e.g. ADR-0024)
In `docs/decisions.md` replace the paused `ADR-XXXX — HEADLINE NUMBER` block with the locked values:
X% + 95% CI, window, the chosen central knob_set, the band rails, the silent/conditioning/source
sensitivities, the O3 and outcome-flip secondaries. Carry the **caveats** verbatim from the template:
irreducible silent band (ADR-0017); 1H counterfactual independence assumption (O1); thin PRE counts;
Nate validates WC2018 only. ADD: board_announced under-allocation Δ (A.1) is still DEFERRED and is
DESCRIPTIVE only — never in X% (`prompts/scrape_board_announced.md`).

## Gate + checkpoint
- The locked ADR states a BAND + CI + sensitivity table, not a bare point (CLAUDE.md §1).
- `pytest` stays green (no code changes expected; if you re-run s08, summary is unchanged).
- Update `next_session.md`: headline LOCKED; the only optional remaining unit is the deferred
  board_announced scrape (descriptive). The modeling pipeline is DONE.
- STOP.
