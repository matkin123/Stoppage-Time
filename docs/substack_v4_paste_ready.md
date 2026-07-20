# substack_v4_paste_ready.md — ADR-0040 copy-paste update

Generated 2026-07-20. The **live Substack post** still carries ADR-0039 numbers (23.3% /
12.1%). This file gives you the **complete text** of every paragraph that changes, ready to
paste directly into the Substack editor. Replace the whole paragraph — don't find-replace
inside Substack.

Image swaps are called out in each block. See the **Image Checklist** at the bottom.

---

## BLOCK 1 — Opening paragraph

**Find:** the paragraph that begins "If stoppage time were measured correctly…"
**What changed:** 23.3% → 21.4%, [20.1%, 27.3%] → [18.2%, 25.2%], 12.1% → 10.8%, [10.4%, 14.2%] → [9.1%, 12.8%]

---

If stoppage time were measured correctly, I estimate that **21.4%** of matches in the last six major international tournaments would have finished with a different scoreline [95% CI: 18.2%, 25.2%] — and **10.8%** with a different result [9.1%, 12.8%] (World Cups '18 & '22, Euros '20 & '24, Copa '24, AFCON '23).

---

## BLOCK 2 — Nate calibration paragraph (Methodology, Step 1)

**Find:** the paragraph starting "Stoppage *played* is the easy half…"
**What changed:** r 0.870 → 0.836, average error 1.67 → 1.54 min, owed mean 17.0 → 16.2 min,
omitted mean 8.2 → 7.3 min, positive in 95% → 98% of matches.

**Also swap the image directly above this paragraph** (the Nate calibration scatter):
→ upload `figures/f07_nate_calibration_bordered.png`

---

Stoppage *played* is the easy half — whistle-to-whistle added time, read straight off the event clock — and my played clock matches his almost exactly (r = 0.992). That near-exact match is what makes the owed estimate believable: Nate, with a stopwatch and no access to this pipeline, found the same shortfall (r = 0.836, average error 1.54 minutes). Across the 314 matches, the owed stoppage average (mean) is 16.2 minutes and the omitted average is 7.3 minutes, positive in 98% of matches.

---

## BLOCK 3 — Decay band sentence (Objection 1)

**Find:** the sentence "The whole decay band runs from…"
**What changed:** 22.0% → 20.2% (fastest), 24.5% → 22.4% (slowest), 23.3% → 21.4% headline

This is a single sentence; only replace this sentence, not the whole paragraph.

---

The whole decay band runs from 20.2% (fastest decay) to 22.4% (slowest), under three points around the 21.4% headline.

---

## BLOCK 4 — Objection 2, score-state paragraph

**Find:** the paragraph starting "2nd half stoppage scores at about the same rate…"
**What changed:** headline 23.3% → 21.4%, conditioned 23.1% → 21.0%

---

2nd half stoppage scores at about the same rate whether the game is level at 90 (0.0886 [0.0567, 0.1318]) or not (0.0786 [0.0581, 0.1039]), with heavily overlapping intervals. Conditioning the entire model on score state at 90 barely moves the headline, from 21.4% to 21.0%.

---

## BLOCK 5 — Objection 3, stage-source paragraph

**Find:** the paragraph starting "Split the same window by match type…"
**What changed:** group stage 24.4% → 22.5%, knockouts 20.1% → 18.2%, central 23.3% → 21.4%

---

Split the same window by match type: group stage 0.0847 (56 goals / 660.8 live-minutes) against elimination 0.0727 (17 goals / 233.7 live-minutes), the point estimate actually leans *higher* in the group stage (rate ratio 1.17, binomial p = 0.69). There is no separate elimination effect to price into the model. Carried all the way through: source every match's rate from the group stage alone and the headline lands at 22.5%; from the knockouts alone, 18.2% — both inside the envelope, with the all-matches central at 21.4% (the sensitivity table shows this as the knockout-vs-group row).

---

## BLOCK 6 — Objection 4, flip split sweep sentence

**Find:** the sentence "Sweeping that split across the whole plausible range…"
**What changed:** 11.2%–12.9% → 10.0%–11.5%

Single sentence replacement:

---

Sweeping that split across the whole plausible range, 0.40 to 0.60, moves the result figure only between 10.0% and 11.5%.

---

## BLOCK 7 — Objection 5, stakes sentence

**Find:** the sentence "First, let's set the stakes: the predicted flip rate…"
**What changed:** flip 12.1% → 10.8%, tied 7.46% → 6.7%, lead-by-one 4.61% → 4.1%

Single sentence replacement:

---

First, let's set the stakes: the predicted flip rate (10.8%) decomposes into tied matches (6.7%) and lead-by-one matches (4.1%). This objection touches second group.

---

## BLOCK 8 — Objection 5, Elo re-pricing paragraph

**Find:** the paragraph starting "Within the 121 lead-by-one matches…"
**What changed:** 0.44 pts moves result to "between 12.1% and 12.5% — inside the [10.4%, 14.2%] interval"
→ now "between 10.8% and 11.2% — inside the [9.1%, 12.8%] interval"

