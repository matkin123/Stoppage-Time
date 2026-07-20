# substack_post_v4 — COMBINED change map: as-published → current lock (ADR-0039)

**Purpose.** This is a single paste-guide for the **live Substack piece**. It collapses the two
prior number-only change maps — `substack_v4_changes_adr0035.md` (the Euro 2024 POST→PRE
reclassification) and `substack_v4_changes_adr0039.md` (the s05 injury-window re-key) — into ONE
original→final delta.

Use this because **the live post was never edited after it was first published**, so it still
shows the *as-published* numbers (headline **24.8% / 13.0%**, pools 115 PRE / 199 POST). Two locks
have landed since (ADR-0035, then ADR-0039). Rather than apply them in sequence, work down the
single "Original → Final" column below and port each number once. The two intermediate re-locks
chain cleanly (every ADR-0035 "after" value is the ADR-0039 "before" value), so nothing is lost by
merging them.

**Headline delta (as-published → now):**
- Scoreline **24.8% → 23.3%**  (CI **[21.7%, 28.6%] → [20.1%, 27.3%]**)
- Result-flip **13.0% → 12.1%**  (CI **[11.3%, 15.1%] → [10.4%, 14.2%]**)

**Why it moved (two independent causes, both downward, both inside the originally-published envelope):**
1. **ADR-0035 — Euro 2024 reclassified POST → PRE** (UEFA opted out of the 2022 directive). Moves
   Euro 2024's 51 matches into the PRE pool (pools **115/199 → 166/148**) and applies excess-only
   celebration crediting to them, lowering their owed. Small, PRE-driven: **24.8% → 24.4%**.
2. **ADR-0039 — s05 injury window re-keyed to the next live ball.** The injury dead-time window was
   keyed to the inconsistently-logged `Referee Ball-Drop`, which fabricated ~10-min windows and
   over-credited owed stoppage. Re-keyed to the next in-play segment start; both era residuals
   floored at 0. Lowers `true_stoppage` roughly uniformly (mean owed 17.4 → 17.0 min), shifting the
   whole grid down ~1.1 pp: **24.4% → 23.3%**. Calibration *improves* (MAE 1.77 → 1.67; r 0.875 → 0.870).

Both moves are number-only (no argument, structure, or wording changed) **except** the content
suggestions flagged at the bottom, which you asked for and which go beyond the minimal edits.

> **Line numbers** below refer to the canonical `docs/substack_post_v4.md`. Your live post's line
> numbering may differ — match by the surrounding text in the **Context** column.

---

## Numbers that changed — Original (as-published) → Final (ADR-0039)

| # | Line | Context | Original → **Final** |
|---|---|---|---|
| 1 | 3 | Headline sentence | scoreline `24.8%` → **`23.3%`**; CI `[21.7%, 28.6%]` → **`[20.1%, 27.3%]`**; flip `13.0%` → **`12.1%`**; flip CI `[11.3%, 15.1%]` → **`[10.4%, 14.2%]`** |
| 2 | 37 | Estimator fit + "owed − played" descriptive | r `0.875` → **`0.870`**; avg error `1.77` → **`1.67`** min; owed mean `17.6` → **`17.0`**; omitted mean `8.8` → **`8.2`**; positive `96%` → **`95%`** (played-clock `r = 0.992` UNCHANGED) |
| 3 | 90 | Decay half-life sweep | `23.3` → **`22.0`** (h=2); `26.1` → **`24.5`** (h=8); central `24.8` → **`23.3`** (h=4) |
| 4 | 92 | Natural-experiment PRE vs POST rate | `0.086 PRE (24 goals/279)` → **`0.089 PRE (37 goals/415)`**; `0.080 POST (49/615)` → **`0.075 POST (36/479)`** — see **CONTENT A + B** |
| 5 | 96 | Conditioning sweep | `24.8` → **`23.3`** (overall); `24.5` → **`23.1`** (tied/non-tied split) |
| 6 | 100 | λ-source / stage sweep | group `25.9` → **`24.4`**; knockout `21.5` → **`20.1`**; central `24.8` → **`23.3`** |
| 7 | 104 | Objection 4 split-sweep span | `"12.0% and 13.9%"` → **`"11.2% and 12.9%"`** |
| 8 | 108 | Flip decomposition (stakes) | flip `(13%)` → **`(12.1%)`**; tied `7.86%` → **`7.46%`**; lead-by-1 `5.12%` → **`4.61%`** |
| 9 | 110 | Objection 5 Elo re-pricing | max move `0.38` → **`0.44`** points; band `"12.9% and 13.4%"` → **`"12.1% and 12.5%"`**; flip CI `[11.3%, 15.1%]` → **`[10.4%, 14.2%]`** |
| 10 | 116 | Sampling CI + band + envelope | CI `[21.7%, 28.6%]` → **`[20.1%, 27.3%]`**; width `6.9` → **`7.1`**; lead band `21.4–27.3` → **`20.2–25.6`**; joint envelope `18.9–28.6` → **`17.3–27.0`** |
| 11 | 120 | Band-width recap | one-at-a-time `5.9` → **`5.5`**; CI width `6.9` → **`7.1`**; envelope `9.7` → **`9.7`** (net unchanged); PRE-only top `27.3` → **`25.6`**; group `25.9` → **`24.4`**; knockout `21.5` → **`20.1`** |
| 12 | 128 | Per-match owed prose | `"roughly 19"` → **`"roughly 21"`** — see **CONTENT E** |
| 13 | 132 | Flip decomposition recap | flip `13.0` → **`12.1`**; tied `7.86` → **`7.46`**; lead-by-1 `5.12` → **`4.61`**; `"5.1-point slice"` → **`"4.6-point slice"`**; `"close to 13%"` → **`"close to 12%"`** (`"at most 0.4 points"` UNCHANGED — 0.44 rounds to 0.4) |
| 14 | 134 | Per-tournament owed | Copa `25.3` → **`22.9`** min; AFCON `23.5` → **`25.2`**; Euros `"about 15"` → **`"about 14"`** — see **CONTENT D (rank swap)** |

