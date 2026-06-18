# Decisions (ADR log)

Every methodology choice gets an entry here. Newest at top. The counterfactual headline
number and its band must be locked here (with the chosen knob_set) before publishing.

---

## ADR-0023 — IMPL-7 Parts A.2 + C built: productivity-premium band, O3 gross-up, outcome-flip wired (X% still NOT locked) (2026-06-18)

**Build session, not a lock.** Executed `prompts/impl_7_board_cooling.md` Parts A.2 + C against the
processed tables (Part B de-scoped per ADR-0022; Part A.1 announced-board Δ DEFERRED — see below). The
ADR-0021 directional decisions are now wired into s07/s08/s09 and reproduce their targets exactly.
**X% is deliberately still NOT locked** (the ADR-XXXX template stays blank; the lock is the final,
separate session). Upstream FROZEN (bip.py/s03 r=0.943; s05 estimator r=0.825; ADR-0019 remodel).

**What was built.**
- **Two new knobs** in `params.yaml:counterfactual` → `productivity_premium_knobs: [observed, open_play]`
  and `timewaste_grossup_knobs: ["off", "on"]`. The grid is now 5-axis (silent × cond × source × prem ×
  gw), knob_set string `"{silent}|{cond}|{source}|{prem}|{gw}"`, 96 rows on the `all` group.
- **Productivity-premium band (ADR-0021 #2)** in s08: `open_play` swaps the per-window stoppage λ for the
  cohort's `regular`-play λ on the omitted minutes (helper `regular_lambda_cells`, cell key
  `("__regular__", cohort)`). live_share cancels in μ, so this is a λ choice; the rails are EXACT to
  ADR-0021: 1H+2H **16.3% (open_play floor) .. 23.8% (observed)**; 2H_only **9.7% .. 17.1%**.
