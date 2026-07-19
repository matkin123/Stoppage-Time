# substack_post_v4 — PASTE-READY paragraphs (live post → ADR-0039 lock)

**What this is.** One copy-paste block per paragraph that changed, in article order, so you can
update the **live Substack post** (still at the as-published **24.8% / 13.0%**) to the current lock
(**23.3% / 12.1%**). Find the paragraph in your live post, select it, replace with the block here.

**Headline delta:** scoreline **24.8% → 23.3%** (CI **[21.7%, 28.6%] → [20.1%, 27.3%]**);
result-flip **13.0% → 12.1%** (CI **[11.3%, 15.1%] → [10.4%, 14.2%]**). Both moves downward, both
inside the originally-published envelope.

**How to read each entry:**
- The **fenced block is the paste text.** It's given in the same markdown your post uses
  (`**bold**`, `[text](url)`) — paste as-is if your editor accepts markdown, or re-apply the
  bold/links to match your live formatting.
- The primary block is **number-only** (minimal change to your published wording).
- Where the change map recommended a **prose fix**, it appears directly below as an **OPTIONAL**
  full-paragraph alternate — your call whether to use it.
- Paragraphs not listed here did **not** change; leave them as-is.
- Read the **"Checks before you publish"** section at the bottom before you post — it covers one
  unverified number, one thing to search-and-delete, and an optional revision note.

---

## 1. Headline (opening, right under "Stoppage time is a sham.")

*Changed: 24.8% → 23.3%; [21.7%, 28.6%] → [20.1%, 27.3%]; 13.0% → 12.1%; [11.3%, 15.1%] → [10.4%, 14.2%].*

```
If stoppage time were measured correctly, I estimate that **23.3%** of matches in the last six major international tournaments would have finished with a different scoreline [95% CI: 20.1%, 27.3%] — and **12.1%** with a different result [10.4%, 14.2%] (World Cups '18 & '22, Euros '20 & '24, Copa '24, AFCON '23).
```

---

## 2. "Stoppage time is systematically under-awarded" (the Nate Silver anchor)

*RECONCILED with paragraph 3. Two fixes: **96% → 95%** (matches the updated "Stoppage Error" figure and
paragraph 3), and the sentence now reports the **all-six-tournament** aggregate the figure actually
plots — so paragraphs 2 and 3 describe the same 314 matches and agree (95% too early, ~8-min average)
instead of appearing to contradict. Use this block:*

```
**1. Stoppage time is systematically under-awarded.** During the 2018 World Cup, Nate Silver [hand-measured](https://web.archive.org/web/20260408205134id_/https://fivethirtyeight.com/features/world-cup-stoppage-time-is-wildly-inaccurate/) every match in the group stage and found that referees under-award stoppage time in 97% of matches, by an average of 6 minutes. I pulled the stoppage time data across the five major tournaments since. The direction and magnitude of error is striking: across all six tournaments, 95% of matches ended too early, by an average of eight minutes.
```

**Why (verified against `data/interim/` — per-match owed − played over the production parquet):**
- All six tournaments (= all 314): **94.9% → 95%** ended too early, mean omitted **8.16 → 8.2 min**. This is what paragraph 3 *and* the figure report.
- Five tournaments since 2018 (excludes WC2018): **95.2%** too early, mean omitted **8.81 min** (median 8.11).
- WC2018 alone is the mildest (mean omitted **5.6 min**), so excluding it *raises* the average. That is why the published "8 min" for a five-only cohort sat *below* paragraph 3's all-314 "8.2 min" — an impossible ordering. And the as-published "96%" was simply stale; the true value is 95% in every cut.

**OPTIONAL alternate — keep paragraph 2 explicitly about the five tournaments you added to Nate's 2018.**
Honest five-only numbers are **95% / ~9 min** (95.2% / 8.81). This preserves "I extended Nate's work,"
but it reads ~1 min *above* paragraph 3's 8.2 min, so a careful reader may ask why — the all-six block
above avoids that entirely. If you use this, consider it fine as-is (the subset genuinely runs a touch
higher):

