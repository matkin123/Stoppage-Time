# The Stoppage Time That Never Gets Played

*An estimate of what would happen if stoppage time were actually measured correctly. Primarily a methodology piece, with some reflections at the end.*

---

Stoppage time is a sham.

Over the last six major international tournaments, if stoppage time were awarded according to the laws of the game, I estimate that **24.8%** of matches would have finished with a different scoreline [95% CI: 21.7%, 28.6%], and **13.0%** with a different result [95% CI 11.3%, 15.1%].

## Why I dug into this

The motivation for this model comes from two insights about football matches:

**1. Stoppage time is systematically under-awarded.** During the 2018 World Cup, Nate Silver hand-measured every match in the group stage and found that referees under-award stoppage time in 97% of matches, by an average of 6 mins. I pulled the stoppage time data for all 314 matches across six major international tournaments since. The direction and magnitude of error is striking; 96% of matches ended too early, by an average of 8 minutes.

![](../figures/requested/agg_01_scatter_estimate_vs_played.png)

**2. Teams are much more productive during stoppage time.** The goal-scoring rate in second-half stoppage time is 1.9× the rate of the average minute.

![](../figures/requested/agg_02_productivity_by_bucket.png)

In short, referees chronically under-award the crucial minutes that flip match outcomes.

## The data

All of the data in this project comes from StatsBomb, one of the sport's gold-standard providers. StatsBomb codes each match into a timestamped log of on-ball events: pass, shot, tackle, throw-in, foul, card, substitution, ball out of play. Each match carries roughly 3,000 to 3,600 logged events, about 30 to 37 per minute. The coding is done by a combination of computer vision and human intervention. Professional clubs buy this data to scout players and analyze opponents, among them Club Brugge. Since 2018, StatsBomb has released part of that professional database free for research. This project runs entirely on the free release. I use all 314 match logs from the last six major international tournaments (World Cups 2018 and 2022, Euros 2020 and 2024, Copa América 2024, AFCON 2023).

## Methodology

The core idea is simple. Take all 314 matches as played. For each, append the stoppage the referee should have added but didn't, and ask one question: would at least one more goal plausibly have dropped in? Average that probability across the 314 matches. That average is the headline. The work is making each step checkable.

**Step 1 — Measure stoppage *played* and stoppage *owed*, and validate against Nate Silver's data.** The hard part is owed stoppage. The Laws of the Game (Law 7) tell the referee to add all time lost to substitutions, injuries, celebrations, cards, VAR checks, and time-wasting, but they put a number on none of it. There is no stated limit on how long a routine throw-in or goal kick may take before the delay counts as lost time. So to measure owed stoppage you have to supply the thresholds the Laws omit. Nate Silver's 2018 stopwatch study supplied them, and I adopt his table unchanged. His allowances are generous, giving a throw-in a full 20 seconds before any of it counts as owed:

| Routine restart | Normal allowance (excess beyond this counts as owed) |
|---|---|
| Throw-in | 20 s |
| Goal kick | 30 s |
| Corner kick | 45 s |
| Free kick | 60 s |

A throw-in that takes 50 seconds owes 30; one that takes 15 owes nothing. Genuine stoppages (celebrations, subs, cards, injuries) are credited separately.

I calibrate the estimator against the one independent ground truth that exists: Nate Silver's by-hand measurement of all 32 World Cup 2018 matches, where he recorded both the stoppage that should have been added and the stoppage that was.

![](../figures/f07_nate_calibration.png)

Stoppage *played* is the easy half — whistle-to-whistle added time, read straight off the event clock — and my played clock matches his almost exactly (r = 0.992). That near-exact match is what makes the owed estimate believable: Nate, with a stopwatch and no access to this pipeline, found the same shortfall (r = 0.875, average error 1.77 minutes). Across the 314 matches, owed stoppage averages about 17.6 minutes a match and played stoppage about 8.9, leaving roughly 8.8 omitted minutes, positive in 97% of matches.

**Important Context - Changes to the stoppage time rules in 2022:** FIFA directed referees to count stoppages more honestly. The biggest change was to add *all* of a goal celebration to stoppage, rather than the perceived "excess" of one.[^1]

