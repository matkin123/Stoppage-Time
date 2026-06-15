# Next session — pointer to the current unit of work

Read `CLAUDE.md §6` first: **one self-contained unit per session, then stop.** Do not chain
these items into one marathon session.

**AUTHORITATIVE POINTER (2026-06-15):** Items 1 and 2 are DONE. The silent-component research
has been run; findings are in `prompts/silent_component_findings.md` (reviewed). **IMPL-0
(validation scaffolding) is DONE** (see below). The current work is the **implementation of the
recommended fix**, decomposed into the modular sessions **IMPL-1 → IMPL-4 below**. Start at
**IMPL-1**. Each session does ONE unit, validates its gate, checkpoints to `docs/decisions.md` +
this file, then stops.

**Turnkey prompts (open a fresh session and run one):**
- `prompts/impl_1_plumb_markers.md`      → IMPL-1
- `prompts/impl_2_reclassify_bip.md`     → IMPL-2
- `prompts/impl_3_estimator_validate.md` → IMPL-3
- `prompts/impl_4_counterfactual_lock.md`→ IMPL-4
Each is self-contained; the per-session detail below is the same content in one place.

---

## IMPL-0 — DONE (2026-06-15). Validation scaffolding (the external cross-check is now in-repo).

Built so every IMPL session can validate against Nate without re-transcribing a JPG:
- **`data/raw/nate_2018/nate_wc2018.csv`** — Nate's 32 WC2018 matches (home, away, `bip`,
  `expected`, `actual`), transcribed from `~/Downloads/nate silver WC stoppage 2018.jpg` and
  checked in. The project no longer depends on that external file.
- **`src/lib/nate.py`** — the shared harness. Key calls:
  - `nate.reconcile()` → 32 rows with `match_id` (reconciles on the UNORDERED, name-normalized
    team pair — 538 flips some home/away and spells "S. Korea"/"South Korea" differently).
  - `nate.truth_minutes("bip"|"expected"|"actual")` → {match_id: minutes}.
  - `nate.metric(pred_by_mid, truth_by_mid)` → {n, r, mae}.
  - `nate.report(pred_by_mid, column, label)` → prints r/MAE + the low/high diagnostic.
  - `nate.regulation_bip_minutes()` / `nate.board_total_minutes()` → ready-made per-match preds.
- **`tests/test_nate.py`** — 4 green guards: table parses + DIFF-consistent; `expected` mean is
  the ~13.2 min level (not `actual`); all 32 reconcile; AND the harness reproduces the validated
  board fit. Reproduced live: **BIP arm r=0.943 MAE=1.25** (the IMPL-2 baseline) and
  **board arm r=0.992 MAE=0.134** (ADR-0011). See ADR-0012.

**Column mapping — DO NOT CROSS (baked into nate.py docstring):**
`bip` → s03 BIP (IMPL-2 gate, r≥0.94) · `expected` → true-stoppage estimator (IMPL-3 gate, beat
0.73–0.77) · `actual` → board (already done, regression guard).

---

## Context (why we are here)

The pipeline ran end-to-end (s01–s09) but a cross-check of WC 2018 against Nate Silver's
published 538 numbers exposed a structural problem upstream:

- **Stages 1–3 are VALIDATED.** My per-match ball-in-play matches 538's to r=0.94, mean
  error 1.25 min. Clock reconstruction and BIP are correct. Do not re-litigate these.
- **The board number was wrong:** we used time *played* (integer `90'+X` label), which over-
  reads the announced board by ~1.5 min. → fixed in Item 1.
- **The true-stoppage estimator was wrong/too low:** old s05 `lower_bound` ≈ 7.5 min vs
  538's "expected" ≈ 13.2 min. The corrected "excess over normal flow" method recovers the
  right *level* but only correlates r≈0.73–0.77 per match. The residual gap is **the silent
  component** (see Item 2). → research first, then rebuild.