```
**1. Stoppage time is systematically under-awarded.** During the 2018 World Cup, Nate Silver [hand-measured](https://web.archive.org/web/20260408205134id_/https://fivethirtyeight.com/features/world-cup-stoppage-time-is-wildly-inaccurate/) every match in the group stage and found that referees under-award stoppage time in 97% of matches, by an average of 6 minutes. I pulled the stoppage time data across the five major tournaments since. The direction and magnitude of error is striking; 95% of those matches ended too early, by an average of nearly nine minutes.
```

---

## 3. Estimator fit (Methodology, Step 1 — the "played clock matches his almost exactly" paragraph)

*Changed: r 0.875 → 0.870; avg error 1.77 → 1.67 min; owed mean 17.6 → 17.0; omitted mean 8.8 → 8.2;
positive 96% → 95%. (Played-clock r = 0.992 UNCHANGED.)*

```
Stoppage *played* is the easy half — whistle-to-whistle added time, read straight off the event clock — and my played clock matches his almost exactly (r = 0.992). That near-exact match is what makes the owed estimate believable: Nate, with a stopwatch and no access to this pipeline, found the same shortfall (r = 0.870, average error 1.67 minutes). Across the 314 matches, the owed stoppage average (mean) is 17.0 minutes and the omitted average is 8.2 minutes, positive in 95% of matches.
```

---

## 4. Decay band (Objection 1 — "The whole decay band runs…")

*Changed: 23.3 → 22.0 (fastest); 26.1 → 24.5 (slowest); central 24.8 → 23.3.*

```
The whole decay band runs from 22.0% (fastest decay) to 24.5% (slowest), under three points around the 23.3% headline.
```

---

## 5. Natural experiment (Objection 1 — "a natural experiment in doubling added time")

*Changed: 0.086 (24/279) → 0.089 (37/415) PRE; 0.080 (49/615) → 0.075 (36/479) POST.*

**Primary (number-only):**

```
**Important context — a natural experiment in doubling added time.** When the 2022 directive roughly doubled second-half stoppage, the per-minute scoring rate barely moved: 0.089 PRE (37 goals / 415 live-minutes) to 0.075 POST (36 / 479). Being in stoppage looks genuinely different from ordinary football with the clock still running — the urgency it manufactures wouldn't exist in a stopped-clock version of the match — so pricing those minutes down toward open play, as the decay does, is probably conservative. One confound cuts the other way: POST teams wasted more regulation time once they learned it would be topped up, so more of each match slid past 90 into stoppage, and part of the premium is just "late minutes of a shortened game." Either way, the model prices both urgency and selection down toward open play, and the answer barely moves.
```

