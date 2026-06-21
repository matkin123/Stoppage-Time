# Data dictionary

Stage → table mapping and column definitions. Times are seconds of cumulative match clock
unless noted. Parquet lives under `data/interim/` and `data/processed/`.

## matches  (s01, period ends added by s02) — interim
| col | meaning |
|---|---|
| match_id | StatsBomb match id |
| tournament | key from tournaments.yaml (e.g. wc_2022) |
| competition / competition_id / season_id | StatsBomb identifiers |
| group | PRE / POST |
| date | YYYY-MM-DD |
| home / away | team names |
| home_score / away_score | final (regulation+ET, excl shootout) |
| ft_score | "h-a" string |
| stage | competition stage name |
| p1_end_s / p2_end_s | within-period length of halves 1/2 (from s02) |

## events_norm  (s02) — interim
match_id, idx, period, clock_s, possession, type, team, player, play_pattern, duration_s,
out, off_camera, shot_outcome, card, pass_outcome, gk_type, gk_outcome. clock_s =
period-relative timestamp + period offset (see src/lib/clock.py). `possession` carries the
StatsBomb possession id (needed for the s03 possession-boundary restart rule, ADR-0009).
shot_outcome/card are helper columns (ADR-0006); pass_outcome/gk_type/gk_outcome are the
out-of-play markers plumbed for the s05 marker-gated silent term (ADR-0013).

## bip_segments  (s03) — interim
match_id, period, start_s, end_s, in_play(bool), phase, bucket. Contiguous in-play/dead
intervals from the gap method. phase ∈ {regular, 1H_stoppage, 2H_stoppage, extra_time}.

## match_minutes  (s03) — interim
match_id, bucket, phase, live_seconds. Live seconds allocated per 10-min bucket × phase,
splitting segments at bucket and phase boundaries.

## goals  (s04) — interim
match_id, clock_s, period, team, is_stoppage ∈ {none,1H,2H}, score_home_after,
score_away_after. Excludes penalty shootouts (period 5).

## match_state  (s04) — interim
match_id, state_at_45, state_at_90 ∈ {tied,lead_by_1,lead_by_2plus}, leader ∈
{home,away,none}, home_at_90, away_at_90.

## incident_stoppage  (s05, var_s by s06b) — interim
match_id, period, celebration_s, sub_s, card_s, injury_s, restart_excess_s, silent_marked_s,
silent_all_s, var_s, lower_bound_base_s, lower_bound_s, injury_present(bool).
lower_bound_base_s = merged union of celebration/sub/card/injury windows ∩ s03 dead (ADR-0016).
lower_bound_s adds restart_excess (excess of a routine restart's dead time over its standard
allowance, IMPL-5 / ADR-0017) — net restart credit = lower_bound_s − lower_bound_base_s.
silent_marked_s = ≥20s non-restart "data gaps" whose lead edge carries an out-of-play marker;
silent_all_s = every such gap credited (the known-wrong `silent_all` guardrail). All windows are
deduped (no double count).

## true_stoppage  (s05) — interim
Per match: match_id, lower_bound_s, lower_bound_base_s, silent_marked_s, residual_silent_s,
true_stoppage_s. The owed-stoppage estimator `T_true` =
lower_bound_s + silent_marked_s + residual constant (re-fit + frozen on WC2018, ADR-0017).
Calibrated to Nate Silver's WC2018 "expected" column (r = 0.825, MAE 2.44 min).

## played_in_stoppage  (s06a) — interim
match_id, tournament, group, period, played_in_stoppage_min, board_announced, source ∈
{sofascore,espn,fifa,statsbomb}. The measured quantity is time PLAYED in stoppage
(period_end − 2700s, Nate's "actual"; renamed from the old "board" in ADR-0019). Now regenerable
from StatsBomb Half-End timestamps (ADR-0011) rather than an external scrape; sourced via
raw/board/board_added_time.csv. board_announced = the 4th-official board number (currently NULL
placeholder, pending the deferred SofaScore scrape; never enters X%).

## productivity  (s07) — processed
scope (pooled / group:PRE / tournament:wc_2022 / …), dimension (bucket / phase /
state_2H_stoppage), phase_or_bucket, state, metric ∈ {goals,shots,shots_on_target},
n_events, live_minutes, rate, ci_lo, ci_hi (exact Poisson 95%).

## stoppage_live_share  (s07) — processed
match_id, tournament, phase ∈ {1H_stoppage, 2H_stoppage, any_stoppage}, live_seconds,
live_share. Split at the 45:00/90:00 boundary (DC1); a hard assert guarantees these
live-seconds equal the match_minutes ledger so λ exposure and productivity share one table.

## played_in_stoppage_descriptive  (s07) — processed
Per group (PRE/POST): mean, median, count of played_in_stoppage_min per match.

## timewasting_descriptive  (s07) — processed
Per (match, half): match_id, group, period, played_min, timewaste_rate (= 1 − live_share),
timewaste_min (dead-ball minutes within the added time that WAS played). Same rate the s08
gross-up applies to the OMITTED clock (IMPL-7 Part A.2 / ADR-0023).

## counterfactual  (s08) — processed
Per-match: match_id, window ∈ {1H+2H, 2H_only}, knob_set, p_change.
counterfactual_summary: window, group, knob_set, pct_changed, pct_outcome_flip,
ci_lo, ci_hi (scoreline 95% CI), flip_ci_lo, flip_ci_hi (outcome-flip 95% CI), n_matches.
knob_set = "{silent}|{conditioning}|{source}|hl={half_life}|{grossup}" (ADR-0024), e.g.
the locked central `silent_marked|overall|pooled_all|hl=4.0|on`. A reported (non-swept)
`…|hl=4.0|geometric` row carries the stoppage-within-stoppage ceiling.
pct_changed = X% (≥1 extra goal, scoreline); pct_outcome_flip = stricter winner/draw flip.

## decay_profile  (s08) — processed
Per match at the central spec: match_id, omitted_2h_clock_min (the grossed-up decay horizon T),
live_share_2h, omitted_2h_live_min, obs_rate (2H-stoppage λ start), floor_rate (open-play floor).
Lets the s09 decay figure trace to a checkpointed table (ADR-0024).
