# ADR-0039 (DRAFT — PROPOSED, Phase 0 pressure test; DO NOT IMPLEMENT until human sign-off)

## s05 injury-stoppage pairing: replace the `Referee Ball-Drop` key with the next live ball-in-play event (s03 in-play segment start)

**Status: PROPOSED. This is the Phase-0 read-only red-team. Nothing in the locked pipeline was
touched** (`src/s05_incident.py`, `params.yaml`, `data/processed/*.parquet`, `tournaments.yaml`,
prior ADRs all byte-stable). Evidence exhibit: `docs/injury_pairing_pressure_test.md`
(regenerate via `python -m src.injury_pairing_pressure_test`). Decision needed at the human
checkpoint before Phase 1 (implement + re-lock).

---

### Context — the bug (2026-07-16 manual audit)
`s05` credits five identifiable dead-time components into `lower_bound_s` (a union ∩ s03 dead).
Four (celebration / sub / card / restart_excess) bracket to the **next restart play_pattern**.
The fifth — **injury** — is the only one keyed to the next **`Referee Ball-Drop`** event, capped
at `max_injury_s`=600 s. When the matching drop is missing, `_next_resume` grabs a distant drop
(often a different half) and the window clips to the 600 s cap; `intersect-with-dead` then credits
routine throw-in/goal-kick dead time across that 10-min window as "injury stoppage." Confirmed on
match 3939992 (Costa Rica 2-1 Paraguay, Copa 2024): 42.2 owed / 7.1 played, all injury windows
mis-paired.

The proposed fix (memory `project_statsbomb_injury_pairing.md`) was **plain next-restart**, like
sub/card. The pressure test red-teamed that, and a human checkpoint then sharpened the target: an
injury window should end at **the next live, ball-in-play event**, not at a throw-in/goal-kick
"restart" *marker*. The right operationalisation of "next live ball" is the **next s03 in-play
segment start** — the Opta-calibrated live-ball boundary the whole pipeline already rests on, which
depends on **no** event-type marker at all. We tested four rules (`current`, plain `restart`,
`earliest`-of, and `inplay` = next in-play segment start). **Headline conclusions up front:**

1. **The current key is indefensible** — `Referee Ball-Drop` is present near an injury only ~29% of
   the time and absent 50% of the time. Keying an estimator component off it should not survive
   review. **Change is warranted on correctness grounds.**
2. **Use the next live ball-in-play event (`inplay`), not a restart marker.** It is the best-calibrated
   candidate (WC2018 r 0.870 ≈ locked 0.875, MAE **1.67 < locked 1.77**), it beats both plain
   next-restart (r 0.846) and earliest-of (r 0.854), and it is conceptually bulletproof: it reuses
   the calibrated s03 segmentation and structurally credits **at most one dead segment** per injury,
   so it cannot exhibit the "grab a distant marker, sweep 10 min" pathology. Marker-based rules
   overshoot a genuinely-earlier resumption (plain next-restart overshoots the ball-drop in 45.5% of
   both-marker cases).
3. **The fix barely moves the headline, and what movement appears is a residual-refit artifact, not
   the POST over-credit correction the audit assumed.** Done properly, the injury re-pairing nets
   ≈ 0 across the POST pool (the Copa over-credit fix is cancelled by an AFCON *under*-credit
   recovery). The value of this change is **defensibility**, not a new number.

---

### Pressure-test findings (six tournaments, 1,983 Injury Stoppage events)

**P1 — was ball-drop ever a workable key? No.** Of 1,983 injuries, next `Referee Ball-Drop` in the
same half is: genuine/nearby (≤120 s) **29.2%**; present but >120 s away (mis-pair risk) **20.7%**;
**absent 50.1%**. Gap when present: median 90 s but p90 = 1,042 s, max 2,738 s. Under the Laws a
dropped ball only restarts play when the ref stopped it with no clear possession; most injuries
occur with the ball already out, so the correct restart *is* a throw-in/goal-kick/free-kick and the
ball-drop is *legitimately* absent. The current rule therefore either credits 0 (half the time) or
grabs a distant drop — never the right window.

