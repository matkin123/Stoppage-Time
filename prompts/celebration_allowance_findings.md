# Findings — goal-celebration over-credit is the dominant per-match error vs Nate (2026-06-25)

**Status: EXPLORATION / EVIDENCE. No code or lock touched.** This file is the evidence behind the
turnkey unit `prompts/impl_celebration_allowance.md`. Re-derive with
`python -m src.celebration_allowance_whatif` (reads production parquet only; writes nothing).

**DECISION (2026-06-25, ADR-0030): apply the allowance to PRE tournaments ONLY** (WC2018, Euro2020).
POST (WC2022+) keeps the full goal→kickoff gap because the 2022 directive instructs referees to add the
FULL celebration — so full-gap is the CORRECT POST model and POST `true_stoppage` stays unchanged. The
evidence below validates on WC2018, which is entirely PRE, so the prize numbers ARE the PRE story.

## The question
The f07 calibration panel (true-stoppage estimator vs Nate Silver `expected`, 32 WC2018 matches)
sits at **r=0.825, MAE 2.44 min** — good, but few matches land on the diagonal; most are a little
high or a little low. Can we identify *signatures* of over- vs under-estimation in the match logs
and narrow the gap? (Narrowing to Nate buys credibility; StatsBomb is the gold-standard source.)

## What the estimator is (so the gap is locatable)
`true_stoppage = lower_bound + silent_marked + residual(24.2s const)`, where
`lower_bound = union(celebration, sub, card, injury, restart_excess) ∩ s03-dead`.
Only `restart_excess` is a Nate-style `max(0, gap−allowance)` threshold (ADR-0017). `celebration`,
`sub`, `card`, `injury` are **full identifiable dead windows** (ADR-0016). So the premise "we adopt
Nate's thresholds, we should match" is only partly true: the threshold logic is applied to four
routine restarts but NOT to the goal-celebration restart.

## Two clean, opposite signatures (32 WC2018, split at ±1.5 min signed error)

| group | n | err | celebration | card | injury | restart_exc | silent_marked | silent_unmarked(dropped) | goals |
|---|---|---|---|---|---|---|---|---|---|
| UNDER | 12 | −2.84 | 0.62 | 1.65 | **0.05** | 1.61 | 2.52 | 8.62 | 1.75 |
| ON    |  9 | −0.19 | 0.99 | 1.64 | 2.11 | 1.92 | 4.21 | 7.89 | 2.33 |
| OVER  | 11 | +3.25 | **3.77** | 3.22 | 2.55 | 1.03 | 4.66 | 8.66 | **3.91** |

(values are per-match means, minutes.)

**OVER = high-scoring / celebration-heavy.** `corr(err, celebration)=+0.72`, `corr(err, goals)=+0.57`
— the two strongest single correlates. An OLS of Nate `expected` on the six components gives implied
"exchange rates" (a coef <1 on a credited term ⇒ it over-credits vs Nate):

```
intercept +4.36 | celebration +0.24 | sub +0.73 | card +0.71 | injury +0.69 | restart_exc +1.60 | silent_marked +0.38   (R²=0.80)
```

Celebration's **0.24** is the standout: each minute we credit as celebration "buys" only ~0.24
Nate-minutes — ~4× over-credit. Concretely, the worst over-shoots are blowouts:
- Portugal–Spain (6 goals): celebration credit **9.11 min** alone; err **+5.25** (Nate 14.13, us 19.38).
- England–Panama (6-1): celebration **7.41 min**; err **+6.38** (Nate 19.02, us 25.39).
- Argentina–Croatia (0-3): celebration **5.61 min**; err **+3.58**.

The whole estimator is ~16% too steep: `estimator = −2.13 + 1.16·nate`, so high matches over- and low
matches under-predict — and celebration is what carries the excess slope (it scales with goals).

**UNDER = genuine stoppage StatsBomb under-logged.** These matches have ~zero logged Injury Stoppage
events (injury 0.05 min) yet Nate credits 10–16 min. The missing time sits in the **unmarked silent
bucket** the marker-gate drops (mean 8.6 min). Poster child **Sweden–S.Korea**: Nate 14.97, us 9.11,
err −5.86, unmarked bucket **14.57 min** — that match had the tournament's first VAR-awarded penalty;
VAR checks / long treatments make dead gaps whose lead edge carries no StatsBomb out-of-play marker.

