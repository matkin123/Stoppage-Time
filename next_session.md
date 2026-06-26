# Next session — pointer to the current unit of work

Read `CLAUDE.md §6` first: **one self-contained unit per session, then stop.** Do not chain
these items into one marathon session.

---

## DONE + RE-LOCKED (2026-06-25) — HEADLINE = 24.8% scoreline / 13.0% flip (ADR-0031). Method 2 + PRE celebration allowance ADOPTED.

**User-approved adoption (human checkpoint).** Both measured-but-pending changes are now PRODUCTION and the
headline is RE-LOCKED. Full record: `docs/decisions.md` **ADR-0031** (supersedes ADR-0025's numbers). The two
upstream changes: **ADR-0029** (Method 2 same-half live share/z) + **ADR-0030** (PRE-only celebration
allowance, `residual_silent_pre_s=94.1`).

**What was run:** `python run.py --stage 06b → 08 → 09` (s05 already re-run for the allowance). Regenerated
`processed/counterfactual*.parquet`, `decay_profile.parquet`, `figures/f0*.png`, `docs/numbers_ledger.md`.
**pytest 11 green** — `test_s08_decay_endpoints` constants refreshed to the adopted combined rails
(0.241/0.175/0.099; were Method-2-only 0.246/0.179/0.101).

**LOCKED VALUES (regenerated grid, group=all, 1H+2H, `silent_marked|overall|pooled_all|hl=4.0|on`):**
- **Scoreline X% = 24.8% [95% CI 21.7%, 28.6%]**; **outcome-flip 13.0% [11.3%, 15.1%]** (reported separately).
- 2H_only: scoreline 17.0% [15.0%, 19.5%], flip 8.9% [7.9%, 10.3%].
- Lead one-factor band **21.4%–27.3%**; full joint envelope **18.9%–28.6%**; sampling CI width 6.9%.
- Decay band 1H+2H 23.3%(h2)/24.8%(h4)/26.1%(h8); gross-up off/on/geom 21.4/24.8/26.0%; λ-source
  pooled_all 24.8 · pre 27.3 · post 23.7 · regime 24.9; conditioning overall 24.8 · tied_nontied 24.5.

**Why it moved (23.6%→24.8%):** Method 2 alone +1.7 pp (25.3%); PRE celebration allowance alone −0.5 pp;
net 24.8%/13.0%. Entire move is PRE — **POST `true_stoppage` byte-identical** (max|Δ|=0.000000 / 199 POST
matches). Both central and envelope stay inside the previously published outer bound. Estimator improved:
r 0.825→0.875, MAE 2.44→1.77 (WC2018 = all PRE). Silent treatment / caveats / coverage UNCHANGED from ADR-0025.

### → NEXT UNIT (editorial refresh, NOT modeling): re-render hand-authored prose/figures to 24.8%/13.0%.
The canonical source of truth (parquet, ledger, ADR, CLAUDE.md) is re-locked. These DERIVATIVE artifacts still
hard-code the OLD 23.6%/12.1% and must be refreshed before publishing (grep "23.6"/"12.1"/"20.6"/"27.4"):
`docs/substack_post.md`, `docs/model_review_v2.md`, `docs/model_review_v3.md`, `docs/model_review_v4_ray.md`,
`docs/DEP_methods_substack.md`, `src/figures_requested.py` / `src/fig_*.py`. (Some — `bip_headline_sensitivity`,
`method2_samehalf` — cite 23.6% as the historical BASELINE they compare against; those are correct as history,
verify before changing.) Do as its own session per CLAUDE.md §6.

---

## SUPERSEDED (2026-06-24) — TEST METHOD 2 (same-half live share + same-half gross-up). [DONE — see ADR-0028 above.]

**Read `docs/decisions.md` ADR-0027 first** — it records why we're here. The s08 gross-up has an
ASYMMETRY: it converts omitted added-time CLOCK → omitted LIVE minutes using a **match/window-specific
live share** (`lsw`, the stoppage-window in-play fraction) but a **pooled whole-match scalar z=0.382**
for the time-wasting re-credit. ADR-0027 already tested **Method 1** (make z window-specific by
re-running the s05 attribution clipped to `period_s>2700`): it shifts central X% ~−0.2 pp (inside the
gross-up band [21.1%, 24.2%]) and, surprisingly, LOWERS the showcase match Spain–England because that
match's added-time deadness is UNMARKED (window z₂H = 0.008), so the marker-gated estimator can't see
it. Method 1 inherits low signal / high skew from a 5–11 min window and just re-expresses the locked
`silent_marked` vs `silent_all` axis at window scope. **Method 2 is the more defensible fix.**

### What Method 2 is (the user's spec, verbatim intent)
Assume the OMITTED minutes look like the **average SAME-HALF minute** — for BOTH the live share AND the
gross-up z. **"Same-half" = that half's REGULAR play + that half's PLAYED stoppage combined**:
- 1H omitted stoppage → calibrate to ALL of period 1 (regulation 0–45:00 **plus** the 1H added time
  that was actually played).
- 2H omitted stoppage → calibrate to ALL of period 2 (regulation **plus** the 2H added time that was
  actually played).

Rationale (why this beats Method 1): it is calibrated to the specific teams on the day, it captures 2H
fatigue/subs, and it rests on a 45+ min base instead of a few skewed minutes — sidestepping Method 1's
(1) low-signal/high-skew window and (2) the live-share-specific-but-z-pooled asymmetry. Both factors now
come from the same reference period.

### Exactly what to compute (per match, per half h∈{1H,2H})
Everything traces to existing parquet — NO re-run of s01–s07 needed.

1. **Same-half live share `ls_half[m,h]`** — from `interim/bip_segments.parquet` (cols `match_id,
   period, start_s, end_s, in_play`). For period p (1→1H, 2→2H): `dur = end_s - start_s`;
   `ls_half = Σ dur[in_play] / Σ dur`, over ALL segments of that period (do NOT clip at 2700 — the
   whole played half). This REPLACES the stoppage-window `lsw = ls_ratio[(m,h)]` that s08 reads from
   `stoppage_live_share.parquet`.
2. **Same-half gross-up `z_half[m,h]`** — counted addable stoppage ÷ total dead time, over the whole
   half, matching `genuine_stoppage_share` (s08 line 89) but per (match,period) instead of pooled:
   - `dead[m,h] = Σ dur where NOT in_play`, over that period (from bip_segments, as above).
   - `counted[m,h] = lower_bound_s + silent_marked_s` for that `(match_id, period)` from
     `interim/incident_stoppage.parquet`. **EXCLUDE `residual_silent_s`** (the pooled z excludes it —
     it's a frozen estimator constant, not a per-event mechanism; match that definition).
   - `z_half = counted / dead`. This REPLACES the scalar `z_genuine` (0.382) in the gross-up.
3. **Rewire the closed form** (clone the math from `src/s08_counterfactual.py main()`, central knob_set
   only — `silent_marked|overall|pooled_all|hl=4.0|on`, windows 1H+2H and 2H_only):
   - true_stoppage `tsw` and played `plw` UNCHANGED (`ts_window_min`, `played`). Method 2 only changes
     the CLOCK→LIVE conversion + the decay horizon.
   - gross-up factor (was `flw = lsw*(1 + z_genuine*(1-lsw))`): use
     **`flw = ls_half*(1 + z_half*(1 - ls_half))`** per (match,half).
   - `olive[h] = max(0, tsw - plw) * flw`.
   - decay horizon (was `T2 = olive_2H / ls2`): use **`T2 = olive_2H / ls_half[2H]`**.
   - `avg2 = avg_lambda(T2, 4.0, obs2, floor2)`; `mu_1H+2H = lam1*olive_1H + avg2*olive_2H`;
     `mu_2H_only = avg2*olive_2H`; `P = 1 - exp(-mu)`; `X% = mean(P)`.
   - **λ rates (`lam1`, `obs2`, `floor2`) stay as the pooled cells** — Method 2 changes only the
     live-share/z conversion, not the goals-per-live-minute population rates.
   - outcome-flip: reuse `outcome_flip()` exactly (tied@90 → P(mu); lead_by_1@90 → P(mu/2);
     lead_by_2plus → 0), keyed on `match_state.state_at_90`.

### Deliverables (report, do not lock)
1. **Headline:** central X% **scoreline** (1H+2H and 2H_only) and **outcome-flip**, vs the LOCKED
   23.6% scoreline / 12.1% flip and vs Method 1 (~23.4%). State whether Method 2 stays inside the
   gross-up band **[21.1%, 24.2%]** or moves out of it.
2. **Spain–England (Euro 2024 final)** specifically: omitted time (min), omitted LIVE minutes, P
   scoreline, P flip — under Method 2 vs the locked central (19.6% scoreline / 10.3% flip) vs Method 1
   (17.8% / 9.3%). EXPECTED direction: Method 2 should RAISE it, because whole-half live share (~0.55–0.60)
   ≫ its unrepresentatively-dead stoppage-window share (~0.26) — i.e. it rejects the "omitted minutes are
   as dead as the few wasted played ones" assumption. Confirm and quantify.
3. **Diagnostics to report:** pooled-mean `ls_half` vs stoppage-window `lsw` (1H and 2H); pooled-mean
   `z_half` vs 0.382; corr(`ls_half`, `z_half`). NOTE the cancellation caveat: the locked headline is
   robust partly because live share scales BOTH omitted-live AND λ-exposure (μ ≈ G·omitted/total, ADR-0026).
   Method 2 changes the omitted-live live share but NOT the λ-exposure live share (still stoppage-window
   live-minutes in `build_lambda_cells`), so it deliberately breaks that cancellation — flag how much of
   any headline move comes from that vs from z_half.

### Guardrails (CLAUDE.md §6 + ADR-0025 lock)
- **This is ANALYSIS, not a lock or a build.** Do all of it in a standalone script (e.g.
  `src/method2_samehalf.py`) that READS the production parquet and writes only a small report (md/print).
  Do NOT overwrite `processed/counterfactual*.parquet`, the s08 grid, the figures, or `params.yaml`.
  (Pattern to copy: `src/bip_headline_sensitivity.py` writes to a throwaway dir; ADR-0026.)
- If Method 2 moves the central X% **materially** (outside [21.1%, 24.2%], or flips the
  scoreline/outcome story), STOP and bring it to a human checkpoint before any lock change — the
  headline is LOCKED (ADR-0025) and silent treatment is a calibrated POINT, not a band.
- Write up the result as a new ADR (ADR-0028) and update this pointer.

### Constants + paths (sanity-check; read live values from the code/parquet, don't hard-code)
- Central knob_set `silent_marked|overall|pooled_all|hl=4.0|on`; windows `1H+2H` (headline) and `2H_only`.
- `thr = params.yaml:phases.half_stoppage_s = 2700`; decay `h = 4.0`.
- pooled λ sanity values: 1H stoppage `lam1 ≈ 0.0478`, observed 2H `obs2 ≈ 0.0816`, open-play floor
  `floor2 ≈ 0.0427` /live-min; `z_genuine ≈ 0.382`; `residual_silent_s = 24.2`; addable split
  `f1 ≈ 0.372 / f2 ≈ 0.628`.
- true_stoppage (central): `ts_window_min = (lower_bound_s + silent_marked_s + 24.2*fshare[h]) / 60`,
  `fshare = {1H:f1, 2H:f2}`; omitted clock = `max(0, ts - played_in_stoppage_min)`.
- Files: `interim/{matches,match_state,incident_stoppage,bip_segments,played_in_stoppage}.parquet`,
  `processed/{stoppage_live_share,productivity}.parquet`. Spain–England = `matches.stage=='Final'` in
  the Euro 2024 (POST) tournament. Reproduce the locked central P first (must match
  `processed/counterfactual.parquet`) BEFORE swapping in Method 2 — that proves the harness is faithful.

---

**[SUPERSEDED by ADR-0031 re-lock, 2026-06-25 — now 24.8% / flip 13.0%; see the top of this file. Block retained as the original-lock history.]**
**HEADLINE LOCKED — 2026-06-19 (ADR-0025). THE MODELING PIPELINE IS DONE.** X% = **23.6%
(95% CI 20.6%–27.4%)**, window **1H+2H**, central knob_set `silent_marked|overall|pooled_all|hl=4.0|on`.
Framing: *if stoppage time were measured and awarded per the rulebook, ~24% of matches would have ended
with a DIFFERENT SCORELINE.* Reported with a sensitivity table over the LEGITIMATE knobs (decay
half-life 22–25%, gross-up off/on/geom 21.1/23.6/24.2%, λ source 22.6–26.1%, conditioning 23.4–23.6%;
joint envelope 18.6–27.3%) + the sampling CI. **Outcome-flip secondary reported separately: 12.1%
[10.6%, 14.2%]** (scoreline ≠ outcome). **KEY LOCK DECISION (user 2026-06-19): silent treatment is a
SINGLE CALIBRATED ESTIMATE (silent_marked, calibrated to Nate), reported as a POINT — NOT a sensitivity
range.** silent_none/all are known-wrong bounds, kept ONLY as an internal grid guardrail; never reported
as a range (this REVISES red-team must-fix #1). s09 reporting + f05 figure updated accordingly; ADR-0025
written; 26/26 pytest green. **Only optional remaining unit: the DEFERRED descriptive board_announced
scrape (`prompts/scrape_board_announced.md`) — never enters X%.** Everything below is HISTORY.

**AUTHORITATIVE POINTER (2026-06-18) — HEADLINE MODEL REDESIGN IN FLIGHT; X% LOCK STILL PAUSED. [SUPERSEDED — LOCKED ADR-0025 above.]**
Full spec: **`docs/redesign.md`**. **IMPL-6 DONE — RATIFIED 2026-06-18 (ADR-0019).** The closed-form
any-extra-goal remodel is built and validated (see ADR-0019 for the grid + the TWO-TEAM-rate trap):
W/D/L Monte Carlo replaced by `mu = sum_h lambda_h * omitted_live_h`, `P(change)=1-exp(-mu)`,
`X%=mean(P(change))`; team_role dropped; λ pooled (added `pooled_all`); 1H window plumbed; board
RENAMED to played_in_stoppage (+ NULL `board_announced` for R1); DC1 live-minute denominator
reconciled (811→894.5, asserts to 0.00s); DC3 f01 regulation-only. **24 pytest green; s07→08→09
re-run.** New grid (central `silent_marked|overall|pooled_all`): **1H+2H X=23.8% [20.4%, 27.9%]**,
2H_only 17.1%; full grid 12.5–36.4%; silent bands none 12.5–14.9% / marked 22.6–26.1% / all
32.1–36.4%; monotone none≤marked≤all in all 144 cells. **X% is deliberately NOT LOCKED** (CLAUDE.md
§6 — lock is the final session, after IMPL-7).

**POST-IMPL-6 DECISIONS RATIFIED 2026-06-18 (ADR-0021) — metric framing + the band the lock SELECTS.**
After the user reasoned through the closed form from first principles (why 23.8% is not a bug — the
live_share cancels in mu, so X% ≈ stoppage goals × omitted/played CLOCK ratio, both Nate-validated),
four decisions are locked into the SPEC (not the number): (1) **Headline = different SCORELINE**
(≥1 extra goal; central 23.8%, 1H+2H) and ALSO report the stricter "different OUTCOME" (winner/draw
flips, ≈12.7% illustrative). (2) **Productivity-premium BAND** is committed: UPPER = observed
stoppage λ (today) 23.8% / 2H 17.1%; LOWER = open-play λ (`productivity[phase=regular]`≈0.0427) on
omitted minutes 16.3% / 2H 9.7% → honest band ≈16–24%, truth nearer the top. (3) **O3 in-stoppage
time-wasting gross-up** — implement faithfully even though it RAISES X% (no agenda). (4) **First-goal
hazard — do NOT overengineer**: `P(≥1)=1−P(0)` already only uses the pre-first-goal hazard, and the
open-play floor brackets it. These BUILD in **IMPL-7 Part C** so the final session just SELECTS rails.
Full rationale: `docs/decisions.md` ADR-0021 + `docs/redesign.md` ADDENDUM. **X% still NOT LOCKED.**

**IMPL-8 — omitted-time productivity DECAY — DONE 2026-06-19 (ADR-0024). HUMAN CHECKPOINT PENDING.**
Built `prompts/impl_8_productivity_decay.md`. Method A exponential decay now lives in s08:
`avg_lambda(T,h)` ramps the per-match 2H rate from the observed 2H-stoppage cell (0.0816) toward the
`__regular__` open-play floor (0.0427) over the omitted window; **1H unchanged**; decay horizon = the
GROSSED-UP clock `T = olive_2H / live_share_2H` (recomputed per bootstrap draw). Knob swapped to
`productivity_decay_halflife_min: [.inf, 8, 4, 2, 0]` (central **h=4**, band **[2,8]**; `.inf`/`0`
are regression-only endpoints). Bootstrap now draws BOTH endpoint cells. Two central flips folded in:
**gross-up central = ON** (+ geometric-ceiling row reported) and **silent = headline POINT
(silent_marked)**. **z-CORRECTION (2026-06-19, user interrogation):** the gross-up over-credited by
recurring the FULL dead share (implicit `z=1`); only the genuine-stoppage fraction of dead time recurs.
Measured z = (lower_bound+silent_marked)/total_dead in regulation = **0.382** (`genuine_stoppage_share`,
traces to bip_segments + incident_stoppage); gross-up now recurs `z·(1−ls)≈0.18`, collapsing the
geometric tail to just above ON (was 1/live_share). **Results (NOT a lock): central
`silent_marked|overall|pooled_all|hl=4.0|on` = 1H+2H 23.6% [CI 20.6%, 27.4%]; 2H_only 16.0%;
outcome-flip 12.1%.** Decay band 1H+2H 22.2%(h2) .. 23.6%(h4) .. 24.9%(h8). Gross-up rails (h=4,
z=0.382): off 21.1% → on 23.6% → geometric 24.2%. Endpoints back out the OLD rails byte-close: h=inf
1H+2H 23.8% / 2H_only 17.1%; h=0 2H_only 9.7% (h=0 1H+2H = 17.0%, not 16.3% — decay floors only 2H, by
design). Assumption÷sampling 4.0× → **1.3×** with silent fixed. New permanent figure
**`figures/f06_productivity_decay.png`**; new table `processed/decay_profile.parquet`; **26 pytest green**
(`test_s08_decay_endpoints`, `test_s08_avg_lambda_decay`). **NEXT: bring the grid + f06 to the user for
the human checkpoint, then run the LOCK (do NOT lock X% in IMPL-8).**

**→ CURRENT UNIT = DONE.** The final LOCK ran 2026-06-19 (ADR-0025). No modeling unit remains; the only
optional follow-up is the deferred descriptive board_announced scrape (`prompts/scrape_board_announced.md`).

**THEN — the final LOCK** (IMPL-7 Parts A.2 + C DONE 2026-06-18, ADR-0023; R1+R2 DONE).
- R1 — announced-board sourcing: **DONE 2026-06-18 (ADR-0020).** YES, free for all six via SofaScore
  incidents API (`injuryTime.length` per half). Findings: `prompts/research_board_findings.md`;
  memory `reference_board_announced.md`.
- R2 — cooling-break policy/detection: **DONE + DE-SCOPED 2026-06-18 (ADR-0022).** Read-only empirical
  check REJECTED the "improves r vs Nate" hypothesis. **Cooling detection is DROPPED — Part B not built.**
  Findings: `prompts/research_cooling_findings.md`; memory `reference_cooling_policy.md`.
- IMPL-7 Parts A.2 + C — **DONE 2026-06-18 (ADR-0023).** Wired into s07/s08/s09, all reproduce ADR-0021:
  productivity-premium BAND rails (1H+2H 16.3% open_play floor .. 23.8% observed; 2H_only 9.7% .. 17.1%),
  O3 time-wasting gross-up (1H+2H 23.8→31.6%, faithful/RAISES X%), outcome-flip secondary (12.2% 1H+2H /
  8.8% 2H_only), A.2 in-stoppage time-wasting descriptive (pooled rate 50.6%, PRE 3.26 / POST 5.19 min).
  Two new knobs in `params.yaml` (`productivity_premium_knobs`, `timewaste_grossup_knobs`); 5-part
  knob_set; central `silent_marked|overall|pooled_all|observed|off`. **24 pytest green.**
- **DEFERRED — IMPL-7 Part A.1 (announced-board under-allocation Δ).** `board_announced` still NULL.
  Turnkey scrape unit: **`prompts/scrape_board_announced.md`** (SofaScore incidents, 314 matches,
  ~3 h rate-limited; ADR-0020 API). Δ = `true_stoppage − board_announced` is a DESCRIPTIVE distortion
  only (never calibrated into X%). Run as its own session before/independent of the lock.
- **RED-TEAM the methodology — DONE 2026-06-18.** Findings: `prompts/redteam_methodology_findings.md`.
  **Verdict: publishable WITH CAVEATS — no FATAL issues.** The central object is sound (realized
  2H-stoppage goal counts are Poisson, var/mean=0.99) and magnitudes match Opta/538. The exposure is
  framing, not arithmetic. **MUST-FIX items the LOCK must absorb (all anticipated by the docs; the job
  is to LEAD with them, not just report alongside):**
  1. **Lead with the BAND ≈16–24%, not the 23.8% point.** Observed stoppage λ is endogenous to game
     state (over-states); `[20.3,28.0]` is within-knob CI only — the silent axis (12.5%→36.4%) is the
     dominant uncertainty and must be named.
  2. **Separate scoreline from outcome in the wording.** "≥1 extra goal in ~24%" vs "result flips in
     ~12.2%". 32.7% of the 23.8% mass is `lead_by_2plus` matches that cannot flip. "Ended differently"
     attached to 23.8% is the most attackable sentence.
  3. **Carry the COVERAGE caveat verbatim:** Nate validates WC2018 only; POST (esp. Copa 25.3 / AFCON
     23.5 min true_stoppage, ~2× WC2018 silent) is validated only indirectly (frozen-2018 estimator
     constants + the WC2022 Opta BIP point). That flag must survive into the headline ADR.
  Nice-to-have: reframe the Poisson justification (cite late-goal non-homogeneity, not Maher/Dixon-Coles);
  report pre/post X% split (PRE 26.1 / POST 22.8 — kills the composition-artifact objection); cite the
  post-directive Bundesliga under-addition study as external support for POST omitted-time>0;
  (optional, descriptive) re-derive shot subtype for the 96 stoppage goals to state the penalty share.
  **TWO red-team findings DOWNGRADED 2026-06-19 (SERIOUS→COSMETIC), both verified read-only:**
  - **S4 (BIP gap-rule transfer) — DEFUSED.** The 20s rule's premise is dense active logging, and
    event-logging density is constant across all six tournaments (62.6 events/live-min ±4%); active
    inter-event gaps have median 0.70s / q99 6.0s, so the 20s cut is ~3× past q99 (0.26% of gaps ≥20s)
    — ADR-0009's G∈[15,25] sweep holds everywhere. live_share's Copa/AFCON dip (0.43/0.47 vs ~0.51–0.56)
    is real football (more dead time), NOT a logging artifact, and runs conservative for X%. No longer
    a must-fix; cite the density-uniformity as a defense.
  - **S5 (penalty composition) — interpretation corrected (per user).** Elevated stoppage-penalty
    incidence is NOT referees applying a different threshold; refs are consistent across normal/stoppage
    time. The higher rate is teams playing more aggressively (open-field play), consistently refereed —
    so penalties are aggression/flow-driven and partly transplantable, not a "different-refereeing"
    artifact. The residual (does that aggression persist in omitted/decided-game minutes?) just folds
    into S2's productivity-premium band; the lumpiness worry is already defused by C1 (counts incl.
    penalties are Poisson, var/mean 0.99). Penalty share is now a NICE-TO-HAVE descriptive diagnostic.
- **THEN — lock X% + CI + sensitivity band** — turnkey prompt **`prompts/lock_headline.md`**.
  Fill the ADR-XXXX HEADLINE template in `docs/decisions.md`, eyes open: just SELECT the rails (silent
  treatment, productivity-premium rail, window, λ source) from the s08 grid + ledger. HUMAN CHECKPOINT —
  decide WITH the user. Nothing left to BUILD.
Each is self-contained; **`docs/redesign.md`** is the full spec.
**Everything below this line is HISTORY (IMPL-0→IMPL-6, all DONE).**

**AUTHORITATIVE POINTER (2026-06-15):** Items 1 and 2 are DONE. The silent-component research
has been run; findings are in `prompts/silent_component_findings.md` (reviewed). **IMPL-0
(validation scaffolding) is DONE** (see below). **IMPL-1 (plumb out-of-play markers through s02)
is DONE** (2026-06-15 — see ADR-0013).

**IMPL-2 CLOSED — RATIFIED 2026-06-15 (ADR-0014 + ADR-0015): do NOT promote marker-gating into
`bip.py`. `bip.py` stays the validated duration rule. Marker-gating is applied ONLY to the s05
stoppage silent term (that is IMPL-3).** Built the marker-gated reclassifier (`src/lib/silent.py`,
kept but UNWIRED) and tried promoting it into `bip.py`; the promote-gate cannot be met —
marker-gating REGRESSES validated BIP (r 0.943→≤0.92, MAE 1.25→4.0) because 538's WC2018 BIP
(55.3) is BELOW the old duration rule (56.0): the long silent gaps are GENUINELY dead and only 25%
carry a marker. Reverted `bip.py`/`s03_bip.py`/`params.yaml`/`tests` to the ADR-0013 baseline
(s03 green at 3460s). The "one shared classifier in bip.py" hypothesis is FALSIFIED and abandoned.

**Why marker-gating IS the right tool for s05 (not BIP).** BIP = TOTAL dead time; stoppage =
ADDABLE dead time — genuinely different questions. The marker test splits the silent bucket:
`silent_marked` correlates r=0.71 with Nate `expected`, `silent_unmarked` only r=0.25 (a flat
~8.4 min/match baseline). The old estimator over-counts because it credits the unmarked flat
baseline as addable stoppage (`lb + all silent` → mean 19.7, the Germany-Sweden 17.4 signature).
Marker-gating the SILENT TERM fixes it: `lb + marked silent` r=0.768 MAE 3.15; `marked silent +
calibrated const` MAE 2.22, mean 13.2.

**External data (Wyscout/FIFA/CIES/tracking) — DECLINED for the silent-component goal (ADR-0015).**
Wyscout's explicit interruption events label ball-out timing (the BIP axis, already r=0.943), not
addable-ness (the hard part); it covers WC2018 only (duplicates Nate) and never the POST
tournaments the headline depends on. Survey saved to memory `reference_external_datasets.md` as a
triangulation footnote, not a model input.

**IMPL-3 DONE — RATIFIED 2026-06-16 (ADR-0016).** Built the marker-gated true-stoppage estimator
in s05 (`bip.py`/s03 untouched, verified): `lower_bound + marker-gated silent + residual constant`.
Validated vs Nate `expected` (32 WC2018): ablation lower_bound r=0.655 → +marked silent r=0.768
(MAE 3.15, mean 11.26) → +residual r=0.768 (MAE 2.75, mean 13.16 ≈ Nate 13.16). **Gate met** (beat
0.61–0.73 baseline, hit reset ~0.77 target). Diagnostic: vs the old over-counter the LOW matches
collapse (Germany–Sweden +10.9→+3.3, Russia–Egypt +6.9→−0.7, Uruguay–Saudi +7.5→+0.9) while HIGH
hold (Belgium–Panama +0.2, Tunisia–England +3.3). Residual constant `silent.residual_silent_s=114.0`
(1.9 min) FROZEN in params, fit on 2018, applied to all six. New artifact
`interim/true_stoppage.parquet` (per match); `silent_marked_s` added to `incident_stoppage.parquet`.
**Coverage flag:** Nate is WC2018-only; POST validated indirectly via the frozen 2018 calibration +
s03 WC2022 Opta BIP gate.

**IMPL-4 SETUP DONE (2026-06-16) — data + plumbing staged so IMPL-4 is turnkey:**
- `incident_stoppage.parquet` now ALSO carries `silent_all_s` (ungated upper bound, ~2837 min total
  vs 1344 marked) — the data source for the `silent_all` knob. `var_s` repopulated (s06b re-run, my
  s05 re-run had reset it to 0).
- `params.yaml:silent` now exposes `estimator_pearson_r: 0.768` and `estimator_mae_min: 2.75` for
  IMPL-4's CI propagation.
- New guard tests (`tests/test_pipeline.py`): `test_s05_silent_marked_within_all`,
  `test_s05_true_stoppage_estimator`. **All 22 tests green.**
- `prompts/impl_4_counterfactual_lock.md` now has a Handoff + Gotchas section: exact columns, the
  s08 `true_stoppage_minutes` (~line 134) + `true_stoppage_knobs` list to rewire, and the key
  LANDMINE — s08 is a 2H-only (period 2) frame but the residual (114s) / MAE (2.75) were fit on
  FULL-MATCH totals vs Nate, so they must be scaled to the 2H frame, not bolted on raw.

**IMPL-4 CODED + TESTED but X% deliberately UNLOCKED (2026-06-16).** The silent-treatment knob
(`silent_none`/`silent_marked`/`silent_all`) is wired into s08, the ~±2.75 min estimator MAE is
2H-scaled and propagated into the `silent_marked` CI, s09 + ledger updated, new guard test added
(23 green, all gates green). The grid answered the decisive question — **X% is NOT robust to the
silent assumption:** silent_none 2.9–4.0%, silent_marked 7.4–9.9%, silent_all 9.6–12.7% (it
roughly triples). A headline that swings 3%→12% cannot be locked, so we go back and improve the
per-match estimator FIRST. IMPL-4 stays coded-but-unlocked; re-run it AFTER IMPL-5.

**IMPL-5 DONE — RATIFIED 2026-06-17 (ADR-0017).** Made the s05 estimator more precise by folding
**restart-excess** (Nate's allowances: throw-in 20s / goal-kick 30s / corner 45s / free-kick 60s,
credit `max(0, gap−allowance)`) into `lower_bound`. **Task A KEPT, Task B (marker refinements)
DROPPED** — no lead-window/trail-edge variant beat the bar (lead-window over-credits and re-inflates
Germany–Sweden; trail-edge gating drops r below 0.768). `silent.py` UNCHANGED; bip.py/s03 FROZEN.
Validated vs Nate `expected` (32 WC2018): ablation lower_bound r=0.655 → +restart_excess r=0.754 →
+marked silent r=0.825 (MAE 2.49) → +residual **r=0.825 / MAE 2.44, mean 13.16** — beats ADR-0016's
0.768 / 2.75 on BOTH axes. Diagnostic holds (LOW shrinks, HIGH holds). Re-fit + froze on 2018:
`incident.restart_normal_s` (NEW), `silent.residual_silent_s` 114.0→24.2, `estimator_pearson_r`
0.768→0.825, `estimator_mae_min` 2.75→2.44. New cols `restart_excess_s`/`lower_bound_base_s` on
incident parquet; s06b re-run to restore `var_s`; **all 23 pytest green.** **Honest finding:**
restart_excess raises the `silent_none` FLOOR but does NOT narrow the `marked`↔`all` band — the
silent uncertainty is irreducible with free StatsBomb data, so X% likely still ships as a band.

**IMPL-4 RE-RUN — SUPERSEDED BY THE REDESIGN (2026-06-17, ADR-0018).** The s08 grid was re-run with
the tighter estimator (silent_marked ~8.1–9.9%) but X% was NOT locked: the user reopened the model at
first principles (metric → any-extra-goal, drop team_role, pool λ, add the 1H window, rename board).
The old W/D/L-flip s08 is being replaced in IMPL-6. See `docs/redesign.md` + ADR-0018. Do NOT re-run
the old s08 to lock; do IMPL-6 instead.

**Turnkey prompts (open a fresh session and run one):**
- `prompts/research_board.md`        → R1 (DONE 2026-06-18, ADR-0020 — SofaScore; see research_board_findings.md)
- `prompts/research_cooling.md`      → R2 (DONE + DE-SCOPED 2026-06-18, ADR-0022 — see research_cooling_findings.md)
- `prompts/impl_7_board_cooling.md`  → IMPL-7 (CURRENT — board under-allocation Part A + band-building Part C; Part B cooling DE-SCOPED)
- `prompts/impl_6_remodel.md`        → IMPL-6 (DONE 2026-06-18, ADR-0019 — core remodel)
- `prompts/impl_1..3, impl_5, impl_4_counterfactual_lock` → IMPL-0→IMPL-5 (DONE — history)
Each is self-contained; **`docs/redesign.md`** is the full spec the IMPL prompts execute.

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

### Methodology decision (REVISED 2026-06-15, ADR-0015): TWO definitions — bip.py unchanged, marker-gating in s05 only
The "one shared classifier in bip.py" idea (originally DECIDED here) was FALSIFIED in IMPL-2 and is
abandoned. BIP and stoppage answer DIFFERENT questions: BIP = TOTAL dead time (it needs the
unmarked silent gaps, which are genuinely dead — 538's WC2018 BIP 55.3 < the duration rule's 56.0);
stoppage = ADDABLE dead time (it must EXCLUDE the flat unmarked baseline). One classifier cannot
serve both: marker-gating BIP regresses it (r 0.943→≤0.92).

**Decision:** `src/lib/bip.py` STAYS the validated duration rule (ADR-0003/0013) — s03 untouched,
do not re-tune. Marker-gating (`src/lib/silent.py`) is applied ONLY to the s05 stoppage silent
term (IMPL-3). The findings doc's §"DECIDED: one classifier in bip.py" is superseded — see the
note now in that file.

---

### IMPL-1 — DONE (2026-06-15). Out-of-play markers plumbed through s02. See ADR-0013.

**Outcome:** added `pass_outcome`, `gk_type`, `gk_outcome` to `interim/events_norm.parquet`
(`out` was already there). s02 gate PASSED; s03 BIP UNCHANGED (3460s, share 0.569) — columns not
yet consumed. Spot-check across all six tournaments confirmed the same populated schema; key
finding for IMPL-2: the `out` flag lands mostly on Block/Clearance/Miscontrol and is sparse, so
the marker set must OR `out` with `pass_outcome="Out"` (5,471 rows) etc., not rely on `out` alone.
Next: **IMPL-2** (`prompts/impl_2_reclassify_bip.md`).

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

### IMPL-2 — DONE/CLOSED (2026-06-15, ADR-0014 + ADR-0015). Marker-gated reclassifier built; NOT promoted into bip.py.

**Outcome:** built `src/lib/silent.py` (the marker test, kept but UNWIRED) and tried promoting it
into `bip.py` as the shared live/dead classifier. The promote-gate could not be met — marker-gating
REGRESSES validated BIP (r 0.943→≤0.92, MAE 1.25→4.0) because 538's WC2018 BIP (55.3) is BELOW the
duration rule's 56.0: the long silent gaps are genuinely dead and only ~25% carry a marker. Per the
prompt's STOP instruction, reverted `bip.py`/`s03_bip.py`/`params.yaml`/`tests` to the ADR-0013
baseline (s03 green at 3460s). The follow-up investigation (decomposing dead time into restart /
silent_marked / silent_unmarked) proved the marker test is the right tool for the s05 stoppage term,
not for BIP. **Decision ratified by the user:** abandon the bip.py promotion; apply marker-gating
ONLY in s05 (IMPL-3). `silent.py` is ready to be consumed by s05. See ADR-0014/0015 for the full
diagnostic and the marker set.

Next: **IMPL-3** (`prompts/impl_3_estimator_validate.md`).

---

### IMPL-3 — DONE (2026-06-16, ADR-0016). Estimator built in s05, r=0.768 / MAE 2.75 vs Nate `expected`. Next: IMPL-4.

**Goal:** build the corrected true-stoppage estimator **in s05** (NOT bip.py) as
`lower-bound credit + marker-gated-silent + calibrated-residual + explicit injury/sub/goal credit`,
freeze the residual constant on 2018, and validate against Nate's 32 WC2018 matches. `bip.py`/s03
stay untouched — they are the validated duration rule.

**Do:**
- In `src/s05_incident.py`, keep the existing lower-bound components (celebration/sub/card/injury,
  each ∩ s03 dead segments) as-is — small and stable, do NOT re-derive. ADD a marker-gated silent
  term: of the ≥`silent.min_silent_gap_s` non-restart gaps, credit ONLY those whose lead edge
  carries an out-of-play marker (use `src/lib/silent.py`, already written). DROP the unmarked
  silent gaps — genuinely dead (BIP keeps them) but a flat non-addable ~8.4 min/match baseline;
  crediting them is the over-count.
- Fit a single **residual-silent constant** on 2018 (the irreducible unmarked-but-addable
  remainder). Freeze it in `params.yaml`; apply the SAME constant to all six tournaments (POST
  cannot be fit — no ground truth).

**Gate — RESET (the old ≥0.85 target is falsified; ~25% marker coverage caps it at ~0.77):**
- **Per-match:** Pearson r + MAE (min) vs Nate's **`expected`** column (NOT `actual`). Use
  `src/lib/nate.report(pred, "expected", "estimator")`. **Beat the ~0.61–0.73 baseline; target
  ~0.77.** Landing ~0.77 with a clean ablation IS success — do not chase 0.85.
- **Aggregate:** 32-match mean estimator vs Nate's `expected` mean — stays ≈13 min level.
- **Diagnostic:** per-match before/after for the five named matches — error shrinks on the three
  low-injury ones (Germany–Sweden, Russia–Egypt, Uruguay–Saudi) WITHOUT breaking the two
  injury-dominated ones (Belgium–Panama, Tunisia–England).
- **Ablation table:** r/MAE for lower-bound alone → + marker-gated silent → + residual-constant.
- **Coverage flag:** Nate validates WC2018 only; POST is validated indirectly via the frozen 2018
  calibration + the s03 WC2022 Opta BIP gate.

**Checkpoint:** ADR with the full validation table; freeze the residual constant in `params.yaml`.
Update this file: mark IMPL-3 DONE, point to IMPL-4. STOP. **Bring the r/MAE/diagnostic table to
the user before proceeding.**

---

### IMPL-4 — Propagate estimator error into s08; re-run s07→s09; lock X% (HUMAN CHECKPOINT)

**Goal:** make the silent treatment an explicit sensitivity knob, make the headline CI honest,
then lock the single modeled claim. **The decisive question: does X% even depend on the silent
assumption?** If robust across the knob, the irreducible silent uncertainty does not threaten the
claim and we say so; if not, we report the band.

**Data ready (IMPL-4 setup, 2026-06-16):** `incident_stoppage.parquet` carries `silent_marked_s`
+ `silent_all_s`; `params.yaml:silent` has `residual_silent_s`/`estimator_pearson_r`/
`estimator_mae_min`. Rewire `s08:true_stoppage_minutes` (~line 134) + `counterfactual.true_stoppage_knobs`.
**LANDMINE:** s08 is a 2H-only (period 2) frame; the residual/MAE were fit on FULL-MATCH totals vs
Nate — scale them to the 2H frame, don't bolt on raw. Full handoff in `prompts/impl_4_counterfactual_lock.md`.

**Do:**
- Add a **silent-treatment knob to s08** with ≥3 settings, run end-to-end at each:
  `silent_none` (credit zero silent — hard lower bound), `silent_marked` (the IMPL-3 marker-gated
  central estimate), `silent_all` (credit all ≥threshold silent — old over-count upper bound).
  Report X% at each so the headline's sensitivity to the silent assumption is visible.
- Propagate the per-match estimator error (IMPL-3 MAE, ~±2–3 min) into the s08 bootstrap so the CI
  reflects estimator uncertainty, not just sampling. The current `[2.6–2.8%]` band is too tight.
  Only close (tied / 1-goal) matches flip the outcome — prioritize estimator accuracy there.
- Re-run s07 (finalize productivity), then s08 (sensitivity grid), then s09 (figures + ledger).

**Gate:**
- s07: every productivity cell reports n_events + live_minutes.
- s08: full sensitivity grid INCLUDING the silent-treatment knob — **read it before locking X%**
  (CLAUDE.md §4/§6); judge whether X% is robust to the silent knob.
- s09: deterministic figures + numbers ledger; every figure traces to a script + checkpointed
  table + documented assumption.

**Checkpoint:** lock the headline **X% + CI + sensitivity band** in `docs/decisions.md` with the
user, eyes open; state how sensitive X% is to the silent knob. This closes the silent-component
work.

---

## DEFERRED — original "solution b" stub (HISTORICAL; superseded by IMPL-1→IMPL-4 above)

Rebuild true-stoppage estimator as `restart-excess + calibrated-silent + explicit injury/
sub/goal credit`; freeze the calibration constant on 2018; wire Nate's exact 2018 numbers as
the validation/replacement arm. Also: propagate per-match estimator error (~±2 min MAE) into
the s08 bootstrap so the CI is honest (current `[2.6–2.8%]` band is too tight). Only the
close (tied / 1-goal) matches move the headline — prioritize estimator accuracy there.
