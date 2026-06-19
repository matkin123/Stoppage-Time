# IMPL-8 — Omitted-time productivity decay (Method A) + gross-up central flip

**Self-contained session (CLAUDE.md §6). One unit: rebuild s08's productivity term as a
per-minute decay, then stop at the grid + figure for the human checkpoint. Do NOT lock X% here —
the lock is its own session (`prompts/lock_headline.md`).**

## Why
Reviewer-preempt: counterfactual (unobserved) added minutes should NOT inherit the full end-game
urgency premium. Observed 2H-stoppage λ (0.0816) is ~1.91× the regular open-play λ (0.0427) because
it is measured over short, late, high-urgency windows. The more time we hypothetically add, the less
productive teams should be — so λ applied to omitted 2H minutes must **decay from the observed
stoppage rate toward the open-play floor** as the omitted window grows. This *replaces* the binary
`productivity_premium` rails (`observed` / `open_play`), which are exactly the two limits of the
decay. Decided with the user 2026-06-19; see the prototype figure `figures/requested/productivity_decay.png`.

## Model (Method A — exponential decay, half-life parametrized)
Per omitted **2H** minute t (clock minutes into the counterfactual added time):

    lambda(t) = floor + (obs - floor) * 0.5 ** (t / h)

- `obs`   = the **2H-stoppage** goal rate (the current `observed` 2H λ cell). START.
- `floor` = the cohort's **regular open-play** goal rate (the existing `__regular__` cell). FLOOR.
- `h`     = half-life in minutes (the swept band parameter). `h -> inf` reproduces `observed`
            (no decay); `h -> 0` reproduces `open_play` (floor everywhere). The two existing rails
            ARE the endpoints — assert this (see gate).

A match with `T` omitted 2H **clock** minutes gets the closed-form **average** rate over its window:

    avg_lambda(T, h) = floor + (obs - floor) * (1 - exp(-k*T)) / (k*T),   k = ln(2)/h

Then `mu_2H(match) = avg_lambda(T_match, h) * olive_2H(match)`, where `olive_2H` is the existing
omitted-LIVE 2H minutes (clock × live-factor, gross-up still applied to the live-factor as today).

**Decay horizon = the GROSSED-UP clock (user decision 2026-06-19), written so it tracks whatever
gross-up is active:**

    T_match = olive_2H(match) / live_share_2H(match)

This is exactly the grossed clock because `olive = grossed_clock × live_share`, so it self-consistently
gives: gross-up `off` → raw omitted clock `max(0, tsw-plw)`; **`on` (default) → one-pass grossed
clock `max(0,tsw-plw)×(2-live_share)`**; geometric → `max(0,tsw-plw)/live_share`. Horizon and
live-minutes can never drift. Guard `live_share > 0`. In the bootstrap, `olive_2H` already varies with
the silent estimator-error draw, so `T_match = ol2/live_share` must be recomputed per iteration too.

**1H is UNCHANGED.** Per the user, added 1H minutes keep the current productivity assumption
(observed 1H-stoppage λ). Decay applies to the 2H window only. `mu_1H` is computed exactly as now.

## Where it goes (`src/s08_counterfactual.py`)
- The decay replaces the per-window constant 2H λ. Today the 2H cell rate `lam["2H"]` is a constant
  applied to all matches; make the 2H rate **per-match** = `avg_lambda(T_match, h)` using the drawn
  `obs` (2H-stoppage cell) and `floor` (`__regular__` cohort cell).
- **Bootstrap (do this right — both endpoints carry sampling uncertainty):** the decay is a
  deterministic transform of TWO drawn rates. Today each match indexes ONE λ cell per window; for the
  2H window you now need BOTH the 2H-stoppage cell AND the `__regular__` floor cell drawn per
  iteration, then combine via `avg_lambda`. Add a second per-match cell index for the floor so
  `cell_ce` / `cellidx` carry both; the Gamma draws already exist (`__regular__` is a cell). This
  keeps the CI honest: it now reflects sampling error in BOTH the 73-goal 2H-stoppage rate and the
  675-goal open-play rate, transformed through the decay.
