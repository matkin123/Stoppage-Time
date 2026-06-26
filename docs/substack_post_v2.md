# The Stoppage Time That Never Gets Played

*A fully reproducible measurement across the last six major international tournaments (314 matches). Owed stoppage vs. stoppage actually played — and what the missing minutes would have changed.*

---

Stoppage time is a sham.

Over the last six major international tournaments, if stoppage time were awarded according to the laws of the game, I estimate that **24.8%** of matches would have finished with a different scoreline, and **13.0%** with a different result.

Those are the only two modeled numbers in this piece, and I keep them apart everywhere: a *scoreline* can change without the *result* changing. Both ship with a confidence interval and a full sensitivity table, never as bare point estimates — the scoreline figure is **24.8% [95% CI 21.7%, 28.6%]**, the result figure is **13.0% [95% CI 11.3%, 15.1%]**. "About 1 in 8" is that 13.0% (one match in 7.7, to be exact). Everything below traces to a script, a checked-in table, and a documented assumption. That is the standard of proof, and the entire pipeline is public.

## Why I dug into this

The motivation for this model comes from two insights about football matches:

**1. Stoppage time is systematically under-awarded.** During the 2018 World Cup, Nate Silver found that refs omit roughly half of true stoppage time. Building on Nate's work, I pulled the data for every match in the last 6 major international tournaments (World Cup '18 & '22, Euros '20 & '24, Copa '24, AFCON '23), and plotted the relationship between true versus played stoppage time.†

![Owed stoppage vs. stoppage actually played, all 314 matches](../figures/requested/agg_01_scatter_estimate_vs_played.png)

*My estimate of owed stoppage (vertical) against the stoppage actually played (horizontal), every match across all six tournaments. The cloud sits well above the line of equality: almost every match owes more added time than it gets.*

**2. Teams are much more productive during stoppage time.**

![Goals per live minute by stage of the match](../figures/requested/agg_02_productivity_by_bucket.png)

*Goals per live minute, by stage of the match. The stoppage-time bars (highlighted) tower over open play — second-half stoppage runs about 1.9× the open-play rate.*

In short, referees chronically under-award the crucial minutes that flip match outcomes.

*† Others have corroborated this finding, and measured biases that impact stoppage-time allocation. [VERIFY: add the specific external citations — e.g. the post-2022 league analyses of under-added time — before publishing; those figures sit outside my six-tournament dataset and I have not independently confirmed them.]*

## The data

Every number here rests on one dataset, so it is worth a paragraph on what it is and where it is thin.

StatsBomb (now Hudl StatsBomb) hand-codes each match into a timestamped log of on-ball events: pass, shot, tackle, throw-in, foul, card, substitution, ball out of play. It is one of the sport's gold-standard providers, and professional clubs buy the same feed to scout players and analyze opponents, among them Club Brugge, AZ Alkmaar, and Panathinaikos. Since 2018 StatsBomb has released part of that professional database free for research. This project runs entirely on the free release.

The sample is the 314 matches of the last six major international tournaments, split by the 2022 directive: 115 PRE (World Cup 2018, Euro 2020) and 199 POST (World Cup 2022, Euro 2024, Copa América 2024, AFCON 2023). Each match carries roughly 3,000 to 3,600 logged events, about 30 to 37 per minute.

The data is strong but not uniform, and the model is built around where it is weakest:

- Only two of the six tournaments have an independent ball-in-play figure to check against. Opta published regulation ball-in-play for World Cup 2018 (54:50) and World Cup 2022 (58:04). The other four inherit a method calibrated on those two.
- StatsBomb's explicit "injury stoppage" event is logged inconsistently (in 94% to 100% of matches, depending on tournament), so the model never trusts it directly. It reconstructs dead time from the timestamps instead.
- Logging density varies. AFCON 2023 and Copa América 2024 are the thinnest (about 30 events a minute, and the most off-camera play); World Cup 2018 is the most idiosyncratic, with twice as many long no-event gaps as any other tournament. These are real differences in football and in coverage, and they set the limits I return to at the end.

## How the counterfactual actually works

The core idea is simple. Take all 314 matches as played. For each, append the stoppage the referee should have added but didn't, and ask one question: would at least one more goal plausibly have dropped in? Average that probability across the 314 matches. That average is the headline. The work is making each step checkable.