**Two rows worth an extra glance (the two locks pushed them in different directions):**
- **Row 11, joint envelope width** round-trips: `9.7` (published) → `10.0` (ADR-0035, wider PRE sample)
  → `9.7` (ADR-0039). Net unchanged, so leave it — but if you already ported an intermediate `10.0`,
  set it back to `9.7`.
- **Row 12, "roughly 19 → roughly 21"** moved entirely in ADR-0035 (removing low-owed Euro 2024 from
  POST *raises* the POST-pool mean owed to ≈21) and held at ~21 under ADR-0039. See **CONTENT E**.

---

## Numbers that did NOT change (rate/quality/static — do not touch)

These ride quantities identical across both locks (goals, live-minutes, ball-in-play `s03`,
productivity `s07`, the Nate allowance ladder, the Elo census). Listed so you can confirm you didn't
miss anything, not so you edit them.

- Line 9 — Nate Silver 2018 anchor (`97%` / `6 min`) and the five-tournament figure (`96%` / `8 min`). **See CONTENT C — pre-existing, unverified.**
- Line 13/84/86/154 — productivity headline rates `0.0816` / `0.0427` / `1.9×`; `0.082` / `0.043`.
- Line 37 — played-clock agreement `r = 0.992` (played is `s03`-derived, not owed).
- Line 41 — BIP anchors: WC2022 `57:40` / Opta `58:04`; WC2018 `56:00` / Opta `54:50` / FiveThirtyEight `55:18`.
- Line 96 — tied/non-tied 2H-stoppage rates `0.0886 [0.0567, 0.1318]` / `0.0786 [0.0581, 0.1039]`.
- Line 100 — stage block `0.0847` / `0.0727` / `56` / `660.8` / `17` / `233.7` / `1.17` / `0.69`.
- Line 104 — `0.548` (2H-stoppage p_trail), `n = 31`, CI `[0.375, 0.713]`.
- Lines 108/110/122 — census `121` lead-by-one, `98`/`95` unflippable; Elo internals `60%` leader-stronger / `38` mean gap / `146` crossover / `39` of `121` (`32%`) / `55%` (n=31) / `51%` (n=287).
- Line 128 — `12.7` min (WC2018 owed).
- Line 134 — Elo minute band `157–203` / `~300 Elo`.

---

## Suggested argument / content changes (BEYOND the minimal number edits)

These are the judgment calls and prose fixes the minimal passes deliberately left alone. They are
recommendations — your call — but each is either an accuracy fix or a place the original wording no
longer fits the numbers.

**CONTENT A — soften "barely moved" (line 92).** The prose still says the per-minute scoring rate
"barely moved" across the 2022 directive. As published, that gap was `0.086` vs `0.080` (~7%) — a
defensible "barely." At the current numbers it is `0.089` PRE vs `0.075` POST, a **~16% decline** —
twice as large, and *downward*. "Barely moved" is now a stretch.
> Suggested rewrite: *"…the per-minute scoring rate moved only modestly, and if anything slightly
> **down**: 0.089 PRE to 0.075 POST."* This actually **strengthens** the Objection-1 point — POST
> scoring did not rise even though second-half stoppage roughly doubled, so pricing omitted minutes
> down toward open play (as the decay does) is if anything conservative.

**CONTENT B — kill any "more than twice the live minutes" claim (line 92 / natural experiment).**
As published, the POST pool had far more live-minutes than PRE (`615` vs `279`, ≈2.2×) because POST
held more matches (199 vs 115). The reclassification **inverts** this: PRE now has `415` live-minutes
vs POST `479` — only **1.15×**. Any sentence in your live copy that leans on POST having "more than
twice" / "double" the live minutes of PRE is now **false** and must be cut or reworded. (This was
already removed from the canonical README/Methodology; confirm your Substack draft doesn't still
carry it.)