Decisions already made with the user:
- **Board = precise time-played**, aligned with how Nate measured "actual" (expected-vs-
  played), and available for all six tournaments. (Item 1.)
- We will eventually rebuild true-stoppage as
  `restart-excess + calibrated-silent + explicit injury/sub/goal credit`, freezing the
  calibration constant on 2018 and wiring Nate's exact 2018 numbers as the validation/
  replacement arm — **BUT NOT until Item 2's search has been done.**

---

## ITEM 1 — DONE (2026-06-15). Next session: start ITEM 2 (authoring the research prompt).

**Outcome:** the precise time-played board is implemented, but NOT from ESPN. Investigation
showed ESPN freezes its clock at 45:00/90:00 during added time (whole-minute labels only,
r ceiling 0.943 vs Nate) and its one second-level signal (broadcast wallclock) is corrupt on
~half the boundary markers (5/32 WC2018 usable). Instead the board now comes from StatsBomb's
`Half End` whistle timestamp — already on matches.parquet as `p1_end_s`/`p2_end_s` — as
`period_end_s − 2700`. Validated vs Nate's 32 WC2018 matches: **MAE 0.135 min, r=0.992**
(gate was MAE<0.5, r>0.95 — passed). All six tournaments, fully local, no scrape. Generator:
`src/board_statsbomb.py`; CSV now float `board_min`, `source=statsbomb`; s06a re-run clean
(PRE 6.8, WC2022 11.4). See ADR-0011. ESPN scraper kept only as an optional sensitivity path.

---

## ITEM 1 (a) — Implement the precise time-played board  [DONE — see above]

**Goal:** replace the current integer board with a precise (sub-minute) time-played figure
per match-half, for all six tournaments.

What we currently have: `src/scrape_board_espn.py` reads ESPN commentary half-end markers
("First Half ends 45'+8'", "Second Half ends 90'+9'") and records the **integer added
minute** → biased ~1.5 min high vs Nate's precise "actual."

What to do:
- Capture the **precise** stoppage played, not the integer minute label. ESPN commentary
  entries carry a structured clock; the half-end "ends" entry has a `time` object — pull the
  precise value (seconds into added time), or otherwise derive precise played time (e.g. from
  the last in-play event clock before the half-end marker). Aim to reproduce Nate's "ACTUAL"
  column (e.g. Russia–Saudi 06:45 total) within a few seconds.
- Output: same CSV/parquet shape as now (`data/raw/board/board_added_time.csv` →
  `interim/board_added_time.parquet`), columns `date, home, away, period, board_min, source`,
  but `board_min` is now precise minutes (float), source still `espn`.
- **Validation gate for this item:** for the 32 WC2018 matches Nate published, the precise
  played board must match Nate's "ACTUAL" column closely (target mean abs err < ~0.5 min,
  r > 0.95). Nate's 32-match table (home, away, BIP, expected, actual) is transcribed in the
  prior session transcript and in the cross-check scripts — re-transcribe from the attached
  image `~/Downloads/nate silver WC stoppage 2018.jpg` if needed.
