# s05 injury->ball-drop pairing -- Phase 0 pressure test

Events: 1,106,277  Injury Stoppage: 1,983  Referee Ball-Drop: 729  (ratio drop/injury = 0.37)

## Self-consistency (replication vs locked parquet)
max |Δ lower_bound_s|      current-rule vs locked: 0.0000s
max |Δ lower_bound_base_s| current-rule vs locked: 0.0000s

refit PRE residual  (excess celeb, WC2018): current=94.1s  restart=14.7s  earliest=20.6s  inplay=25.9s   [locked pre=94.1]
refit POST residual (full celeb,   WC2018): current=24.2s  restart=-55.2s  earliest=-49.3s  inplay=-47.7s   [locked post=24.2]

## P4 -- WC2018 calibration (all-PRE) vs Nate `expected`
| rule | n | r | MAE (min) | refit pre-resid (s) | mean est (min) | mean nate |
|---|---|---|---|---|---|---|
| current | 32 | 0.875 | 1.77 | 94.1 | 13.16 | 13.16 |
| restart | 32 | 0.846 | 1.83 | 14.7 | 13.16 | 13.16 |
| earliest | 32 | 0.854 | 1.78 | 20.6 | 13.16 | 13.16 |
| inplay | 32 | 0.870 | 1.67 | 25.9 | 13.16 | 13.16 |

(Refit is mean-preserving by construction, so mean est == mean nate for every rule; r and MAE are the quality signals.)

max |Δ true_stoppage| current-rule vs locked parquet: 0.034s  (validates refit path)

## Projected before->after -- mean true_stoppage (owed), minutes
| tournament | era | n | current | restart | earliest | inplay | Δ(earliest) | Δ(inplay) |
|---|---|---|---|---|---|---|---|---|
| wc_2018 | PRE | 64 | 12.70 | 12.77 | 12.74 | 12.70 | +0.04 | +0.00 |
| euro_2020 | PRE | 51 | 15.04 | 14.05 | 13.92 | 14.04 | -1.12 | -1.00 |
| euro_2024 | PRE | 51 | 14.65 | 13.98 | 13.87 | 14.00 | -0.78 | -0.65 |
| wc_2022 | POST | 64 | 17.45 | 15.71 | 15.59 | 15.72 | -1.86 | -1.73 |
| copa_america_2024 | POST | 32 | 25.30 | 22.27 | 22.08 | 22.15 | -3.21 | -3.15 |
| afcon_2023 | POST | 52 | 23.54 | 24.37 | 24.32 | 24.42 | +0.78 | +0.88 |
| **PRE pool** | PRE | 166 | 14.02 | 13.53 | 13.45 | 13.51 | -0.57 | -0.51 |
| **POST pool** | POST | 148 | 21.29 | 20.17 | 20.06 | 20.17 | -1.23 | -1.12 |

## P1 -- Was Referee Ball-Drop ever a workable key?
Injury events: 1983.  next ball-drop in SAME period:
  within 120s (genuine pairing): 579 (29.2%)
  present but >120s away (mis-pair risk): 410 (20.7%)
  NO later ball-drop in the period (key absent): 994 (50.1%)
  gap to next drop when present: median 90s  p90 1042s  max 2738s

## P2 -- earliest-of{restart,drop} vs plain next-restart (overshoot check)
injury events with BOTH markers: 976; restart-only: 986; drop-only: 13; neither: 8
  of BOTH: ball-drop strictly earlier than next restart (plain next-restart would OVERSHOOT): 444 (45.5%)
  overshoot amount when it happens: median 57s  p90 136s

## P3 -- resumption windows: live play swept in, then stripped by ∩dead
  restart: Σ raw injury window 2596.9 min; Σ (window ∩ dead) 1645.0 min; live stripped by ∩dead 951.9 min (36.7%)
  earliest: Σ raw injury window 2096.8 min; Σ (window ∩ dead) 1545.4 min; live stripped by ∩dead 551.3 min (26.3%)
  inplay: Σ raw injury window 2503.5 min; Σ (window ∩ dead) 1581.1 min; live stripped by ∩dead 922.4 min (36.8%)
  (lower_bound_s uses ∩dead only, so any live span inside a resumption window is removed.)

