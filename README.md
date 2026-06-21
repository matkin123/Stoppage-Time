# Stoppage Time

> *If stoppage time were measured and awarded in full, **23.6%** of matches would have finished
> with a different scoreline — and **12.1%** with a different result.*

A reproducible quantitative investigation into football stoppage time. Across **314 matches** from
six major international tournaments, referees systematically under-award added time: the minutes
that were owed but never played are large enough that, properly awarded, roughly **one match in
four would have a different scoreline**.

The headline `X%` is the single modeled claim. It ships with a confidence interval, a sensitivity
table, and an external calibration — never as a bare point estimate. Every number in this repo
traces to a script, a checkpointed parquet table, and a documented assumption (see
[`docs/decisions.md`](docs/decisions.md), the ADR log, and [`CLAUDE.md`](CLAUDE.md), the project
contract).

---

## Headline results

| Claim | Central | 95% CI (sampling) | Assumption band |
|---|---|---|---|
| **Different scoreline** (≥1 extra goal anywhere in the omitted added time) | **23.6%** | **[20.6%, 27.4%]** | 21.1% – 26.1% |
| **Different result** (the winner/draw actually changes) | **12.1%** | **[10.6%, 14.2%]** | — |
| Second-half-only variant (comparison, not the headline) | 16.0% | [14.0%, 18.5%] | 14.1% – 17.4% |

*Window: full match (first- and second-half stoppage combined), pooled across all 314 matches.
Central knob set `silent_marked | overall | pooled_all | hl=4.0 | on`. Locked in
[`docs/decisions.md`](docs/decisions.md) ADR-0025.*

**"Different scoreline" and "different result" are kept strictly apart.** A different *scoreline*
(≥1 extra goal anywhere, 23.6%) is weaker than a different *result* (the winner or draw actually
changes, 12.1%): 95 of 314 matches led by two-plus goals at 90:00 and are treated as unflippable.
Conflating the two would overstate the claim, so they are always reported separately.

Two uncertainty objects are also kept apart throughout: the **sampling CI** (finite goal counts +
estimator error) and the **specification / assumption band** (how `X%` moves as modeling choices
change). Once the data-gap handling is calibrated, neither dominates — the one-factor band (5.0 pts)
is ≈0.7× the sampling width, and the full joint envelope across all legitimate knobs is 18.6%–27.3%.

---

## What this is

This is a **counterfactual estimate over 314 already-played matches**:

> *If the stoppage minutes that were truly owed but never played had actually been played, in how
> many matches would at least one additional goal plausibly have been scored — and within those,
> how many results would have flipped?*

