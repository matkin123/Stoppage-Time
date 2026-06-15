# Next session — pointer to the current unit of work

Read `CLAUDE.md §6` first: **one self-contained unit per session, then stop.** Do not chain
these items into one marathon session. Item 1 is a small, shippable change. Item 2 is a
research-prompt-authoring task whose *output* is a prompt to run in a *later, separate*
session. Do not start the estimator rebuild (the deferred "solution b") until the Item 2
search has been run and its findings reviewed.

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

## ITEM 2 — Author a fresh research prompt to better measure the "silent component"

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

## DEFERRED (do NOT start until Item 2 search is reviewed) — "solution b"

Rebuild true-stoppage estimator as `restart-excess + calibrated-silent + explicit injury/
sub/goal credit`; freeze the calibration constant on 2018; wire Nate's exact 2018 numbers as
the validation/replacement arm. Also: propagate per-match estimator error (~±2 min MAE) into
the s08 bootstrap so the CI is honest (current `[2.6–2.8%]` band is too tight). Only the
close (tied / 1-goal) matches move the headline — prioritize estimator accuracy there.