- Note (do NOT silently change scope): the **announced** 4th-official board ("Fourth official
  has announced X minutes") exists in ESPN commentary **only for WC 2018** — the format
  changed afterward, so Euro2020/WC2022/Euro2024/Copa2024/AFCON2023 have no announced board
  via ESPN. We deliberately chose precise *time-played* because it is consistent with Nate
  and available for all six. Keep the 2018 announced board only as an optional sensitivity
  note if trivially cheap; do not block on it.
- Re-run only s06a (`python run.py --stage 06a`) to rejoin; do NOT run s08/s09 this session.
- Checkpoint: add an ADR entry in `docs/decisions.md` recording the board definition change
  (time-played, precise, Nate-aligned) and the 2018 validation result. Update this file.

---

## ITEM 2 — DONE (2026-06-15). Research prompt authored AND run; findings reviewed.

**Outcome:** wrote `prompts/silent_component_search.md` (the prompt) and ran it; the deliverable
is `prompts/silent_component_findings.md`.

**Recommendation (read the findings file for the full version):** the fix needs **no new data
source**. The silent over-count comes from `src/lib/bip.py:60` (`gap >= max_live_gap_s`)
crediting every long gap as dead without checking whether the ball actually left play. StatsBomb
stamps an explicit **ball-out-of-play marker at the leading edge of every genuinely dead ball**
(`pass.outcome="Out"`, the `out=true` flag on Pass/Carry/Shot, `Foul Committed`, shot-leaves-
field, goal, `Injury Stoppage`, `Substitution`/`Player Off`, `Bad Behaviour`, `Referee
Ball-Drop`, `Half End`), plus goalkeeper-held events for the "keeper holding a live ball" case.
Reclassify a silent gap as dead **only** when its lead edge carries an out-of-play marker (or its
trail edge a restart pattern); otherwise treat it as live. Validate against Nate's 32 WC2018
matches; freeze a small residual-silent constant on 2018. All six tournaments share the schema,
so this generalizes by construction. Nate (2018-only) is the calibration/validation arm.

**The implementation is IMPL-1 → IMPL-4 below.** This supersedes the old "solution b" DEFERRED
stub (retained at the bottom for historical reference only).

---

## ITEM 2 (original spec, retained for reference) — Author the research prompt

**This item produces a PROMPT, not an implementation.** Write a standalone, self-contained
research prompt (save it as `prompts/silent_component_search.md`) to be run in a *separate*
session. Its job: find a more accurate way to measure the "silent component" — the current
sole cause of the per-match gap vs Nate.

The prompt must:
- **Define the expertise required** so the searcher operates at the right level. Two hats:
  (1) **soccer/football quantitative analyst** — deep familiarity with event-data providers
  (StatsBomb, Opta/Stats Perform, Wyscout, SkillCorner, Second Spectrum), ball-in-play and
  stoppage methodology, FIFA/IFAB added-time rules, and prior public work (538/Nate Silver,
  Opta's BIP releases, academic time-motion studies); and (2) **expert web-scraping / data-
  sourcing engineer** — comfortable with hidden/public sports APIs (ESPN, FlashScore,
  Soccerway, WhoScored, FBref), match-event feeds, video-derived timing, and reconciling
  heterogeneous sources to a common match key.
- **State the problem precisely** (paste the description below verbatim into the prompt).
- **Ask for candidate data sources / signals** that can distinguish "ball sitting dead" from
  "ball in play, nothing logged" — e.g. provider fields that flag ball-out-of-play directly
  (StatsBomb `out`/`50-50`, GK events, `Referee Ball-Drop`), VAR/injury logs, tracking-data
  in-play flags, broadcast clock / "added time" overlays, or third-party BIP feeds; and a
  recommendation on which is most accurate, accessible, and cross-tournament consistent.
- **Demand a validation plan** against Nate's 2018 ground truth (the bar is r and MAE on the
  32 published matches, plus matched tournament aggregate), and require the searcher to flag
  any source that does not cover all six tournaments.
- Be explicit that the deliverable is a *recommendation + sourcing plan*, not code, and that
  implementation happens in a later session only after the user reviews it.

### Problem statement to paste verbatim into the prompt:

> It's almost entirely the silent component (gaps ≥20s with no restart event), and it comes
> from one conflation: a 20-second gap in StatsBomb's event stream can mean two completely
> different things, and timing alone can't tell them apart:
>
> 1. A real stoppage — injury treatment, VAR check, a melee. Nate counts this. ✅
> 2. Sparse but live play — slow build-up, keeper holding under no pressure, an off-camera
>    stretch where StatsBomb just logged fewer events. Nate, watching video, sees the ball is
>    in play and counts nothing. ❌
>
> My heuristic credits both as dead. Look at the pattern:
> - Germany–Sweden: only 2 injuries, but 12.6 min of "silent" → I say 17.4, Nate saw 8.9.
>   Those ~8 extra minutes are live play with sparse events, not stoppage.
> - Russia–Egypt, Uruguay–Saudi: same signature — few injuries, fat silent bucket, I over-
>   count by ~6 min.
> - Contrast Belgium–Panama / Tunisia–England: 7 and 10 injuries. Here the silent gaps are
>   real (injury treatment genuinely empties the event stream), and I land within ~1–2 min —
>   even slightly under, because long treatments exceed what the gaps captured.
>
> So the gap is not random measurement jitter — it's a systematic confound: matches with few
> injuries but choppy event-logging get inflated; matches dominated by genuine injuries are
> accurate. The restart-excess piece (the throw-in/corner/free-kick thresholds) is small and
> stable across all matches — it's not the problem. The problem is that StatsBomb's clock
> can't distinguish "ball sitting dead" from "ball in play, nothing logged."

---

## IMPLEMENTATION — modular sessions (do IMPL-1 first; one unit per session)

This implements the reviewed recommendation in `prompts/silent_component_findings.md`. Respect
`CLAUDE.md §6`: each IMPL-n is a self-contained session that ends at its gate. Do NOT chain them.
The two human checkpoints are **IMPL-3** (estimator vs Nate — decide the per-match method) and
**IMPL-4** (s08 sensitivity grid — lock X%).

### Methodology decision (DECIDED 2026-06-15): ONE ball-state classifier, in bip.py
We are improving how the project decides live-vs-dead, so the improvement belongs **everywhere**:
the marker-gating logic becomes THE classifier in `src/lib/bip.py`, and both BIP and the
true-stoppage estimator read from it. Two different live/dead definitions would be incoherent and
untraceable. This is NOT collapsing BIP and stoppage into one number — true stoppage stays
`dead − normal-restart-excess + injury/sub/goal credit` in s05, layered on top of the shared
classifier.

**Why promoting into bip.py is safe (not a re-litigation of the validated BIP):** the silent
over-count is the SAME absolute seconds in both metrics. On BIP (~55 min base) it's a ~15%
perturbation → r stayed at 0.94 despite the flaw. On stoppage (~13 min base) the same seconds are
~65% → r collapsed to 0.73. Marker-gating removes those seconds from both: a small nudge UP on BIP
(toward 538's truth) and a big jump on stoppage. A correct classifier improves both; if it ever
improves stoppage while regressing BIP, the marker logic is WRONG — stop and debug, do not ship.

**The one guardrail — re-calibration, not "don't touch":** s03's gap constants
(`min_dead_gap_s`/`max_live_gap_s`) were tuned to hit Opta's WC2022 3484s. Marker-gating moves
seconds dead→live, so pooled BIP will rise and likely breach the ±90s gate on first run. That is
EXPECTED → **re-tune** (you may not need `max_live_gap_s` at all once markers do the work). Promote
to bip.py only when, after re-tuning: WC2022 pooled BIP hits Opta ±90s AND per-match BIP r vs 538
holds ≥ 0.94. If you cannot get BIP to re-validate, that is a red flag about the marker logic — do
NOT fall back to a quiet estimator-only patch; bring it to the user.

---

### IMPL-1 — Plumb out-of-play markers through s02 normalization (data prep; low risk)

**Goal:** make the disambiguating fields available downstream without changing any behavior yet.

**Do:**
- In `src/s02_normalize.py` (and the shared event-normalization lib), project these raw
  StatsBomb fields into `interim/events_norm.parquet`, one column each:
  - `out` (bool; from the `out` flag on Pass/Carry/Ball Receipt*/Shot),
  - `pass_outcome` (str; StatsBomb `pass.outcome.name`, e.g. "Out", "Injury Clearance",
    "Incomplete", "Offside"),
  - `gk_type` (str; `goalkeeper.type.name`, e.g. "Collected", "Smother", "Save", "Pick-up"),
  - `gk_outcome` (str; `goalkeeper.outcome.name`).
- Keep the existing columns and the existing s02 gates intact.

**Gate (this session is done only when green):**
- s02's existing gates still pass (`clock_s` monotonic within match; recovered period lengths
  sane). Re-run `python run.py --stage 2`.
- Sanity on the new columns (print, eyeball, record in the ADR): `out=True` appears on a
  non-trivial fraction of Pass/Carry rows; `pass_outcome` includes "Out"; `gk_type` is populated
  for goalkeeper events. Non-null rates are plausible across ALL six tournaments (spot-check one
  match per tournament) — same schema must mean same population.
- Re-run `python run.py --stage 3` to confirm nothing downstream broke (BIP unchanged — these
  columns are not yet consumed).

**Checkpoint:** ADR in `docs/decisions.md` (new fields carried through s02, why, validation
spot-check). Update this file: mark IMPL-1 DONE, point to IMPL-2. STOP.

---

### IMPL-2 — Marker-gated silent reclassification → promote into bip.py (the one classifier)

**Goal:** build the reclassifier that decides, per ≥`min_silent_gap_s` gap, dead vs live using
the markers; prove it in isolation; then make it THE live/dead classifier in `src/lib/bip.py`
(re-tuned), feeding both BIP and the estimator. See the Methodology decision above.

**Do:**
- Implement a function (suggest `src/lib/silent.py`) that, given a match's normalized events,
  classifies each candidate silent gap (a gap with no restart pattern at its trail edge and
  ≥ threshold) as **dead** iff its lead edge carries an out-of-play marker — any of:
  `out=True`; `pass_outcome` ∈ {"Out","Injury Clearance"}; a shot leaving the field
  (`shot_outcome` ∈ {"Off T","Saved Off T","Wayward","Blocked","Goal"}); `type` ∈
  {"Foul Committed","Offside","Bad Behaviour","Substitution","Player Off","Injury Stoppage",
  "Referee Ball-Drop","Half End"} — **else live**.
- Special-case (B): a `gk_type` ∈ {"Collected","Smother","Pick-up"} with **no** subsequent
  `out` before the next touch ⇒ keeper holding a LIVE ball ⇒ gap is live (do not credit).
- Add the threshold + the marker set to `params.yaml` (e.g. `silent.min_silent_gap_s`,
  `silent.out_of_play_types`) — deterministic, pinned, documented.
- **Promote into `bip.py`:** replace the `gap >= max_live_gap_s` silent rule (`bip.py:60`) with
  the marker-gated classifier so BIP and the estimator share ONE live/dead definition. Then
  **re-tune** the s03 calibration: marker-gating moves seconds dead→live, so pooled WC2022 BIP
  will rise — adjust/remove the residual gap constant until the gate passes. A first-run breach
  is expected (re-tune), not a failure.

**Gate (promotion is allowed only when BOTH external gates hold after re-tuning):**
- **s03 BIP must re-validate, not just survive:** WC2022 pooled regulation BIP within ±90s of
  3484s; in-play share 55–60%; AND per-match BIP r vs 538 holds ≥ 0.94 (do not regress the
  validated number). If BIP cannot re-validate → STOP, the marker logic is suspect, bring it to
  the user. Do NOT fall back to an estimator-only patch.
- Print, per WC2018 match, the OLD silent total vs the NEW (marker-gated) silent total; confirm
  the new totals **drop most** on the low-injury matches (Germany–Sweden, Russia–Egypt,
  Uruguay–Saudi) and **barely move** on the injury-dominated ones (Belgium–Panama,
  Tunisia–England). This is the smell test before the full IMPL-3 validation.

**Checkpoint:** ADR (reclassifier logic, marker set, the re-tuned s03 constant + before/after
BIP-vs-538 and Opta numbers). Update this file: mark IMPL-2 DONE, point to IMPL-3. STOP.

---

### IMPL-3 — Rebuild true-stoppage estimator + validate vs Nate (HUMAN CHECKPOINT)

**Goal:** rebuild true-stoppage as
`restart-excess + marker-gated-silent + calibrated-residual + explicit injury/sub/goal credit`,
freeze the residual constant on 2018, and validate against Nate's 32 WC2018 matches.

**Do:**
- Replace the old s05 lower-bound / corrected-excess silent term with the IMPL-2 marker-gated
  silent. Keep restart-excess as-is (it's small and stable — do NOT re-derive). Keep the explicit
  injury/sub/goal credit.
- Wire Nate's exact 32-match table (home, away, BIP, expected, actual) as the validation/
  replacement arm. Re-transcribe from `~/Downloads/nate silver WC stoppage 2018.jpg` if the
  in-repo copy is missing.
- Fit a single **residual-silent constant** on 2018 (the irreducible unobserved dead time after
  marker-gating). Freeze it; apply the SAME constant to all six tournaments (POST cannot be
  fit on its own — no ground truth).

**Gate (and the numbers to report to the user — this is a human checkpoint):**
- **Per-match:** Pearson r + MAE (min) vs Nate's **`expected`** column (NOT `actual` — `expected`
  is the should-be-added model, ~13.2 min; `actual` is the board target). Use
  `src/lib/nate.report(pred, "expected", "estimator")`. Must beat current r≈0.73–0.77
  (target ≳0.85), MAE down.
- **Aggregate:** 32-match mean corrected stoppage vs Nate's `expected` mean — stays ≈13 min level.
- **Diagnostic:** per-match before/after for the five named matches — error shrinks on the three
  low-injury ones WITHOUT breaking the two injury-dominated ones.
- **Ablation table:** r/MAE for (A) alone → (A)+(B) → +residual-constant, so each piece is
  traceable.
- **Coverage flag:** state plainly that Nate validates WC2018 only; POST is validated indirectly
  via the frozen 2018 calibration + the s03 WC2022 Opta BIP gate.

**Checkpoint:** ADR with the full validation table; freeze the residual constant in `params.yaml`.
Update this file: mark IMPL-3 DONE, point to IMPL-4. STOP. **Bring the r/MAE/diagnostic table to
the user before proceeding.**

---

### IMPL-4 — Propagate estimator error into s08; re-run s07→s09; lock X% (HUMAN CHECKPOINT)

**Goal:** make the headline CI honest, then lock the single modeled claim.

**Do:**
- Propagate the per-match estimator error (the IMPL-3 MAE, ~±2 min) into the s08 bootstrap so the
  CI reflects estimator uncertainty, not just sampling. The current `[2.6–2.8%]` band is too
  tight. Only close (tied / 1-goal) matches flip the outcome — prioritize estimator accuracy
  and error propagation there.
- Re-run s07 (finalize productivity), then s08 (sensitivity grid), then s09 (figures + numbers
  ledger).

**Gate:**
- s07: every productivity cell reports n_events + live_minutes.
- s08: full sensitivity grid produced — **read it before locking X%** (CLAUDE.md §4/§6).
- s09: deterministic figures + numbers ledger; every figure traces to a script + checkpointed
  table + documented assumption.

**Checkpoint:** lock the headline **X% + CI + sensitivity band** in `docs/decisions.md` with the
user, eyes open. This closes the silent-component work.

---

## DEFERRED — original "solution b" stub (HISTORICAL; superseded by IMPL-1→IMPL-4 above)

Rebuild true-stoppage estimator as `restart-excess + calibrated-silent + explicit injury/
sub/goal credit`; freeze the calibration constant on 2018; wire Nate's exact 2018 numbers as
the validation/replacement arm. Also: propagate per-match estimator error (~±2 min MAE) into
the s08 bootstrap so the CI is honest (current `[2.6–2.8%]` band is too tight). Only the
close (tied / 1-goal) matches move the headline — prioritize estimator accuracy there.