**Step 2 — Reconstruct the live football, and check it against outside numbers.** Dead time is the gap between two timestamps: a pass goes out of play, a throw-in is received, and the seconds in between are dead. Summed across a match, those gaps give *ball-in-play*. I validate it against the best external anchors there are. For the 2022 World Cup my reconstruction reads 57:40 against Opta's 58:04 (−24s); for 2018, 56:00 against Opta's 54:50 (+70s), with FiveThirtyEight's 55:18 in between. (Opta, now Stats Perform, publishes the industry-standard ball-in-play figures.)

Some gaps have no restart to explain them: the ball goes out of play, then a pass arrives, with no throw-in logged in between. The matches are coded by hand off the broadcast feed, so silent gaps open for all sorts of reasons: the camera cuts away from the pitch, the human coder takes a bite of a sandwich, who knows. I set one global threshold for how long such a gap must run before the ball counts as dead. Sweeping it from 12 to 30 seconds is the ±1 minute of per-match uncertainty I carry, rather than a false-precision point. The headline moves by less than 0.1 percentage points across that whole range, because the live-football level enters the final number twice — once in the scoring rate, once in the exposure — and the two largely cancel.

**Step 3 — Calcualte the probability of a goal in the missing minutes.** Each omitted live minute is assigned a goal rate. Expected extra goals is rate times minutes, and the chance of at least one extra goal follows from the Poisson formula. Start with the simplest version:

```
μ  =  (goal rate) × (omitted live minutes)
P(≥1 extra goal)  =  1 − e^(−μ)
Headline  =  average of P across the 314 matches
```

Three terms need defining, and that is the whole model.

**1. Omitted live minutes.** Owed minus played gives omitted *clock*. Scoring differs by half, so the window splits into first and second half:

```
μ  =  λ₁ · ℓ₁  +  λ₂ · ℓ₂
```

where `λ_h` is goals per live minute in half *h* and `ℓ_h` is the omitted live minutes in that half.

**2. The live share.** An omitted minute is assumed to look like the average minute of that *same half* — its regulation play plus the added time that was actually played — not like the few, unusually dead minutes of stoppage the referee did add. That same reference period also sets how much of the re-added time would itself be wasted: referees would have to top up for stoppage *within* the stoppage, but only the genuine-stoppage share of dead time recurs, not ordinary dead-ball flow. Anchoring both to a 45-minute base, on the teams playing that day, beats reading them off the handful of skewed minutes that happened to be played.

**3. The rate.** `λ₁` is the first-half stoppage rate, held fixed. `λ₂` starts at the observed second-half stoppage rate and decays toward the open-play floor across the window. Putting it together, per match:

```
ℓ_h  =  max(0, owed_h − played_h) × (same-half live share) × (in-stoppage gross-up)
μ    =  λ₁ · ℓ₁  +  (decayed λ₂) · ℓ₂
P    =  1 − e^(−μ)
Headline  =  mean of P over 314 matches
```

Why the decay? See Objection 1.

## Objections

**Objection 1: If we add more time, teams won't keep scoring at the same rate.**

True, and the model is built around it. Scoring is not even across a match: it climbs, and second-half stoppage is the most productive window on the field.

| Window | Goals per live-minute | Goals (n) |
|---|---|---|
| 2nd-half stoppage (the late-game peak) | **0.0816** | 73 |
| 1st-half stoppage | 0.0478 | 23 |
| Regulation open play (the floor) | **0.0427** | 675 |

That peak is 1.9× the open-play rate, and the reason is not the referee. It is how football is played late: a losing team commits bodies forward, defenses stretch, the game opens up. Which is the objection restated. The rate is endogenous to game state: the minutes observed at 0.0816 are selected for desperation, so pricing fresh, neutral minutes there would overstate the result.

So the rate decays. No omitted second-half minute is priced at the raw peak. Each is priced on a curve falling from 0.0816 toward the open-play floor of 0.0427, with a half-life swept from 2 to 8 minutes (central 4). The longer the hypothetical window, the closer its minutes are priced to ordinary open play. The floor *is* open play, so even under maximum decay an added minute is never priced below match-average football. It is still football.

![](../figures/f06_productivity_decay.png)

The whole decay band runs from 23.3% (fastest decay) to 26.1% (slowest), under three points around the 24.8% headline.

**Important Context - What happened when stoppage time actually increased substantially overnight, and what it means for the assumption of decay.** When the 2022 directive roughly doubled added time, the per-minute scoring rate in those minutes barely moved: PRE second-half stoppage ran 0.086 (24 goals / 279 live-minutes), POST 0.080 (49 goals / 615 live-minutes), with more than twice the live stoppage minutes. This indicates that stoppage time is not just ordinary football with the clock still running. Being in it is psychologically different, and the urgency it manufactures would not exist in a stopped-clock version of the same match. So the model's estimate is probably conservative.

