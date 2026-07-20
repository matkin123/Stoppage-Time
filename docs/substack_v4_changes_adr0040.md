# substack_post_v4.md — before→after changelog for ADR-0040 (2026-07-20)

Minimal number-only edits to the live Substack post. All changes are pure number replacements;
no prose, structure, or argument changes. Hand-port by searching for the old value and replacing
with the new.

## Headline (opening paragraph)
- `**23.3%**` → `**21.4%**`
- `[95% CI: 20.1%, 27.3%]` → `[95% CI: 18.2%, 25.2%]`
- `**12.1%**` → `**10.8%**`
- `[10.4%, 14.2%]` → `[9.1%, 12.8%]`

## Step 1 calibration (Methodology section)
- `r = 0.870, average error 1.67 minutes` → `r = 0.836, average error 1.54 minutes`
- `17.0 minutes` (owed mean) → `16.2 minutes`
- `8.2 minutes` (omitted mean) → `7.3 minutes`
- `positive in 95% of matches` → `positive in 98% of matches`

## Objection 1 — decay band
- `22.0% (fastest decay) to 24.5% (slowest)` → `20.2% (fastest decay) to 22.4% (slowest)`
- `around the 23.3% headline` → `around the 21.4% headline`

## Objection 2 — score-at-90 conditioning
- `from 23.3% to 23.1%` → `from 21.4% to 21.0%`

## Objection 3 — stage-source robustness
- `24.4%` (group stage) → `22.5%`
- `20.1%` (knockouts) → `18.2%`
- `central at 23.3%` → `central at 21.4%`

## Objection 4 — flip split sweep
- `between 11.2% and 12.9%` → `between 10.0% and 11.5%`

## Objection 5 — flip decomposition and Elo bound
- `(12.1%) decomposes into tied matches (7.46%) and lead-by-one matches (4.61%)` →
  `(10.8%) decomposes into tied matches (6.7%) and lead-by-one matches (4.1%)`
- `at most 0.44 points, to between 12.1% and 12.5% — inside the [10.4%, 14.2%] interval` →
  `at most 0.44 points, to between 10.8% and 11.2% — inside the [9.1%, 12.8%] interval`

## Results and sensitivity section
- CI `[20.1%, 27.3%]` → `[18.2%, 25.2%]`; width `7.1 points` → `7.0 points`
- Band `20.2–25.6%` → `19.2–23.7%`; envelope `17.3–27.0%` → `16.3–24.9%`
- `band (5.5 pts) is about the size of` → `band (4.5 pts) is below`
- `CI (7.1 pts)` → `CI (7.0 pts)`; `envelope (9.7 pts)` → `envelope (8.6 pts)`
- `top of the band at 25.6%` → `top of the band at 23.7%`
- `22.5% from the group stage` → `22.5%`; `20.1% from the knockouts` → `18.2%`  ← (already updated above)

## Limitations section
- `12.1% flip splits into 7.46 points ... and 4.61 points` →
  `10.8% flip splits into 6.7 points ... and 4.1 points`
- `moves the result figure by at most 0.4 points` → unchanged (bound still holds)
- `leave the aggregate flip result close to 12%` → `close to 11%`
- `from 12.7 minutes (2018 World Cup) to roughly 21 minutes` →
  `from 13 minutes (2018 World Cup) to roughly 19 minutes`
- `Copa América 2024 (22.9 min) and AFCON 2023 (25.2)` →
  `Copa América 2024 (20.4 min) and AFCON 2023 (21.9)`

## Reflections section
- `1 in 4 scorelines change` → `roughly 1 in 5 scorelines change`
