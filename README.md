# Stoppage time is a sham.

> *If stoppage time were measured and awarded in full, **21.4%** of matches would have finished
> with a different scoreline [95% CI 18.2%, 25.2%] — and **10.8%** with a different result
> [9.1%, 12.8%].*

A reproducible quantitative investigation into football stoppage time. Across **314 matches** from
six major international tournaments, referees systematically under-award added time: the minutes
that were owed but never played are large enough that, properly awarded, roughly **one match in
five would have a different scoreline**.

The headline `X%` is the single modeled claim. It ships with a confidence interval, a sensitivity
table, and an external calibration — never as a bare point estimate. Every number in this repo
traces to a script, a checkpointed parquet table, and a documented assumption (see
[`docs/decisions.md`](docs/decisions.md), the ADR log, and [`CLAUDE.md`](CLAUDE.md), the project
contract).

> **The public write-up is on Substack: [The Stoppage Time That Never Gets Played](https://matkin.substack.com/p/the-stoppage-time-that-never-gets).**
> The headline lock lives in [`docs/decisions.md`](docs/decisions.md) ADR-0040.

---

## Headline results

| Claim | Central | 95% CI (sampling) | Assumption band |
|---|---|---|---|
| **Different scoreline** (≥1 extra goal anywhere in the omitted added time) | **21.4%** | **[18.2%, 25.2%]** | 19.2% – 23.7% |
| **Different result** (the winner/draw actually changes) | **10.8%** | **[9.1%, 12.8%]** | — |
| Second-half-only variant (comparison, not the headline) | 14.2% | [12.1%, 16.6%] | 12.8% – 15.3% |

*Window: full match (first- and second-half stoppage combined), pooled across all 314 matches.
Central knob set `silent_marked | overall | pooled_all | hl=4.0 | on`. Locked in
[`docs/decisions.md`](docs/decisions.md) ADR-0040 (re-lock; supersedes ADR-0039's 23.3% / 12.1%).*

**"Different scoreline" and "different result" are kept strictly apart.** A different *scoreline*
(≥1 extra goal anywhere, 21.4%) is weaker than a different *result* (the winner or draw actually
changes, 10.8%): 95 of 314 matches led by two-plus goals at 90:00 and are treated as unflippable.
Conflating the two would overstate the claim, so they are always reported separately.

Two uncertainty objects are also kept apart throughout: the **sampling CI** (finite goal counts +
estimator error, width 7.0 pts) and the **specification / assumption band** (how `X%` moves as
modeling choices change). Once the data-gap handling is calibrated, neither dominates — the
one-factor band (4.5 pts) is ≈0.6× the sampling width, and the full joint envelope across all
legitimate knobs is 16.3%–24.9%.

---

## Why I dug into this

The investigation rests on two empirical facts about modern football:

1. **Stoppage time is systematically under-awarded.** In 2018, Nate Silver hand-measured all 32
   World Cup matches and found referees under-award added time in **97% of matches**, by ~6 minutes
   on average. This project extends that to every match in the last six major international
   tournaments.
2. **Teams are much more productive during stoppage time.** The goal-scoring rate in second-half
   stoppage is **1.9× the rate of the average minute** — so the chronically omitted minutes are
   exactly the ones most likely to flip a match.

---

## The data

All match and event data are **StatsBomb open data** (the free research release) — a timestamped
log of ~3,000–3,600 on-ball events per match (pass, shot, tackle, throw-in, foul, card, sub, ball
out of play). No xG, no 360 data.

| Tournament | Era | Matches |
|---|---|---|
| FIFA World Cup 2018 | PRE | 64 |
| UEFA Euro 2020 | PRE | 51 |
| FIFA World Cup 2022 | POST | 64 |
| UEFA Euro 2024 | PRE | 51 |
| Copa América 2024 | POST | 32 |
| Africa Cup of Nations 2023 | POST | 52 |
| **Total** | | **314** (PRE 166, POST 148) |

`PRE` vs `POST` splits the sample around the 2022 IFAB/Collina directive that instructed officials
to add time for *all* stoppages. The directive changed how much went on the board (stoppage
*played* rose ~7.0 → 11.0 min/match), but goals **per live-minute** are statistically
indistinguishable across the split — so the model pools all six tournaments for its scoring rates
and treats PRE/POST only as a robustness axis.

---

## How it's measured

The core idea is simple: take all 314 matches as played; for each, append the stoppage the referee
should have added but didn't, and ask whether at least one more goal would plausibly have dropped
in; average that probability across the 314 matches. The work is making each step checkable. The
pipeline reconstructs three quantities per match and combines them in closed form.

**Step 1 — Measure stoppage *played* and stoppage *owed*, and validate against Nate Silver.**
The Laws of the Game (Law 7) tell the referee to add all time lost to subs, injuries,
celebrations, cards, VAR, and time-wasting — but put a number on none of it. So owed stoppage needs
the thresholds the Laws omit. We adopt Nate Silver's 2018 stopwatch allowances unchanged (generous:
a throw-in gets 20 s before any of it counts):

| Routine restart | Normal allowance (excess beyond this counts as owed) |
|---|---|
| Throw-in | 20 s |
| Goal kick | 30 s |
| Corner kick | 45 s |
| Free kick | 60 s |

Genuine stoppages (celebrations, subs, cards, injuries) are credited separately. Calibrated against
Nate Silver's by-hand World Cup 2018 measurement, owed stoppage tracks his "expected" at
**r = 0.836** (MAE 1.54 min) and stoppage *played* tracks his "actual" at **r = 0.992**. Across the
314 matches, owed stoppage averages ~**16.2** min/match and played ~**8.9**, leaving ~**7.3**
omitted minutes, positive in **98%** of matches. *(In 2022 FIFA directed referees to add all
time-wasting — chiefly full goal-celebration time rather than perceived excess; the estimator
applies this PRE/POST-conditionally.)*

**Step 2 — Reconstruct the live football, and check it against outside numbers.** Dead time is the
gap between two timestamps; summed across a match, the gaps give *ball-in-play*. The reconstruction
reads **57:40** for WC2022 against Opta's 58:04 (−24s), and **56:00** for 2018 against Opta's 54:50
(+70s), with FiveThirtyEight's 55:18 in between. A single global threshold sets how long a "silent"
gap (no logged restart) must run before the ball counts as dead; sweeping it 12→30 s is the ±1 min
of per-match uncertainty carried. The headline moves <0.1 pp across that whole range, because the
live level enters the final number twice (rate and exposure) and largely cancels.

**Step 3 — Price the missing minutes.** Each omitted live minute is assigned a goal rate; expected
extra goals is rate × minutes, and the chance of ≥1 extra goal follows from the Poisson formula:

```
ℓ_h  =  max(0, owed_h − played_h) × (same-half live share) × (in-stoppage gross-up)
μ    =  λ₁ · ℓ₁  +  (decayed λ₂) · ℓ₂
P    =  1 − e^(−μ)
Headline  =  mean of P over 314 matches
```

`λ₁` is the first-half stoppage rate, held fixed; `λ₂` starts at the observed second-half stoppage
rate and **decays** toward the open-play floor across the omitted window (why: Objection 1). An
omitted minute is assumed to look like the average minute of that *same half* — its regulation play
plus the added time actually played — not the few unusually dead minutes the referee did add. The
metric is deterministic; randomness enters only the confidence-interval bootstrap.

Full methodology (estimand, identification, every load-bearing assumption):
[`docs/Methodology.md`](docs/Methodology.md) and the narrative
[Substack write-up](https://matkin.substack.com/p/the-stoppage-time-that-never-gets).

---

## Objections

**1. "Add more time and teams won't keep scoring at the same rate."** True, and the model is built
around it. Second-half stoppage is the most productive window on the field (**0.0816** goals/live-min,
1.9× open play) — but the rate is endogenous to game state, so no omitted minute is priced at that
peak. `λ₂` decays from 0.0816 toward the **open-play floor 0.0427** on a curve with half-life swept
2–8 min (central 4); the floor *is* open play, so even maximal decay never prices added minutes
below match-average football. The whole decay band runs **20.2% (fastest) to 22.4% (slowest)** —
under three points around the 21.4% headline. *(Tell: when the 2022 directive roughly doubled added
time, the per-minute rate moved only modestly — PRE 0.089, POST 0.075 — well short of full decay, so
the truth sits nearer the top of the band.)*

| Window | Goals per live-minute | Goals (n) |
|---|---|---|
| 2nd-half stoppage (the late-game peak) | **0.0816** | 73 |
| 1st-half stoppage | 0.0478 | 23 |
| Regulation open play (the floor) | **0.0427** | 675 |

**2. "The high rate is just trailing teams chasing a level scoreline."** It isn't. Second-half
stoppage scores at about the same rate whether the game is level at 90 (0.0886 [0.0567, 0.1318]) or
not (0.0786 [0.0581, 0.1039]), with heavily overlapping intervals. Conditioning the entire model on
score-at-90 barely moves the headline, **21.4% → 21.0%**.

**3. "The high rate is a knockout-stage effect."** It isn't. Group stage 0.0847 (56 goals / 660.8
live-min) vs elimination 0.0727 (17 / 233.7) — the point estimate actually leans *higher* in the
group stage (rate ratio 1.17, binomial p = 0.69). No separate elimination effect to price. Carried
through the model, a group-stage-only λ gives 22.5% and a knockout-only λ gives 18.2% — both inside
the envelope (sensitivity table, knockout-vs-group row).

**4. "The result figure assumes a goal is equally likely to fall to either team."** The model does
split omitted-time goals 50/50; measured in the data the trailing team takes **0.548** of lead-by-one
stoppage goals (n = 31, 95% CI [0.375, 0.713]). Sweeping the split 0.40–0.60 moves the *result*
figure only **11.2%–12.9%** and leaves the *scoreline* headline untouched (it never uses the split).

**5. "But the team leading by one is usually the stronger side, so an even split still overstates
flips."** The mirror of Objection 4, and it fails on the data. Scope first, by *flip mass*: of the
10.8% flip the 98 tied games contribute **6.7 pp** (immune — any goal flips) and the 95 two-goal
games contribute **0** (unflippable), leaving the 121 one-goal games' **4.1 pp — just 38% of the
flip** — as the only mass the split can move. Even handing the leader *every* omitted goal floors the
flip at **6.7% = 31% of the 21.4% scoreline**. Pre-match World Football Elo for all 314: in
those matches the leader is stronger 60% of the time but by only **38 Elo**, because "exactly one goal
apart at 90" strips out the mismatches. Quality does predict who scores next (logit on the Elo gap
**β = +0.33/100 Elo, p < 0.001**), but the trailing team's chase outweighs it until the leader is
~**146 Elo** stronger — a bar only **39 of the 121** clear. So the trailing side still takes more
than half: **0.509** across one-goal games (any minute at a one-goal margin, n = 287), **0.548** in the
stoppage portion alone (n = 31). Re-pricing every match's split by its fitted, quality-conditioned
trailing-share moves the *result* figure at most **0.44 pp** (to 10.8%–11.2%, inside the CI); scoreline
untouched. (ADR-0034; `docs/team_quality_flip_test.md`.)

