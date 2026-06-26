# The Stoppage Time That Never Gets Played

*A fully reproducible measurement across the last six major international tournaments (314 matches). Owed stoppage vs. stoppage actually played — and what the missing minutes would have changed.*

---

Stoppage time is a sham.

Over the last six major international tournaments, if stoppage time were awarded according to the laws of the game, I estimate that **24.8%** of matches would have finished with a different scoreline [95% CI: 21.7%, 28.6%], and **13.0%** with a different result [95% CI 11.3%, 15.1%].

## Why I dug into this

The motivation for this model comes from two insights about football matches:

**1. Stoppage time is systematically under-awarded.** During the 2018 World Cup, Nate Silver showed that referees under-award stoppage time in 97% of matches, by an average of 8 mins. Building on Nate's work, I pulled the data for every match in the last 6 major international tournaments (World Cup '18 & '22, Euros '20 & '24, Copa '24, AFCON '23).

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

**Changes to the stoppage time rules in 2022:** FIFA directed referees to add all time-wasting. The biggest change was to add *all* of a goal celebration to stoppage, rather than the perceived "excess" of one.[^1]

**Step 2 — Reconstruct the live football, and check it against outside numbers.** Dead time is the gap between two timestamps: a pass goes out of play, a throw-in is received, and the seconds in between are dead. Summed across a match, those gaps give *ball-in-play*. I validate it against the best external anchors there are. For the 2022 World Cup my reconstruction reads 57:40 against Opta's 58:04 (−24s); for 2018, 56:00 against Opta's 54:50 (+70s), with FiveThirtyEight's 55:18 in between. (Opta, now Stats Perform, publishes the industry-standard ball-in-play figures.)

Some gaps have no restart to explain them: the ball goes out of play, then a pass arrives, with no throw-in logged in between. The matches are coded by hand off the broadcast feed, so silent gaps open for all sorts of reasons: the camera cuts away from the pitch, the human coder takes a bite of a sandwich, who knows. I set one global threshold for how long such a gap must run before the ball counts as dead. Sweeping it from 12 to 30 seconds is the ±1 minute of per-match uncertainty I carry, rather than a false-precision point. The headline moves by less than 0.1 percentage points across that whole range, because the live-football level enters the final number twice — once in the scoring rate, once in the exposure — and the two largely cancel.

**Step 3 — Price the missing minutes.** Each omitted live minute is assigned a goal rate. Expected extra goals is rate times minutes, and the chance of at least one extra goal follows from the Poisson formula. Start with the simplest version:

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

**What happened when stoppage time actually increased substantially overnight, and what it means for the assumption of decay.** When the directive roughly doubled added time, the per-minute scoring rate in those minutes barely moved: PRE second-half stoppage ran 0.086 (24 goals / 279 live-minutes), POST 0.080 (49 goals / 615 live-minutes), with more than twice the live stoppage minutes. If the extra minutes were mostly teams running out a decided game, the rate would have cratered. It held. That is the tell that stoppage time is not just ordinary football with the clock still running. Being in it is psychologically different, and the urgency it manufactures would not exist in a stopped-clock version of the same match. So the truth sits nearer the top of the model's band than the bottom.

Now the confound, honestly. Part of why post-directive productivity stayed high is composition, not psychology. In POST matches fewer minutes were live by the 90th, because regulation wasting rose once teams learned time gets topped up later, so more of each match slid into stoppage. And the later minutes of a foreshortened live set are the most productive minutes there are. Some of the stoppage premium is therefore just "these are late minutes of a shortened game," which is exactly the endogeneity the decay and the open-play floor already discount. The honest reading: the premium is partly real urgency and partly selection, the model prices both down toward open play, and the answer barely moves either way.

**Objection 2: The high rate is just trailing teams chasing a level scoreline.**

When a side trails late it throws bodies forward, so maybe the premium is only desperate, level matches. If so, it would collapse when the game is not close. It doesn't. Second-half stoppage scores at about the same rate whether the game is level at 90 (0.0886) or not (0.0786), with heavily overlapping intervals. Conditioning the entire model on score state at 90 barely moves the headline, from 24.8% to 24.5%.

**Objection 3: The high rate is a knockout-stage effect.**

Maybe the late rate is inflated by win-or-go-home stakes. It isn't. Split the same window by match type: group stage 0.0847 (56 goals / 660.8 live-minutes) against elimination 0.0727 (17 goals / 233.7 live-minutes), the point estimate actually leaning *higher* in the group stage (rate ratio 1.17, binomial p = 0.69). There is no separate elimination effect to price.

**Objection 4: The result figure assumes a goal is equally likely to fall to either team.**

When a team leads by one at 90, the result flips only if the trailing side scores, and the chasing team scores more often than the leader, so a flat 50/50 split should understate flips. The model does split omitted-time goals 50/50. Measured in the data, the trailing team takes 0.548 of the goals scored in lead-by-one stoppage situations (n = 31, interval spanning 0.5). Sweeping that split across the whole plausible range, 0.40 to 0.60, moves the result figure only between 12.0% and 13.9%, and leaves the scoreline headline untouched, because the scoreline asks for any extra goal by either side and never uses the split.