**Step 1 — Measure the live football, and check it against outside numbers.** When the ball is dead, StatsBomb logs nothing, so gaps open in the timestamps. Those gaps reconstruct *ball-in-play*. The check: for 2022, the reconstruction reads 57:40 against Opta's 58:04 (−24s); for 2018, 56:00 against Opta's 54:50 (+70s), with FiveThirtyEight's 55:18 in between. One global threshold sets how long a silent gap must run before the ball counts as dead. Sweeping it from 12 to 30 seconds is the ±1 minute of per-match uncertainty I carry rather than a false-precision point. The headline barely moves across that range, because the live-football level enters the final number once in the scoring rate and once in the exposure, and the two places largely cancel.

**Step 2 — Separate stoppage *owed* from stoppage *played*, and check that too.** Played stoppage is easy: whistle-to-whistle added time, read off the event clock. Owed stoppage is the hard part. The Laws of the Game (Law 7) tell the referee to add on all time lost to substitutions, injuries, celebrations, cards, VAR checks, and time-wasting, but they put a number on none of it. There is no stated limit on how long a routine throw-in or goal kick may take before the delay counts as lost time. So to measure owed stoppage you have to supply the thresholds the Laws omit. Nate Silver's 2018 stopwatch study supplied them, and I adopt his table unchanged:

| Routine restart | Normal allowance (excess beyond this counts as owed) |
|---|---|
| Throw-in | 20 s |
| Goal kick | 30 s |
| Corner kick | 45 s |
| Free kick | 60 s |