---

## Results and sensitivity

The whole result on one page:

| Quantity | Value |
|---|---|
| **Headline — different scoreline (central)** | **21.4%** |
| 95% bootstrap confidence interval (sampling) | **[18.2%, 25.2%]** |
| Lead band — one modeling choice varied at a time | **19.2% – 23.7%** |
| Full envelope — all modeling choices varied jointly | **16.3% – 24.9%** |
| **Different *result*** — winner/draw actually changes | **10.8% [9.1%, 12.8%]** |
| Second-half-only variant (comparison, not the headline) | 14.2% [12.1%, 16.6%] |

**Two kinds of uncertainty, kept apart.** *Sampling* uncertainty is the bootstrap CI
**[18.2%, 25.2%]** (width 7.0 pts): over 1,000 draws each goal-rate cell is redrawn from a
Jeffreys–Gamma posterior and a shared owed-stoppage estimator error is split across the two halves.
*Specification* uncertainty is how the headline moves as defensible modeling choices change, one at
a time (the 19.2–23.7% band) or all jointly (the 16.3–24.9% envelope).

| Modeling choice | Levels → X% | Spread |
|---|---|---|
| **Decay half-life** | h=2 20.2 · **h=4 21.4** · h=8 22.4 | ~2.2 pts |
| **Score at 90** (conditioning) | overall **21.4** · split by tied/not-tied 21.0 | ~0.4 pts |
| **Knockout vs group stage** | all matches **21.4** · group stage 22.5 · knockout 18.2 | ~4.3 pts |
| **λ source** (PRE vs POST) | all-pooled **21.4** · POST-only 19.7 · regime-matched 21.8 · PRE-only 23.7 | ~4.0 pts |
| **Gross-up** (in-stoppage wasting) | off 19.2 → **on 21.4** → geometric 21.9 | ~2.7 pts |
| One-at-a-time band (min–max of the swept knobs) | **19.2% – 23.7%** | 4.5 pts ≈ 0.6× sampling |
| Full joint envelope (all swept knobs together) | **16.3% – 24.9%** | 8.6 pts ≈ 1.2× sampling |