**CONTENT C — verify the line-9 anchor "96% / average of 8 minutes" before publishing.** This is a
**pre-existing** discrepancy, independent of both locks and never re-derived in either pass. A fresh
recompute of the five-non-2018 cohort gives roughly **98% / ~9 min**, not 96% / 8 min. Recommend
checking it against whatever generated the original figure-11 number and reconciling. Note this is a
*different population* from the all-314 omitted average on line 37 (now `8.2 min`) — don't conflate
the two.

**CONTENT D — reorder Copa / AFCON on line 134 (rank swap).** Under ADR-0039 the per-tournament owed
order flipped: **AFCON 2023 (25.2 min) now exceeds Copa América 2024 (22.9)** — the reverse of the
published order (Copa 25.3 > AFCON 23.5). The minimal edit kept the original name order (Copa first),
so the sentence now reads "…higher in Copa América 2024 (22.9 min) and AFCON 2023 (25.2)…" — true
relative to the Euros, but AFCON is the larger of the pair yet listed second.
> Suggested rewrite: *"…owed stoppage runs higher in AFCON 2023 (25.2 min) and Copa América 2024
> (22.9) than in the Euros (about 14)…"* — names in descending order, cleaner and non-misleading.

**CONTENT E — sanity-read the sentence around "roughly 19 → roughly 21" (line 128).** This moved in
the *counter-intuitive* direction: removing the comparatively low-owed Euro 2024 cohort from POST
*raised* the POST-pool average owed. If the surrounding sentence implies the corrections *lowered*
owed stoppage, re-read it in context so the direction reads right. (Number is correct; this is a
prose-consistency check only.)

**CONTENT F — consider a one-line "updated since publication" note (optional; editorial integrity).**
The live post shipped at **24.8% / 13.0%** and this pass takes it to **23.3% / 12.1%**. Both moves are
downward, small, and land **inside the originally-published envelope** (the published joint envelope
was 18.9–28.6%; the new central 23.3% and its band sit well within it). A transparent one-liner —
e.g. *"Updated: reclassified Euro 2024 as pre-directive and corrected an injury-window over-credit;
the headline moved 24.8% → 23.3%, still inside the original uncertainty band"* — pre-empts any "the
number changed" objection and doubles as evidence of the model's stability. Optional; your call on
whether to surface the revision at all.

**CONTENT G — the "~1 in 4" / "~1 in 8" framing still holds (no edit needed).** At 23.3% scoreline the
Reflections "1 in 4 scorelines change" line (line 146) is still accurate (≈1 in 4.3); at 12.1% the
result-flip is still ≈1 in 8. If you want to be tight, 23.3% reads as "just under 1 in 4," but no
change is required.

---

## Figures to re-upload (regenerated to ADR-0039; swap alongside the text)

The published figures were rendered at the *as-published* numbers and are now stale. Four changed
and must be re-uploaded; three are byte-identical (ride the unchanged productivity / static content)
and can be left as-is.

| Post location | Figure | File | Status |
|---|---|---|---|
| Line 11 (under-award scatter) | "Stoppage Error" | `figures/requested/Stoppage Error.png` | **CHANGED** — title 96%→95%, footer owed 17.6→**17.0** / missing 8.8→**8.2** / r 0.88→**0.87** / MAE 1.77→**1.67** |
| Line 35 (Nate calibration) | f07 | `figures/f07_nate_calibration.png` | **CHANGED** — model panel r 0.88→**0.87**, MAE 1.77→**1.67** |
| Line 114 (results table) | t3 | `figures/t_headline_results.png` | **CHANGED** — 24.8%→**23.3%**, flip 13.0%→**12.1%**, all bands/CIs |
| Line 118 (sensitivity grid) | t4 | `figures/t_sensitivity_grid.png` | **CHANGED** — central 23.3% across rows; decay/stage/PRE-POST rows updated |
| Line 15 (productivity) | "Goal Productivity" | `figures/requested/Goal Productivity.png` | unchanged (s07 rates fixed) |
| Line 82 (rate by phase) | agg_02 | `figures/requested/agg_02_productivity_by_bucket.png` | unchanged (s07) |
| Line 29 (Nate allowance table) | t_restart | `figures/t_restart_allowances.png` | unchanged (static ladder) |
| Line 88 (decay curve) | f06 | `figures/f06_productivity_decay.png` | unchanged (productivity rates fixed) |
| Line 148 (group third-place table) | — | external BBC screenshot | not regenerable here |

---

_Reconcile against: `docs/decisions.md` (ADR-0035 → ADR-0039), `docs/numbers_ledger.md`. Every changed
cell above traces to `counterfactual_summary.parquet` / the regenerated exhibit docs
(`docs/flip_split_sensitivity.md`, `docs/team_quality_flip_test.md`). Superseded source maps:
`docs/substack_v4_changes_adr0035.md`, `docs/substack_v4_changes_adr0039.md`._