It is a descriptive functional of a fixed, fully-observed population, not a forecast. There is no
held-out future to predict, so validity rests on (a) the inputs being unbiased and (b) the
transfer assumptions being defensible — both anchored to external ground truth (see
[Validation](#validation--standard-of-proof)).

### The matches

| Tournament | Era | Matches |
|---|---|---|
| FIFA World Cup 2018 | PRE | 64 |
| UEFA Euro 2020 | PRE | 51 |
| FIFA World Cup 2022 | POST | 64 |
| UEFA Euro 2024 | POST | 51 |
| Copa América 2024 | POST | 32 |
| Africa Cup of Nations 2023 | POST | 52 |
| **Total** | | **314** (PRE 115, POST 199) |

`PRE` vs `POST` splits the sample around the 2022 IFAB/Collina directive that instructed officials
to add time for *all* stoppages. The directive changed how much went on the board (stoppage
*played* rose ~6.8 → 10.0 min/match), but goals **per live-minute** are statistically
indistinguishable across the split — so the model pools all six tournaments for its scoring rates
and treats PRE/POST only as a robustness axis.

---

## How it's measured

The pipeline reconstructs, for each match, three quantities and combines them in closed form:

1. **Stoppage owed (`T_true`)** — the added time that *should* have been played. Built bottom-up
   from identifiable dead time (celebrations, subs, cards, injuries, excess restart time) plus
   marker-confirmed "data gaps," with a single calibrated residual constant. Calibrated against
   Nate Silver's hand-measured World Cup 2018 stopwatch data (**r = 0.825**, MAE 2.44 min).
2. **Stoppage actually played (`T_play`)** — whistle-to-whistle added time read off the event
   clock (matches Nate's "actual" column at **r = 0.992**).
3. **Omitted minutes (`O = max(0, T_true − T_play)`)** — positive in **97% of matches**: owed
   17.3, played 8.9, **omitted 8.6** min/match (of which ~5.1 are live ball-in-play).

Extra goals in the omitted live minutes are priced with a Poisson model,
`P(≥1 extra goal) = 1 − exp(−μ)`, where `μ = Σ_h λ_h · ℓ_h`. The headline `X%` is the mean of that
per-match probability across all 314 matches. The metric is deterministic; randomness enters only
the confidence-interval bootstrap.

The full write-up — estimand, identification, every load-bearing assumption, and the figures — is
[`docs/model_review_v2.md`](docs/model_review_v2.md). It is self-contained (figures embedded) and is
the canonical methodological reference.

### Sensitivity (each knob swept with the others held at central, full match)

| Modeling choice | Levels → X% | Spread |
|---|---|---|
| **λ source** | pooled **23.6** · POST-only 22.6 · regime-matched 23.8 · PRE-only 26.1 | ~3.5 pts |
| **In-stoppage gross-up** | off 21.1 → **on 23.6** → geometric ceiling 24.2 | ~3.1 pts |
| **Decay half-life** | h=2 22.2 · **h=4 23.6** · h=8 24.9 | ~2.7 pts |
| **Conditioning** | overall **23.6** · tied/not-tied 23.4 | ~0.2 pts |
| One-factor band (min–max of the above) | **21.1% – 26.1%** | ≈0.7× sampling |
| Full joint envelope (all knobs together) | **18.6% – 27.3%** | ≈1.3× sampling |

The data-gap handling is **not** treated as a sweepable knob: "credit none" (10.8%) and "credit
all" (37.3%) are *known-biased bounds*, not honest uncertainty. The estimator is calibrated to the
defensible middle and only its calibration error is propagated into the CI (see
[`docs/decisions.md`](docs/decisions.md) ADR-0025).

---

## Common objections

**1. "If you added the missing minutes, teams would be less productive per minute — you can't price
new time at the urgent end-of-game rate."**

Agreed in principle — and this is exactly why the model uses a **decay rate**, not the raw
end-of-game rate. Second-half stoppage is the most productive window in the match
(**0.0816** goals/live-min, ~1.9× the open-play average) precisely because it is short, late, and
urgent. We do **not** assume newly-added minutes inherit that premium. For each marginal omitted
second-half minute, the per-minute scoring rate **decays geometrically** from the observed
second-half-stoppage rate (0.0816) toward the **open-play floor** (0.0427):

```
λ(t) = floor + (observed − floor) · 0.5^(t / h)
```

The half-life `h` is the explicit knob and is reported as a band (`h ∈ [2, 8]` min, central
`h = 4`). The two bounding cases fall out exactly: `h → ∞` is "no decay" (full premium) and
`h → 0` is "full decay" (every added minute at the open-play floor). Crucially, **the floor is the
open-play rate** — even maximal decay never prices added minutes below match-average pace, because
they remain football, not nothing. The decay moves the headline only between 22.2% and 24.9%; the
objection is real, it is modeled, and it does not break the claim. (Detail:
[`docs/model_review_v2.md`](docs/model_review_v2.md) §4.1.)

**2. "Isn't 24% just noise?"** No. The 95% sampling CI is [20.6%, 27.4%] and the full assumption
envelope is 18.6%–27.3% — the floor of every legitimate corner is still ~1 in 5.

**3. "Does a model calibrated on 2018 transfer to Copa América and AFCON?"** This is the most
exposed assumption and is named as such. The owed-stoppage estimator is calibrated on World Cup
2018 only (the lone tournament with independent ground truth); the constants are then applied
unchanged where owed time runs ~1.5–2× higher. The PRE/POST λ check and the WC2022 Opta ball-in-play
anchor bound it, but it remains the model's headline risk (see [Limitations](#limitations--open-questions)).

**4. "Why no expected goals (xG)?"** Deliberate — the project avoids any xG-model dependence and
prices everything from directly-counted goals and second-level timestamps (ADR-0002).

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
| s01 ingest | `matches.parquet` | match counts == checksums (115 / 199) |
| s02 normalize | `events_norm.parquet` | clock_s monotonic; sane period lengths |
| s03 ball-in-play | `bip_segments`, `match_minutes` | **WC2022 BIP within ±90s of Opta 58:04** |
| s04 goals/state | `goals`, `match_state` | after-90 goal share ~12–13%; finals match |
| s05 incident | `incident_stoppage`, `true_stoppage` | `lower_bound ≤ total dead time` |
| s06a played-in-stoppage | `played_in_stoppage.parquet` | PRE ~7 min, POST WC2022 ~11–12 min |
| s06b VAR | (`var_s` filled) | `var_s ≥ 0` (fallback estimator) |
| s07 productivity | `productivity`, `stoppage_live_share` | every cell reports n + live_minutes |
| s08 counterfactual | `counterfactual(+summary)`, `decay_profile` | sensitivity grid produced |
| s09 figures | `figures/*.png`, `numbers_ledger.md` | deterministic |

Stages are **idempotent** (each reads the prior stage's parquet and writes its own) and use
**deterministic seeds** (`config/params.yaml`). Figures and `data/{raw,interim,processed}` are
regenerable and gitignored; regenerate figures with `make s09`.

---

## Validation & standard of proof

Two external anchors certify the model's **inputs** (neither certifies its output — see limitation 1):

- **Nate Silver, World Cup 2018** (32 matches, hand-measured with a stopwatch at FiveThirtyEight).
  Our owed-stoppage estimator tracks his "expected" (should-be-added) minutes at **r = 0.825**
  (MAE 2.44 min); our stoppage-played clock tracks his "actual" at **r = 0.992**. His own numbers
  show **13.16 owed vs 6.98 played** — a 1.9× shortfall an outside observer found independently.
  The table is checked in at `data/raw/nate_2018/nate_wc2018.csv` (the only non-regenerable data
  in the repo).
- **Opta, World Cup 2022 ball-in-play.** Opta publishes 58:04 of average ball-in-play per match;
  our gap-method reconstruction gives 57:40 (24s low). This certifies the live-share denominator.

The **standard of proof**: every figure traces to a script + a checkpointed table + a documented
assumption. A stage is "done" only when its pytest acceptance gate is green. The locked headline,
its band, and the chosen knob set live in [`docs/decisions.md`](docs/decisions.md); the
script-to-figure ledger is [`docs/numbers_ledger.md`](docs/numbers_ledger.md).

---

## Limitations & open questions

Honest list, least-defensible first (full version in
[`docs/model_review_v2.md`](docs/model_review_v2.md) §7):

1. **No independent counterfactual benchmark.** Every external check is on an *input*; `X%` itself
   is not falsified against any outside number.
2. **POST coverage gap.** The estimator is calibrated on World Cup 2018 only; the POST cohort —
   where the headline mostly lives and where owed time is ~1.5–2× higher — rides on frozen-2018
   constants and a single WC2022 ball-in-play point.
3. **Data-gap-as-point.** Reporting the calibrated middle (not a none↔all band) is what makes the
   band tight; a reviewer who insists none/all are legitimate uncertainty sees a far wider range.
4. **First-half thinness.** ~1/3 of the headline rests on a 23-goal first-half-stoppage rate, with
   no game-state propagation across the first-half increment.
5. **Productivity transfer is an assumption, not a measurement.** The decay band brackets the
   urgency premium but cannot rule out that *omitted* minutes are systematically unlike any
   observed minute.

---

## Repository layout

```
config/      locked dataset (tournaments.yaml) + tunable params (params.yaml)
src/lib/     shared code (clock, bip, silent-gap, stats, nate-validation harness)
src/s0*.py   pipeline stages s01–s09
data/        raw (immutable cache) · interim · processed   (gitignored, regenerable)
             except data/raw/nate_2018/  (checked-in external ground truth)
docs/        decisions.md (ADR log) · model_review_v2.md (canonical write-up) ·
             data_dictionary.md · numbers_ledger.md · TRANSFER.md
figures/     deterministic figures from s09 (gitignored, regenerable)
tests/       pytest acceptance gates (one per stage)
```

### Documentation map

| Document | Purpose |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Project contract: goal, locked decisions, conventions, per-stage gates |
| [`docs/model_review_v2.md`](docs/model_review_v2.md) | Canonical methodological write-up (read start-to-finish, figures embedded) |
| [`docs/decisions.md`](docs/decisions.md) | ADR log — every methodology choice, newest first; the headline lock (ADR-0025) |
| [`docs/data_dictionary.md`](docs/data_dictionary.md) | Stage → table → column definitions |
| [`docs/numbers_ledger.md`](docs/numbers_ledger.md) | Every article figure → producing table + cell (regenerated by s09) |

---

## Data sources & attribution

Match and event data are **StatsBomb open data** (match + event JSON only — no 360 data, never
cloned), used under StatsBomb's open-data terms. Board added time (stoppage played) is curated into
`data/raw/board/board_added_time.csv`. World Cup 2018 ground truth is Nate Silver's published
FiveThirtyEight measurement, transcribed to `data/raw/nate_2018/nate_wc2018.csv`. The Opta
ball-in-play figure (58:04, WC2022) is used only as a published calibration target.
