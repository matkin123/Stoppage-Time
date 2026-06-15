# Decisions (ADR log)

Every methodology choice gets an entry here. Newest at top. The counterfactual headline
number and its band must be locked here (with the chosen knob_set) before publishing.

---

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

## ADR-XXXX — HEADLINE NUMBER (fill after s08)
Chosen central knob_set: ______. X% = ____% (95% CI ____–____%). Non-tied X% = ____%.
Rationale for the central knob choice and the main caveats (behavioral assumption,
endogenous stoppage length, thin PRE counts) go here.