**OPTIONAL prose fix (CONTENT A).** As published the gap was ~7% ("barely moved" was fair); at the
new numbers it's a ~16% *decline*, so "barely moved" is a stretch. This rewrite is more accurate and
actually *strengthens* the point (scoring didn't rise even though 2nd-half stoppage doubled). Use this
block *instead of* the one above if you want the fix:

```
**Important context — a natural experiment in doubling added time.** When the 2022 directive roughly doubled second-half stoppage, the per-minute scoring rate moved only modestly, and if anything slightly *down*: 0.089 PRE (37 goals / 415 live-minutes) to 0.075 POST (36 / 479). Being in stoppage looks genuinely different from ordinary football with the clock still running — the urgency it manufactures wouldn't exist in a stopped-clock version of the match — so pricing those minutes down toward open play, as the decay does, is probably conservative. One confound cuts the other way: POST teams wasted more regulation time once they learned it would be topped up, so more of each match slid past 90 into stoppage, and part of the premium is just "late minutes of a shortened game." Either way, the model prices both urgency and selection down toward open play, and the answer barely moves.
```

---

## 6. Objection 2 (score-state conditioning)

*Changed: headline 24.8% → 23.3%; conditioned 24.5% → 23.1%. (Tied/non-tied rates UNCHANGED.)*

```
2nd half stoppage scores at about the same rate whether the game is level at 90 (0.0886 [0.0567, 0.1318]) or not (0.0786 [0.0581, 0.1039]), with heavily overlapping intervals. Conditioning the entire model on score state at 90 barely moves the headline, from 23.3% to 23.1%.
```

---

## 7. Objection 3 (knockout-stage effect)

*Changed: group 25.9 → 24.4; knockout 21.5 → 20.1; central 24.8 → 23.3. (Stage rates UNCHANGED.)*

```
Split the same window by match type: group stage 0.0847 (56 goals / 660.8 live-minutes) against elimination 0.0727 (17 goals / 233.7 live-minutes), the point estimate actually leans *higher* in the group stage (rate ratio 1.17, binomial p = 0.69). There is no separate elimination effect to price into the model. Carried all the way through: source every match's rate from the group stage alone and the headline lands at 24.4%; from the knockouts alone, 20.1% — both inside the envelope, with the all-matches central at 23.3% (the sensitivity table shows this as the knockout-vs-group row).
```

---

## 8. Objection 4 (50/50 split sweep)

*Changed: span "12.0% and 13.9%" → "11.2% and 12.9%". (0.548 / n = 31 / CI UNCHANGED.)*

```
The model does split omitted-time goals 50/50. Measured in the data, the trailing team takes 0.548 of the goals scored in lead-by-one stoppage situations (n = 31, 95% CI [0.375, 0.713]). Sweeping that split across the whole plausible range, 0.40 to 0.60, moves the result figure only between 11.2% and 12.9%.
```

---

## 9. Objection 5 — stakes ("First, let's set the stakes…")

*Changed: flip 13% → 12.1%; tied 7.86% → 7.46%; lead-by-1 5.12% → 4.61%.*

```
First, let's set the stakes: the predicted flip rate (12.1%) decomposes into tied matches (7.46%) and lead-by-one matches (4.61%). This objection touches second group.
```

---

## 10. Objection 5 — Elo re-pricing ("Within the 121 lead-by-one matches…")

*Changed: max move 0.38 → 0.44 points; band "12.9% and 13.4%" → "12.1% and 12.5%"; flip CI
[11.3%, 15.1%] → [10.4%, 14.2%]. (All Elo census internals UNCHANGED.)*

```
Within the 121 lead-by-one matches, the objection still falls flat. I pulled pre-match World Football [Elo rankings](https://en.wikipedia.org/wiki/World_Football_Elo_Ratings) for all 314 matches: in lead-by-one situations the leader is the stronger side 60% of the time. The average Elo gap is 38, because the lead-by-one subset already filters many of the lopsided mismatches this objection imagines (95 of the 314 matches are lead-by-2+ at 90, and therefore unflippable). Team quality genuinely predicts who scores next — a logistic fit on the Elo gap is significant — but the trailing team's *late chase* outweighs that *team quality* edge until the leader is about 146 Elo stronger, a bar only 39 of the 121 matches (32%) clear. So the trailing side still takes more than half the goals: 55% in 2nd half stoppage time (n = 31), and 51% at any minute of lead-by-one matches (n = 287). Re-pricing every match's split by its own quality-conditioned trailing-share moves the result figure by at most 0.44 points, to between 12.1% and 12.5% — inside the [10.4%, 14.2%] interval.
```

---

## 11. Results & sensitivity — "Two kinds of uncertainty…"

*Changed: CI [21.7%, 28.6%] → [20.1%, 27.3%]; width 6.9 → 7.1; lead band 21.4–27.3 → 20.2–25.6;
envelope 18.9–28.6 → 17.3–27.0.*

```
Two kinds of uncertainty, kept apart. *Sampling* uncertainty is the bootstrap CI **[20.1%, 27.3%]** (width 7.1 points): over 1,000 draws, each goal-rate cell is redrawn from a Jeffreys–Gamma posterior and a shared owed-stoppage estimator error is split across the two halves. *Specification* uncertainty is how the headline moves as defensible modeling choices change, one at a time (the 20.2–25.6% band) or all jointly (the 17.3–27.0% envelope).
```

---

## 12. Results & sensitivity — "The one-at-a-time band…"

*Changed: one-at-a-time 5.9 → 5.5; CI width 6.9 → 7.1; PRE-only top 27.3 → 25.6; group 25.9 → 24.4;
knockout 21.5 → 20.1. (Joint envelope 9.7 net UNCHANGED — if you ported an intermediate 10.0, set it
back to 9.7.)*

```
The one-at-a-time band (5.5 pts) is about the size of the sampling CI (7.1 pts), and the joint envelope (9.7 pts) only modestly exceeds it. The headline does not hinge on any single knob. The PRE-only λ source sets the top of the band at 25.6%, on a thin, wide-interval PRE sample; the central pooled rate is the one to read. Sourcing every match's rate from one stage moves the headline modestly either way — 24.4% from the group stage, 20.1% from the knockouts — and both stay inside the envelope.
```

---

## 13. Limitations — "The calibration that anchors the entire model…"

*Changed: "roughly 19" → "roughly 21" min. (12.7 min WC2018 UNCHANGED.) Note: this moved UPWARD —
removing low-owed Euro 2024 from POST raised the POST-pool mean owed. The surrounding sentence reads
correctly ("jumped … to roughly 21"), so no prose change is needed — see CHECK E.*

```
The calibration that anchors the entire model — the owed-stoppage estimator in Step 1 — is fit on World Cup 2018 only. That's the lone tournament where an independent observer measured the truth by hand. The residual term this calibration produces is then frozen and applied unchanged to the other five tournaments. This application crosses the 2022 stoppage time policy change, when owed stoppage time jumped from 12.7 minutes (2018 World Cup) to roughly 21 minutes. While my mechanics for estimating owed stoppage time update to reflect the policy change (e.g., by capturing the full time spent on celebrating goals, rather than the excess), the estimate cannot be validated externally. (P.S. If someone wants to grab a stopwatch and hand-measure dozens of post policy change matches, let me know.)
```

---

## 14. Limitations — "The result figure asks more of that model…"

*Changed: flip 13.0 → 12.1; tied 7.86 → 7.46; lead-by-1 5.12 → 4.61; "5.1-point slice" → "4.6-point
slice"; "close to 13%" → "close to 12%". ("at most 0.4 points" UNCHANGED — 0.44 rounds to 0.4.)*

```
The result figure asks more of that model than the scoreline does, so I report it separately. Flipping a scoreline needs one more goal by either side. Changing a result requires knowing which side scores it, which requires a per-match estimate of each team's scoring probability that this model does not build. Objections 4 and 5 discuss how much that gap matters. The 12.1% flip splits into 7.46 points from matches level at 90, where any goal flips the result no matter who scores, and 4.61 points from one-goal games, where team quality decides. Only that second slice is sensitive to a better per-team model. I tested the 4.6-point slice directly ([ADR-0034](https://github.com/matkin123/Stoppage-Time/blob/main/docs/decisions.md)): swapping the flat 50/50 split for a per-match, Elo-conditioned one moves the result figure by at most 0.4 points. So I believe a more sophisticated model would leave the aggregate flip result close to 12%.
```

---

## 15. Limitations — "The six tournaments are pooled but not identical…"

*Changed: Copa 25.3 → 22.9 min; AFCON 23.5 → 25.2; Euros "about 15" → "about 14".*

**Primary (number-only, keeps the published name order):**

```
The six tournaments are pooled but not identical. For instance, owed stoppage runs higher in Copa América 2024 (22.9 min) and AFCON 2023 (25.2) than in the Euros (about 14). But the model pools only one thing across them: the stoppage time goals-per-live-minute rate, applied to each match's own omitted minutes. Re-sourcing it from PRE-only, POST-only, or regime-matched cohorts keeps the headline inside its band. Truth is, I pool the six because I need the sample. Given a choice between widening the regional pool (Copa, AFCON) and widening the time horizon (pre-2018), I expect the regional pool to produce the more accurate model, because football varies less across space than across time. For example, the national squads all draw overwhelmingly from the same club leagues, so the region now marks a federation more than a style. (For what it's worth, the mean pre-match Elo gap between opponents runs 157 to 203 across all six tournaments, a spread under 50 Elo. AFCON differs on absolute strength, its teams averaging about 300 lower, but the relative gaps are stable.)
```

**OPTIONAL prose fix (CONTENT D).** Under the new numbers the rank flipped — AFCON (25.2) now exceeds
Copa (22.9) — but the primary block lists the larger value second. This rewrite lists them in
descending order (cleaner, non-misleading). Use *instead of* the block above:

```
The six tournaments are pooled but not identical. For instance, owed stoppage runs higher in AFCON 2023 (25.2 min) and Copa América 2024 (22.9) than in the Euros (about 14). But the model pools only one thing across them: the stoppage time goals-per-live-minute rate, applied to each match's own omitted minutes. Re-sourcing it from PRE-only, POST-only, or regime-matched cohorts keeps the headline inside its band. Truth is, I pool the six because I need the sample. Given a choice between widening the regional pool (Copa, AFCON) and widening the time horizon (pre-2018), I expect the regional pool to produce the more accurate model, because football varies less across space than across time. For example, the national squads all draw overwhelmingly from the same club leagues, so the region now marks a federation more than a style. (For what it's worth, the mean pre-match Elo gap between opponents runs 157 to 203 across all six tournaments, a spread under 50 Elo. AFCON differs on absolute strength, its teams averaging about 300 lower, but the relative gaps are stable.)
```

---

## Checks before you publish

- **CHECK B — search your live post for "twice" / "double" the live minutes and delete it.** As
  published, POST had ~2.2× the live-minutes of PRE. The Euro 2024 reclassification *inverts* this:
  PRE now has 415 live-minutes vs POST 479 — only ~1.15×. Any sentence claiming POST had "more than
  twice" / "double" the live minutes of PRE is now **false**. (It's absent from paragraph 5 above, but
  confirm it isn't lurking elsewhere in your live draft.)
- **CHECK C — RESOLVED (paragraph 2 anchor).** The old "96% / 8 min" was two problems: 96% was stale
  (real value 95%), and "8 min" described a five-only cohort while paragraph 3's "8.2 min" describes all
  314 — and since WC2018 is the mildest tournament (mean omitted 5.6 min), the five-only average is
  actually *higher* (8.8), so "8 < 8.2" was impossible. Fixed in block 2 by reporting the all-six
  aggregate the figure plots (95% / ~8 min = the same 314 matches as paragraph 3). The change map's
  guessed "98%" was wrong; verified figure is **95%** (94.9% over all 314, 95.2% over the five). No
  further verification needed — traced to `data/interim/true_stoppage.parquet` + `played_in_stoppage.parquet`.
- **CHECK E — paragraph 13 direction reads right (no edit expected).** "roughly 19 → roughly 21"
  moved *up* (removing low-owed Euro 2024 from POST raised the POST mean). The sentence says owed
  "jumped … to roughly 21," which is correct — just confirm nothing nearby implies the corrections
  *lowered* owed.
- **CHECK G — the "1 in 4 scorelines change" line in Reflections is still fine.** 23.3% ≈ 1 in 4.3, so
  "1 in 4" holds; "just under 1 in 4" if you want to be tight. No edit required.
- **OPTIONAL (CONTENT F) — a one-line "updated since publication" note.** Both moves are downward,
  small, and inside the originally-published envelope, so a transparent note pre-empts any "the number
  changed" objection and doubles as evidence of the model's stability. Paste-ready if you want it:

```
_Updated since publication: I reclassified Euro 2024 as pre-directive (UEFA opted out of the 2022 directive) and corrected an injury-window over-credit. The headline moved from 24.8% to 23.3% (result-flip 13.0% to 12.1%) — both downward and inside the original uncertainty band._
```

---

## Figures to re-upload (rendered at the old numbers — swap alongside the text)

| Where in the post | Figure | File | What changed |
|---|---|---|---|
| Under paragraph 2 (under-award scatter) | "Stoppage Error" | `figures/requested/Stoppage Error.png` | title 96%→95%; footer owed 17.6→**17.0**, missing 8.8→**8.2**, r 0.88→**0.87**, MAE 1.77→**1.67** |
| Step 1 (Nate calibration) | f07 | `figures/f07_nate_calibration.png` | model panel r 0.88→**0.87**, MAE 1.77→**1.67** |
| Results table | t3 | `figures/t_headline_results.png` | 24.8%→**23.3%**, flip 13.0%→**12.1%**, all bands/CIs |
| Sensitivity grid | t4 | `figures/t_sensitivity_grid.png` | central 23.3% across rows; decay/stage/PRE-POST rows updated |

**Unchanged — leave as-is:** "Goal Productivity", `agg_02_productivity_by_bucket.png`,
`t_restart_allowances.png`, `f06_productivity_decay.png` (all ride the unchanged s07 rates / static
ladder), and the external BBC third-place screenshot.

---

_Source of truth: `docs/decisions.md` (ADR-0035 → ADR-0039), `docs/numbers_ledger.md`,
`docs/substack_v4_changes_combined.md`. The repo copy `docs/substack_post_v4.md` already carries these
final numbers; this file exists to port them into the live post._
