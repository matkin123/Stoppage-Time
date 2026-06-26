# Outcome-flip 50/50 team-split: empirical validation + leverage

Standalone check of the one assumption in the **outcome-flip** secondary metric (s08 `outcome_flip`, locked 13.0% / ADR-0031): when a team leads by one at 90', the flip credits the trailing team with a fixed **half** of the total omitted-time goals (`P = 1 - exp(-mu * p_trail)`, `p_trail = 0.5`). The **headline scoreline** metric (24.8%) does NOT use this split -- it asks '>=1 extra goal by either team' and rides the total `mu`, so nothing below can move it. READS production parquet; no locked artifact touched.

## 1. What the data says (p_trail measured from event goals)

Population = goals scored while one side led by **exactly one** before the goal. `p_trail` = fraction scored by the **trailing** team (the flip-relevant equalizer). Pre-goal margin is reconstructed by subtracting each goal from the post-goal score. Intervals are Jeffreys 95%.

| population (lead-by-1 game-state) | n | trailing | leading | p_trail | 95% CI |
|---|---|---|---|---|---|
| 2H stoppage-time goals (most relevant) | 31 | 17 | 14 | 0.548 | [0.375, 0.713] |
| 1H stoppage-time goals | 10 | 5 | 5 | 0.500 | [0.224, 0.776] |
| all stoppage-time goals (1H+2H) | 41 | 22 | 19 | 0.537 | [0.386, 0.682] |
| 2H stoppage OR after 80:00 | 70 | 33 | 37 | 0.471 | [0.358, 0.588] |
| all 2H goals after 75:00 | 91 | 43 | 48 | 0.473 | [0.372, 0.575] |
| ALL goals (next-goal-in-1-goal-game anchor) | 287 | 146 | 141 | 0.509 | [0.451, 0.566] |

By era (all stoppage goals):

| era | n | trailing | leading | p_trail | 95% CI |
|---|---|---|---|---|---|
| PRE | 12 | 7 | 5 | 0.583 | [0.312, 0.820] |
| POST | 29 | 15 | 14 | 0.517 | [0.341, 0.690] |

Every cut straddles 0.50. The directly-relevant added-time window (2H stoppage) leans slightly toward the trailing team (**0.548**, n=31, CI contains 0.5); it reverses toward the leader in the broader late window (~0.47 after 75-80', the counter-attack channel); and the large-sample anchor sits at **0.509** (n=287, tight CI). The trailing-desperation and leading-counter channels roughly cancel -- **0.50 is well-calibrated**, not a convenient guess.

## 2. How load-bearing is it (flip re-run over p_trail)

Per-match `mu` recovered from the locked grid (`mu = -ln(1 - p_change)`, central `silent_marked|overall|pooled_all|hl=4.0|on`, window 1H+2H); the flip is re-evaluated at each `p_trail`. The split touches ONLY the lead_by_1 matches (state@90: lead_by_1 121, tied 98, lead_by_2plus 95); tied matches flip on any goal regardless of `p_trail`.

| p_trail | source | flip X% |
|---|---|---|
| 0.400 |  | 12.04% |
| 0.471 | late-window (>75') | 12.71% |
| **0.500** | **model (locked)** | **12.98%** |
| 0.537 |  | 13.31% |
| 0.548 | 2H stoppage (measured) | 13.41% |
| 0.600 |  | 13.87% |

lead_by_1 is the largest state bucket, so the split touches a big share of matches -- but because the measured value is so near 0.5, leverage is small: the most-relevant point estimate (0.548) moves the flip just **+0.4 pp to ~13.4%**, and the full p_trail in [0.40, 0.60] span is only 12.0%-13.9%. The headline scoreline (24.8%) is unaffected at every value.

## 3. Conclusion (for the methods record / a pre-empt)

The 50/50 split is **empirically supported and non-load-bearing**. Keep 0.5 as the central -- it now traces to a measurement (n=31 in the cleanest cut, CI containing 0.5) plus this p-sweep band, the same script+table+documented-assumption standard every other knob gets (CLAUDE.md sec 1), rather than an unexamined constant. The honest caveat is sample size: n=31 in the cleanest cut cannot statistically distinguish 0.50 from 0.55, so 0.5 is both defensible and unresolvable to finer precision. If a single best-supported value is preferred over the round number, the added-time-specific 0.548 nudges the flip from 13.0% to ~13.4% -- inside the CI either way.

_Reproduce: `python -m src.flip_split_sensitivity`. Harness check: p_trail=0.5 reproduces the locked pct_outcome_flip (0.12976) to <1e-6._