---

Within the 121 lead-by-one matches, the objection still falls flat. I pulled pre-match World Football [Elo rankings](https://en.wikipedia.org/wiki/World_Football_Elo_Ratings) for all 314 matches: in lead-by-one situations the leader is the stronger side 60% of the time. The average Elo gap is 38, because the lead-by-one subset already filters many of the lopsided mismatches this objection imagines (95 of the 314 matches are lead-by-2+ at 90, and therefore unflippable). Team quality genuinely predicts who scores next — a logistic fit on the Elo gap is significant — but the trailing team's *late chase* outweighs that *team quality* edge until the leader is about 146 Elo stronger, a bar only 39 of the 121 matches (32%) clear. So the trailing side still takes more than half the goals: 55% in 2nd half stoppage time (n = 31), and 51% at any minute of lead-by-one matches (n = 287). Re-pricing every match's split by its own quality-conditioned trailing-share moves the result figure by at most 0.44 points, to between 10.8% and 11.2% — inside the [9.1%, 12.8%] interval.

---

## BLOCK 9 — Results and sensitivity, uncertainty paragraph

**Find:** the paragraph starting "Two kinds of uncertainty, kept apart…"
**What changed:** CI [20.1%, 27.3%] → [18.2%, 25.2%], width 7.1 pts → 7.0 pts,
band 20.2–25.6% → 19.2–23.7%, envelope 17.3–27.0% → 16.3–24.9%

**Also swap both table images in this section:**
→ Headline results table: upload `figures/t_headline_results.png`
→ Sensitivity grid table: upload `figures/t_sensitivity_grid.png`

---

Two kinds of uncertainty, kept apart. *Sampling* uncertainty is the bootstrap CI **[18.2%, 25.2%]** (width 7.0 points): over 1,000 draws, each goal-rate cell is redrawn from a Jeffreys–Gamma posterior and a shared owed-stoppage estimator error is split across the two halves. *Specification* uncertainty is how the headline moves as defensible modeling choices change, one at a time (the 19.2–23.7% band) or all jointly (the 16.3–24.9% envelope).

---

## BLOCK 10 — Results and sensitivity, band interpretation paragraph

**Find:** the paragraph starting "The one-at-a-time band…"
**What changed:** band 5.5 pts → 4.5 pts, "about the size of" → "below", CI 7.1 → 7.0 pts,
envelope 9.7 pts → 8.6 pts, top of band 25.6% → 23.7%, group 24.4% → 22.5%, KO 20.1% → 18.2%

---

The one-at-a-time band (4.5 pts) is below the sampling CI (7.0 pts), and the joint envelope (8.6 pts) only modestly exceeds it. The headline does not hinge on any single knob. The PRE-only λ source sets the top of the band at 23.7%, on a thin, wide-interval PRE sample; the central pooled rate is the one to read. Sourcing every match's rate from one stage moves the headline modestly either way — 22.5% from the group stage, 18.2% from the knockouts — and both stay inside the envelope.

---

## BLOCK 11 — Limitations, calibration owed-range paragraph

**Find:** the paragraph starting "The calibration that anchors the entire model…"
**What changed:** "roughly 21 minutes" → "roughly 19 minutes", "12.7 minutes" → "13 minutes"

---

The calibration that anchors the entire model — the owed-stoppage estimator in Step 1 — is fit on World Cup 2018 only. That's the lone tournament where an independent observer measured the truth by hand. The residual term this calibration produces is then frozen and applied unchanged to the other five tournaments. This application crosses the 2022 stoppage time policy change, when owed stoppage time jumped from 13 minutes (2018 World Cup) to roughly 19 minutes. While my mechanics for estimating owed stoppage time update to reflect the policy change (e.g., by capturing the full time spent on celebrating goals, rather than the excess), the estimate cannot be validated externally. (P.S. If someone wants to grab a stopwatch and hand-measure dozens of post policy change matches, let me know.)

---

## BLOCK 12 — Limitations, flip decomposition paragraph

**Find:** the paragraph starting "The result figure asks more of that model…"
**What changed:** 12.1% → 10.8%, tied 7.46 pts → 6.7 pts, lead-by-one 4.61 pts → 4.1 pts,
"4.6-point slice" → "4.1-point slice", "close to 12%" → "close to 11%"

---

The result figure asks more of that model than the scoreline does, so I report it separately. Flipping a scoreline needs one more goal by either side. Changing a result requires knowing which side scores it, which requires a per-match estimate of each team's scoring probability that this model does not build. Objections 4 and 5 discuss how much that gap matters. The 10.8% flip splits into 6.7 points from matches level at 90, where any goal flips the result no matter who scores, and 4.1 points from one-goal games, where team quality decides. Only that second slice is sensitive to a better per-team model. I tested the 4.1-point slice directly ([ADR-0034](https://github.com/matkin123/Stoppage-Time/blob/main/docs/decisions.md)): swapping the flat 50/50 split for a per-match, Elo-conditioned one moves the result figure by at most 0.4 points. So I believe a more sophisticated model would leave the aggregate flip result close to 11%.

---

## BLOCK 13 — Limitations, Copa/AFCON owed-times paragraph

**Find:** the paragraph starting "The six tournaments are pooled but not identical…"
**What changed:** Copa América 2024 22.9 min → 20.4 min, AFCON 2023 25.2 → 21.9 min, Euros "about 14" unchanged

---

The six tournaments are pooled but not identical. For instance, owed stoppage runs higher in Copa América 2024 (20.4 min) and AFCON 2023 (21.9) than in the Euros (about 14). But the model pools only one thing across them: the stoppage time goals-per-live-minute rate, applied to each match's own omitted minutes. Re-sourcing it from PRE-only, POST-only, or regime-matched cohorts keeps the headline inside its band. Truth is, I pool the six because I need the sample. Given a choice between widening the regional pool (Copa, AFCON) and widening the time horizon (pre-2018), I expect the regional pool to produce the more accurate model, because football varies less across space than across time. For example, the national squads all draw overwhelmingly from the same club leagues, so the region now marks a federation more than a style. (For what it's worth, the mean pre-match Elo gap between opponents runs 157 to 203 across all six tournaments, a spread under 50 Elo. AFCON differs on absolute strength, its teams averaging about 300 lower, but the relative gaps are stable.)