## Results and sensitivity

The whole result on one page.

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
| **λ source** | all-pooled **24.8** · POST-only 23.7 · regime-matched 24.9 · PRE-only 27.3 | ~3.6 pts |
| **Gross-up** (in-stoppage wasting) | off 21.4 → **on 24.8** → geometric 26.0 | ~4.6 pts |
| **Decay half-life** | h=2 23.3 · **h=4 24.8** · h=8 26.1 | ~2.8 pts |
| **Conditioning** | overall **24.8** · split by tied/not-tied 24.5 | ~0.3 pts |
| One-at-a-time band | **21.4% – 27.3%** | 5.9 pts ≈ 0.9× sampling |
| Full **joint** envelope | **18.9% – 28.6%** | 9.7 pts ≈ 1.4× sampling |

The one-at-a-time band (5.9 pts) is about the size of the sampling CI (6.9 pts), and the joint envelope (9.7 pts) only modestly exceeds it. The headline does not hinge on any single knob. The PRE-only λ source sets the top of the band at 27.3%, on a thin, wide-interval PRE sample; the central pooled rate is the one to read.

Flip mechanics: the model splits omitted-time goals 50/50 between the two teams (Objection 4) and treats any match leading by two or more at 90 as unflippable. 95 of the 314 matches were already decided by two or more goals at 90, so they cannot flip at all.

**The honest limitation.** The owed-stoppage estimator is anchored on World Cup 2018, then frozen and applied unchanged to the other five tournaments. That transfer crosses the 2022 directive: the one calibration tournament sits on the PRE side, while the headline mostly lives on the POST side, where referees were explicitly told to behave differently. And the extrapolation is large. Owed time runs 17 to 25 minutes a match across the POST tournaments against 12.7 for 2018, with Copa América and AFCON nearly double the calibration level. The model's most exposed quantity is exactly where it can't be directly verified. It is validated only indirectly, through the frozen-2018 constants and the 2022 ball-in-play point. I would rather name that than bury it.

## What the missing minutes cost, and why it's live right now

We are in the middle of a World Cup, which makes this less a measurement exercise than a running indictment, because the errors do not stay local. A match is the unit, but a tournament is a bracket, and brackets compound.

Start in the group stage, where the margins are thinnest. Teams advance on goal difference and goals scored, often separated by a single goal across three matches. The number that bites here is the scoreline figure, not the result figure. 24.8% of matches would have finished with a different score under correctly-added time, and a changed score is exactly what moves goal difference. A team can go out on a tiebreaker built from minutes that were never played. Then it stacks. Lay a one-in-eight chance of a flipped *result* end to end across a seven-game run to the final and, under a simple independence assumption, it is better than even odds that at least one result along the path would have broken differently. The team that lifts the trophy is probably the team that should be there. The bracket that delivered it is not obviously the bracket the rules would have produced.

It is fair to ask whether the current fix is working. FIFA keeps changing the regime. The 2022 directive told referees to add time more fully, and the boards rose without closing the gap. For 2026, Pierluigi Collina, who chairs the referees committee and drove the 2022 change, shifted emphasis again, adding throw-in and goal-kick countdown clocks. Early signs are cautiously positive: less overt time-wasting, ball-in-play roughly stable. *[VERIFY: 2026 in-tournament figures are external to my six-tournament dataset; confirm "less wasting, stable ball-in-play" against live data before publishing.]* But a countdown clock on the stadium screen changes what stoppage time looks like more than what it adds up to. The boards are visible. The minutes that never get played are not.

And here is the part no measurement settles: most fans don't want these minutes anyway. During Qatar, my friends were not annoyed that stoppage time was being wasted, or that a stoppage *inside* stoppage time almost never gets added back. They were annoyed by the added time itself, by being made to sit through eight extra minutes when they wanted the game to end. The reform gave them more of the thing they disliked, while the quieter theft, the live football removed from the game, went unremarked.

So let me put it in the plainest terms. An extra five minutes sounds like nothing. But at the rate teams actually score in second-half stoppage (0.0816 goals per live minute), five minutes is worth about four-tenths of a goal a match, and even at the ordinary open-play floor (0.0427) it is about a fifth. Goals are rare and lumpy, and a fifth of a goal is not small when it is spread across a knockout bracket where one goal is the whole tournament. High-variance events decide these competitions, and the minutes most likely to produce them are precisely the minutes most reliably left off the clock. To anyone who shrugs that it is only five minutes: that is the point you are missing.

[^1]: I update my stoppage-time estimate for post-directive tournaments to count all goal-celebration stoppage, rather than 25%, which I calibrated to Nate.

---

The full pipeline — every stage, every table, every assumption, reproducible end to end — is here: **https://github.com/matkin123/Stoppage-Time**
