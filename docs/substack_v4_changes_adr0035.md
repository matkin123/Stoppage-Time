# substack_post_v4 — change map for the ADR-0035 re-lock

**Purpose.** This is a paste-guide for the live Substack piece. Every edit made to
`docs/substack_post_v4.md` under the Euro 2024 POST→PRE reclassification (ADR-0035) is listed
below with its location, the exact before→after text, and why it moved. Edits are **number-only**:
no argument, structure, or wording changed except where explicitly flagged at the bottom. If you
only want to touch the numbers that actually moved in your published copy, work down this list.

**Headline delta:** scoreline 24.8% → **24.4%**, result-flip 13.0% → **12.9%**. The move is small
and entirely PRE-driven: reclassifying Euro 2024's 51 matches into the PRE pool applies era-conditional
celebration crediting (excess-only) to them, which lowers their true_stoppage. POST is byte-identical.
Pools: PRE 115→**166**, POST 199→**148**.

---

## Numbers that changed

| # | Line | Context | Before → After |
|---|---|---|---|
| 1 | 3 | Headline sentence | scoreline `24.8%` → **`24.4%`**; CI `[21.7%, 28.6%]` → **`[21.1%, 28.3%]`**; flip `13.0%` → **`12.9%`**; flip CI `[11.3%, 15.1%]` → **`[11.2%, 15.0%]`** |
| 2 | 37 | "owed − played" descriptive | owed `17.6` → **`17.4`**; omitted `8.8` → **`8.7`** (match-level flooring) |
| 3 | 90 | Decay half-life sweep | `23.3` → **`23.0`** (h=2); `26.1` → **`25.7`** (h=8); central `24.8` → **`24.4`** (h=4) |
| 4 | 92 | Natural-experiment PRE vs POST rate | `0.086 PRE (24 goals/279)` → **`0.089 PRE (37 goals/415)`**; `0.080 POST (49/615)` → **`0.075 POST (36/479)`** — see **FLAG A** |
| 5 | 96 | Conditioning sweep | `24.8` → **`24.4`** (overall); `24.5` → **`24.1`** (tied/non-tied split) |
| 6 | 100 | λ-source / stage sweep | `25.9` → **`25.5`** (group); `21.5` → **`21.2`** (knockout); central `24.8` → **`24.4`** |
| 7 | 104 | Flip sensitivity span top | `13.9` → **`13.8`** |
| 8 | 108 | Flip decomposition | `(13%)` → **`(12.9%)`**; tied `7.86` → **`7.87`**; lead-by-1 `5.12` → **`5.00`** |
| 9 | 110 | Elo split test | max move `0.38` → **`0.36`**; band `"12.9% and 13.4%"` → **`"12.8% and 13.2%"`**; flip CI `[11.3%, 15.1%]` → **`[11.2%, 15.0%]`** |
| 10 | 116 | Sampling CI + envelope | CI `[21.7%, 28.6%]` → **`[21.1%, 28.3%]`**; width `6.9` → **`7.2`**; lead band `21.4–27.3` → **`21.1–26.7`**; joint envelope `18.9–28.6` → **`18.1–28.2`** |
| 11 | 120 | Band-width recap | one-at-a-time `5.9` → **`5.6`**; CI width `6.9` → **`7.2`**; envelope `9.7` → **`10.0`**; PRE-only `27.3` → **`26.7`**; group `25.9` → **`25.5`**; knockout `21.5` → **`21.2`** |
| 12 | 128 | Per-match owed prose | `"roughly 19"` → **`"roughly 21"`** — see **FLAG B** |
| 13 | 132 | Flip decomposition recap | `13.0` → **`12.9`**; tied `7.86` → **`7.87`**; lead-by-1 `5.12` → **`5.00`**; `"5.1-point slice"` → **`"5.0-point slice"`** |

---

## Numbers that did NOT change (pooled-invariant — do not touch)

These ride quantities that are the same before and after the reclassification, so they are correct
as printed in v4. Listed so you can confirm you didn't miss anything, not so you edit them.

- Line 9 — Nate Silver 2018 anchor (`97%` / `6 min`) and the five-tournament figure (`96%` / `8 min`). See **FLAG C**.
- Per-tournament owed: Copa `25.3`, AFCON `23.5`, Euros `~15`, WC2018 `12.7` (these are per-tournament, not pooled).
- BIP anchors (WC2018 54:50, WC2022 58:04) and the productivity ratios `0.0816` / `0.0427` / `1.9×`.
- Natural-experiment goals-per-live-minute pair used elsewhere `0.0886` / `0.0786`; the shots block `0.0847` / `0.0727` / `56` / `660.8` / `17` / `233.7` / `1.17` / `0.69`.
- Elo internals: `0.548` (2H-stoppage p_trail) / `n=31` / its CI; `60%` leader-stronger / `−38` mean Δ / `95` unflippable / `146` crossover / `39%` p_trail-sensitive / `32%` tied floor / `55%` / `n=287`.
- Elo minute band `157–203` / `300 Elo`; productivity `0.082` / `0.043`.

---

## Flags — three judgment calls for you to make by hand

**FLAG A (Line 92 — "barely moved" wording).** The number edit is done (`0.089 PRE` vs `0.075 POST`),
but the prose still says the rate "barely moved" across the directive. Under the OLD pools that gap
was 0.086 vs 0.080 (~7%). Under the NEW pools it's 0.089 vs 0.075 — a **~16% drop**, twice as large.
"Barely moved" is now a stretch. I left the wording untouched (this was a number-only pass), but
recommend you soften it in the live copy — e.g. "moved only modestly" or state the direction
(post-directive matches score slightly *slower* per live minute). Your call on framing.

**FLAG B (Line 128 — "roughly 19" → "roughly 21").** This moved in the *less* intuitive direction:
removing Euro 2024 (a comparatively low-owed cohort) from POST *raises* the POST average owed, so the
per-match figure went up, not down. The new value (POST mean owed ≈ 21.3) is correct, but if your
surrounding sentence implies the reclassification lowered things, re-read it in context.

**FLAG C (Line 9 — "96% / average of 8 minutes", left UNCHANGED).** This is a **pre-existing**
discrepancy, not introduced by ADR-0035. Recomputing the five-non-2018 anchor from the current data
gives roughly **98% / ~9 min**, not 96% / 8 min. I did not touch it because it predates this re-lock
and isn't a pooled quantity I re-derived in this pass. Recommend you verify it against whatever source
generated the original figure-11 number before publishing, and reconcile if needed.

---

_Reconcile against: `docs/decisions.md` (ADR-0035), `docs/numbers_ledger.md`. Every changed cell above
traces to `counterfactual_summary.parquet` / the regenerated exhibit docs._
