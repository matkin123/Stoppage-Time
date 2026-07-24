# The 2026 World Cup Played the Most Stoppage Time in History. Most of It Was Water Breaks.

**FIFA's reforms changed what stoppage time is. They haven't fixed how it's counted.**

---

*This piece uses data from all 96 WC2026 matches through the Round of 16, supplied by Opta via Sky Sports. [My previous piece](link) covered six major international tournaments through the pre-2026 era.*

---

The 2026 World Cup played more stoppage time per match than any tournament in our analysis: 12.4 minutes on average. That number is also misleading.

About seven of those minutes, per match, were mandatory hydration breaks: referee-called stoppages for heat management that FIFA added for 2026 as part of a broader set of rule changes. Strip them out, and the genuine stoppage at this World Cup was 5.3 minutes per match, below any tournament before the 2022 directive.

![Non-hydration stoppage time per tournament: WC 2026 falls below pre-directive levels once hydration breaks are removed](../figures/sky_wc2026/stoppage_by_tournament_bordered.png)

That is real progress, in its narrow way. FIFA's head referee Pierluigi Collina reversed course for 2026: after Qatar, which roughly doubled added time while actually reducing ball-in-play minutes, he introduced countdowns for throw-ins and goal-kicks. The data is consistent with those rules having worked at the margins. Routine time-wasting appears to have come down.

But the hydration breaks are mandatory, not compensatory. They do nothing to address the stoppages that are still systematically under-counted: VAR reviews, injuries (and "injuries"), goal celebrations, arguments with the referee. The countdown clock helps with throw-ins. It does not help with any of those.

## The gap

England 3-2 Mexico, the match of the tournament. After Gordon was fouled in the box, Kane converted at 60' to make it 3-1. Jiménez headed in at 69', and the last 20 minutes became a Mexican siege on the English goal. At 90', the board showed 12 minutes of added time. The match log shows 18 minutes were owed. England held on. Mexico had six extra minutes sitting unclaimed.

![Owed vs. played stoppage time per match: all 96 WC2026 matches, regulation halves](../figures/sky_wc2026/agg_01_scatter_estimate_vs_played_wide.png)

That is not a one-off. Every single WC2026 match ended too early: 100% of 96 matches owed more than was played, by an average of seven minutes. The scatter above plots owed against played. No dot lands above the diagonal.

## Why the missing minutes matter

Goal-scoring in 2nd half stoppage time at WC2026 ran at nearly twice the open-play rate: 0.081 goals per live minute versus 0.046.

![Goals per live minute by phase: 2H stoppage time is nearly twice the open-play rate](../figures/sky_wc2026/agg_02_productivity_by_bucket_bordered.png)

That premium appears in every tournament I have measured. It persists here, under the new rules. The minutes most likely to change a scoreline are the minutes most reliably left off the clock.

## The number

Applying the same Poisson model from my [previous piece](link) to the Opta data: if stoppage time were measured and awarded correctly at the 2026 World Cup, **23% of matches would have ended with a different scoreline [95% CI: 20.5%–26.5%]**, and **10% with a different result [8.5%–11.2%]**.

These figures are consistent with, and slightly higher than, the six-tournament headline I reported before (21.4% scoreline, 10.8% result flip). The confidence interval is tighter here because the Opta data records wall-clock dead time directly, without the event-log estimator I had to build for the StatsBomb data.

## What changed, and what didn't

FIFA made real changes for 2026. Countdowns on throw-ins and goal-kicks appear to have reduced routine time-wasting. Genuine stoppage falling below pre-directive levels is not what you'd expect if nothing had improved.

What hasn't changed: the structural under-counting of VAR, injuries, and celebrations. Those are larger sources of delay and harder to enforce than a countdown clock. The hydration breaks now dominate the headline stoppage number and make the figure less interpretable, not more. They inflate the total without compensating for the stoppages that actually matter.

One in four matches at this World Cup would have ended differently under the rulebook. The countdown timer doesn't help with that.

The full pipeline, reproducible end to end, is on my [GitHub](https://github.com/matkin123/Stoppage-Time).