The one-at-a-time band (4.5 pts) is below the sampling CI (7.0 pts), and the joint
envelope only modestly exceeds it — the headline does not hinge on any single knob. The PRE-only λ
source sets the top of the band (23.7%) on a thin, wide-interval PRE sample; the central pooled rate
is the one to read. The knockout-vs-group row is a separate λ-source robustness check (like the
geometric ceiling) — sourcing every match's rate from one stage gives 22.5% (group) or 18.2%
(knockout), both inside the envelope — and is excluded from the band/envelope so it never re-centres
the headline. The data-gap handling is **not** a sweepable knob: "credit none" (≈11.8%) and
"credit all" (≈23.9%) are *known-biased bounds*, not honest uncertainty — the estimator is
calibrated to the defensible middle and only its calibration error enters the CI (ADR-0025/0040).

**Flip mechanics.** The model splits omitted-time goals 50/50 (Objection 4) and treats any match
leading by two-plus at 90 as unflippable; 95 of 314 matches were already decided by ≥2 goals at 90.

**The honest limitation.** The owed-stoppage estimator is anchored on World Cup 2018, then frozen
and applied unchanged to the other five tournaments — a transfer that crosses the 2022 directive
(the lone calibration tournament, World Cup 2018, is PRE, while the headline pools all six
tournaments across the directive) and an extrapolation (owed time runs 16–22 min/match across the
POST tournaments vs 13 for 2018, with Copa and AFCON considerably above the calibration level). 

