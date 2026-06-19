# RED-TEAM findings — adversarial methodology review before the X% lock (2026-06-18)

Read-only critique of the Stoppage Time headline (`docs/redesign.md`, `docs/decisions.md`
ADR-0011→0023, `docs/numbers_ledger.md`, `config/params.yaml`, `src/s08_counterfactual.py`).
Three hats: mathematician/statistician, soccer quant, literature. Every claim is tied to a
table/ADR or a cited source. No pipeline file, param, or ADR was modified. All numbers below
were re-derived live from `data/processed/` + `data/interim/`.

---

## 1. Verdict

**Publishable with caveats — not as a bare "23.8% of matches would have ended differently."**
Nothing here is FATAL. The central object — `P(≥1 extra goal) = 1 − exp(−μ)` per match, averaged
— is sound, and it is *empirically* well-behaved: the realized count of 2H-stoppage goals per match
is essentially Poisson (mean 0.2325, var 0.2301, **var/mean = 0.99**; observed {0:249, 1:57, 2:8}
vs Poisson(0.2325) {248.8, 57.8, 6.7}), so `1−exp(−μ)` is the right functional form at the realized
stoppage window. The headline magnitudes are corroborated by the best available external sources
(Opta's 58:04 WC2022 BIP verbatim; 538's 7.3→13.2 min; ~10–12 min POST). The headline is also
**not outlier-driven** (median per-match P = 0.231; 97.5% of matches have P>0; the top 20 matches
contribute only 14.5% of the summed probability mass), so it is robust to any single match.

