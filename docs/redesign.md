# Redesign — first-principles remodel of the headline counterfactual (2026-06-17)

**Status: SCOPED, not yet implemented. X% lock is PAUSED** — do not lock a number until this
remodel is built and re-validated. This supersedes the **s08 headline design** in
ADR-0008/0016/0017 *for the metric only*; the upstream estimator (s05, r=0.825), `bip.py`/s03
(r=0.943), the board=time-played measurement (ADR-0011), and the Nate harness stay **FROZEN**.

This doc is the single reference. The turnkey session prompts execute pieces of it:
`prompts/impl_6_remodel.md` (core remodel), `prompts/research_board.md` + `prompts/research_cooling.md`
(deferred research), `prompts/impl_7_board_cooling.md` (distortion add-ons). Read `CLAUDE.md §6`:
one self-contained unit per session.

## Why we reopened the model
The IMPL-4 grid showed X% swinging 3%→12% across the silent knob; IMPL-5 tightened the estimator
(r 0.768→0.825) but the marked↔all band did not narrow (ADR-0017). Before locking, the user reopened
the model at first principles. Two classes of change: (1) the metric and lambda were over-engineered
for the question, and (2) the model is missing real stoppage (the 1H window, time-wasting within
stoppage, cooling breaks) and conflates "board" with "time played".

## DECIDED (with the data that backs each)

### D1 — Metric: change = any extra goal (drop W/D/L result-flip)
A match "ends differently" iff **≥1 additional goal** would have been scored in the omitted stoppage
time. A 3-1 → 3-2 counts. Replace the 10k-sim W/D/L Monte Carlo with the closed form, per match:

    mu = sum_h  lambda_h * omitted_live_h          (h over stoppage windows {1H, 2H})
    P(change) = 1 - exp(-mu)
    X% = mean over matches of P(change)

Rationale: the claim is about whether properly-played stoppage would have produced more goals, not
who wins. The closed form is exact, deterministic, and removes the sim entirely.

### D2 — Drop team_role; keep tied_nontied as a sensitivity only; default OVERALL
team_role (leading/trailing/level) existed ONLY to decide WHICH team scores, which mattered for W/D/L
flips. Under D1 only the TOTAL two-team rate enters mu, so team_role is dropped. Data (2H-stoppage
lambda, goals per team-live-minute):

    PRE : all .0493 | tied .0716 (n10) | nontied .0403 (n14) | lead .0345 (n6)  | trail .0460 (n8)
    POST: all .0432 | tied .0391 (n14) | nontied .0450 (n35) | lead .0463 (n18) | trail .0437 (n17)

Cells are within Poisson noise (6-18 goals each -> SE 25-40%). tied vs nontied is not robustly
different (PRE tied is HIGHER, contradicting "non-tied scores faster"; POST ~ equal; pooled tied
.0482 vs nontied .0436). Conditioning partitions a 73-goal sample into noisier sub-cells without
moving the aggregate -> that is WHY it "barely matters." Default to overall; keep tied_nontied as a
reported sensitivity.

### D3 — Pool PRE+POST for the central lambda; pre/post is a board/composition story, not a lambda driver
The 2022 directive (Collina/IFAB, debut WC2022) told officials to add the REAL time lost for ALL
stoppages (celebrations, subs, injuries, red cards, penalties, VAR, time-wasting) — not only
celebrations. It changes how much goes on the BOARD, not how the game is played per live minute.
No first-principles reason goals-per-live-minute should differ pre/post, and the data agrees
(.0493 vs .0432, within noise). pre/post also conflates tournament composition (PRE = WC2018+Euro2020
vs four different POST tournaments). -> pool for the central lambda; report pre/post as a sensitivity;
the directive's real effect lives in the bigger boards / larger omitted minutes.

### D4 — Silent central = silent_marked + propagated estimator error; none/all are guardrails only
(unchanged from the IMPL-4 settle) Calibrate the headline to silent_marked with the r=0.825 /
MAE-2.44 estimator error propagated into the CI. silent_none / silent_all are definitional rails kept
ONLY as monotonicity guardrails — never calibrate the headline to them ("garbage estimates").

## TARGET MODEL (precise spec)
Per match, per stoppage window h in {1H, 2H}:

    true_stoppage_h       = s05 estimator (should-have-added), period-h        [FROZEN, r=0.825]
    played_in_stoppage_h  = period_end_s - 2700                                [RENAME of "board"]
    omitted_h             = max(0, true_stoppage_h - played_in_stoppage_h)     [clock min never played]
    live_share_h          = ball-in-play share within stoppage window h        [2H~0.49; ADD 1H]
    omitted_live_h        = omitted_h * live_share_h
    lambda_h              = pooled (PRE+POST), overall, two-team goals/live-min in window h  [ADD 1H]
    mu                    = sum_h lambda_h * omitted_live_h
    P(change)             = 1 - exp(-mu)
    X%                    = mean over matches of P(change)

CI: keep the existing s08 machinery — bootstrap lambda (Jeffreys Gamma) + a silent_marked
estimator-error draw (D4) — but the central metric is now the closed form, not the W/D/L sim.

Variable rename (DC2): today's "board" is time PLAYED in stoppage, not the announced board.
Rename to `played_in_stoppage` everywhere (s06a output, s08 input, s09 ledger, ADR prose). Introduce
`board_announced` (the 4th-official number) as a SEPARATE column. **R1 RESOLVED (ADR-0020):** the
announced board is sourceable FREE for ALL SIX tournaments from SofaScore's incidents API
(`injuryTime.length` per half) — no longer NULL. See `prompts/research_board_findings.md`. Wire in IMPL-7.

