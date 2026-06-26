# StatsBomb data quality & gap structure, by tournament

_Regenerate with `python -m src.statsbomb_quality` (writes this file and
`data/processed/statsbomb_quality_by_tournament.parquet`). Standalone diagnostic — NOT a
pipeline stage. These are **descriptive metrics of the StatsBomb event feed**, independent
of the headline counterfactual, so they are unaffected by the ADR-0029 Method-2 migration._

This is the reference for "how good is the raw data, and how does it differ across the six
tournaments?" — useful background for the methodology/Substack writeups. All figures are
**per match, regulation halves (P1+P2) only**, to match Opta's 90-minute ball-in-play
convention.

## How the gap threshold works (so the numbers below mean something)

The ball-in-play reconstruction (`s03`, `src/lib/bip.py`) walks consecutive events and labels
each inter-event interval `[last_event, next_event]` dead or live. An interval is **dead** if
**either**:

1. **restart boundary** — the next possession opens with a restart `play_pattern` (throw-in,
   corner, free kick, goal kick, kick-off, keeper); counted dead at any length
   (`min_dead_gap_s = 0`); **or**
2. **silent gap** — `gap ≥ max_live_gap_s` (**20s**), regardless of pattern: the stretch where
   StatsBomb simply stopped logging (injury, VAR, melee, off-camera, slow restart).

**The threshold is a classifier, not a deductible — and crediting is whole-gap, binary.** A 25s
silent gap against a 20s threshold contributes the **full 25s** of dead time, not 5s. Raise the
threshold to 30s and that same gap flips to **fully live** (0s). There is no partial crediting.

**Dead time ≠ stoppage.** `s03` measures *total* dead time; the stoppage estimate (`s05`) is the
*addable* **subset**, built component-by-component, so most dead time is never stoppage:

| Dead-gap type | Credited to stoppage |
|---|---|
| Incident window (goal celebration, sub, card, injury) | the **whole window** (clipped to a max, ∩ measured dead) |
| Routine restart gap | **only the excess over an allowance** — throw-in 20s, goal-kick 30s, corner 45s, FK 60s; kick-off & keeper excluded |
| Silent gap (≥20s, non-restart) | **marked → whole gap; unmarked → nothing** (unmarked silent gaps are a flat ~8.4 min/match non-addable baseline) |
| — | plus a frozen residual constant (24.2s/match) |

## Silent gaps — the threshold-sensitive imperfection

The long no-event stretches the 20s threshold governs. Prevalence and length vary sharply by
tournament; **WC 2018 is the outlier** (16.7 silent gaps/match, ~2×
any other, and 28% of its dead time is silent vs 16–21%
elsewhere — though its gaps are the *shortest*).

| Tournament | Silent gaps/match | Mean len (s) | Median (s) | Silent dead/match | Max gap (s) | Silent % of dead |
|---|---|---|---|---|---|---|
| WC 2018 (PRE) | 16.7 | 42 | 32 | 696s (11.6m) | 259 | 28% |
| Euro 2020 (PRE) | 8.1 | 48 | 35 | 388s (6.5m) | 244 | 16% |
| WC 2022 (POST) | 8.7 | 48 | 35 | 420s (7.0m) | 254 | 16% |
| Euro 2024 (POST) | 8.5 | 47 | 35 | 401s (6.7m) | 345 | 17% |
| Copa 2024 (POST) | 10.5 | 55 | 41 | 574s (9.6m) | 348 | 19% |
| AFCON 2023 (POST) | 12.3 | 53 | 35 | 655s (10.9m) | 415 | 21% |

**PRE vs POST:** PRE (115 matches) 12.9 silent gaps/match, mean 44s,
560s/match (9.3 min). POST (199 matches) 9.9 gaps/match,
mean 51s, 501s/match (8.4 min).

## Restart-boundary dead time — normal-flow stoppages (contrast)

The bulk of dead time, and legitimate ball-out-of-play the rulebook would *not* add back. Far
more uniform across tournaments than silent gaps, which is why the silent slice is the
interesting one.

| Tournament | Restart gaps/match | Restart dead/match |
|---|---|---|
| WC 2018 (PRE) | 78 | 1768s (29.5m) |
| Euro 2020 (PRE) | 92 | 2014s (33.6m) |
| WC 2022 (POST) | 99 | 2204s (36.7m) |
| Euro 2024 (POST) | 89 | 2005s (33.4m) |
| Copa 2024 (POST) | 100 | 2462s (41.0m) |
| AFCON 2023 (POST) | 103 | 2506s (41.8m) |

## StatsBomb logging quality

Direct signals of how thickly each tournament was logged. **AFCON 2023 and Copa 2024 are the
thinnest** (lowest event density, AFCON the most off-camera and the longest silent gaps). **WC
2018 is the only tournament with zero off-camera flags** — that field was not populated in that
era's data, so 2018's silent gaps are invisible to the off-camera signal. The `Injury Stoppage`
event type is populated inconsistently (93.8%–100% of matches), which is why `s05` falls back to
marker-gated silent gaps rather than trusting that event type.

| Tournament | Events/match | Events/min | Off-camera/match | % matches w/ Injury evt |
|---|---|---|---|---|
| WC 2018 (PRE) | 3,476 | 35.8 | 0.0 | 97% |
| Euro 2020 (PRE) | 3,597 | 37.3 | 45.5 | 96% |
| WC 2022 (POST) | 3,579 | 35.4 | 48.9 | 94% |
| Euro 2024 (POST) | 3,571 | 36.8 | 38.9 | 98% |
| Copa 2024 (POST) | 3,101 | 31.5 | 42.5 | 100% |
| AFCON 2023 (POST) | 3,039 | 29.9 | 64.2 | 100% |

> **Only 2 of 6 tournaments have an external truth.** Opta published regulation ball-in-play only
> for WC 2018 (54:50) and WC 2022 (58:04); the 20s threshold is calibrated against those. Euro
> 2020/2024, Copa, and AFCON inherit a threshold tuned on the World Cups.

## Why one global threshold can't fit every tournament

The gaps that **flip** live↔dead as the threshold sweeps 12→30s are the non-restart gaps in
that band. Their per-match density is the local slope of reconstructed BIP w.r.t. the threshold.
**WC 2018 carries 19.3 flip-band gaps/match vs ~9.0 for
the POST tournaments — a 2.14× ratio.** Roughly twice the flip-mass means 2018's
reconstructed ball-in-play responds ~2.1× more steeply to the threshold, so no single
global value sits at every tournament's true point at once — the residual is tournament-specific,
not an offset one knob could remove.

| Tournament | Flip-band gaps/match [12,30s) |
|---|---|
| WC 2018 (PRE) | 19.3 |
| Euro 2020 (PRE) | 7.5 |
| WC 2022 (POST) | 8.3 |
| Euro 2024 (POST) | 8.6 |
| Copa 2024 (POST) | 9.0 |
| AFCON 2023 (POST) | 10.3 |

_Source: `src/statsbomb_quality.py` over `data/interim/events_norm.parquet` (+ `matches.parquet`).
Checkpointed table: `data/processed/statsbomb_quality_by_tournament.parquet`._