**P2 — marker rules overshoot; the in-play boundary sidesteps the problem.** Of 976 injuries with
*both* markers, the ball-drop is strictly **earlier** than the next restart in **45.5%** (median
57 s, p90 136 s): a genuine dropped-ball resumption can be followed by more dead events before a
"From …" restart pattern, so plain next-restart *overshoots* it. earliest-of{restart, drop} fixes
that particular overshoot but still inherits both markers' sparsity/noise. The `inplay` rule avoids
the whole marker question — it ends the window at the **next in-play segment start** (the moment the
ball is next live per s03), which needs no marker to be present. (For reference: 986 injuries have
restart-only, 13 drop-only, 8 neither.)

**Injury-flag location — validates the `inplay` rule.** 66.9% of injury flags fall inside an s03
**dead** segment (ball already stopped → "next in-play start" is exactly the resumption); the other
33.1% fall in a **live** segment (play briefly continued). Because the window is intersected with
s03 dead, a live-flagged injury contributes only the *following* dead segment, and by construction
the `[flag, next in-play start]` window spans **at most one** dead segment — so `inplay` is
structurally incapable of over-crediting.

**P3 — live play is swept in but fully stripped by ∩dead.** Resumption windows contain live
football (raw Σ: restart 2,597 → ∩dead 1,645 min, 36.7% stripped; earliest 2,097 → 1,545, 26.3%;
inplay 2,504 → 1,581, 36.8%). Because `lower_bound_s` credits only the window **∩ s03 dead**, no
live span is ever credited. Gate stays safe (P6).

**P4 — calibration (THE BIG ONE). The fix slightly DEGRADES the WC2018 fit and forces a NEGATIVE
POST residual.** Both `residual_silent_pre_s` (94.1) and `residual_silent_s` (24.2) are
**mean-anchored** to WC2018 Nate `expected` (13.16 min), so any refit is mean-preserving on WC2018
by construction — the quality signals are **r** and **MAE**:

| rule | WC2018 r | MAE (min) | refit PRE resid | refit POST resid |
|---|---|---|---|---|
| current (locked) | **0.875** | 1.77 | 94.1 s | 24.2 s |
| plain next-restart | 0.846 | 1.83 | 14.7 s | **−55.2 s** |
| earliest-of | 0.854 | 1.78 | 20.6 s | **−49.3 s** |
| **inplay (next live ball)** | **0.870** | **1.67** | 25.9 s | **−47.7 s** |

- **`inplay` is the best-calibrated candidate.** Its r (0.870) essentially ties the locked ball-drop
  rule (0.875) and sits far above both marker rules (0.846 / 0.854); its MAE (1.67) *beats* even the
  locked rule (1.77). The marker rules degrade r because they depend on sparse/noisy markers; the
  in-play boundary does not, so it recovers the per-match correlation the ball-drop key had, without
  the ball-drop key's indefensible sparsity. **This is the decisive calibration result: the change
  the human asked for is not a reluctant trade-off — it is a strict calibration improvement.**
- **The POST residual refit still goes negative under every alternative (−47.7 s for inplay).** It is
  fit on WC2018 with *full-gap* celebration (the POST convention). Adding injury credit there raises
  the estimate above Nate → negative residual. A negative "irreducible unmarked-but-addable
  remainder" is **incoherent**. It arises because WC2018 has the *worst* ball-drop logging in the set
  (17.9% presence), so switching its injuries from "credit 0" to a real resumption moves its lb the
  most — independent of which resumption rule we pick. Handling: **floor at 0** (D2).

**Was the POST over-credit "baked into" the frozen residual? No — and that is the problem.** The
residual is calibrated on WC2018 (PRE), whose injuries currently credit ≈ 0; the Copa/AFCON
distant-drop over-credit never touched it. So correcting POST injuries does *not* flow through the
residual. Instead, changing WC2018's injuries **forces a residual refit that then sprays a uniform
shift across all 314 matches** — a confound, not a correction.

**Channel decomposition (`inplay`) — the decisive result:**