- Gross-up (ADR-0021 #3) scales `olive` (live minutes) via the live-factor; decay scales λ. They
  compose multiplicatively — leave the gross-up code as is. The decay **horizon tracks the gross-up**:
  `T_match = olive_2H / live_share_2H` (the grossed clock under whatever gross-up knob is active). The
  DEFAULT/central model is gross-up `on` (one-pass), so the central horizon is the one-pass grossed
  clock. Do NOT use the pre-gross-up clock.

## Knob change (`config/params.yaml`)
Replace `productivity_premium_knobs: [observed, open_play]` with a decay-half-life sweep, e.g.:

    productivity_decay_halflife_min:
      - inf      # endpoint, regression-test only: = old observed rail (no decay)
      - 8.0      # REPORTED BAND CEILING (least decay -> highest X%)
      - 4.0      # CENTRAL (point estimate)
      - 2.0      # REPORTED BAND FLOOR (most decay -> lowest X%)
      - 0.0      # endpoint, regression-test only: = old open_play floor (instant decay)

`inf`/`0.0` are kept ONLY so the grid still BACKS OUT the old two rails exactly (regression continuity
+ the endpoint gate). **Reported uncertainty band = half-life [2.0, 8.0] min; central = 4.0 min**
(user decision 2026-06-19). The knob_set string gains the half-life in place of the premium rail.

## Also fold in (small, same s08 rebuild — confirmed with user 2026-06-19)
1. **Gross-up central = ON.** The directive's own logic says stoppage time must compensate for the
   stoppages within it, so ON is the defensible central (OFF leaves in-stoppage time-wasting
   uncompensated). Flip the central knob_set to `...|on`. Also REPORT (need not be a full knob) the
   **geometric fixed-point ceiling**: full stoppage-within-stoppage compensation is `1/(1-r)=1/live_share`,
   which makes `omitted_live = omitted_clock` exactly — the true upper rail above single-pass ON.
2. **Silent treatment is a POINT, not a band, in the HEADLINE.** `silent_none` and `silent_all` are
   KNOWN-WRONG (the model is calibrated to Nate at `silent_marked`); keep them in the grid as bounds
   but the headline reports `silent_marked` as the point estimate and bands only over the legitimate
   knobs (λ-source, decay half-life, gross-up). With silent fixed, assumption-vs-sampling uncertainty
   drops from ~3.0× to ~1.6× (computed 2026-06-19) — name this in the lock.

## Gate (session done only when green)
- **Endpoint regression:** at `h=inf` the grid reproduces the old `observed` X% (1H+2H 23.8% /
  2H_only 17.1%) and at `h=0.0` the old `open_play` floor (16.3% / 9.7%), byte-close. Assert in a
  new pytest (`test_s08_decay_endpoints`).
- **Monotonicity:** X% is monotone decreasing in shorter half-life (more decay → lower X%) for the
  central spec. Assert.
- s07 unchanged; s08 grid regenerated; s09 figures + ledger updated; all existing pytest green.
- **Regenerate the decay figure** (per-marginal-minute λ + effective-average-vs-omitted-minutes,
  with the realistic omitted-2H histogram), marking central h=4 and the band edges h=2 / h=8. The
  prototype is `figures/requested/productivity_decay.png` — promote it into s09 as a permanent figure.
- **HUMAN CHECKPOINT:** bring the regenerated grid + figure to the user. Half-life is already decided
  (central 4, band [2,8]); confirm the resulting central X% + band visually, and that gross-up ON +
  the silent-point framing read correctly. Do NOT lock X% — that is the next session.

## Checkpoint / handoff
- ADR in `docs/decisions.md`: the decay model (Method A, 2H-only, rails = 2H-stoppage→open-play,
  1H unchanged), the gross-up central flip + geometric ceiling, the silent-point framing, and the
  selected central `h`.
- Update `docs/numbers_ledger.md`: new central X% under decay + CI; the decay endpoints back out the
  old rails; the assumption-vs-sampling ratio (~1.6× with silent fixed).
- Update `next_session.md`: IMPL-8 DONE → point to the lock (`prompts/lock_headline.md`).
- Do NOT chain into the lock. STOP.