---

## BLOCK 14 — Reflections, "1 in 4" sentence

**Find:** the sentence "Recall that roughly 1 in 4 scorelines change…"
**What changed:** "1 in 4" → "roughly 1 in 5"

Single sentence replacement (inside bullet point #2 of the WC2026 section):

---

Recall that roughly 1 in 5 scorelines change when stoppage time is awarded correctly.

---

## IMAGE CHECKLIST

All images below have been regenerated as of 2026-07-20 and contain ADR-0040 data.

| Section in post | File to upload | Changed by ADR-0040? |
|---|---|---|
| Step 1 — scatter of owed vs played (all 314 matches) | `figures/requested/agg_01_scatter_estimate_vs_played_wide_bordered.png` | YES — % above line now 98%, typical-match annotation ~8 min played / ~15 min owed, footer r=0.836/MAE=1.54 |
| Step 1 — Nate calibration scatter | `figures/f07_nate_calibration_bordered.png` | YES — model panel shows r=0.836, MAE=1.54 min (was 0.870/1.67) |
| Results — headline results table | `figures/t_headline_results.png` | YES — 21.4%/10.8% and updated CIs |
| Results — sensitivity grid table | `figures/t_sensitivity_grid.png` | YES — all X% values updated |
| Objection 1 — goal scoring bar chart | `figures/requested/agg_02_productivity_by_bucket_bordered.png` | NO — rates unchanged; existing image is fine |
| Step 1 — restart allowances table (Nate's ladder) | `figures/t_restart_allowances.png` | NO — static, no update needed |
| Objection 1 — productivity decay chart | `figures/f06_productivity_decay_bordered.png` | NO — lambda values unchanged |
| Objection 2 — game-state table | `figures/requested/t01_gamestate_productivity.png` | NO — rates unchanged |

**Note on `figures/requested/Stoppage Error.png` and `Goal Productivity.png`:** These files
(Jul 17 timestamp) are not generated by any pipeline script and cannot be automatically
regenerated. The publication-quality equivalents that ARE regenerated are:
- Scatter → `agg_01_scatter_estimate_vs_played_wide_bordered.png` (use this instead)
- Bar chart → `agg_02_productivity_by_bucket_bordered.png` (rates unchanged, either version fine)

---

## VERIFICATION — locked numbers (ADR-0040, 2026-07-20)

All numbers in this file match `docs/decisions.md` (ADR-0040) and `docs/numbers_ledger.md`:

| Metric | Value |
|---|---|
| Headline scoreline | **21.4%** [95% CI: 18.2%, 25.2%] |
| Headline flip | **10.8%** [9.1%, 12.8%] |
| Estimator fit | r = 0.836, MAE = 1.54 min |
| Owed mean / Omitted mean | 16.2 min / 7.3 min |
| Positive in % of matches | 98% |
| Decay band | 20.2% (h=2) – 22.4% (h=8) |
| Score-state conditioned | 21.4% → 21.0% |
| Stage robustness | 22.5% (group), 18.2% (KO), 21.4% (central) |
| Flip split sweep (0.40–0.60) | 10.0% – 11.5% |
| Flip decomposition | tied 6.7%, lead-by-one 4.1% |
| Elo re-pricing bound | to 10.8%–11.2%, inside [9.1%, 12.8%] |
| 1-at-a-time band | 19.2%–23.7% (4.5 pts) |
| Joint envelope | 16.3%–24.9% (8.6 pts) |
| Copa 2024 owed | 20.4 min |
| AFCON 2023 owed | 21.9 min |
| WC2018 owed (calibration anchor) | 13 min |
| Post-directive owed range | ~19 min |

*Source of truth: `docs/decisions.md` (ADR-0040), `docs/numbers_ledger.md`.*
*Full target text: `docs/substack_post_v4.md`.*