| tournament | era | Δ owed (min) | residual channel | lb/injury channel |
|---|---|---|---|---|
| WC 2018 | PRE | +0.00 | −1.14 | +1.14 |
| Euro 2020 | PRE | −1.00 | −1.14 | +0.13 |
| Euro 2024 | PRE | −0.65 | −1.14 | +0.49 |
| WC 2022 | POST | −1.73 | −1.20 | −0.54 |
| Copa 2024 | POST | −3.15 | −1.20 | −1.95 |
| AFCON 2023 | POST | +0.88 | −1.20 | +2.08 |

The **residual channel is a near-uniform −1.14/−1.20 min for every match** (both residuals fall by
roughly the same amount, since the injury credit added to WC2018-lb is nearly the same under either
celebration mode). The **genuine lb/injury channel nets ≈ 0 across the POST pool**: Copa −1.95 and
WC2022 −0.54 (real over-credit removed) are cancelled by **AFCON +2.08** (missing ball-drops
recovered → previously under-credited). So the injury re-pairing *itself* barely changes POST owed;
the whole visible POST pool move is the WC2018-driven residual artifact. (earliest-of gives the same
picture: POST lb-channel Copa −1.99 / WC2022 −0.64 / AFCON +2.01.)

**P5 — POST concentration is a ball-drop-*logging* gradient, not football, and the fix's direction
is mixed.** Ball-drop presence (≤120 s): WC2018 17.9%, AFCON 21.5% (the two worst), Copa 36.6%, WC
2022 34.0%, Euro 2020 30.9%, Euro 2024 39.1%. This tracks `docs/statsbomb_data_quality.md` (AFCON
& Copa thinnest-logged; WC2018 has no off-camera flags). The current rule's bias is therefore a
*logging* bias — but the fix corrects it in **opposite directions**: it removes over-credit where
distant drops were grabbed (Copa) and *adds* credit where drops were absent (AFCON, Euro 2020/24).
So it does **not** cleanly narrow the PRE/POST natural-experiment gap (see below).

**P6 — gate & union safe.** Zero `lower_bound_s > total dead` violations under any rule (shorter
windows only shrink the union ∩ dead). Sub/card/celebration/restart_excess intervals are identical
across rules by construction — only the injury interval feeding the union changes.

**P7 — edges clean.** 9/314 matches have no Injury Stoppage event (unaffected). 61 ET-period
injuries across 20 matches (periods 1-4 handled; shootout period ≥5 skipped as today). 994/1,983
(50%) injuries currently credit 0 for lack of a ball-drop; next-restart recovers genuine injury
dead time for these. **Cap:** the 600 s cap binds on 198/989 windows (20%) *today* — a direct
symptom of the mis-pairing — and **0%** under both proposed rules. The cap can stay at 600 s
(now non-binding) or be lowered to ~300 s for tidiness; not load-bearing.

**Worked example — match 3939992 (Costa Rica 2-1 Paraguay):** true_stoppage 42.2 → 26.8 (plain
restart) → 25.4 (earliest-of) → **25.4** (inplay); injury∩dead 31.2 → 12.4 → 10.9 → 10.9 min.
Confirms the audit; inplay and earliest agree on this match.

---

### Natural-experiment impact (the reason this touches the headline)
Mean owed (true_stoppage), current → `inplay` (earliest-of shown for comparison):

| pool | current | inplay (resid refit) | inplay (**resid floored ≥0**) | earliest (floored ≥0) |
|---|---|---|---|---|
| PRE (166) | 14.02 | 13.51 (−0.51) | 13.51 (−0.51) | 13.45 (−0.57) |
| POST (148) | 21.29 | 20.17 (−1.12) | **20.96 (−0.33)** | 20.88 (−0.40) |
| POST − PRE gap | 7.27 | 6.66 (−0.61) | **7.45 (+0.18)** | 7.43 (+0.16) |

The PRE/POST *gap* barely changes, and its sign depends entirely on how the negative residual is
handled: the residual channel cancels in the PRE−POST difference, leaving only the small, mixed
injury channel. **The audit's premise — "correcting NARROWS the PRE/POST gap" — does not hold
once the re-pairing is done properly.**

---

### Decision points for the human

