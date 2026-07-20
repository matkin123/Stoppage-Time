# substack_post_v4 — change map for the ADR-0039 re-lock

**Purpose.** This is a paste-guide for the live Substack piece. Every edit made to
`docs/substack_post_v4.md` under the s05 injury-window re-key (ADR-0039) is listed below with its
location, the exact before→after text, and why it moved. Edits are **number-only**: no argument,
structure, or wording changed except where explicitly flagged at the bottom. If you only want to
touch the numbers that actually moved in your published copy, work down this list. (This re-lock
supersedes the ADR-0035 numbers; if you already hand-ported ADR-0035, this is the delta on top of it.)

**Headline delta:** scoreline 24.4% → **23.3%**, result-flip 12.9% → **12.1%**. Unlike ADR-0035 (a
tournament reclassification), this is a **methodology fix to the owed estimator**: the s05 injury
dead-time window was keyed to the inconsistently-logged `Referee Ball-Drop` event, which fabricated
~10-min injury windows and over-credited owed stoppage. It is now keyed to the next live ball (next
s03 in-play segment start), and the two era residuals are floored at 0. That lowers `true_stoppage`
(mean owed 17.4 → 17.0 min/match) roughly uniformly across the surface, so the whole grid shifts down
~1.1–1.2 pp. **Pools are UNCHANGED** (PRE 166 / POST 148). Both central and joint envelope stay inside
the previously published outer bound. Calibration improved (MAE 1.77 → 1.67 min; r 0.875 → 0.870).

---

## Numbers that changed

| # | Line | Context | Before → After |
|---|---|---|---|
| 1 | 3 | Headline sentence | scoreline `24.4%` → **`23.3%`**; CI `[21.1%, 28.3%]` → **`[20.1%, 27.3%]`**; flip `12.9%` → **`12.1%`**; flip CI `[11.2%, 15.0%]` → **`[10.4%, 14.2%]`** |
| 2 | 37 | Estimator fit + "owed − played" descriptive | r `0.875` → **`0.870`**; avg error `1.77` → **`1.67`** min; owed mean `17.4` → **`17.0`**; omitted mean `8.7` → **`8.2`**; positive `96%` → **`95%`** (played-clock `r = 0.992` UNCHANGED) |
| 3 | 90 | Decay half-life sweep | `23.0` → **`22.0`** (h=2); `25.7` → **`24.5`** (h=8); central `24.4` → **`23.3`** (h=4) |
| 4 | 96 | Conditioning sweep | `24.4` → **`23.3`** (overall); `24.1` → **`23.1`** (tied/non-tied split) |
| 5 | 100 | λ-source / stage sweep | group `25.5` → **`24.4`**; knockout `21.2` → **`20.1`**; central `24.4` → **`23.3`** |
| 6 | 104 | Objection 4 split-sweep span | `"12.0% and 13.8%"` → **`"11.2% and 12.9%"`** |
| 7 | 108 | Flip decomposition (stakes) | flip `(12.9%)` → **`(12.1%)`**; tied `7.87%` → **`7.46%`**; lead-by-1 `5.00%` → **`4.61%`** |
| 8 | 110 | Objection 5 Elo re-pricing | max move `0.36` → **`0.44`** points; band `"12.8% and 13.2%"` → **`"12.1% and 12.5%"`**; flip CI `[11.2%, 15.0%]` → **`[10.4%, 14.2%]`** |
| 9 | 116 | Sampling CI + band + envelope | CI `[21.1%, 28.3%]` → **`[20.1%, 27.3%]`**; width `7.2` → **`7.1`**; lead band `21.1–26.7` → **`20.2–25.6`**; joint envelope `18.1–28.2` → **`17.3–27.0`** |
| 10 | 120 | Band-width recap | one-at-a-time `5.6` → **`5.5`**; CI width `7.2` → **`7.1`**; envelope `10.0` → **`9.7`**; PRE-only top `26.7` → **`25.6`**; group `25.5` → **`24.4`**; knockout `21.2` → **`20.1`** |
| 11 | 132 | Flip decomposition recap | flip `12.9%` → **`12.1%`**; tied `7.87` → **`7.46`**; lead-by-1 `5.00` → **`4.61`**; `"5.0-point slice"` → **`"4.6-point slice"`**; `"close to 13%"` → **`"close to 12%"`** (`"at most 0.4 points"` UNCHANGED — 0.44 rounds to 0.4) |
| 12 | 134 | Per-tournament owed | Copa `25.3` → **`22.9`** min; AFCON `23.5` → **`25.2`**; Euros `"about 15"` → **`"about 14"`** — see **FLAG C (rank swap)** |