---

## Reproducing the result

```bash
make setup                          # create .venv with pinned deps (NumPy held <2 on purpose)
source .venv/bin/activate
python -m pytest tests/test_lib.py -q   # unit tests, no data needed

python run.py --stage 1             # ingest match lists
python run.py --stage 2             # normalize events (streams JSON in-memory; ~few hundred MB)
python run.py --stage 3             # ball-in-play  <-- STOP and confirm the calibration gate
# ... s04, s05, s06a (needs board CSV), s06b, s07, s08, s09

python run.py --list                # show all stages
make all                            # run the whole pipeline in build order
make test                           # all acceptance gates
```

Work proceeds **one stage per session** and is validated against an external ground truth before
building downstream — see [`CLAUDE.md`](CLAUDE.md) §6 for why this is a hard rule. The two human
checkpoints that matter most are the **s03 calibration** and the **s08 sensitivity grid**.

### Pipeline (stage → output → acceptance gate)

| Stage | Output | Gate |
|---|---|---|
| s01 ingest | `matches.parquet` | match counts == checksums (166 / 148) |
| s02 normalize | `events_norm.parquet` | clock_s monotonic; sane period lengths |
| s03 ball-in-play | `bip_segments`, `match_minutes` | **WC2022 BIP within ±90s of Opta 58:04** |
| s04 goals/state | `goals`, `match_state` | after-90 goal share ~12–13%; finals match |
| s05 incident | `incident_stoppage`, `true_stoppage` | `lower_bound ≤ dead`; `lower_bound + silent_marked ≤ dead` |
| s06a played-in-stoppage | `played_in_stoppage.parquet` | PRE ~7 min, POST WC2022 ~11–12 min |
| s06b VAR | (`var_s` filled) | `var_s ≥ 0` (fallback estimator) |
| s07 productivity | `productivity`, `stoppage_live_share` | every cell reports n + live_minutes |
| s08 counterfactual | `counterfactual(+summary)`, `decay_profile` | sensitivity grid produced |
| s09 figures | `figures/*.png`, `numbers_ledger.md` | deterministic |

Stages are **idempotent** (each reads the prior stage's parquet and writes its own) and use
**deterministic seeds** (`config/params.yaml`). Figures and `data/{raw,interim,processed}` are
regenerable and gitignored; regenerate figures with `make s09`.

---

## Repository layout

```
config/      locked dataset (tournaments.yaml) + tunable params (params.yaml)
src/lib/     shared code (clock, bip, silent-gap, stats, nate-validation harness)
src/s0*.py   pipeline stages s01–s09
data/        raw (immutable cache) · interim · processed   (gitignored, regenerable)
             except data/raw/nate_2018/  (checked-in external ground truth)
docs/        decisions.md (ADR log) · Methodology.md (methodology write-up) ·
             substack_post_v*.md (public narrative, latest = current) ·
             data_dictionary.md · numbers_ledger.md · TRANSFER.md
figures/     deterministic figures from s09 (gitignored, regenerable)
tests/       pytest acceptance gates (one per stage)
```

### Documentation map

| Document | Purpose |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Project contract: goal, locked decisions, conventions, per-stage gates, session/README-sync rule |
| [Substack post](https://matkin.substack.com/p/the-stoppage-time-that-never-gets) | The published public narrative write-up |
| [`docs/Methodology.md`](docs/Methodology.md) | Methodology write-up (estimand, the three steps, assumptions) |
| [`docs/decisions.md`](docs/decisions.md) | ADR log — every methodology choice, newest first; the headline lock (ADR-0040) |
| [`docs/data_dictionary.md`](docs/data_dictionary.md) | Stage → table → column definitions |
| [`docs/numbers_ledger.md`](docs/numbers_ledger.md) | Every article figure → producing table + cell (regenerated by s09) |

---

## Data sources & attribution

Match and event data are **StatsBomb open data** (match + event JSON only — no 360 data, never
cloned), used under StatsBomb's open-data terms. Board added time (stoppage played) is curated into
`data/raw/board/board_added_time.csv`. World Cup 2018 ground truth is Nate Silver's published
FiveThirtyEight measurement, transcribed to `data/raw/nate_2018/nate_wc2018.csv`. The Opta
ball-in-play figures (58:04 WC2022, 54:50 WC2018) are used only as published calibration targets.