The exposure is in **framing and presentation, not arithmetic**. Three things must change before
the lock or the claim is indefensible to a hostile referee: (a) the headline verb "ended
differently" reads as *different result*, but 23.8% is *different scoreline* — the actual
result-flip number is 12.2%, and **32.7% of the 23.8% mass comes from already-decided
(`lead_by_2plus`) matches that cannot flip**; (b) X% must lead as a **band (≈16–24%)**, never the
single optimistic `observed`-λ rail, because the observed stoppage λ is endogenous to game state and
plausibly over-states the counterfactual; (c) the published `[20.3%, 28.0%]` CI is honest only
*within* the central knob — the silent axis alone swings 12.5%→36.4% — so it must never be shown as
"the" uncertainty. All three are already anticipated in the docs (ADR-0021 #1/#2, ADR-0017/D4); the
red-team verdict is that they must move from "reported alongside" to "the way the number is led."

---

## 2. Prioritized findings

Grades: **FATAL** (claim collapses) / **SERIOUS** (materially moves X% or its honesty) /
**COSMETIC** (framing/footnote). "Pre-empted?" = do the current docs already address it.

| # | Steel-manned attack | Hat | Grade | Pre-empted? | Concrete fix / caveat |
|---|---|---|---|---|---|
| S1 | "Ended differently" colloquially means a different **winner**, but 23.8% counts any **extra goal**. 32.7% of the X% mass is `lead_by_2plus` blowouts where the scoreline moves but nothing changes; only 31% of matches are tied at 90'. The honest result-flip number is **12.2%**. | Stat | **SERIOUS** | Partly — ADR-0021 #1 reports outcome-flip 12.2% alongside | Headline must pair the two: "≥1 extra goal in ~24% of matches; the *result* actually flips in ~12%." Do not let the verb imply outcome. |
| S2 | The observed 2H-stoppage λ=0.0816 (≈1.9× open-play 0.0427) is **endogenous to game state** — added time is longer and play more frantic precisely when a team is chasing. Transplanting it onto *all* omitted minutes (incl. decided games) over-states μ. Under the `observed` rail, `lead_by_2plus` matches carry the *highest* mean P (0.257) despite being coast situations — a tell. | Stat/Quant/Lit | **SERIOUS** | Yes — productivity-premium band, `open_play` floor = 16.3% | **Lead with the band 16.3–23.8%**, not the 23.8% point. Soften ADR-0021's "truth nearer the top" to "bracketed by the band"; the literature (non-homogeneous, score-state-dependent goal arrival) says the transplant likely over-states. |
| S3 | The estimator that produces `true_stoppage` (hence `omitted`, hence X%) is validated against Nate **only on WC2018 (32 matches)**. The entire POST cohort — where the headline lives — is validated *indirectly* (frozen-2018 constants + the WC2022 Opta BIP point). POST `true_stoppage` runs nearly 2× WC2018 (Copa 25.3, AFCON 23.5 vs WC2018 12.6 min); none of that is externally checked. | Quant | **SERIOUS** | Yes — "coverage flag" repeated in ADR-0016/0017 | Keep the coverage flag in the locked ADR verbatim. Add the external corroboration found by the lit review: a Bundesliga 2022-23 study finds referees *still* under-add ~2:10 post-directive — independent support that POST omitted-time > 0. |
| S4 | BIP is a **gap method (20s rule)** calibrated to a **single Opta point** (WC2022 58:04) under a *different* operational definition (Opta = proprietary continuous clock). The 20s threshold has no canonical standing. The four non-WC2022 POST tournaments' BIP (hence live_share, a multiplicative factor on X%) is uncalibrated. | Quant/Lit | **COSMETIC** *(was SERIOUS — verified & defused)* | Partly — ADR-0003/0009 calibrate; r=0.943 vs Nate 2018 BIP is a *second* independent anchor | **Re-checked read-only and largely defused.** The rule's premise is dense active logging ("an event every few seconds") — and that density is *constant* across all six tournaments: **62.6 events/live-min ±4%** (wc18 62.1, euro20 63.7, wc22 62.0, euro24 62.5, copa 64.5, afcon 61.8). Within-possession active gaps have **median 0.70s / q99 6.0s**, so the 20s cut sits ~3× past q99 (only **0.26%** of active gaps ≥20s) — which is why ADR-0009's G∈[15,25] sweep stays within ±90s. `live_share` *does* vary (2H-stoppage: WC2018/Euro ~0.51–0.56 vs **Copa 0.43 / AFCON 0.47**), but with density uniform that spread is a real football signal (more dead time), not a 20s-rule artifact, and it runs *conservative* for the uncalibrated tournaments (lower live_share → lower omitted_live → lower X%). Residual caveat: BIP's absolute *level* still rests on two anchors (Opta WC2022 + 538 WC2018); the cross-tournament *transfer* is now data-supported, not merely assumed. |
| S5 | The productivity λ **pools penalties, free-kick and open-play goals indiscriminately**, and the processed tables can't separate them (`events_norm` carries no shot subtype). A stoppage penalty is a near-certain (~75–80%), discrete, high-leverage *step* event triggered by a foul/handball/VAR call — not a Poisson open-play increment — and clusters around late goalmouth scrambles. | Quant | **COSMETIC** *(was SERIOUS — folds into S2 + C1)* | No (measurement gap real; interpretation corrected) | **Interpretation corrected.** Elevated stoppage-penalty *incidence* is **not** referees applying a different threshold in added time — refs are broadly consistent across normal and stoppage time. The higher rate reflects teams playing **more aggressively** (more bodies forward, more goalmouth contact), which refs still referee the same way. So the penalty component is *aggression/flow*-driven — partly transplantable, not a "different-refereeing" artifact. The only residual — whether that aggression *persists in the omitted minutes* (which skew to decided games) — is exactly the game-state endogeneity already bracketed by **S2's productivity-premium band**; and the lumpiness/"step-event" worry is already empirically defused by **C1** (realized counts, *including* whatever penalties are among the 73, are Poisson, var/mean 0.99). Optional descriptive diagnostic: re-derive shot subtype for the 96 stoppage goals to report the penalty share (nice-to-have, not a blocker). |
| S6 | The published headline CI `[20.3%, 28.0%]` reflects only λ-sampling (Jeffreys-Gamma) + the silent_marked estimator MAE. The **silent treatment alone** swings none 12.5–14.9 / marked 22.6–26.1 / all 32.1–36.4 — a far bigger axis reported *outside* the CI. Shown alone, the CI is falsely tight. | Stat | **SERIOUS** | Yes — D4/ADR-0017 keep none/all as guardrails; CLAUDE.md §1 mandates a band | Never present `[20.3,28.0]` as *the* uncertainty. Lead with the full sensitivity envelope (productivity-premium 16.3–23.8 + the silent rails as the dominant axis); the CI is the within-knob sampling error only. |
| C1 | Poisson within a 2–5 min, extreme-score-state window: homogeneity / over-dispersion / time-inhomogeneity. Maher/Dixon–Coles are *match-total* models and don't license a constant within-window rate; the goal-timing literature says arrival is non-homogeneous and rising. | Stat/Lit | **COSMETIC** | No (justification, not the math) | The *form* is fine: `P(≥1)` needs only the mean, and realized counts are Poisson (var/mean 0.99), so within-window time-inhomogeneity is irrelevant to `1−exp(−μ)`. **Reframe the justification**: cite non-homogeneous goal-timing work (late-minute inflation), not Maher/Dixon–Coles. |
| C2 | O1 independence: 1H and 2H omitted windows treated as independent, and a 1H extra goal is a bonus increment that does *not* propagate to the rest of the match. Adding 1H lifts the headline +6.7pt (17.1→23.8). | Stat | **COSMETIC** | Yes — O1 caveat explicit (ADR-0019) | Internally consistent for the *scoreline-count* metric. Keep **2H_only (17.1%)** prominent as the cleaner, propagation-free comparison; caveat the 1H independence wherever 1H+2H leads. |
| C3 | 96-cell knob grid → garden-of-forking-paths; is `silent_marked\|overall\|pooled_all\|observed\|off` a principled prior or a post-hoc pick? | Stat | **COSMETIC** | Yes — D2/D3/D4 rationale predates the grid (ADR-0018 before ADR-0019) | Defensible as a pre-registered prior. The one optimistic lean is choosing `observed` as the lead rail — fixed by S2 (lead with the band). State the central knob is chosen *a priori*, not by scanning the grid. |
| C4 | Is 23.8% a POST-composition artifact (AFCON/Copa climate, refereeing, logging density) rather than the directive? | Quant | **COSMETIC** | Yes — D3 pools λ; pre/post sensitivities | Not an artifact: pre/post X% = pooled 23.8 / **PRE 26.1** / POST 22.8 — PRE is *higher* and the CIs overlap heavily, so the directive regime does not drive the number. Report the split to defend this. |
| C5 | StatsBomb logging density (the Germany–Sweden over-count) varies by tournament → biases the POST silent term. Concretely, silent_marked/match is ~2× higher in Copa (5.9) / AFCON (6.3) than WC2018 (3.2) — exactly the tournaments with no ground truth. | Quant | **SERIOUS but pre-empted** | Yes — the whole IMPL-2→5 silent-band program | The silent band is the designed response (irreducible, shipped as a rail). No new fix; ensure the locked caveat names Copa/AFCON specifically as the unvalidated high-silent cohort. |
| C6 | 73 2H goals (23 1H) sliced into tied/non-tied sub-cells (n=10–35) is too thin to condition on. | Quant | **COSMETIC** | Yes — D2 makes `overall` central, `tied_nontied` a sensitivity | No change; keep `overall` central. The CI already carries the 73-goal λ uncertainty. |
| C7 | `live_share` of the *omitted* minutes is proxied by the *played*-window live share (~0.49). Omitted minutes (deader, more time-wasting) plausibly have lower live share → X% slightly over-stated; the O3 gross-up pushes the other way. | Stat | **COSMETIC** | Partly — O3 gross-up is the opposite-direction sensitivity | Second-order and bounded. Note that the band is dominated by the λ choice (S2) and silent (S6), not by live_share (which cancels *between* the two λ rails — ADR-0021 #2). |

---

## 3. Recommended pre-lock actions

### Must fix (the lock is indefensible without these)
1. **Lead with the band, not the point (S2, S6).** The headline number is **≈16–24%** (open-play
   floor → observed-stoppage rail), with `[20.3%, 28.0%]` shown as the *within-knob* CI on the
   central rail only, and the silent axis (12.5%→36.4%) named as the dominant uncertainty. Do not
   publish 23.8% as a bare point (CLAUDE.md §1).
2. **Separate scoreline from outcome in the headline wording (S1).** Pair "≥1 extra goal in ~24%
   of matches" with "the result actually changes in ~12%." The verb "ended differently" alone,
   attached to 23.8%, is the single most attackable sentence in the piece.
3. **Carry the coverage caveat verbatim into the locked ADR (S3):**
   Nate validates WC2018 only; the POST cohort (esp. Copa/AFCON) is validated *indirectly*
   (frozen-2018 estimator constants + the WC2022 Opta BIP point), and that flag must survive
   into the headline ADR. (S4's BIP-transfer worry is now data-defused — see nice-to-have #7.)

### Nice to have (strengthens, not blocking)
5. **Reframe the Poisson justification (C1):** cite the late-minute goal-inflation / non-homogeneous
   arrival literature, and state explicitly that the realized stoppage-goal counts are Poisson
   (var/mean 0.99) so `1−exp(−μ)` is empirically licensed — pre-empt the "constant-rate" attack.
6. **Report the pre/post X% split (C4)** (PRE 26.1 / POST 22.8) to kill the composition-artifact
   objection, and cite the post-directive Bundesliga under-addition study (S3) as independent
   external support for POST omitted-time > 0.
7. **State that BIP transfers across tournaments (S4), with evidence.** Event-logging density is
   constant (62.6 events/live-min ±4% across all six), and the 20s cut sits ~3× past the q99 of
   active gaps (only 0.26% ≥20s), so ADR-0009's G∈[15,25] sweep holds everywhere — the 20s
   threshold is not a single hand-tuned knob, and the Copa/AFCON `live_share` dip is real football
   (and conservative), not a logging artifact.
8. **(Optional) Quantify the penalty share of the stoppage goals (S5).** A one-off read-only
   re-derivation of shot subtype for the 96 stoppage goals (73 2H + 23 1H) would let the piece
   state the penalty share outright. *Not a blocker*: penalties are aggression-driven (consistently
   refereed) and the realized counts are already Poisson with them included (C1), so this is
   descriptive colour, not a correction to X%.

### Explicitly NOT required
- No re-build, re-tune, or re-run to "improve" the number — the lock is a SELECT, not a BUILD
  (CLAUDE.md §6; `prompts/lock_headline.md`). None of the findings demand a model change; they
  demand framing, caveats, and one descriptive diagnostic.

---

## 4. Literature appendix

High-credibility sources only (academic journals + Opta/Stats Perform + FiveThirtyEight/Silver +
major outlets). Each line states what it supports (✅) or undercuts (⚠️).

**Direction & magnitudes — strongly corroborating.**
- **538 / Neil Paine, "World Cup Stoppage Time Is Wildly Inaccurate" (2018).** WC2018 averaged 7.3
  added min; ~13.2 min if all lost time were counted; 31/32 games under-counted ≥2 min. ✅ Identical
  thesis; maps onto the PRE setup (≈7 announced vs ≈13 true). The r=0.825 anchor is sound but ⚠️ don't
  over-sell *per-match* precision (~32% of variance unexplained).
- **Opta Analyst — WC2022 ball-in-play 58:04** (vs PL 54:45/54:49). ✅ The 58:04 calibration target
  is Opta's published figure verbatim — the best possible anchor.
- **FIFA / Collina directive coverage (FIFA, CNN, Al Jazeera).** Officials told to compensate
  accurately for all stoppages; WC2022 ~10 min average, long tail to 27 min. ✅ POST ~11–12 min is
  consistent; this is exactly the PRE/POST hinge.

**Method generality & Poisson — two framing concerns (both now COSMETIC).**
- **Siegle & Lames; Linke, Link & Lames (J. Sports Sciences / IJCSS); Frontiers EPT study.** Net
  playing time ~52–55 min, ~108 interruptions/match, EPT declining 66%→56% across a half. ✅ 58 min
  level is in range. ⚠️ Academic studies define stoppages **event-by-event**, not by a fixed time
  gap — the 20s rule is nonstandard (feeds S4). *But* the gap rule's premise (dense active logging)
  is empirically uniform across all six tournaments (62.6 events/live-min ±4%), so its
  cross-tournament transfer is data-verified — S4 downgraded to COSMETIC.
- **Maher (1982); Dixon–Coles (1997); Karlis–Ntzoufras (bivariate Poisson).** ⚠️ These are
  **match-total** models; they do **not** license a constant within-window rate (feeds C1 — reframe,
  don't rely on them).
- **"Temporal dynamics of goal scoring" (arXiv 2501.18606); "is scoring a predictable Poissonian
  process?" (arXiv 1002.0797); "How does the past influence the future" (arXiv 1207.4471); Premier
  League/Opta late-goal analysis; PLOS ONE pre-halftime study.** Goal arrival rises monotonically
  through a match, ~24.8% of goals in the 76'–90' bucket, record 13.2% at 90'+. ⚠️/✅ The late
  premium's *sign and rough size* (1.4–1.9×) are well-backed — but the rate is non-homogeneous and
  **score-state-dependent**, which (a) supports an elevated stoppage λ yet (b) implies endogeneity/
  over-statement when transplanted onto all omitted minutes (feeds S2).

**Novelty & independent support — corroborating.**
- **"Additional time error…" (Science & Medicine in Football, 2024)** — Bundesliga 2022-23 referees
  still under-add 2:10 ± 2:24 *after* the directive, most when goal difference > 1. ✅ Independent
  confirmation that POST omitted-time > 0 (feeds S3); also ✅ that already-decided games are
  under-added — consistent with omitted time concentrating in non-tied matches.
- **Morgulev & Galily (J. Behavioral & Experimental Economics, 2019); "Rational Rule Breaking";
  Stirling / Kocsoy referee-bias work (SSRN/ScienceDirect).** Systematic strategic time-wasting by
  leading teams; refereeing on a knife-edge. ✅ Mechanism behind under-addition.
- **No published counterfactual** computing the share of matches whose scoreline/winner flips under
  properly-measured stoppage. ✅ Genuinely novel — but ⚠️ first-mover means no external replication,
  so the methodological burden of proof is entirely on this study.

Sources:
- [538 — World Cup Stoppage Time Is Wildly Inaccurate](https://fivethirtyeight.com/features/world-cup-stoppage-time-is-wildly-inaccurate/)
- [538 — There's Way More Stoppage Time At This World Cup](https://fivethirtyeight.com/features/youre-not-imagining-things-theres-way-more-stoppage-time-at-this-world-cup/)
- [Neil Paine — You're Not Imagining Things (Substack)](https://neilpaine.substack.com/p/youre-not-imagining-things-theres)
- [FIFA — Collina on calculating stoppage time accurately](https://inside.fifa.com/refereeing/news/collina-weve-asked-referees-to-calculate-stoppage-time-more-accurately)
- [Al Jazeera — Why so much stoppage time at the 2022 World Cup](https://www.aljazeera.com/news/2022/12/5/why-has-there-been-so-much-stoppage-time-at-the-2022-world-cup)
- [CNN — Why so much stoppage time at the 2022 World Cup](https://www.cnn.com/2022/11/23/football/extra-time-qatar-world-cup-explainer-spt-intl)
- [Opta Analyst — WC2022 ball in play 58:04](https://x.com/OptaAnalyst/status/1610976697318531073)
- [Opta Analyst — Definitive Guide to Premier League Time-Wasting](https://theanalyst.com/articles/guide-to-premier-league-time-wasting)
- [Opta Analyst — Ball in Play 2025-26](https://theanalyst.com/articles/premier-league-ball-in-play-are-we-seeing-less-football-2025-26)
- [Opta Analyst — World Cup 2022 Facts](https://theanalyst.com/articles/world-cup-2022-the-facts-fifa-qatar)
- [Linke, Link & Lames — Game Interruptions and Running Performance (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC6243615/)
- [Ball in/out of play and possession in elite soccer (J. Sports Sciences)](https://www.tandfonline.com/doi/full/10.1080/17461391.2023.2203120)
- [Effective playing time affects technical-tactical and physical parameters (Frontiers)](https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2023.1229595/full)
- [Dixon & Coles 1997 (RSS Series C)](https://rss.onlinelibrary.wiley.com/doi/abs/10.1111/1467-9876.00065)
- [Maher 1982 (Statistica Neerlandica)](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-9574.1982.tb00782.x)
- [Temporal dynamics of goal scoring in soccer (arXiv 2501.18606)](https://arxiv.org/abs/2501.18606)
- [Is scoring goals a predictable Poissonian process? (arXiv 1002.0797)](https://arxiv.org/pdf/1002.0797)
- [How does the past of a soccer match influence its future? (arXiv 1207.4471)](https://arxiv.org/pdf/1207.4471)
- [Are goals just before halftime worth more? (PLOS ONE)](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0240438)
- [Opta/PL — why more late goals in 2025-26](https://www.premierleague.com/en/news/4437338/opta-analysis-of-why-more-late-goals-are-being-scored-in-2025-26-premier-league-season)
- [Additional time error in association football (Science & Medicine in Football)](https://www.tandfonline.com/doi/full/10.1080/24733938.2024.2435843)
- [Referee bias: actual vs expected additional time — Kocsoy (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S2773161825000011)
- [Stirling — referees add unexplained time on a knife edge](https://www.stir.ac.uk/news/2026/april-2026-news/football-referees-add-unexplained-additional-time-when-results-are-on-a-knife-edge/)
- [Morgulev & Galily — time-wasting in EPL (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S2214804319301430)

*Caveat on sourcing: the literature figures were extracted from search-result snippets (WebFetch was
unavailable in the research environment); the headline numbers — 58:04, 7.3/13.2 min, 54:45/54:49,
ATE 2:10 — appear verbatim in those snippets. Pull exact in-context quotes from the article bodies
before final publication.*