There is a big confounding variable, though. In POST matches, fewer minutes were live by the 90th, because regulation time-wasting rose once teams learned that time would get topped up later. As a result, more of each match slid into stoppage. Some of the stoppage premium is therefore just “these are late minutes of a shortened game.” The honest reading: the stoppage time premium is partly real urgency and partly selection; the model prices both down toward open play, and the answer barely moves either way.

**Objection 2: The high rate is just trailing teams chasing a level scoreline.** When a side trails late it throws bodies forward, so maybe the premium is only desperate, level matches. 

Second-half stoppage scores at about the same rate whether the game is level at 90 (0.0886 [0.0567, 0.1318]) or not (0.0786 [0.0581, 0.1039]), with heavily overlapping intervals. Conditioning the entire model on score state at 90 barely moves the headline, from 24.8% to 24.5%.

**Objection 3: The high rate is a knockout-stage effect.** Maybe the late rate is inflated by win-or-go-home stakes. 

Split the same window by match type: group stage 0.0847 (56 goals / 660.8 live-minutes) against elimination 0.0727 (17 goals / 233.7 live-minutes), the point estimate actually leans *higher* in the group stage (rate ratio 1.17, binomial p = 0.69). There is no separate elimination effect to price into the model. Carried all the way through: source every match's rate from the group stage alone and the headline lands at 25.9%; from the knockouts alone, 21.5% — both inside the envelope, with the all-matches central at 24.8% (the sensitivity table shows this as the knockout-vs-group row).

**Objection 4: The result figure assumes a goal is equally likely to fall to either team.** When a team leads by one at 90, the result flips only if the trailing side scores, and the chasing team scores more often than the leader, so a flat 50/50 split should understate flips. 

The model does split omitted-time goals 50/50. Measured in the data, the trailing team takes 0.548 of the goals scored in lead-by-one stoppage situations (n = 31, 95% CI [0.375, 0.713]). Sweeping that split across the whole plausible range, 0.40 to 0.60, moves the result figure only between 12.0% and 13.9%, and leaves the scoreline headline untouched, because the scoreline asks for any extra goal by either side and never uses the split.

## Results and sensitivity

| Quantity | Value |
|---|---|
| **Headline — different scoreline (central)** | **24.8%** |
| 95% bootstrap confidence interval (sampling) | **[21.7%, 28.6%]** |
| Lead band — one modeling choice varied at a time | **21.4% – 27.3%** |
| Full envelope — all modeling choices varied jointly | **18.9% – 28.6%** |
| **Different *result*** — winner/draw actually changes | **13.0% [11.3%, 15.1%]** |
| Second-half-only variant (comparison, not the headline) | 17.0% [15.0%, 19.5%] |

Two kinds of uncertainty, kept apart. *Sampling* uncertainty is the bootstrap CI **[21.7%, 28.6%]** (width 6.9 points): over 1,000 draws, each goal-rate cell is redrawn from a Jeffreys–Gamma posterior and a shared owed-stoppage estimator error is split across the two halves. *Specification* uncertainty is how the headline moves as defensible modeling choices change, one at a time (the 21.4–27.3% band) or all jointly (the 18.9–28.6% envelope).

| Modeling choice | Levels → X% | Spread |
|---|---|---|
| **Decay half-life** | h=2 23.3 · **h=4 24.8** · h=8 26.1 | ~2.8 pts |
| **Score at 90** (conditioning) | overall **24.8** · split by tied/not-tied 24.5 | ~0.3 pts |
| **Knockout vs group stage** | all matches **24.8** · group stage 25.9 · knockout 21.5 | ~4.4 pts |
| **λ source** (PRE vs POST) | all-pooled **24.8** · POST-only 23.7 · regime-matched 24.9 · PRE-only 27.3 | ~3.5 pts |
| **Gross-up** (in-stoppage wasting) | off 21.4 → **on 24.8** → geometric 26.0 | ~4.6 pts |
| One-at-a-time band | **21.4% – 27.3%** | 5.9 pts ≈ 0.9× sampling |
| Full **joint** envelope | **18.9% – 28.6%** | 9.7 pts ≈ 1.4× sampling |