**D1 — Pairing rule.** Recommend **`inplay` = injury → next s03 in-play segment start** (the next
live, ball-in-play event), cap 600 s (now non-binding; could drop to ~300 s for tidiness). Rationale:
(i) it is exactly "measure stoppage as the time from the injury flag to the next live ball," the
principled definition, needing **no** event-type marker; (ii) best calibration of all candidates —
r 0.870 ≈ locked 0.875, MAE 1.67 < locked 1.77 (P4); (iii) structurally credits at most one dead
segment, so it cannot over-credit (injury-flag-location diagnostic); (iv) gate-safe (P3/P6); (v) it
reuses the Opta-calibrated segmentation the entire pipeline already trusts. earliest-of{restart,
drop} is the second choice (r 0.854, near-identical pools) if a marker-based rule is preferred for
implementation simplicity; plain next-restart is third (overshoots 45.5% of genuine drops, r 0.846).

**D2 — Residual handling (load-bearing).** A refit is mandatory (changing injury pairing without
refitting would un-anchor WC2018 from Nate). But the POST refit is negative under every alternative
(−47.7 s for inplay). Three options:
  - (a) ship the negative residual as the literal fit (−48 s) — **not recommended** (indefensible;
    a reviewer will call it a fudge; magnitude is a WC2018-logging artifact);
  - (b) **floor both residuals at 0** — recommended. Reading: inplay injury credit + full
    celebration + marked-silent already account for POST addable stoppage; no positive remainder is
    warranted, and we add no negative one. PRE stays positive (25.9 s). This is the conservative,
    coherent choice.
  - (c) hold the residuals frozen — rejected (un-anchors WC2018).

**D3 — Go / no-go.** Recommendation: **GO to Phase 1**, with `inplay` + floored residuals. Unlike
the earliest-of framing (a reluctant "replace an indefensible key even though calibration dips
slightly"), inplay makes the case clean: it is *both* the correct definition *and* a calibration
improvement (MAE 1.67 < 1.77, r ≈ preserved). Set expectations: the six-tournament headline
(ADR-0035, 24.4% / 12.9%) will move only slightly — both pools' owed fall modestly under floored
residuals (PRE −0.51, POST −0.33 min), so omitted stoppage and X% edge **down** a little, roughly
symmetric across eras, leaving the natural-experiment story intact. **The exact X% MUST come from
the Phase 1 s08 grid — the mean-owed shift does not map 1:1 to the counterfactual** (X% depends on
true_stoppage in *added time* per half, not whole-match owed).

---

### Phase 1 plan (only after human approves the above)
1. `src/s05_incident.py` injury branch (~:159): replace the `want_type="Referee Ball-Drop"` resume
   with the **next s03 in-play segment start**. s05 **already loads `bip_segments.parquet`** (`:108`)
   and builds `dead_seg` per (match, period) at `:117-119`; add a sibling `inplay_start` dict
   (`seg[seg["in_play"]]` grouped by (match_id, period), sorted `start_s`) right there and pass the
   period's array into the injury branch — `r = first in-play start > t0`, keep the cap. No new file
   read, no `bip.py` reconstruction.
2. Refit `residual_silent_pre_s` / `residual_silent_s` on WC2018 under the new rule, **floored at 0**
   (per D2b): PRE ≈ 25.9 s (was 94.1), POST → **0** (refit is −47.7, floored). Update `params.yaml`
   + the `estimator_pearson_r`/`estimator_mae_min` (→ ~0.870 / ~1.67).
3. Re-run `s05 → s06b → s08 → s09`; regenerate `data/processed/*.parquet`, `figures/*`,
   `docs/numbers_ledger.md`.
4. Update the s05 pytest gate (WC2018 r/MAE) and `tests/test_pipeline.py` decay endpoints if they
   move.
5. Report the **before→after headline delta** (scoreline X% + CI, flip + CI, lead band, joint
   envelope, PRE/POST rates) from the regenerated grid, exactly like the ADR-0035 block.
6. Write the real ADR-0039 in `docs/decisions.md`; if the human approves, re-lock and run the
   **README §7 sync pass** (repoint/re-mirror the latest `docs/substack_post_v*.md`, grep out stale
   numbers). Touch `CLAUDE.md §1/§2` + the Substack changelog only if the move is material.
