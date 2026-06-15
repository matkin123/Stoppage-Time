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
match_id, idx, period, clock_s, type, team, player, play_pattern, duration_s, out,
off_camera, shot_outcome, card. clock_s = period-relative timestamp + period offset
(see src/lib/clock.py). shot_outcome/card are helper columns (ADR-0006).

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
match_id, period, celebration_s, sub_s, card_s, injury_s, var_s, lower_bound_s,
injury_present(bool). lower_bound_s = merged union of all incident windows (no double count).

## board_added_time  (s06a) — interim
match_id, tournament, group, period, board_min, source ∈ {sofascore,espn,fifa}.
Sourced from raw/board/board_added_time.csv (the one unavoidable external input).

## stoppage_live_share  (s07) — processed
match_id, tournament, phase ∈ {2H_stoppage, any_stoppage}, stoppage_seconds, live_seconds,
live_share. Feeds the s08 m_live computation.

## productivity  (s07) — processed
scope (pooled / group:PRE / tournament:wc_2022 / …), dimension (bucket / phase /
state_2H_stoppage), phase_or_bucket, state, metric ∈ {goals,shots,shots_on_target},
n_events, live_minutes, rate, ci_lo, ci_hi (exact Poisson 95%).

## counterfactual  (s08) — processed
Per-match: match_id, knob_set, p_flip. counterfactual_summary: group, knob_set,
pct_changed, ci_lo, ci_hi, pct_nontied_changed, n_matches. knob_set =
"true_stoppage|lambda_conditioning|lambda_source".