- **O3 in-stoppage time-wasting gross-up (ADR-0021 #3)** in s08: `gw="on"` grosses up the omitted CLOCK
  by (1 + timewaste_rate), timewaste_rate = (1 − live_share), so the live factor becomes
  `lsw*(2−lsw)` vs `lsw`. Faithful, RAISES X% (user sign-off, no agenda): central 1H+2H **23.8 → 31.6%**,
  2H_only **17.1 → 23.6%**.
- **Outcome-flip secondary (ADR-0021 #1)** in s08: stricter "different OUTCOME" cut on `state_at_90` —
  tied flips on any extra goal (1−exp(−μ)); lead_by_1 flips when the trailing team (half-rate) equalizes+
  (1−exp(−μ/2)); lead_by_2plus unflippable. Per-knob `pct_outcome_flip`; central **12.2%** (1H+2H) /
  **8.8%** (2H_only). Matches ADR-0021's "≈12.7% illustrative."
- **A.2 time-wasting within played stoppage (Part A)** in s07: dead-ball minutes during the added time
  that WAS played = `played × (1 − live_share)` per (match, half) → `processed/timewasting_descriptive.parquet`.
  Pooled rate **50.6%** (dead/played); mean min/match PRE **3.26** / POST **5.19**. This is the same rate
  the s08 O3 gross-up consumes — one source, no double estimate.
- **s09**: f05 narrowed to the focused band figure (cond=overall, source=pooled_all, 12 rows labelled
  silent × prem × grossup); ledger gains Productivity-premium-band, O3-gross-up, Outcome-flip, and A.2
  sections. **CENTRAL** knob is now the 5-part `silent_marked|overall|pooled_all|observed|off` = 23.8%
  [CI 20.3%, 28.0%].

**Gate: PASSED.** `pytest` green (24/24; `test_s08_silent_knob_brackets_headline` updated to pivot the
5-part knob_set with prem+gw in the index so the none≤marked≤all monotonicity still holds per cell).

**DEFERRED (turnkey, separate session): Part A.1 announced-board under-allocation.** `board_announced`
stays NULL. The SofaScore incidents scrape (314 matches, ~3 h rate-limited, ADR-0020 API) is its own
unit — `prompts/scrape_board_announced.md`. When populated, Δ = `true_stoppage − board_announced`
becomes a full-sample DESCRIPTIVE distortion (never calibrated into the headline; same treatment as the
cooling sensitivity, ADR-0022). User chose "defer scrape; wire plumbing" to keep this session modular
and compute-light (CLAUDE.md §6).

---

## ADR-0022 — R2 resolved: cooling-break detection DE-SCOPED — no robust accuracy gain (2026-06-18)

**Research + read-only empirical check (`prompts/research_cooling.md`); no pipeline change.** The
redesign hypothesised that adding cooling-break duration as PURE stoppage would improve match-level r
vs Nate (IMPL-7 Part B). Tested against the processed tables; the hypothesis is **rejected**, so
cooling detection is **dropped from IMPL-7**. Full writeup: `prompts/research_cooling_findings.md`;
durable pointer in memory `reference_cooling_policy.md`.

**Policy context (why detection was ever in scope).** Mandatory-every-match breaks start at WC2026,
AFTER our sample. In-sample, breaks are rule-triggered: **AFCON2023** had two per match by CAF rule;
**WC2022** had ~none (winter + air-conditioned, WBGT threshold never met); **WC2018/Euro2020/Euro2024/
Copa2024** are temperature-variable (~32 °C WBGT/air trigger, ~30'/75' or ~25', 90s–3min by body).

**Empirical finding (the decisive part).**
1. **Already captured.** On AFCON2023 (breaks guaranteed), the clear break gaps (>120s in the 25'–40'
   window, n=36) average 168s, of which the s05 estimator (`restart_excess` + marker-gated silent)
   ALREADY credits **~122s (73%)**, missing only **~46s/break** (the per-restart allowance shaved off,
   ADR-0017). The "uncounted silent gap" premise is ≤27% true.
2. **No robust r gain (WC2018, the ONLY Nate-validated set; baseline r=0.825 / MAE 2.44).** WC2018
   barely had breaks (4/32 matches >120s gap, 2/32 >150s — the mild-venue prior). A naive "+3 min/break"
   DEGRADES (r→0.780, MAE +1.07) by double-counting the 73% already credited; the correct
   "missed-remainder only" (+~46s) moves r by +0.012–0.014 at strict thresholds but −0.016 at a loose
   one — sign flips with the threshold, i.e. within noise.
3. **Unvalidatable where it matters.** Breaks concentrate in POST (AFCON/Copa), which has no Nate
   ground truth; the one external check (WC2018) can't show a gain.

**Decision.** De-scope cooling detection from IMPL-7 (drop Part B). Do not build the weather-gating /
commentary pipeline. If ever wanted, represent cooling ONLY as a small, clearly-labeled POST-only
sensitivity (~46s/break × detected breaks ≈ ~1.5 min/match on AFCON), shown as a band, never
calibrated into the headline — same treatment as the announced-board under-allocation (ADR-0020).
This does NOT change the frozen s05 estimator or the headline; IMPL-7 now = board_announced
under-allocation (R1/ADR-0020) + Part C band-building (ADR-0021).

---

## ADR-0021 — Headline framing + productivity-premium band (pre-lock DIRECTION; X% still NOT locked) (2026-06-18)

A post-IMPL-6 (ADR-0019) discussion with the user resolved four modeling questions that steer IMPL-7
and the final lock. These are DIRECTIONAL decisions recorded as the source of truth; **X% is still
not locked** (that is the final session). Build the s08/s09 changes in IMPL-7, not before.

**1. Metric framing (extends D1).** Headline = "stoppage time is a sham; measured properly, X% of
matches would have ended with a DIFFERENT SCORELINE" — i.e. ≥1 extra goal in the omitted stoppage
(central 23.8% on the 1H+2H window). ALSO report the stricter "different OUTCOME" cut (winner/draw
status flips), ≈12.7% illustrative (only the 98 tied + 121 lead-by-1 matches can flip; per-team
half-rate split). **Report both; the headline number is scorelines.**

**2. Productivity-premium BAND (new committed sensitivity).** The end-game productivity premium
(final minutes run ~1.4× the match-average pace per clock-minute; observed 2H-stoppage λ=0.0816 vs
open-play 0.0427) reflects urgency that cannot be assumed for ALL the newly-added omitted minutes.
Ship the headline as a band over the λ applied to omitted time:
- **UPPER = observed stoppage λ** (today): 1H+2H **23.8%**, 2H-only 17.1%.
- **LOWER = open-play λ (0.0427)** on omitted minutes: 1H+2H **16.3%**, 2H-only 9.7%.
Honest headline band ≈ **16–24%**, truth nearer the top (omitted minutes are end-of-half, same game
state); 16.3% is the "zero-premium" floor (still ~1 in 6). NOTE: `live_share` CANCELS in mu (it
scales λ up and omitted_live down equally), so mu ≈ goals-per-CLOCK-min × omitted-CLOCK-min — the
band is driven by the λ choice, not by the live-share assumption.

**3. O3 time-wasting gross-up — RESOLVED: implement faithfully (IMPL-7).** Add back, to omitted
CLOCK time, the in-stoppage time-wasting that added time itself generates, then apply productivity to
the live portion. The user accepts this RAISES X% (opposite to the "predicts too many changes" worry)
— **measure faithfully, no agenda.** [[feedback-modeling-decisions]]

**4. First-goal hazard — minor, do NOT overengineer.** P(≥1)=1−P(0 goals) already depends only on the
pre-first-goal hazard, so "I don't care what happens after the first goal" is built into the closed
form (and is exactly why D1's any-goal metric beats the old W/D/L sim — it needs no post-goal state).
Observed λ is mildly inflated by the 8 of 73 2H-stoppage goals that are 2nd+ goals in the same window;
the open-play floor (#2) already brackets that, so leave it. Optional IMPL-7 nicety only: re-estimate
λ on pre-first-goal stoppage minutes.

---

## ADR-0020 — R1 resolved: announced 4th-official board sourceable free (SofaScore) for all six (2026-06-18)

**Research only (`prompts/research_board.md`); no pipeline change. Wiring is IMPL-7.** The redesign
left `board_announced` NULL "pending R1" (DC2); R1 now confirms the announced board (the +X minutes
the 4th official shows at 45'/90', distinct from the time-PLAYED measurement of ADR-0011) is
obtainable FREE for ALL SIX tournaments — better than the redesign assumed (it scoped this as
possibly-NULL / WC2022-only). Full writeup: `prompts/research_board_findings.md`; durable pointer in
memory `reference_board_announced.md`.

**Source = SofaScore unofficial JSON API.** `https://api.sofascore.com/api/v1/event/{id}/incidents`
emits one incident per half: `{"length":9,"time":90,"incidentType":"injuryTime"}` → `length` = the
announced board minutes (integer), `time` 45 = 1H, `time` 90 = 2H. Event IDs via
`…/unique-tournament/{ut}/season/{s}/events/last/{page}` (WC ut=16: 2018 s=15586, 2022 s=41087;
AFCON ut=270: 2023 s=56021; Euro/Copa via `…/search/all?q=`). **Verified populated live** for the
oldest + least-mainstream cases: WC2018 KOR–GER (7659904) 1H+3/2H+9; AFCON2023 NGA–CMR (11940739)
1H+6/2H+10; a 2024-era match (9576070) +2/+4. Strong inference all six covered — still spot-check
Euro2020/Euro2024/Copa2024 with one event each before relying.

This UPDATES ADR-0010's "Sofascore was Cloudflare-blocked" note: the *summary* path was blocked, but
the *incidents* path works. Caveats: unofficial/undocumented, Cloudflare rate-limits (~1 req/25–30s,
UA + sleep), ToS gray area; join to StatsBomb by teams+date; spot-check ~5 `length` values vs
BBC/Guardian live text to confirm it is the announced minimum, not derived. Confirmed dead ends:
StatsBomb (only Half-End timestamps = time played = `played_in_stoppage`), Wikipedia (verified —
goals/cards only), API-Football (`time.extra` = event minute-offset, not the board), results DBs,
and FIFA's public match center (exact figure lives in the non-public referee report).

**Implication for IMPL-7:** populate `board_announced` from `injuryTime.length` (×60 → seconds) for
all six; under-allocation Δ = `true_stoppage − board_announced` becomes a FULL-SAMPLE distortion, not
WC2022-only. The board=time-played MEASUREMENT (ADR-0011) is unchanged — this is the separate
announced number it was always distinct from.

## ADR-0019 — IMPL-6: core remodel built — closed-form any-extra-goal metric, pooled λ, 1H window, board renamed (2026-06-18)

**Human checkpoint — new sensitivity grid produced; X% still NOT locked** (the lock is the
post-IMPL-7 session; ADR-XXXX template below). Executed `prompts/impl_6_remodel.md` against
`docs/redesign.md`. Upstream FROZEN as planned (bip.py/s03 r=0.943; s05 estimator r=0.825 / MAE 2.44;
board=time-played MEASUREMENT ADR-0011, only renamed here; Nate harness). All 24 pytest green; the
re-run is deterministic (central is closed-form; only the CI bootstrap consumes the seed).

Built (D1–D4 + structural, from ADR-0018):
- **Metric (D1, O2).** s08 replaced the 10k W/D/L Monte Carlo with the deterministic closed form
  `mu = sum_h lambda_h*omitted_live_h`, `P(change)=1−exp(−mu)`, `X%=mean(P(change))`. **O2 resolved with
  the user = mean(1−exp(−μ))** (expected share), not count(μ≥1) — the latter is degenerate here (only 1
  match 2H-only / 3 matches 1H+2H reach μ≥1).
- **λ (D2/D3).** `build_lambda_cells` now keys (cohort, window, conditioning); `team_role`/`_role_of`
  DELETED. λ is the **TWO-TEAM rate** = goals-by-either-team / match-live-minute (NOT per-team — the
  per-team framing is a factor-of-2 trap; λ_2H = 73/894.5 = .0816, λ_1H = 23/481.2 = .0478). Central
  source = `pooled_all` (PRE+POST); pooled_pre / pooled_post / regime_matched are sensitivities;
  conditioning overall (default) + tied_nontied (sensitivity).
- **1H window (O1).** **Headline window = 1H+2H** ("≥1 extra goal anywhere"), confirmed with the user.
  Added a 1H-stoppage λ + 1H live-share; s08 computes true_stoppage / played / omitted / omitted_live per
  half. The full-match IMPL-3 residual (24.2s) and estimator σ (MAE·√(π/2)=3.06 min) are split across
  windows by addable share f2=0.628 / f1=0.372 — one shared estimator draw E, applied ts_1H+=E·f1,
  ts_2H+=E·f2 (reduces to the old 2H-only σ when 1H is dropped). O1 caveat stands: a 1H extra goal is a
  bonus increment; game state is NOT propagated.
- **Rename (DC2).** s06a writes `played_in_stoppage.parquet` (col `played_in_stoppage_min`, =
  period_end−2700, numerically identical to the old board_min — verified max|Δ|=0.000) + a NULL
  `board_announced` for the future 4th-official number (R1). s07/s08/s09/nate.py read the renamed file;
  raw CSV layer (board_statsbomb.py / board_added_time.csv) unchanged. board_statsbomb.py:38 confirms the
  "board" was always time-played, never the announced number — the misnomer is fixed.
- **DC1.** s07 rebuilds stoppage_live_share from segments SPLIT at the 45:00/90:00 boundary (the old code
  keyed on the segment-START phase label, mis-binning every straddling segment → 811 vs 894.5 2H team-min).
  A hard assert now guarantees live-share live-seconds == match_minutes ledger (max diff 0.00s), so λ
  exposure and productivity share ONE table.
- **DC3.** s09 f01 drops extra-time buckets (≥10) so the spurious minute-120 ET/penalty spike no longer
  reads as penalties contaminating regulation scoring.

New grid (group=all, window=1H+2H; X% = mean P[≥1 extra goal], CI = per-cell Jeffreys-Gamma λ +
silent_marked estimator-error bootstrap):
- **Central silent_marked | overall | pooled_all: 23.8% (95% CI 20.4–27.9%).** Same knob, 2H_only: 17.1%.
- By silent treatment (min–max across conditioning×source, 1H+2H): none 12.5–14.9%, marked 22.6–26.1%,
  all 32.1–36.4%. Full grid 12.5–36.4%.
- Monotonic none≤marked≤all in all 144 (window×group×cond×source) cells; every point sits inside its CI
  (the central estimate is analytic now, so the ADR-0008 two-stream "point a hair outside band" wart is gone).

Vs ADR-0017/0018: the marked↔all silent band is still the dominant uncertainty (≈ +10 pt none→marked→all)
— the remodel did NOT narrow it (expected; D4 keeps none/all as definitional rails, not estimates).
Conditioning barely moves X% (overall vs tied_nontied within ~0.3 pt → confirms D2). pooled vs pre/post is
modest (pre ~+2–3 pt with wide CIs from thin PRE counts → confirms D3). Adding the 1H window lifts the
headline ~+6.7 pt (17.1→23.8%) — a real previously-omitted window, not a knob artifact.

Still OPEN (not this session): O3 within-stoppage time-wasting + announced-board under-allocation +
cooling-break stoppage = IMPL-7, pending research R1/R2. X% LOCK = the session after IMPL-7.

## ADR-0001 — Core dataset locked (2026-06-15)
Six tournaments, all in StatsBomb open data with full events. PRE (under-adding,
pre-directive): WC 2018, Euro 2020 → 115 matches. POST (accurate/over-adding): WC 2022,
Euro 2024, Copa América 2024, AFCON 2023 → 199 matches. IDs verified against open-data
`competitions.json` on 2026-06-15 and stored in `config/tournaments.yaml`. AFCON 2023 is
named "African Cup of Nations" upstream (comp 1267 / season 107).

## ADR-0002 — No xG (2026-06-15)
Metrics are goals per live-minute (primary) and shots / shots-on-target per live-minute
(companion, higher event volume = variance reducer). Avoids xG model dependence.

## ADR-0003 — Gap-method ball-in-play, calibrated (2026-06-15)
Dead time = gap from a possession's last event to the next restart event, where restart
play_patterns are From Throw In / Corner / Free Kick / Goal Kick / Kick Off / Keeper
(`params.yaml:bip.restart_play_patterns`). Calibrated against Opta's published WC2022
58:04 (3484s). **s03 calibration gate PASSED**: pooled WC2022 regulation BIP = 3460s
(57.67 min), 24s under target (tolerance ±90s); in-play share 0.569 (sane 0.55–0.60).
Two structural rules together produce this (see ADR-0009): possession-boundary restart
detection + a 20s max-live-gap. `bip.min_dead_gap_s` stays 0.0; the load-bearing knob is
`bip.max_live_gap_s = 20.0`.

## ADR-0009 — Two BIP corrections to pass calibration (2026-06-15)
Two bugs/refinements were needed for s03 to calibrate:
1. **Possession-boundary restart detection.** StatsBomb sets `play_pattern` on *every*
   event of a possession, not just its restart. Reading the pattern per-event flagged
   nearly every intra-possession interval of a set-piece-originated possession as dead
   (BIP collapsed to 27.85 min). Fix: an interval is a restart-dead only at a possession
   boundary (`possession` changes) whose new possession begins with a restart pattern.
   This required carrying the `possession` column through s02.
2. **Max-live-gap rule.** Restart-pattern detection alone over-counted in-play (64.66 min)
   because long silent stretches (injury, VAR, slow restarts within a possession) carry no
   restart event. In active play StatsBomb logs an event every few seconds, so any
   inter-event gap ≥ `bip.max_live_gap_s` (20s) is treated as dead regardless of pattern.
   Swept 6–30s; G=20 → 3460s (24s under target). G∈[15,25] all land within tolerance, so
   the result is not knife-edge.

## ADR-0004 — Disk-safe ingest (2026-06-15)
Machine had ~2.7 GB free at setup. We never clone open-data and never touch 360 data.
s01 caches only the small per-tournament match-list JSON in `raw/statsbomb/`. s02 fetches
each match's event JSON **in memory** and discards it after parsing — nothing large lands
on disk. Trade-off: re-running s02 re-downloads events (cheap, idempotent) instead of
reading a local cache. Deviates from a literal "immutable raw event cache" for disk safety.

## ADR-0005 — Phase taxonomy includes extra_time (2026-06-15)
Spec lists phases {regular, 1H_stoppage, 2H_stoppage}. The dataset has knockout matches
with extra time; we add a fourth label `extra_time` (periods ≥ 3) so ET play is not
misattributed to regulation buckets. Productivity-in-stoppage analysis still focuses on
1H_stoppage / 2H_stoppage.

## ADR-0006 — events_norm carries two helper columns (2026-06-15)
Beyond the data-dictionary minimal columns, `events_norm` also carries `shot_outcome`
(for s04 goal detection) and `card` (for s05/s06b). This avoids re-fetching all event JSON
twice more over the network, at the cost of two extra columns.

## ADR-0007 — VAR fallback estimator only (2026-06-15)
s06b implements the spec's FALLBACK (decision-event excess over the tournament median
goal-celebration gap), not live commentary scraping. Decision events are limited to goals
and red/second-yellow cards (penalty awards and overturned offsides need nested fields not
carried), so `var_s` is itself a lower bound. VAR matters only for the s05 attribution.

## ADR-0008 — Counterfactual CI via Gamma-posterior bootstrap (2026-06-15)
Central per-match p_flip from N=10,000 seeded Poisson sims (per spec). The outer CI
bootstraps λ from its Jeffreys Gamma posterior (Gamma(count+0.5, exposure)) and uses the
exact analytic flip probability per draw (fast, avoids 10k×1k×matches sims). full_measure_538
true_stoppage knob is not yet wired to per-match 538 data and currently falls back to
lower_bound — revisit if 2018 538 per-match measures are sourced.

**Vectorization + two RNG streams (2026-06-15).** The original analytic flip prob was a
pure-Python i,j double sum called ~8.5M times → s08 ran 17+ min. Rewrote it as an
outer-product over truncated Poisson pmfs (k=0..14) with a precomputed sign/flip mask
(`_analytic_pflip`, verified identical to the loop within 1.3e-15), replaced the per-call
scipy pmf with a manual numpy pmf + cached factorials, and the bootstrap is now an einsum
over all matches per draw. Runtime: 17 min → 23 s. Critically, the headline central MC and
the CI bootstrap now draw from **two independent streams** (`seed` and `seed+1`): the
published X% must not move when bootstrap RNG consumption changes. Headline math unchanged.

## ADR-0010 — Board added time scraped from ESPN (2026-06-15)
The fourth-official board number is not in StatsBomb. Sourced it from ESPN's public soccer
summary API (`site.api.espn.com`): the "First Half/Second Half ends" commentary markers are
stamped `45'+X'` / `90'+Y'`, i.e. added minutes played — which slightly OVER-estimates the
announced board (play finishes the minute in progress). That is the conservative direction
for the counterfactual: omitted = max(0, true_stoppage − board) shrinks, so the headline
cannot be inflated by this source. (Sofascore was Cloudflare-blocked.) Matched 314/314 via
date+teamset with a ±1-day, score-validated fallback (US-evening Copa kickoffs land on the
adjacent UTC calendar day). Mean total board ≈ 9.9 min/match; PRE ≈ 8.0, WC2022 ≈ 12.4 —
within s06a reference bands. `src/scrape_board_espn.py`; cache `raw/board/board_added_time.csv`.
Caveat: true_stoppage (s05 lower_bound) UNDER-states real dead time while board OVER-states
the announced number, so measured omitted minutes (mean 1.5, positive in 49% of matches) are
doubly conservative — real omitted time is larger than what the headline X% reflects.

## ADR-0011 — Board redefined as precise time-played from StatsBomb half-end (2026-06-15)
Supersedes the board *source* in ADR-0010 (not its conservative-direction reasoning). Item 1
redefined the "board" as the precise time **actually played** in each regulation half (Nate
Silver's "ACTUAL" column), aligning with how Nate measured added time and giving one figure
available across all six tournaments.

The ESPN scrape cannot deliver this. ESPN freezes its match clock at 45:00 / 90:00 during
added time in *every* feed (commentary, summary keyEvents, core play-by-play) and only exposes
the rounded-up whole-minute label (`45'+3'`). That over-reads Nate by ~1.5 min (MAE 1.46,
bias +1.46) and caps correlation at **r=0.943** — `r` is invariant to any affine correction,
so no calibration can pass the Item 1 gate (r>0.95). ESPN's one second-level signal, the
broadcast `wallclock` on period-boundary markers, was overwritten on ~half the markers by an
2024-04-10 re-ingestion, leaving only 5/32 WC2018 matches with both halves intact (one already
negative). So precise played time is not recoverable from ESPN at the required resolution.

StatsBomb's `Half End` event carries a second-level whistle timestamp, and s02 already surfaces
it as `p1_end_s` / `p2_end_s` on matches.parquet (verified identical to the Half End `period_s`,
diff 0.0). Precise played board = `period_end_s − 2700`. Validated against Nate's 32 published
WC2018 matches: **MAE 0.135 min (~8s), bias +0.10 min, r=0.992, max abs err 0.78 min** — a
second-level, all-six-tournament, fully local source with no scrape and no external dependency
(the board is now regenerable, not "the one unavoidable external input"). New generator
`src/board_statsbomb.py`; cache `raw/board/board_added_time.csv` now holds float `board_min`
(minutes) with `source=statsbomb`. s06a unchanged: 314/314 matches join; PRE mean 6.8 min,
WC2022 11.4 min (both within reference bands). `scrape_board_espn.py` is retained only as an
optional sensitivity path (e.g. the 2018-only *announced* 4th-official board). s08/s09 NOT
re-run this session per the modular-session rule.

## ADR-0012 — Nate 538 ground truth checked in + shared validation harness (2026-06-15)

The silent-component fix (IMPL-1→IMPL-4) hinges on validating against Nate Silver's WC2018
numbers, but those numbers previously existed only in a session transcript and a JPG in
`~/Downloads`. Per CLAUDE.md §6 (validate against an EXTERNAL ground truth that is actually
durable), the 32-match table is now transcribed and checked in at
`data/raw/nate_2018/nate_wc2018.csv` (home, away, `bip`, `expected`, `actual`), so the project
no longer depends on the external file.

Shared harness `src/lib/nate.py` exposes the three validation arms and reconciliation. The
column→quantity mapping is load-bearing and easy to get wrong, so it is fixed here and in the
module docstring: **`bip` → s03 ball-in-play** (IMPL-2 promote-gate, r≥0.94); **`expected` →
true-stoppage estimator** (IMPL-3 gate — the "should-be-added" model, mean ~13.2 min, e.g.
Germany–Sweden 8:56); **`actual` → precise time-played board** (already validated, regression
guard). Crossing `expected`/`actual` would silently corrupt the estimator and the headline
counterfactual.

Reconciliation is on the UNORDERED, name-normalized team pair within wc_2018 — 538 flips some
home/away (its "Iceland–Nigeria" is StatsBomb "Nigeria–Iceland") and spells "S. Korea" where
StatsBomb has "South Korea"; `nate.reconcile()` raises if any of the 32 fails to map.
`tests/test_nate.py` (4 tests, green) guards: table parses + 538's printed DIFF is consistent;
`expected` mean is the ~13.2 min level (not `actual`); all 32 reconcile to distinct match_ids;
and the harness reproduces the validated board fit. Reproduced live: **BIP arm r=0.943,
MAE 1.25 min** (the IMPL-2 baseline) and **board arm r=0.992, MAE 0.134 min** (matches ADR-0011)
— i.e. the harness is correct against two independent ground-truth points before any IMPL
session runs. No pipeline stage re-run; this is scaffolding only.

## ADR-0013 — IMPL-1: out-of-play markers plumbed through s02 (2026-06-15)

The marker-gated silent reclassifier (IMPL-2) needs StatsBomb's intrinsic ball-out-of-play
signals, but s02 previously projected only `out`/`off_camera`/`shot_outcome`/`card`. IMPL-1 adds
three more raw fields to `interim/events_norm.parquet`, one column each — data prep only, nothing
consumes them yet:
- `pass_outcome` ← `pass.outcome.name` (e.g. "Out", "Injury Clearance", "Incomplete", "Offside").
- `gk_type` ← `goalkeeper.type.name` (e.g. "Collected", "Smother", "Save", "Shot Faced").
- `gk_outcome` ← `goalkeeper.outcome.name`.
(`out` was already projected at `s02_normalize.py:49`; left as-is.) All used the
`(e.get(x) or {}).get(y) or {}` guard so a present-but-null sub-object doesn't raise.

**Gates green.** s02 re-run (314 matches, 1,106,277 rows): clock monotonic, period lengths sane,
same 3 pre-existing P1-length warnings — gate PASSED. s03 re-run UNCHANGED: WC2022 pooled
regulation BIP 3460s (within ±90s of 3484s), in-play share 0.569 — calibration identical, since
the new columns are not yet consumed.

**Spot-check (recorded per gate).** Whole-corpus non-null: `pass_outcome` 5.2%, `gk_type` 0.85%,
`gk_outcome` 0.38%; `out` is bool, always present, True on 6,977 events. `pass_outcome`
value_counts: Incomplete 48,551 / **Out 5,471** / Unknown 1,895 / Pass Offside 897 / Injury
Clearance 305. The `out=True` flag lands mostly on Block/Clearance/Miscontrol (the ball physically
leaving), not on Pass/Carry as the prompt loosely framed it — expected for StatsBomb; IMPL-2's
marker set must therefore OR `out` together with `pass_outcome="Out"` etc., not rely on `out`
alone. `gk_type` is 100% non-null on the 9,454 `Goal Keeper`-type events (note: the event type is
"Goal Keeper" with a space). Per-tournament one-match spot-check confirmed the SAME populated
schema in all six (pass_outcome non-null ~3.5–6.9%, gk_type ~0.7–1.0%, "Out" present everywhere) —
e.g. wc_2018 m7525 had out=0 but "Out"=29, i.e. some matches encode out-of-play via `pass_outcome`
rather than the `out` flag, reinforcing the OR-the-signals requirement for IMPL-2.

## ADR-0014 — IMPL-2: marker-gated reclassifier BLOCKED — regresses validated BIP, NOT promoted (2026-06-15)

**Decision: do NOT promote marker-gating into `bip.py`. Pipeline left at the ADR-0013 baseline.
The IMPL-2 promotion gate cannot be met; this is a human checkpoint for the user.**

Built the marker-gated silent reclassifier per `prompts/impl_2_reclassify_bip.md`: a candidate
silent gap (no restart `play_pattern` at the trail edge, gap ≥ `silent.min_silent_gap_s`=20s) is
dead iff its LEAD edge carries an out-of-play marker (`out=True`; `pass_outcome∈{Out,Injury
Clearance}`; `shot_outcome∈{Off T, Saved Off Target, Wayward, Blocked, Goal}`; `type∈{Foul
Committed, Offside, Bad Behaviour, Substitution, Player Off, Injury Stoppage, Referee Ball-Drop,
Half End}`), with special-case (B) keeping a keeper-held live ball live. The function is drafted in
`src/lib/silent.py` (kept, unwired). The validation harness used below is `src/lib/nate.py`
(reproduced the documented baseline exactly: old `gap≥20` rule → r=0.943, MAE=1.25, pred mean 56.0).

**The promote-gate failed and cannot be re-tuned to pass.** Promoting marker-gating moves seconds
dead→live, so per-match WC2018 regulation BIP vs 538:

| classifier (WC2018, vs 538 `bip`) | pred mean (min) | r | MAE (min) | WC2022 pooled Δ vs Opta 3484s |
|---|---|---|---|---|
| baseline `gap≥20` (ADR-0013) | 56.0 | **0.943** | **1.25** | −24s ✅ |
| prescribed marker set only | 64.5 | 0.765 | 9.20 | +183s ✗ |
| + "Foul Won" added | 61.6 | 0.863 | 6.26 | +90s |
| + Foul Won + off_camera + residual gap R=45s | 59.1 | 0.920 | 4.00 | +32s ✅ |

Lowering `min_silent_gap_s` to 8s does not help (pooled BIP floors at +148s). Best achievable with
a generous, still-principled marker set is **r≈0.92, MAE≈4.0 — a clear regression** below the
required r≥0.94 / non-regressed gate. Per the prompt's explicit instruction ("if BIP cannot
re-validate, STOP — the marker logic is suspect — bring it to the user; do NOT fall back to an
estimator-only patch") I stopped and reverted `bip.py`, `s03_bip.py`, `config/params.yaml`,
`tests/test_lib.py` to HEAD. s03 re-verified green at the baseline (3460s, share 0.569).

**Root-cause finding (the important part).** The premise behind marker-gating is falsified *for
BIP*: 538's WC2018 regulation BIP mean is **55.3 min — BELOW** the old duration rule's 56.0 min, so
538 counts the long silent gaps as MORE dead, not less. Reclassifying them as live therefore moves
BIP AWAY from truth. Diagnostic over the 1,068 ≥20s non-restart gaps in WC2018: only **25% carry a
lead-edge marker** (12,137s); the other **75% (32,436s ≈ 17 min/match) are unmarked yet genuinely
dead**, led by `Foul Won` (260 — StatsBomb logs Foul Committed *and* Foul Won as a pair and Foul
Won is frequently the trailing event; the prompt's set listed only Foul Committed), `Goal Keeper`
non-hold (278), `Ball Receipt*`/`Miscontrol`/`Block`/`Clearance` (open-play actions where the ball
left play but no flag was set), and `Camera off` (20). StatsBomb simply does not stamp a
machine-readable marker on most genuinely-dead silent gaps, so a marker-gated definition that is
correct for the stoppage estimator is NOT automatically correct for BIP — the "one shared
classifier" hypothesis, as specified, does not hold. The smell-test step (OLD vs NEW per-match
silent totals) was not reached because the gate halts first.

**Follow-up investigation (user asked to dig deeper before deciding).** Decomposed regulation
dead time per WC2018 match into `restart` (normal-flow restart-boundary dead, ~28.9 min),
`silent_marked` (≥20s non-restart gaps WITH a lead-edge marker, ~3.7 min) and `silent_unmarked`
(≥20s non-restart gaps WITHOUT a marker, ~8.4 min), then correlated each against Nate's columns.
Two findings reframe the whole effort:

1. **The marker test is the WRONG tool for BIP but the RIGHT tool for the stoppage estimator.**
   r vs Nate `expected` (the should-be-added target, mean 13.2): `silent_marked` **+0.708**,
   `silent_unmarked` **+0.248** (a near-flat ~8.4 min baseline in every match, std 2.5 — noise for
   stoppage), `injury_s` +0.679, `lower_bound_s` +0.655, `restart` +0.150. The marker test cleanly
   SPLITS the silent bucket into a stoppage-predictive part (marked) and a flat non-addable
   baseline (unmarked).
2. **The over-count is an ATTRIBUTION error, not a live/dead error.** The unmarked silent gaps are
   genuinely dead (BIP needs them), but crediting them as *addable* stoppage adds a flat ~8.4 min
   to every match. Candidate stoppage estimators vs `expected` (mean 13.2): `lb + all silent`
   r=0.752 but **mean 19.7 (the over-counter — Germany-Sweden signature)**; `lb + marked silent`
   **r=0.768, MAE 3.15, mean 11.3**; `marked silent + calibrated constant` **r=0.708, MAE 2.22,
   mean 13.2**. Marker-gating the SILENT TERM removes the over-count and lifts r from ~0.61 to
   ~0.77 — but inside s05, not in bip.py.

**Recommendation:** abandon the bip.py promotion and the "one shared classifier" decision (BIP
wants *total* dead time; stoppage wants only the *addable* subset — genuinely different questions).
Apply marker-gating ONLY to the s05 stoppage silent term in IMPL-3 (`silent.py` is ready for this).
Note the IMPL-3 ceiling looks ~0.77, short of the findings' ≳0.85 hope — flag when scoping IMPL-3.

## ADR-0015 — Silent-component direction RATIFIED: bip.py frozen, marker-gating to s05, external data declined (2026-06-15)

**User ratified the ADR-0014 recommendation and rescoped the remaining work.** Three decisions:

1. **`src/lib/bip.py` and s03 are frozen as the validated duration rule.** The "one shared
   live/dead classifier" hypothesis (originally DECIDED in `silent_component_findings.md` §"one
   classifier in bip.py") is FALSIFIED and abandoned. BIP = TOTAL dead time; stoppage = ADDABLE
   dead time — different questions. BIP genuinely needs the unmarked silent gaps (538 WC2018 BIP
   55.3 < duration rule 56.0); marker-gating them regresses BIP (r 0.943→≤0.92). Do not re-open
   s03 calibration for this.

2. **Marker-gating (`src/lib/silent.py`) is applied ONLY to the s05 stoppage silent term (IMPL-3,
   rescoped).** This is the one validated win: it splits the silent bucket into a stoppage-
   predictive marked part (r=0.708 vs `expected`) and a flat non-addable unmarked baseline
   (r=0.248); `lb + marked silent` → r=0.768. **The IMPL-3 gate is RESET: target ~0.77, not the
   findings' ≳0.85** — StatsBomb marks only ~25% of silent gaps and never marks addable-ness, so
   ~0.77 is the realistic free-data ceiling. `prompts/impl_3_estimator_validate.md` and
   `next_session.md` rewritten accordingly.

3. **External datasets DECLINED for the silent-component goal.** Surveyed Wyscout/Pappalardo,
   FIFA effective-playing-time, CIES, DFL/IDSSE, Metrica, SkillCorner (saved to memory
   `reference_external_datasets.md`). Mechanics of the decline: these sources label ball-out
   *timing* (the BIP axis, already r=0.943), NOT addable-ness (the hard part); the one with a free
   per-gap marker StatsBomb lacks (Wyscout interruptions) covers WC2018 only — duplicating Nate's
   ground truth and never reaching the POST tournaments the headline depends on. Better ball-out
   timing would push more flat non-addable seconds INTO the silent bucket, the wrong direction for
   stoppage. Kept only as an optional triangulation footnote, not a model input.

**Honest ceiling statement (for the article):** the silent component cannot be measured precisely
with free data. Rather than ship a false-precision point estimate, IMPL-4 makes the silent
treatment an explicit s08 sensitivity knob (`silent_none` / `silent_marked` / `silent_all`) and
propagates the ~±2–3 min estimator MAE into the bootstrap CI. The decisive question becomes whether
the headline X% is robust to the silent assumption — if so, the residual uncertainty does not
threaten the claim; if not, it ships as a reported band. This is consistent with CLAUDE.md §1
(X% ships with a CI and sensitivity table, never as a bare point estimate).

## ADR-0016 — IMPL-3: marker-gated true-stoppage estimator built in s05, validated vs Nate (2026-06-16)

**Human checkpoint.** Built the corrected true-stoppage estimator IN s05 (not bip.py — s03 is
frozen, ADR-0015):
`true_stoppage = lower_bound (existing) + marker-gated silent + residual constant`. `bip.py`,
`s03_bip.py` UNCHANGED (verified clean); s03 still calibrated (test green). The estimator validates
against Nate's **`expected`** column (the should-be-added model, mean ~13.2 min), NOT `actual`.

**What was added.**
- `src/lib/silent.py:marked_silent_intervals` — of the ≥`silent.min_silent_gap_s` (20s) non-restart
  gaps, credit ONLY those whose LEAD edge carries an out-of-play marker (`out`; `pass_outcome∈{Out,
  Injury Clearance}`; `shot_outcome∈{Off T, Saved Off Target, Wayward, Blocked, Goal}`; `type∈{Foul
  Committed, Offside, Bad Behaviour, Substitution, Player Off, Injury Stoppage, Referee Ball-Drop,
  Half End}`), minus the keeper-holding-a-live-ball special case. Unmarked silent gaps are dropped —
  genuinely dead (s03 BIP keeps them) but a flat ~8.4 min/match non-addable baseline; crediting them
  is the over-count (the Germany–Sweden 19.8-vs-8.9 signature).
- The lower-bound components (celebration/sub/card/injury ∩ s03 dead) are UNCHANGED — s05 lower-bound
  gate still passes. `silent_marked_s` added per match-period to `incident_stoppage.parquet`; a new
  per-match `interim/true_stoppage.parquet` (lower_bound_s, silent_marked_s, residual_silent_s,
  true_stoppage_s) is the checkpointed estimator table.
- **Residual constant** `silent.residual_silent_s = 114.0` (1.90 min): fit on 2018 as
  mean(Nate `expected`) − mean(lower_bound + marked silent) over the 32 WC2018 matches (13.16 − 11.26).
  FROZEN; the SAME constant applies to all six tournaments (POST has no ground truth to fit on).

**Validation (32 WC2018 matches vs Nate `expected`, ablation):**

| estimator | r | MAE (min) | mean (min) |
|---|---|---|---|
| lower_bound only | 0.655 | 5.72 | 7.53 |
| + marker-gated silent | **0.768** | 3.15 | 11.26 |
| + residual constant (estimator) | **0.768** | **2.75** | **13.16** |
| *(ref) lower_bound + ALL silent (old over-counter)* | 0.752 | 6.60 | 19.69 |

Nate `expected` mean = 13.16. **Gate met:** beats the 0.61–0.73 baseline, lands the reset ~0.77
target (r=0.768); aggregate mean matches Nate at the ~13 min level. The residual is a flat constant,
so it does not change r; it centers the mean and cuts MAE 3.15→2.75.

**Diagnostic (the decisive test — vs the old over-counter):** marker-gating collapses the low-injury
over-count without breaking the injury-dominated matches.

| match | over-counter err | estimator err | Nate |
|---|---|---|---|
| Germany–Sweden (LOW) | +10.9 | +3.3 | 8.9 |
| Russia–Egypt (LOW) | +6.9 | −0.7 | 8.1 |
| Uruguay–Saudi (LOW) | +7.5 | +0.9 | 8.4 |
| Belgium–Panama (HIGH) | +6.1 | +0.2 | 14.3 |
| Tunisia–England (HIGH) | +8.7 | +3.3 | 17.6 |

The two residual over-shoots (Germany–Sweden, Tunisia–England, both +3.3) are the flat-constant
limitation: +1.9 min is added even to matches the marker term already nailed. This is the honest
price of a single calibrated constant and is well inside the band.

**Coverage flag (load-bearing for the article).** Nate validates **WC2018 ONLY**. The POST
tournaments (where the headline lives) are validated only INDIRECTLY — via the frozen 2018 residual
calibration + s03's WC2022 Opta BIP gate. The estimator's all-314-match mean is 16.8 min (POST runs
hotter than 2018, as expected). The silent component cannot be measured precisely with free data
(StatsBomb marks only ~25% of silent gaps and never marks addable-ness, capping r≈0.77); IMPL-4
turns the silent treatment into an explicit s08 sensitivity knob and propagates the ~±2.75 min MAE
into the CI, so X% ships with a band, not false precision (CLAUDE.md §1).

## ADR-0017 — IMPL-5: restart-excess folded into the s05 estimator; residual re-fit; Task B dropped (2026-06-17)

**Human checkpoint.** Made the s05 true-stoppage estimator more precise by crediting routine
**restart time-wasting** — the gap that swung X% 3%→12% across the silent knob (ADR-0016 / IMPL-4)
motivated tightening the per-match estimator before locking X%. `bip.py`/s03 stay FROZEN
(ADR-0014/0015); this changed only the ADDABLE-stoppage estimator (`src/s05_incident.py`,
`config/params.yaml`). `src/lib/silent.py` is UNCHANGED (Task B dropped — see below).

**Task A — Nate's per-restart allowances (KEPT).** A throw-in dragged to 50s or a goal kick to
40s with no foul/sub/injury was credited ZERO in every knob (silent.py EXCLUDES restart-boundary
gaps by design; lower_bound only caught them where they overlapped a foul/sub window). Added a
`restart_excess` component to s05's `comp`: for each routine restart-boundary gap, credit
`max(0, gap − allowance)` as the tail `[last + allowance, restart]`. Allowances
(`params.yaml:incident.restart_normal_s`, FIT/FROZEN on 2018, applied to all six):
Throw In 20s · Goal Kick 30s · Corner 45s · Free Kick 60s. `From Kick Off` (celebration) and
`From Keeper` (largely live) are EXCLUDED. It is identifiable (restart-tagged), so it folds into
the `lower_bound` union and rides the existing intersect-with-dead machinery — deduped against the
card/sub windows (no double-count of a foul→free-kick) and the gate `lower_bound_s ≤ total dead`
holds by construction (every excess interval ⊂ its dead gap ⊂ s03 dead). It belongs in
`lower_bound_s`, which also raises the `silent_none` floor in s08. `lower_bound_base_s`
(the ADR-0016 lower bound, sans restart_excess) is kept as a column for the ablation.

**Validation (32 WC2018 matches vs Nate `expected`, full-match totals, ablation):**

| estimator | r | MAE (min) | mean (min) |
|---|---|---|---|
| lower_bound (celeb/sub/card/injury) | 0.655 | 5.72 | 7.53 |
| + restart_excess | 0.754 | 4.28 | 9.03 |
| + marker-gated silent | **0.825** | 2.49 | 12.76 |
| + residual constant (estimator) | **0.825** | **2.44** | **13.16** |
| *(ADR-0016 estimator, no restart_excess)* | 0.768 | 2.75 | 13.16 |

**Gate BEATEN:** restart_excess lifts r 0.655→0.754 on its own axis (NOT capped by the ~0.77
silent-marker ceiling — it attacks restart time-wasting, a different signal), and the full
estimator hits **r=0.825 / MAE 2.44**, beating ADR-0016's 0.768 / 2.75 on BOTH axes. The residual
is a flat constant, so it does not change r; it re-centers the mean to Nate's 13.16.

**Diagnostic (estimator error, minutes) — low-injury shrinks, injury-dominated holds:**

| match | over-counter | ADR-0016 est | IMPL-5 est | Nate |
|---|---|---|---|---|
| Germany–Sweden (LOW) | +10.9 | +3.3 | +2.5 | 8.9 |
| Russia–Egypt (LOW) | +6.9 | −0.7 | +0.1 | 8.1 |
| Uruguay–Saudi (LOW) | +7.5 | +0.9 | +1.4 | 8.4 |
| Belgium–Panama (HIGH) | +6.1 | +0.2 | −0.6 | 14.3 |
| Tunisia–England (HIGH) | +8.7 | +3.3 | +3.0 | 17.6 |

**Task B — marker refinements (DROPPED; no variant beat the bar).** Tested vs Nate `expected`
(lb fixed with restart_excess; flat residual re-centered per variant). The single lead-edge marker
test (r=0.825) is the best; every refinement REGRESSES it:

| variant | r | MAE | marked cov (32-match) | why dropped |
|---|---|---|---|---|
| baseline (single lead edge) | **0.825** | 2.44 | 119 min | — (kept) |
| lead-window K=2 | 0.804 | 2.98 | 317 min | over-credits (false positives); re-inflates Ger–Swe +2.5→+3.9 |
| lead-window K=3 | 0.812 | 3.13 | 330 min | same — a marker on a *nearby* event ≠ this gap was dead |
| trail = restart pattern | 0.765 | 2.06 | 25 min | guts coverage; r below the 0.768 bar (most marked trails are "Regular Play", not restarts) |
| trail = possession change | 0.701 | 2.58 | 47 min | over-tightens; r collapses |
| lead-window + trail-poss combos | 0.70–0.73 | — | — | all below bar |

So the lever that could narrow the silent band (`silent_marked`→`silent_all`) did NOT pan out:
widening marker coverage pulls in sparse-logging false positives (the Germany–Sweden confound
returns) and tightening it drops genuine stoppage. **Honest conclusion (anticipated in the prompt):
the silent uncertainty is irreducible with free StatsBomb data.** restart_excess raises the
`silent_none` FLOOR (it is now identifiable lower_bound, not silent), which should tighten the band
from below — but the `marked`↔`all` width is unchanged. Whether the headline is now lockable is for
IMPL-4 to re-measure; X% likely still ships as a band, which is a legitimate, publishable finding.

**Re-fit + frozen constants (params.yaml).** Adding restart_excess raised the mean, so the residual
was re-fit on 2018 (`residual = mean(Nate expected) − mean(lower_bound + marked_silent)` =
13.160 − 12.757 min):
- `incident.restart_normal_s`: {Throw In 20, Goal Kick 30, Corner 45, Free Kick 60} s — NEW, frozen.
- `silent.residual_silent_s`: 114.0 → **24.2** s (re-fit).
- `silent.estimator_pearson_r`: 0.768 → **0.825**; `silent.estimator_mae_min`: 2.75 → **2.44**
  (IMPL-4 reads MAE as the 2H-scaled per-match sigma).

**Net effect / sanity.** WC2018 net restart credit +1.50 min/match (marked_silent 3.73); all-314
mean true_stoppage 16.8 → **17.78 min**; POST runs hot as expected (Copa 25.3, AFCON 23.5, WC2022
17.5) — consistent with more routine late-game restart management in recent tournaments. New columns
`restart_excess_s`, `lower_bound_base_s` on `incident_stoppage.parquet`; `true_stoppage.parquet`
now includes restart_excess via `lower_bound_s`. s05 gate green; s06b re-run to repopulate `var_s`
(s05 had reset it); **all 23 pytest green**.

**Coverage flag (unchanged, load-bearing).** Nate validates **WC2018 ONLY**. POST is validated
INDIRECTLY — frozen-on-2018 allowances + residual + the s03 WC2022 Opta BIP gate. The allowances
and residual are fit on 2018 and applied unchanged to all six.

**Next: re-run IMPL-4** (`prompts/impl_4_counterfactual_lock.md`) in a SEPARATE session — s08 grid
+ s09, to see if the tighter estimator (higher floor, r 0.768→0.825) moved the central / narrowed
the band, then lock X%.

## ADR-0018 — Headline model reopened at first principles; metric/λ redesigned; X% LOCK PAUSED (2026-06-17)

**Human checkpoint — DECISIONS recorded, NOT a number.** After the IMPL-4 re-run grid (silent_marked
~8.1–9.9% but the silent band did not narrow, ADR-0017), the user reopened the headline model at first
principles. X% is **deliberately NOT locked**; the ADR-XXXX headline template below stays blank until
the remodel (IMPL-6) + distortion add-ons (IMPL-7) are built and re-validated. Full spec:
`docs/redesign.md`. Sequencing + turnkey prompts: `next_session.md`. Upstream stays FROZEN (bip.py/s03
r=0.943; the s05 estimator r=0.825 — ADR-0014/0015/0016/0017; the board=time-played MEASUREMENT
ADR-0011, only RENAMED here, number unchanged; the Nate harness).

Decisions:
- **D1 — metric → any extra goal.** "Ends differently" = ≥1 additional goal in the omitted stoppage
  (3-1→3-2 counts). Replace the W/D/L 10k-sim with the closed form `mu = sum_h lambda_h*omitted_live_h`,
  `P(change)=1-exp(-mu)`, `X%=mean(P(change))`. The claim is about whether properly-played stoppage
  yields more goals, not who wins; the closed form is exact and drops the sim.
- **D2 — drop team_role; default overall; tied_nontied = sensitivity only.** team_role only served the
  W/D/L flip (which team scores). Under D1 only the total two-team rate enters mu. Data (2H-stoppage λ,
  goals/team-live-min): PRE all .0493 / tied .0716(n10) / nontied .0403(n14) / lead .0345(n6) /
  trail .0460(n8); POST all .0432 / tied .0391(n14) / nontied .0450(n35) / lead .0463(n18) /
  trail .0437(n17). Cells are within Poisson noise (6–18 goals each); tied vs nontied is not robustly
  different (PRE tied HIGHER — contradicts "non-tied scores faster"; pooled tied .0482 vs nontied
  .0436). Conditioning partitions a 73-goal sample into noisier sub-cells without moving the aggregate
  → that is why it "barely matters."
- **D3 — pool PRE+POST for λ; pre/post is a board/composition story.** The 2022 Collina directive
  changed how much goes on the BOARD (add real time for ALL stoppages, not just celebrations), not how
  the game is played per live minute. No first-principles reason λ-per-live-minute changes pre/post,
  and the data agrees (.0493 vs .0432, within noise). pre/post also conflates tournament composition.
  → pool for the central λ; pre/post is a sensitivity; the directive's effect lives in the bigger boards.
- **D4 — silent central = silent_marked + propagated estimator error; none/all guardrails only**
  (unchanged from the IMPL-4 settle; none/all are definitional rails, never calibration targets).

Plus structural: include the 1H stoppage window (`mu = mu_1H + mu_2H`); rename "board" →
`played_in_stoppage` and add a separate `board_announced` (NULL pending research R1); reconcile the λ
exposure denominator with the productivity live-minutes (DC1 — today 811 vs 894.5 2H team-min
disagree); fix the s09 f01 figure's extra-time/penalty spike (DC3). The distortion add-ons
(announced-board under-allocation; within-stoppage time-wasting) and cooling-break pure-stoppage are
IMPL-7, pending the deferred research sessions (`prompts/research_board.md`, `prompts/research_cooling.md`).

## ADR-XXXX — HEADLINE NUMBER (PAUSED — fill after IMPL-6/IMPL-7 re-validate; see ADR-0018 + docs/redesign.md)
Metric (D1): % of matches with ≥1 extra goal in omitted stoppage = mean(1 − exp(−μ)).
X% = ____% (95% CI ____–____%). Window: 1H+2H or 2H-only = ____. Central λ source/conditioning: ____
(default pooled_all / overall). Silent treatment: silent_marked + estimator error (D4).
Sensitivities: silent none/marked/all; conditioning overall/tied_nontied; source pooled/pre/post.
Caveats: irreducible silent band (ADR-0017); 1H counterfactual independence assumption (O1); thin PRE
counts; Nate validates WC2018 only.