## Injury-flag location -- is the ball dead or live when the flag is logged?
  injury flag falls in a DEAD segment: 1327 (66.9%)  in a LIVE segment: 656 (33.1%)  no-seg: 0
  (If the flag is already in dead time, 'next in-play start' is the true resumption. If it is in live time, ∩dead strips the live span so the inplay window still cannot over-credit.)

## P5 -- per-tournament ball-drop presence (data-quality vs football)
| tournament | era | injuries | drop ≤120s | share | no-drop-in-period |
|---|---|---|---|---|---|
| wc_2018 | PRE | 291 | 52 | 17.9% | 72.5% |
| euro_2020 | PRE | 288 | 89 | 30.9% | 45.8% |
| euro_2024 | PRE | 266 | 104 | 39.1% | 46.6% |
| wc_2022 | POST | 403 | 137 | 34.0% | 41.7% |
| copa_america_2024 | POST | 257 | 94 | 36.6% | 26.5% |
| afcon_2023 | POST | 478 | 103 | 21.5% | 60.9% |

## P6 -- s05 gate (lower_bound_s ≤ total dead) under new rules
  current: gate violations = 0
  restart: gate violations = 0
  earliest: gate violations = 0
  inplay: gate violations = 0
  (sub/card/celebration/restart_excess intervals are identical across rules by construction -- only the injury interval feeding the union changes.)

## P7 -- edge cases
  matches with NO Injury Stoppage event: 9 / 314
  injury events in ET periods (3-4): 61  (across 20 matches)
  injury events with NO usable ball-drop key (current rule credits 0 for these): 994 of 1983 (50.1%) -> next-restart recovers genuine dead time here.

## Channel decomposition -- where does the pool move come from? (rule = inplay)
Δ true_stoppage per match = (residual channel, uniform within era) + (lb/injury channel).
  PRE  residual channel: -1.23 min (earliest) / -1.14 min (inplay), uniform over 166 PRE matches
  POST residual channel: -1.23 min (earliest) / -1.20 min (inplay), uniform over 148 POST matches
| tournament | era | Δtotal(inplay) | resid-chan | lb/injury-chan |
|---|---|---|---|---|
| wc_2018 | PRE | +0.00 | -1.14 | +1.14 |
| euro_2020 | PRE | -1.00 | -1.14 | +0.13 |
| euro_2024 | PRE | -0.65 | -1.14 | +0.49 |
| wc_2022 | POST | -1.73 | -1.20 | -0.54 |
| copa_america_2024 | POST | -3.15 | -1.20 | -1.95 |
| afcon_2023 | POST | +0.88 | -1.20 | +2.08 |

## Alternative: floor residual at 0 (a negative 'irreducible remainder' is incoherent)
Residual floored at 0 per era; compares the two candidate rules head-to-head.
| pool | n | current owed | earliest+floored | inplay+floored | Δ(earl) | Δ(inplay) |
|---|---|---|---|---|---|---|
| PRE | 166 | 14.02 | 13.45 | 13.51 | -0.57 | -0.51 |
| POST | 148 | 21.29 | 20.88 | 20.96 | -0.40 | -0.33 |

## Cap (max_injury_s=600) binding frequency
  current: 198/989 injury windows hit the 600s cap (20.0%)
  restart: 0/1962 injury windows hit the 600s cap (0.0%)
  earliest: 0/1975 injury windows hit the 600s cap (0.0%)
  inplay: 0/1975 injury windows hit the 600s cap (0.0%)

## Worked example -- match 3939992 (Costa Rica 2-1 Paraguay, Copa 2024)
  current  : injury∩dead  31.2 min   lower_bound  34.9 min   true_stoppage  42.2 min
  restart  : injury∩dead  12.4 min   lower_bound  20.7 min   true_stoppage  26.8 min
  earliest : injury∩dead  10.9 min   lower_bound  19.2 min   true_stoppage  25.4 min
  inplay   : injury∩dead  10.9 min   lower_bound  19.2 min   true_stoppage  25.4 min