So the user's hunch ("more ambiguous gaps in one set of matches?") is correct and **asymmetric**:
UNDER hides real stoppage in dropped *unmarked* gaps; OVER inflates *celebration* (and has longer
marked gaps too — mean 54s vs 39s in ON). They roughly cancel in the mean (the residual is calibrated
to Nate), so they surface as scatter, not bias.

## Why celebration is the wrong full-gap quantity (the structural root)
The full goal→kickoff gap IS 100% dead time — that's the **BIP / total-dead** quantity (s03 correctly
counts it). But the estimator's target is **addable stoppage** = time lost *beyond a normal restart*.
Every other restart already credits only the excess over an allowance (throw-in 20s … free-kick 60s,
ADR-0017). `From Kick Off` was *deliberately excluded* from that ladder — but only to avoid
double-counting the celebration component, which then kept crediting the full gap. Net effect: the
goal-celebration is the one restart credited on the BIP axis instead of the addable axis. This is
exactly the BIP-vs-addable distinction CLAUDE.md draws; celebration is on the wrong side of it.

## The prize — a celebration allowance (faithful WC2018 re-validation)
Recompute the lower bound changing ONLY the celebration rule to `max(0, gap − allowance)` (the excess
tail `[goal+allowance, kickoff]`), re-fitting the residual each row so the mean stays anchored to Nate
13.16 (apples-to-apples). `allowance=0` reproduces production r=0.825/MAE 2.44 exactly ⇒ harness faithful.

| celeb allowance | r | MAE (min) | signed-err sd |
|---|---|---|---|
| **0s (current)** | 0.825 | 2.44 | 2.84 |
| 30s | 0.857 | 2.08 | 2.44 |
| 45s | 0.869 | 1.92 | 2.29 |
| **60s** | **0.875** | **1.77** | 2.18 |
| 90s | 0.873 | 1.68 | 2.14 |
| 120s | 0.872 | 1.67 | 2.12 |

Improvement plateaus at ~60–90s (not knife-edge). **60s is the recommended central**: round, matches
the existing free-kick allowance ("~a minute per goal, credit the excess"), and tops the r curve.
Prize: **r 0.825→0.875, MAE 2.44→1.77 (~28%), err sd 2.84→2.18.**

## Honest negative — don't chase the UNDER side bluntly
Tested: best celebration allowance (45s) + credit a fraction `f` of the unmarked bucket back for
low-injury matches (n_injury≤2). It makes things **worse**:

```
f=0.00 → r=0.869   f=0.15 → r=0.842   f=0.25 → r=0.816   f=0.35 → r=0.784
```

The unmarked bucket is mostly genuinely-live sparse logging with some real stoppage mixed in; a flat
fraction adds noise, not signal. Recovering it *precisely* needs VAR-check detection or external
Wyscout interruption events (the direction ADR-0015 already declined). Not worth it vs the
celebration fix. **The celebration allowance captures essentially all the cheaply-available gain.**

## Caveats (carry into any adoption)
- **Apply to PRE tournaments (WC2018, Euro2020) ONLY (ADR-0030).** The 2022 directive adds the FULL
  goal celebration, so POST (WC2022, Euro2024, Copa2024, AFCON2023) is correct on the full gap and stays
  byte-identical to current production. The allowance ties to the exact directive boundary the study's
  PRE/POST split is built on — that is what makes it defensible, not a hedge.
- Validated on **WC2018 only** (Nate's coverage), which is entirely PRE — so the allowance is fit AND
  validated precisely where it applies. Euro2020 is PRE-but-unvalidated (same "fit-on-2018, apply-to-era"
  basis as every other frozen constant). POST is unchanged, so needs no new validation.
- The residual becomes **era-conditional**: PRE re-fit ~94s (the credit dropped, so it rises to re-anchor
  the PRE-2018 mean to Nate), POST stays 24.2s. It's still **one fitted parameter** (the allowance) on a
  round, principled value (not knife-edge tuned) → low overfit risk, but IS in-sample on 32 matches.
- Adopting it changes PRE `true_stoppage` → feeds s08 → **could move the LOCKED X% (ADR-0025)**, driven
  entirely by the 115 PRE matches (POST inert). Direction is ambiguous (high-scoring PRE matches lose
  credit but mostly can't flip; low-scoring close ones gain residual and can) — MEASURE it. Human
  checkpoint, not a slip-in. The turnkey unit measures the X% delta and stops.