---

## Numbers that did NOT change (rate/quality-invariant — do not touch)

The fix re-keys only the *owed* (`true_stoppage`) estimate. It never touches goals, live-minutes,
ball-in-play (`s03`), or productivity (`s07`), so every rate, census, and Elo quantity below is
identical before and after. Listed so you can confirm you didn't miss anything, not so you edit them.

- Line 9 — Nate Silver 2018 anchor (`97%` / `6 min`) and the five-tournament figure (`96%` / `8 min`). See **FLAG B**.
- Line 37 — played-clock agreement `r = 0.992` (played is `s03`-derived, not owed).
- Line 92 — natural-experiment productivity `0.089 PRE (37 goals / 415)` / `0.075 POST (36 / 479)`. See **FLAG A**.
- Line 96 — tied/non-tied 2H-stoppage rates `0.0886 [0.0567, 0.1318]` / `0.0786 [0.0581, 0.1039]`.
- Line 100 — stage block `0.0847` / `0.0727` / `56` / `660.8` / `17` / `233.7` / `1.17` / `0.69`.
- Line 104 — `0.548` (2H-stoppage p_trail), `n = 31`, CI `[0.375, 0.713]`.
- Lines 108/110/122 — census `121` lead-by-one, `98` tied, `95` unflippable; Elo internals `60%` leader-stronger / `38` mean gap / `146` crossover / `39` of `121` (`32%`) / `55%` (n=31) / `51%` (n=287).
- Line 128 — `12.7` min (WC2018 owed) and `"roughly 21 minutes"` (POST-pool owed ≈ 20.96, still rounds to 21).
- Line 134 — Elo minute band `157–203` / `~300 Elo`.
- BIP anchors (Line 41): WC2022 `57:40` / Opta `58:04`, WC2018 `56:00` / Opta `54:50` / FiveThirtyEight `55:18`.
- Productivity headline rates: `0.0816` / `0.0427` / `1.9×` (Lines 13/84/86); `0.082` / `0.043` (Line 154).

---

## Flags — judgment calls for you to make by hand

**FLAG A (Line 92 — "barely moved" wording; carries over from ADR-0035, still unresolved).** The
productivity pair (`0.089 PRE` vs `0.075 POST`) did NOT move in this re-lock (it's `s07`, untouched),
so no number edit here. But the prose still says the rate "barely moved" across the directive, and
`0.089` vs `0.075` is a **~16% drop**. "Barely moved" remains a stretch. I left it untouched (number-only
pass); recommend softening in the live copy — e.g. "moved only modestly," or state the direction
(post-directive matches score slightly *slower* per live minute). Your call on framing.

**FLAG B (Line 9 — "96% / average of 8 minutes", left UNCHANGED; pre-existing).** This is a
**pre-existing** discrepancy, not introduced by ADR-0039 (same as ADR-0035's FLAG C). It's the
five-non-2018 cohort, and recomputing from current data gives roughly **98% / ~9 min**, not 96% / 8 min.
Note the all-314 omitted average on Line 37 *did* move this pass (8.7 → 8.2), which is a different
population; do not confuse the two. I did not touch Line 9 because it predates this re-lock and isn't
a quantity I re-derived here. Recommend verifying it against whatever generated the original figure-11
number before publishing.

**FLAG C (Line 134 — Copa / AFCON RANK SWAP; NEW this re-lock).** Under ADR-0039 the per-tournament
owed re-ordered: **AFCON (25.2) now exceeds Copa (22.9)**, reversing the ADR-0035 order (Copa 25.3 >
AFCON 23.5). Both new numbers are correct. I made a **pure number-only** edit that kept the two names
in their original order (Copa named first), so the sentence now reads "…higher in Copa América 2024
(22.9 min) and AFCON 2023 (25.2)…" — still true *relative to the Euros*, but AFCON is now the larger of
the pair yet is listed second. Recommend reordering the names (AFCON first) in the live copy for a
cleaner read. Your call. (The 2018 `12.7` and the POST-pool `"roughly 21"` on Line 128 are unaffected.)

---

_Reconcile against: `docs/decisions.md` (ADR-0039), `docs/numbers_ledger.md`. Every changed cell above
traces to `counterfactual_summary.parquet` / the regenerated exhibit docs (`docs/flip_split_sensitivity.md`,
`docs/team_quality_flip_test.md`)._