A throw-in that takes 50 seconds owes 30; one that takes 15 owes nothing. Genuine stoppages (celebrations, subs, cards, injuries) are credited separately. One refinement matters, because it tracks the 2022 directive exactly. The directive instructed referees to add the *full* goal celebration to stoppage, so for POST matches the whole goal-to-kickoff gap is credited, which is what the rulebook now demands. For PRE matches, where celebrations were not fully added (Nate's 2018 numbers confirm it), the celebration gets the same excess-over-allowance treatment as the other restarts, with a 60-second allowance. Adding that one rule is what tightened the 2018 calibration below from r = 0.825 to 0.875, and average error from 2.44 minutes to 1.77.

Then the estimator is calibrated against the one independent ground truth that exists: Nate Silver's by-hand measurement of all 32 World Cup 2018 matches, where he recorded both the stoppage that should have been added and the stoppage that was.

![Validation against Nate Silver's hand-measured 2018 data](../figures/f07_nate_calibration.png)

*Validation against Nate Silver's independent, hand-measured World Cup 2018 data (32 matches). Left: my owed-stoppage estimate against his should-have-been-added minutes (r = 0.875, average error 1.77 minutes). Right: my stoppage-played clock against his actually-played minutes (r = 0.992, near-exact). The dashed line is perfect agreement.*

The near-exact right panel is what makes the left panel believable: Nate, with a stopwatch and no access to this pipeline, found the same shortfall. Across the 314 matches, owed stoppage averages about 17.6 minutes a match and played stoppage about 8.9, leaving roughly 8.8 omitted minutes, positive in 97% of matches, a bit over half of it live ball once dead time is stripped out.

This shortfall is not a relic of the pre-directive era. The 2022 directive did push the boards up: played stoppage rose from about 6.8 minutes a match (PRE) to 10.0 (POST). But the extra minutes were substantially self-defeating. Across this era about half of all played stoppage is itself dead time (50.6%), and the dead share rose with the boards, from 48% PRE to 52% POST. Of the 3.2 extra minutes the directive bought, only about 1.3 became live football. The rest fed the time-wasting it was meant to punish. More added time, more wasting, roughly flat live ball.

**Step 3 — Price the missing minutes.** Each omitted live minute is assigned a goal rate. Expected extra goals is rate times minutes, and the chance of at least one extra goal follows from the Poisson formula. Start with the simplest version:

```
μ  =  (goal rate) × (omitted live minutes)
P(≥1 extra goal)  =  1 − e^(−μ)
Headline  =  average of P across the 314 matches
```

Three terms need defining, and that is the whole model.

*Omitted live minutes.* Owed minus played gives omitted *clock*. Scoring differs by half, so the window is split into first and second half:

```
μ  =  λ₁ · ℓ₁  +  λ₂ · ℓ₂
```

where `λ_h` is goals per live minute in half *h* and `ℓ_h` is the omitted live minutes in that half.

*The live share, and what an omitted minute looks like.* Converting omitted clock to omitted live needs a live share, and that assumption does real work, so it is explicit. An omitted minute is assumed to look like the average minute of that *same half* — its regulation play plus the added time that was actually played — not like the few, unusually dead minutes of stoppage the referee did add. The same reference period also sets how much of the re-added time would itself be wasted: referees would have to top up for stoppage *within* the stoppage, but only the genuine-stoppage share of dead time recurs, not ordinary dead-ball flow. Anchoring both factors to a 45-minute base, on the specific teams playing that day, is more defensible than reading them off the handful of skewed minutes that happened to be played.

*The rate.* `λ₁` is the first-half stoppage rate, held fixed. `λ₂` starts at the observed second-half stoppage rate and decays toward the open-play floor across the window. Putting it together, per match:

```
ℓ_h  =  max(0, owed_h − played_h) × (same-half live share) × (in-stoppage gross-up)
μ    =  λ₁ · ℓ₁  +  (decayed λ₂) · ℓ₂
P    =  1 − e^(−μ)
Headline  =  mean of P over 314 matches
```

That decay is the model's answer to the one real objection.

## The obvious objection

Add more time and teams won't keep scoring at the same rate.

True, and the model is built around it. Scoring is not even across a match: it climbs, and second-half stoppage is the most productive window on the field.

| Window | Goals per live-minute | Goals (n) |
|---|---|---|
| 2nd-half stoppage (the late-game peak) | **0.0816** | 73 |
| 1st-half stoppage | 0.0478 | 23 |
| Regulation open play (the floor) | **0.0427** | 675 |

That peak is 1.9× the open-play rate, and the reason is not the referee. It is how football is played late: a losing team commits bodies forward, defenses stretch, the game opens up. Which is the objection restated. The rate is endogenous to game state: the minutes observed at 0.0816 are selected for desperation, so pricing fresh, neutral minutes there would overstate the result. The model handles this three ways.

**First, the rate decays.** No omitted second-half minute is priced at the raw peak. Each is priced on a curve falling from 0.0816 toward the open-play floor of 0.0427, with a half-life swept from 2 to 8 minutes (central 4). The longer the hypothetical window, the closer its minutes are priced to ordinary open play. The floor *is* open play, so even under maximum decay an added minute is never priced below match-average football. It is still football.

![Decaying the productivity premium](../figures/f06_productivity_decay.png)

*Left: the per-minute rate assigned to an omitted second-half minute, decaying from the observed stoppage rate (0.0816) toward the open-play floor (0.0427), for half-lives of 2, 4 (central), and 8 minutes. Right: the average rate a match effectively receives as a function of its total omitted minutes. Because most windows are modest, the effective rate sits well above the floor but well below the raw peak.*

The whole decay band runs from 23.3% (fastest decay) to 26.1% (slowest), under three points around the 24.8% headline.

**Second, it is not just a tied-game artifact.** If the premium were only desperate, level matches, it would collapse when the game is not close. It doesn't. Second-half stoppage scores at about the same rate whether the game is level at 90 minutes (0.0886) or not (0.0786), with heavily overlapping intervals. Conditioning the entire model on score state at 90 barely moves the headline, from 24.8% to 24.5%.

**Third, it is not a knockout artifact.** Maybe the late rate is inflated by win-or-go-home stakes. It isn't. Split the same window by match type: group stage 0.0847 (56 goals / 660.8 live-minutes) against elimination 0.0727 (17 goals / 233.7 live-minutes), the point estimate actually leaning higher in the group stage (rate ratio 1.17, binomial p = 0.69). There is no separate elimination effect to price.

One piece of evidence cuts toward the model, and it is worth stating plainly. When the directive roughly doubled added time, the per-minute scoring rate in those minutes barely moved: PRE second-half stoppage ran 0.086 (24 goals / 279 live-minutes), POST 0.080 (49 goals / 615 live-minutes), with more than twice the live stoppage minutes. If the extra minutes were mostly teams running out a decided game, the rate would have cratered. It held. That is the tell that stoppage time is not just ordinary football with the clock still running. Being in it is psychologically different, and the urgency it manufactures would not exist in a stopped-clock version of the same match. So the truth sits nearer the top of the model's band than the bottom.

Now the confound, honestly. Part of why post-directive productivity stayed high is composition, not psychology. In POST matches fewer minutes were live by the 90th, because regulation wasting rose once teams learned time gets topped up later, so more of each match slid into stoppage. And the later minutes of a foreshortened live set are the most productive minutes there are. Some of the stoppage premium is therefore just "these are late minutes of a shortened game," which is exactly the endogeneity the decay and the open-play floor already discount. The honest reading: the premium is partly real urgency and partly selection, the model prices both down toward open play, and the answer barely moves either way.

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

The result figure rests on one extra assumption, and it holds. When a team leads by one at 90, the result flips only if the trailing side scores, so the model splits omitted-time goals 50/50 between the two teams (a lead of two or more cannot flip; a tied game flips on any goal). Measured in the data, the trailing team takes 0.548 of the goals scored in lead-by-one stoppage situations (n = 31, interval spanning 0.5). Sweeping that split across the whole plausible range, 0.40 to 0.60, moves the result figure only between 12.0% and 13.9%, and leaves the scoreline headline untouched, because the scoreline asks for any extra goal by either side and never uses the split.

One number I won't blur: scoreline (24.8%) is not result (13.0%). A scoreline can change without the winner changing, and **95 of the 314 matches** were already decided by two or more goals at 90 minutes, so they cannot flip at all. Conflating the two is the single most attackable sentence anyone could write about this work, so I state them apart, always.

**The honest limitation.** The owed-stoppage estimator is anchored on World Cup 2018, then frozen and applied unchanged to the other five tournaments. That transfer crosses the 2022 directive: the one calibration tournament sits on the PRE side, while the headline mostly lives on the POST side, where referees were explicitly told to behave differently. And the extrapolation is large. Owed time runs 17 to 25 minutes a match across the POST tournaments against 12.7 for 2018, with Copa América and AFCON nearly double the calibration level. The model's most exposed quantity is exactly where it can't be directly verified. It is validated only indirectly, through the frozen-2018 constants and the 2022 ball-in-play point. I would rather name that than bury it.

## What the missing minutes cost, and why it's live right now

We are in the middle of a World Cup, which makes this less a measurement exercise than a running indictment, because the errors do not stay local. A match is the unit, but a tournament is a bracket, and brackets compound.

Start in the group stage, where the margins are thinnest. Teams advance on goal difference and goals scored, often separated by a single goal across three matches. The number that bites here is the scoreline figure, not the result figure. 24.8% of matches would have finished with a different score under correctly-added time, and a changed score is exactly what moves goal difference. A team can go out on a tiebreaker built from minutes that were never played. Then it stacks. Lay a one-in-eight chance of a flipped *result* end to end across a seven-game run to the final and, under a simple independence assumption, it is better than even odds that at least one result along the path would have broken differently. The team that lifts the trophy is probably the team that should be there. The bracket that delivered it is not obviously the bracket the rules would have produced.

It is fair to ask whether the current fix is working. FIFA keeps changing the regime. The 2022 directive told referees to add time more fully, and the boards rose without closing the gap. For 2026, Pierluigi Collina, who chairs the referees committee and drove the 2022 change, shifted emphasis again, adding throw-in and goal-kick countdown clocks. Early signs are cautiously positive: less overt time-wasting, ball-in-play roughly stable. *[VERIFY: 2026 in-tournament figures are external to my six-tournament dataset; confirm "less wasting, stable ball-in-play" against live data before publishing.]* But a countdown clock on the stadium screen changes what stoppage time looks like more than what it adds up to. The boards are visible. The minutes that never get played are not.

And here is the part no measurement settles: most fans don't want these minutes anyway. During Qatar, my friends were not annoyed that stoppage time was being wasted, or that a stoppage *inside* stoppage time almost never gets added back. They were annoyed by the added time itself, by being made to sit through eight extra minutes when they wanted the game to end. The reform gave them more of the thing they disliked, while the quieter theft, the live football removed from the game, went unremarked.

So let me put it in the plainest terms. An extra five minutes sounds like nothing. But at the rate teams actually score in second-half stoppage (0.0816 goals per live minute), five minutes is worth about four-tenths of a goal a match, and even at the ordinary open-play floor (0.0427) it is about a fifth. Goals are rare and lumpy, and a fifth of a goal is not small when it is spread across a knockout bracket where one goal is the whole tournament. High-variance events decide these competitions, and the minutes most likely to produce them are precisely the minutes most reliably left off the clock. To anyone who shrugs that it is only five minutes: that is the point you are missing.

---

The full pipeline — every stage, every table, every assumption, reproducible end to end — is here: **https://github.com/matkin123/Stoppage-Time**