The one-at-a-time band (5.9 pts) is about the size of the sampling CI (6.9 pts), and the joint envelope (9.7 pts) only modestly exceeds it. The headline does not hinge on any single knob. The PRE-only λ source sets the top of the band at 27.3%, on a thin, wide-interval PRE sample; the central pooled rate is the one to read. Sourcing every match's rate from one stage moves the headline modestly either way — 25.9% from the group stage, 21.5% from the knockouts — and both stay inside the envelope.

Flip mechanics: the model splits omitted-time goals 50/50 between the two teams (Objection 4) and treats any match leading by two or more at 90 as unflippable. 95 of the 314 matches were already decided by two or more goals at 90, so they cannot flip at all.

## Limitations

To state the obvious, this is a counterfactual model. While the assumptions are grounded in the best available evidence, the output is unfalsifiable. I don't have external data to test against, because no one has ever played the stoppage time that did not get played.

The calibration that anchors the entire model — the owed-stoppage estimator in Step 1 — is fit on World Cup 2018 only. That's the lone tournament where an independent observer measured the truth by hand, so it's the only place I can check my work against something outside my own pipeline. The residual term this calibration produces is then frozen and applied unchanged to the other five tournaments. This application crosses the 2022 stoppage time policy change, when owed stoppage time jumped from 12.7 minutes (2018 World Cup) to roughly 19 minutes. While the model mechanics for estimating owed stoppage time update to reflect the policy change (e.g., by capturing the full time spent on celebrating goals, rather than the excess), the estimate cannot be validated externally.

P.S. If someone wants to grab a stopwatch and hand-measure dozens of post policy change matches, let me know.

## Reflections

**Significance to the 2026 World Cup.** We are in the middle of the tournament, which makes this as much a measurement exercise as a live indictment of the referee. Some thoughts:

The errors that arise from under-awarded stoppage time compound over the course of a tournament. How many group stage matches would've been decided differently? And therefore how much of the elimination draw was "wrong"? And how many of the elimination matches themselves would have ended differently? By the time we reach the final, we have two teams standing on a stack of errors. In many cases, the team that lifts the trophy is correct. However, the bracket that delivers the result is certainly not the bracket that the rules should have produced.

The new tournament structure means that more teams than ever before will advance (or not) on goal difference, which amplifies the consequences of failing to award stoppage time. Look at the [Group Stage third-place rankings](https://www.bbc.co.uk/sport/football/world-cup/table), which decide who progresses into the elimination round, and remember that 1 in 4 scorelines change when stoppage time is awarded correctly….

**Is the current fix working?** Remember all that stoppage time in Qatar? As noted earlier, it happened because FIFA's head referee, Pierluigi Collina, relseased a directive that instructed referees to add time more fully. The problem was: its main effect was to produce more time-wasting. (We know this because the amount of time the ball was in play nudged up by about 1.3 mins, which was just a fraction of the 3.2 mins added to the average match.) So, Collina reversed course for 2026, implementing (informal) countdowns for throw-in and goal-kicks, among other measures. Early signs are cautiously positive (less overt time wasting, more ball in play), but I do not have access to the data to make an informed judgement.

**What do the people want?** This is the part no amount of measurement settles: from my anecdotal experience, many fans don't want these minutes anyway. During Qatar, some of my friends were not annoyed that more of the clock was being wasted, or that a stoppage inside stoppage time almost never gets added back in full…they were annoyed by the extent of the added time itself. (This is a version of "the game is gone" critique, where "the game" is some notional 1 to 3 minutes that are tacked onto each half, no matter how much time is actually wasted.)

So let me put it in the plainest terms. An extra five minutes sounds like nothing. But at the rate teams actually score in second half stoppage (0.082 goals per live minute), five minutes is worth about four-tenths of a goal, and even at the ordinary open play rate (0.043), it is worth about one fifth. High-variance events (i.e., goals) decide football matches, and change the course of tournaments. The minutes most likely to produce goals are precisely the minutes most reliably left off the clock. To anyone who shrugs that it is only a few minutes: this is the point you are missing.

[^1]: I update my stoppage-time estimate for post-directive tournaments to count all goal-celebration stoppage, rather than 25%, which I calibrated to Nate.

---

The full pipeline — every stage, every table, every assumption, reproducible end to end — is here: **https://github.com/matkin123/Stoppage-Time**
