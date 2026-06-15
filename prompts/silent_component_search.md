# Research prompt — measuring the "silent component" of true stoppage

**How to use this file:** This is a *standalone research prompt* to be run in a fresh,
separate session. Its deliverable is a **recommendation + sourcing plan**, not code. Do not
implement anything from it until the user has reviewed the findings. (See the parent project's
`next_session.md` → ITEM 2 and the DEFERRED "solution b".)

---

## Who you are (required expertise)

Operate simultaneously as **two experts**. Use both hats on every recommendation — a data
source is only useful if it is both methodologically valid *and* actually obtainable.

**Hat 1 — Soccer/football quantitative analyst.** You have deep, working familiarity with:
- Event-data providers and their schemas: **StatsBomb**, **Opta / Stats Perform**, **Wyscout**,
  **SkillCorner**, **Second Spectrum**. You know what each logs, what it omits, and where the
  clock comes from.
- **Ball-in-play (BIP) / effective-playing-time methodology** and **stoppage measurement**,
  including the gap/dead-time approach and its failure modes.
- **FIFA / IFAB added-time rules**, including the 2022 directive to count time lost to
  celebrations, substitutions, injuries, VAR, and time-wasting more completely.
- Prior public and academic work: **538 / Nate Silver's** 2018 World Cup stoppage analysis,
  **Opta's** public BIP releases, and **time-motion / effective-playing-time** studies in the
  sports-science literature.

**Hat 2 — Expert web-scraping / data-sourcing engineer.** You are comfortable with:
- Hidden and public sports APIs and feeds: **ESPN**, **FlashScore**, **Soccerway**,
  **WhoScored**, **FBref**, and provider match-event endpoints.
- **Video-derived timing** (broadcast clock / "added time" overlays, OCR of on-screen graphics)
  and other non-event timing signals.
- **Reconciling heterogeneous sources to a common match key** (date + teams + competition),
  including the coverage, rate-limit, legality/ToS, and stability realities of each source.

---

## The problem (verbatim — this is the precise thing to solve)

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

### Restated as a research question

We need a signal — or a combination of signals — that, for any given ≥20s gap in the StatsBomb
event stream, helps decide **"ball dead"** vs **"ball in play, nothing logged."** The current
heuristic credits every such gap as dead time, which systematically inflates stoppage in
low-injury / choppy-logging matches. Find a better way to resolve that ambiguity, or to bound /
correct the silent component, that **holds across all six tournaments** in the project.

---

## Project constraints (read before recommending)

- **Six tournaments, all on StatsBomb open data**, split PRE vs POST the 2022 directive:
  - PRE: WC 2018, Euro 2020.
  - POST: WC 2022, Euro 2024, Copa América 2024, AFCON 2023.
  Any proposed source/signal **must be assessed for coverage across all six**, not just 2018.
- **No xG, no tracking data we don't already have.** StatsBomb 360 freeze-frames are explicitly
  out of scope for the base pipeline (disk budget); if you propose using 360 or any tracking
  feed, treat it as a separate, flagged option and justify the cost.
- **StatsBomb event data is the spine.** The fix should ideally attach to, augment, or validate
  against the existing event stream keyed by match. New sources must reconcile to the common
  match key (date + home + away + competition).
- The **restart-excess** component (throw-in/corner/free-kick dead-time thresholds) is already
  small and stable — **do not** spend effort re-deriving it. The target is the **silent**
  component only.

---

## What to deliver

1. **Candidate signals / data sources.** Enumerate concrete ways to distinguish "ball sitting
   dead" from "ball in play, nothing logged." For each, say exactly what field/feed provides it
   and how it disambiguates a silent gap. Consider at least:
   - **Provider fields that flag ball-out-of-play directly** — e.g. StatsBomb `out` flags,
     `50-50`, goalkeeper events, `Referee Ball-Drop`, `Half End`/period markers, and any event
     types that imply the ball is dead vs live.
   - **VAR / injury / substitution logs** (StatsBomb or third-party) that mark genuine
     stoppages we currently only infer from event sparsity.
   - **Tracking-data in-play flags** (SkillCorner, Second Spectrum, StatsBomb 360) — flagged as
     higher-cost options with coverage caveats.
   - **Broadcast clock / "added time" overlays** and other **video-derived timing**, including
     OCR of on-screen graphics.
   - **Third-party BIP / effective-playing-time feeds** (Opta public releases, FlashScore,
     WhoScored, FBref, others) usable as ground truth or cross-check.
2. **A recommendation.** Of the candidates, which is **most accurate, most accessible, and most
   cross-tournament consistent**? Rank the top 2–3 and justify the trade-offs explicitly under
   both hats (valid *and* obtainable). Note coverage gaps frankly.
3. **A validation plan** (see next section).
4. **A sourcing plan** for the recommended option: where the data lives, how to pull it
   (API/scrape/manual), rate-limit / ToS / legality notes, the match-key reconciliation
   approach, and the expected effort.

**The deliverable is a recommendation + sourcing plan in prose, NOT code.** Implementation
happens in a later session, only after the user reviews this.

---

## Validation plan (required, and the bar is specific)

Any proposed signal/source must come with a plan to validate it against **Nate Silver's 2018
World Cup ground truth**:

- **Per-match bar:** report **Pearson r and MAE (minutes)** of corrected true-stoppage against
  Nate's published figures on the **32 WC 2018 matches** (his table of home, away, BIP,
  expected, actual). The current corrected method sits at **r ≈ 0.73–0.77** per match; the
  silent confound is the dominant residual. Beat that.
- **Aggregate bar:** also report the **matched tournament aggregate** (mean stoppage across the
  32 matches) vs Nate's, since a method can be right on average but wrong per match (the
  current failure) — we need both.
- **Diagnostic check:** show the correction specifically shrinks the error on the **low-injury,
  fat-silent-bucket matches** (Germany–Sweden, Russia–Egypt, Uruguay–Saudi) without breaking
  the **injury-dominated** ones (Belgium–Panama, Tunisia–England) that are already accurate.
- **Coverage flag (mandatory):** explicitly flag **any source that does not cover all six
  tournaments.** A 2018-only signal can serve as a *calibration/validation* arm but cannot be
  the production estimator for POST tournaments — say so plainly if that's the case.

---

## Output format

Lead with a one-paragraph **bottom-line recommendation**. Then: (1) ranked candidate signals
with the disambiguation mechanism each provides; (2) the recommendation with trade-offs under
both expert hats; (3) the validation plan against Nate's 32 matches (r + MAE + aggregate +
diagnostic); (4) the sourcing plan; (5) an explicit **coverage matrix** of each recommended
source across the six tournaments. Keep claims traceable to a named field, feed, or published
dataset — speculation must be labeled as such.