## OPEN design questions — RESOLVED (O1/O2 in IMPL-6 / ADR-0019; O3 in ADR-0021)
- **O1 — 1H stoppage in the counterfactual.** Including 1H under D1 is clean as "≥1 extra goal
  anywhere in omitted stoppage" (mu = mu_1H + mu_2H). Caveat: a 1H extra goal would in reality alter
  the rest of the match; under the count-extra-goals framing we treat omitted stoppage as bonus
  increments and do NOT propagate game state. Confirm this framing, or keep the headline 2H-only and
  report 1H as a measurement.
- **O2 — X% definition.** Expected share = mean(1 - exp(-mu)) [recommended] vs deterministic count of
  matches with mu >= 1. Confirm.
- **O3 — "time-wasting within stoppage" distortion.** Dead time during played stoppage =
  played - played*live_share (computable NOW, no new data). Decide: all non-live time, or only
  s05-identifiable dead time inside the stoppage window.
  → **RESOLVED (ADR-0021):** implement the gross-up faithfully (add the in-stoppage time-wasting
  back onto omitted CLOCK, then apply productivity to the live portion), even though it RAISES X%.

## ADDENDUM — RESOLVED post-IMPL-6 (2026-06-18, ADR-0021)
Two decisions beyond O1-O3 that IMPL-7 must build and the lock must report:

- **Metric framing (extends D1).** Headline = "different SCORELINE" (≥1 extra goal; central 23.8%,
  1H+2H). ALSO report the stricter "different OUTCOME" (winner/draw flips) cut, ≈12.7% illustrative
  (only tied + lead-by-1 matches can flip; per-team half-rate split). Report both; headline =
  scorelines.
- **Productivity-premium BAND (committed sensitivity).** The omitted minutes need not carry the full
  observed end-game premium (2H-stoppage λ=0.0816 ≈ 1.4× match pace per clock-min vs open-play
  0.0427). Ship a band over the λ applied to omitted time: UPPER = stoppage λ (today) 1H+2H **23.8%**
  / 2H 17.1%; LOWER = open-play λ on omitted minutes 1H+2H **16.3%** / 2H 9.7%. Band ≈ 16-24%, truth
  nearer the top. KEY: `live_share` cancels in mu (scales λ up and omitted_live down equally) →
  mu ≈ goals-per-CLOCK-min × omitted-CLOCK-min; the band is the λ choice, NOT a live-share knob.
- **First-goal hazard — do NOT overengineer.** P(≥1)=1−P(0) only uses the pre-first-goal hazard, so
  "ignore play after the first goal" is already baked in. Observed λ is mildly high (8/73 2H goals are
  2nd+ in-window); the open-play floor already brackets it. Optional only: re-fit λ pre-first-goal.

## DATA-CONSISTENCY fixes (do in IMPL-6)
- **DC1 — lambda exposure denominator != ledger live-minutes.** `build_lambda_cells` sums
  live_share["live_seconds"]/60 keyed per match (2H total ~811 team-min) but the ledger/productivity
  2H-stoppage live-min = 894.5; matches missing from the live_share table fall to 0 exposure while
  their goals still count -> lambda slightly inflated. Fix: ONE canonical per-match
  live-minutes-in-stoppage table feeding BOTH productivity and lambda; verify they match.
- **DC2 — rename board -> played_in_stoppage** (see above).
- **DC3 — s09 figure fix.** `fig_productivity_by_bucket` (f01) currently shows a minute-120 spike
  from extra-time/penalty goals (periods 3-5). Exclude or clearly label ET so the figure stops
  implying penalties contaminate regulation scoring. (The counterfactual is unaffected — it uses the
  regulation 2H-stoppage cell only.)

## RESEARCH (separate sessions) — needed only for the DISTORTION add-ons, not the core remodel
- **R1 (`prompts/research_board.md`)** — **RESOLVED (ADR-0020, 2026-06-18): YES, free for all six.**
  Source = SofaScore incidents API (`injuryTime.length` per half); findings in
  `prompts/research_board_findings.md`. Enables under-allocation Δ = true_stoppage - board_announced
  as a FULL-SAMPLE distortion (not WC2022-only). Wire in IMPL-7.
- **R2 (`prompts/research_cooling.md`)** — **RESOLVED + DE-SCOPED (ADR-0022, 2026-06-18).** Hypothesis
  (add ~3 min pure stoppage; improves match-level r vs Nate) was tested read-only and REJECTED: the s05
  estimator already credits ~73% of a break via `restart_excess`, WC2018 (the only Nate-validated set)
  barely had breaks, and a naive add DEGRADES r while the careful add is within noise. Cooling detection
  is DROPPED from IMPL-7. Findings: `prompts/research_cooling_findings.md`.

## FROZEN — do not reopen
`bip.py` / s03 calibration (r=0.943); the s05 true-stoppage estimator + its constants (r=0.825,
MAE 2.44, residual 24.2s, restart allowances) — ADR-0014/0015/0016/0017; the board=time-played
MEASUREMENT (ADR-0011) — it is only RENAMED, the number is unchanged; the Nate harness
(`src/lib/nate.py`). Nate validates WC2018 only; POST stays validated indirectly.

## Sequence
1. **IMPL-6** (`prompts/impl_6_remodel.md`) — core remodel: D1-D4, target model, O1-O3, DC1-DC3.
   No research needed. Re-validate, re-run s07->s08->s09, bring the new grid to the user. Do NOT lock.
2. **R1 + R2** research sessions (independent; run anytime; deferred to save compute).
3. **IMPL-7** (`prompts/impl_7_board_cooling.md`) — wire board_announced under-allocation (R1/ADR-0020)
   + Part C band-building (ADR-0021). Cooling-break stoppage (Part B) is DE-SCOPED (ADR-0022).
4. **LOCK** X% + CI + band with the user (the paused ADR-XXXX headline template).
