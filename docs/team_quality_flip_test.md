# Team-quality / Elo test of the outcome-flip team-split (ADR-0034)

Settles the reviewer objection that the team leading by one at 90' is the better team, so the trailing side should score **fewer** than half the omitted-window goals (`p_trail < 0.5`) and P(flip) should fall well below half of P(scoreline). Standalone check: READS production parquet + cached World Football Elo (eloratings.net); no locked artifact touched. The **headline scoreline 23.3% is structurally immune** -- it rides total `mu` and never attributes the scorer; only the flip's `lead_by_1` branch (`p_change(mu/2)`) uses the split.

## Analysis A -- exact state-decomposition of the locked 12.1% flip

Faithfulness gate: rebuilding the flip from per-match `mu = -ln(1 - p_change)` on the central knob reproduces the locked `pct_outcome_flip` = **0.12071** (|delta| < 1e-6). State census of the 314 eligible matches: tied **98**, lead_by_1 **121**, lead_by_2plus **95**.

| flip component | state | rule | flip mass (pp) | share of flip |
|---|---|---|---|---|
| tied | 98 | `1-exp(-mu)` (any goal flips; **p_trail-immune**) | 7.46 | 0.618 |
| lead_by_1 | 121 | `1-exp(-mu/2)` (**p_trail-sensitive**) | 4.61 | 0.382 |
| lead_by_2plus | 95 | 0 (unflippable) | 0.00 | 0.000 |
| **total flip** | 314 | | **12.07** | 1.000 |

- **Only 38.2% of the flip is `p_trail`-sensitive.** The tied bucket contributes 7.46 pp regardless of any split; the whole objection can act on at most the 4.61 pp lead_by_1 mass.
- **Tied-only floor:** even at `p_trail = 0` (leader scores *every* lead_by_1 omitted goal -- absurd), the flip cannot fall below **7.46%** = **31.9%** of the 23.3% scoreline (the 98/314 = 31.2% tied share).
- **`flip / scoreline` = 0.517** is a state-census identity, not a `p_trail` artifact: the 95 unflippable lead_by_2plus matches do more to hold the ratio near half than `p_trail` ever could.

## Analysis B -- Elo-conditioned p_trail

**B1 sourcing.** Pre-match World Football Elo (eloratings.net) for both teams in all 314 matches; joined by team + date and integrity-checked (final score set matches StatsBomb for all 314). **B2 signed gap** per lead_by_1 match: `Delta = Elo(trailing@90') - Elo(leading@90')` (Delta < 0 = leader stronger = the objection's case).

The lead_by_1 pool is only modestly skewed toward stronger leaders: mean `Delta = -38` Elo (median -49), leader stronger in **60%** of matches -- not the blowout the objection imagines, because *exactly-1* and *still-live-at-90* both select against mismatches.

**B3 explanatory power + crossover.** Logit of `trailing_scored` on the Elo gap (per 100 Elo). Fit on the powered anchor (all goals in a 1-goal game state) and on the added-time cuts:

| cut | n | p_trail | beta(Delta/100) | se | p | pseudo-R2 |
|---|---|---|---|---|---|---|
| anchor (all 1-goal-game goals) | 287 | 0.509 | +0.369 | 0.071 | 0.000 | 0.0780 |
| 2H stoppage | 31 | 0.548 | +0.052 | 0.166 | 0.756 | 0.0023 |
| 2H after 75' | 91 | 0.473 | +0.234 | 0.114 | 0.040 | 0.0357 |

Full model (anchor, n=287): `logit(trailing_scored) ~ Delta + Delta^2 + minute + C(tournament)` -> **beta_Delta = +0.331** per 100 Elo (se 0.079, p = 0.0000), beta_Delta^2 = -0.011 (p = 0.726), beta_minute = -0.0028 (p = 0.588), pseudo-R2 = 0.087.

- Quality **does** have explanatory power and in the crossover direction the user predicted: `p_trail` **rises** with `Delta` (stronger trailing team => more likely to equalize). The crossover `Delta*` (predicted `p_trail = 0.5`) sits at **-146 Elo** -- i.e. below `Delta = 0`, because the trailing team's late chase lifts `p_trail` above half at equal quality.
- But the added-time cut (2H stoppage, n=31) is under-powered (p = 0.76); the slope is borrowed from the large within-tournament anchor rather than an external competition (no era/mix caveat).

**B4 covariance -- the one channel the pooled mean misses.** Across the 121 lead_by_1 matches, `corr(Delta, mu_omitted) = +0.144` (essentially zero). The mu-weighted mean `Delta` = **-20** Elo vs unweighted **-38** Elo -- weighting by omitted-goal mass makes the gap *less* negative, i.e. nudges `p_trail` **up**, the opposite of the objection's feared `p_trail x mu` covariance.

**B5 re-weight and compare.** Swap the flat `p_trail = 0.5` in the lead_by_1 branch for the per-match fitted `p_trail(Delta)` and recompute the aggregate flip. The abs-level variant uses the fitted (chase-inclusive, observed-scorer) level; the re-centered variants pin the mean to an observed base rate and isolate the dispersion+covariance channel (guardrail: Elo tests residual signal, it does not SET the base rate).

| p_trail construction | flip X% | delta vs locked (pp) |
|---|---|---|
| flat 0.50 (locked) | 12.07% | +0.00 |
| fitted p_trail(Delta), abs level | 12.28% | +0.21 |
| fitted, re-centered to 0.50 | 12.11% | +0.04 |
| fitted, re-centered to 0.509 (obs all) | 12.18% | +0.11 |
| fitted, re-centered to 0.548 (obs 2H stoppage) | 12.51% | +0.44 |
| flat 0.509 (observed, all) | 12.15% | +0.08 |
| flat 0.548 (observed, 2H stoppage) | 12.47% | +0.40 |
| flat 0.40 (leverage floor) | 11.21% | -0.86 |
| flat 0.60 (leverage ceiling) | 12.90% | +0.83 |

Every Elo-informed re-weight lands within **[12.11%, 12.51%]** (the flat 0.40/0.60 rows are the mechanical leverage bounds, not Elo-implied) and the largest move of an Elo-conditioned variant is **0.44 pp** -- inside the locked flip CI [10.4%, 14.2%] and below the 0.5 pp threshold that would trigger an s08 sensitivity row.

## Conclusion

The objection's premise is partly real (leader stronger in 60% of lead_by_1 matches; quality is a significant predictor) but its conclusion does not follow. Three facts defuse it: (1) only 38% of the flip is even `p_trail`-sensitive and the tied floor holds it at 32% of scoreline; (2) the *realized* `p_trail` -- observed scorers, chase included -- is **at/above 0.5** (0.509 all / 0.548 2H stoppage), so the net late-game effect runs opposite to the objection; (3) the `Delta x mu` covariance is ~0 and mu-weighting nudges `p_trail` up. **Keep `p_trail = 0.5`; the 50/50 split is non-load-bearing** (the flip's ADR-0039 value 12.1% comes from the owed re-estimate, not this split -- the split conclusion is unchanged by the re-lock).

_Reproduce: `python -m src.fetch_elo` then `python -m src.team_quality_flip`. Faithfulness gate: flip(0.5) reproduces locked 0.12071 to <1e-6._
