# Next session — pointer to the current unit of work

Read `CLAUDE.md §6` first: **one self-contained unit per session, then stop.** Do not chain
these items into one marathon session.

> **Standing checkpoint rule (CLAUDE.md §7):** before ending any session that touched the model,
> headline, bands, sensitivity, knobs, calibration, tournament set, pipeline, or the public
> narrative, run the **README sync pass** and update `README.md` in the same session. The README
> mirrors the structure of the latest `docs/substack_post_v*.md` and must always link to that
> exact file. Note "README: synced" or "README: no change needed" in your checkpoint.

---

## ✅ DONE (2026-07-20, ADR-0040) — Fixed the `silent_marked` / `lower_bound` DOUBLE-COUNT in the s05 estimator; headline RE-LOCKED to 21.4% / 10.8%

> **Phase 0 (pressure test) + Phase 1 (implement + re-lock) both COMPLETE and human-approved (2026-07-20).**
> `_subtract` helper added to `src/s05_incident.py`; `silent_marked_s` and `silent_all_s` now computed
> with `_subtract(silent_iv, all_intervals)` before intersecting dead — lower_bound and silent_marked
> are provably disjoint. Residuals refit: PRE 25.9→204.1s, POST 0→130.5s (POST floor MOOT). Calibration
> r 0.870→0.836, MAE 1.67→1.54. **Headline RE-LOCKED (ADR-0040): scoreline 23.3%→21.4% [18.2%, 25.2%],
> flip 12.1%→10.8% [9.1%, 12.8%]** (−1.9 / −1.3 pp; data-quality correction, POST-concentrated). Pools
> UNCHANGED (PRE 166 / POST 148); owed 16.2 min/match, omitted 7.3 min, played 8.9 min/match.
> New `test_s05_dedup_lb_plus_sm_below_dead` gate; 27/27 pytest green. **Checkpoint complete:**
> `docs/decisions.md` ADR-0040, `CLAUDE.md §1` re-lock block, `config/params.yaml` constants,
> full README §7 sync, `docs/Methodology.md` + `docs/substack_post_v4.md` minimal number-only edits.
> **NOT committed** (awaiting human's explicit go). The full Phase-0/Phase-1 spec is retained below.

**This is a LOCK-TOUCHING change to the six-tournament StatsBomb headline (23.3% scoreline / 12.1% flip,
ADR-0039).** Per CLAUDE.md §6 it is a two-session unit with a HARD human checkpoint between Phase 0
(read-only pressure test) and Phase 1 (implement + re-lock). Do Phase 0 first as ANALYSIS ONLY, STOP,
and only implement after the human signs off on the design + the projected headline move.

### The finding (2026-07-19 top-5 owed audit)
Auditing the top-5 highest-owed StatsBomb matches (all AFCON'23 / Copa'24, owed 38–46 min vs a 17-min
mean) surfaced a real defect: **`true_stoppage_s = lower_bound_s + silent_marked_s + residual` sums two
terms that partially overlap, so the overlapping dead seconds are credited TWICE.** The audit script is
`src/audit_statsbomb_top5_owed.py` (read-only; keep it — it also backs the validation exhibit below).

- **Mechanism.** `silent.marked_silent_intervals` is *supposed* to be disjoint from the identifiable
  windows (celebration/sub/card/injury/restart_excess). It excludes a silent gap only when the NEXT
  possession begins with a `From …` restart `play_pattern` (`src/lib/silent.py:74`). But an
  injury/sub/card window whose **resume event lacks a `From …` tag** — logged instead as `Goal Keeper`,
  `Shot`, or a `Pass` with `play_pattern` blank / `Other` / `Regular Play` — is NOT excluded by that
  test, so the *same* dead window lands in BOTH `lower_bound_s` (via the injury/sub/card component) and
  `silent_marked_s`. `s05_incident.py:241` then adds them.
- **Smoking gun.** Egypt 1-1 Congo DR (mid=3922240) P1: the 257 s injury window @41:24→45:42 sits inside
  BOTH `injury_s=446` and `silent_marked_s=330` on the same period row. Confirmed on 281/314 matches
  (overlap > 0.5 min); max 15.0 min (Senegal-CIV mid=3922242).
- **It is POST-concentrated** because loose restart tagging tracks data quality. Mean overlap
  (`silent_marked ∩ lower_bound`, ∩dead), min/match: **AFCON 5.52, Copa 4.75, WC2022 2.88, Euro2020 2.99,
  Euro2024 2.83, WC2018 2.58**. Pooled **PRE 2.78 / POST 4.21**.

### Why it matters — and the CORRECT size of the impact (established this session; reproduce it)
The raw POST double-count is 4.21 min/match, but the **headline** impact is smaller because the estimator
is Nate-calibrated on WC2018, which itself carries ~3.0 min of the SAME overlap — so a proper fix must
**dedup AND refit both residuals**, which re-absorbs the WC2018-common level. A back-of-envelope
simulation (refitting both residuals exactly as ADR-0039 did; the POST full-gap refit reproduced
ADR-0039's −47.7 s to the decimal, validating the method) gives:

- **PRE residual** `residual_silent_pre_s` 25.9 → **~204 s** (rises to re-anchor WC2018 to Nate 13.16 min).
- **POST residual** `residual_silent_s` full-gap raw −47.7 s (currently floored 0) → **+130.5 s** — now
  solidly POSITIVE, so the ADR-0039 D2 floor NO LONGER BINDS. That is itself evidence the fix is correct:
  the incoherent-negative residual that ADR-0039 had to floor was a SYMPTOM of this double-count inflating
  `lb+sm` above Nate on WC2018 (see memory [[residual-calibration-mechanics]]).
- **Owed (true_stoppage, full match):** PRE 13.51 → 13.70 (**+0.19**, ≈unchanged — calibration
  re-absorbs); POST 20.96 → 18.92 (**−2.04 min/match**, NOT −4.21). **PRE/POST owed gap 7.45 → 5.22
  (narrows ~2.2 min/match).** Pooled owed move ≈ **−0.86 min/match**.
- **Scale vs ADR-0039:** that re-lock moved scoreline −1.1 pp off a −0.4 min/match pooled owed move; this
  is ~2× larger and POST-concentrated, so expect the scoreline to move DOWN on the order of ~1–3 pp and
  the PRE/POST natural experiment (currently 20.6% vs 26.5%) to converge somewhat. **This WILL likely trip
  the ">1 pp → bring to human" guardrail. The exact X% MUST come from the regenerated s08 grid — do NOT
  extrapolate from mean-owed (omitted = max(0, owed−played) per half is nonlinear; P(≥1 goal) saturates).**

> NOTE — correction to the 2026-07-19 audit's first-pass reassurance: an earlier note in that session
> estimated the impact at "~0.25 min/match added-time differential, sub-0.5 pp." That decomposition was
> WRONG — it only counted overlap past 45:00, but `omitted_h = max(0, ts_h − played_h)` uses the
> WHOLE-half owed (`s08_counterfactual.py:9,343`), so a mid-half injury's overlap DOES propagate. The
> corrected, calibration-aware figure above (~2 min/match POST owed, ~2.2 min gap narrowing) is the one to
> trust.

### PHASE 0 — read-only pressure test (standalone script, NO pipeline writes). Then STOP.
**Role:** senior sports-data scientist red-teaming the fix before a locked line changes. Work in a throwaway
script (pattern: `src/injury_pairing_pressure_test.py` writes only a markdown/print report). Touch NOTHING
in `src/s05_incident.py`, `src/lib/silent.py`, `params.yaml`, `data/processed|interim/*.parquet`,
`tournaments.yaml`, or any ADR. Interrogate, from the data:

1. **Confirm the root cause + choose the fix LOCATION.** Two candidates — decide with evidence:
   - **(A) Dedup at credit time in s05** (recommended default; surgical, provably disjoint): credit
     `silent_marked_s` only on the part of the marked-silent intervals NOT already in the
     `lower_bound` union (celebration/sub/card/injury/restart_excess), then ∩ dead. Zero risk to the
     other components; `silent_all_s` deduped the same way for internal consistency (it's the non-reported
     upper-bound knob, so monotonicity `silent_marked ≤ silent_all` must still hold — verify).
   - **(B) Fix at source in silent.py**: treat a gap as a restart boundary on a `possession` change even
     when the `From …` tag is missing (or when the lead-edge event carries an incident marker). More
     principled but touches the SHARED live/dead classifier that also feeds s03 BIP — quantify whether it
     perturbs `bip_segments` / the s03 calibration gate (it must NOT; BIP = total dead is the validated
     rule). If (B) risks BIP, prefer (A).
2. **Measure WC2018 r/MAE under the dedup** and **refit both residuals** (PRE excess-convention on the
   WC2018 rows as they sit in `incident_stoppage.parquet`; POST full-gap convention = recompute WC2018 lb
   with `is_pre=False`). Reproduce the targets above (PRE ~204 s; POST −47.7→+130.5 s). If they differ
   materially, investigate before proceeding. Report the r/MAE the deduped estimator prints (expect it to
   stay ~0.87 and the residuals to become healthily positive — the floor should stop binding).
3. **Project the six-tournament before→after**: owed PRE/POST, the natural-experiment gap, and (from a
   dry-run of the s08 metric, or clearly flagged as an estimate) the likely scoreline/flip direction and
   rough magnitude. Confirm POST-concentration is a data-quality correction, not a new bias.
4. **Gate interactions.** Confirm the fix keeps `lower_bound_s ≤ dead` and NEWLY makes
   `lower_bound_s + silent_marked_s ≤ total dead` hold by construction (both ⊂ dead and now disjoint) —
   this is the missing guard (Phase 1 adds it as a test) that would have caught the bug.
5. **Anything a StatsBomb expert would flag** — ET periods, the `silent_all` knob, matches with zero
   overlap, whether any legitimately-incremental marked-silent time is wrongly removed (it should not be —
   dedup only removes seconds already credited by an identifiable window).

**Phase 0 deliverable:** a proposed **ADR-0040 draft** (`docs/ADR-0040-draft-silent-dedup.md`) recommending
fix location (A vs B), the refit residual values with the Nate r/MAE evidence, the projected before→after
on WC2018 + the six pools, and a go/no-go. **Then STOP for the human checkpoint.**

### PHASE 1 — implement (only after human sign-off on the ADR-0040 draft). Then STOP.
1. **Code:** implement the chosen fix. For (A): add a `_subtract(a, b)` interval helper to
   `src/s05_incident.py` and credit `silent_marked_s = _intersect_total(_subtract(silent_iv,
   all_intervals), dead)` (and the same for `silent_all_s` with `silent_all_iv`). Update the module
   docstring's silent-term paragraph to state it is disjoint from `lower_bound`.
2. **Refit residuals → `config/params.yaml`** (`residual_silent_pre_s`, `residual_silent_s`) to the
   Phase-0 values; update `estimator_pearson_r` / `estimator_mae_min` to what s05 prints. Note in the ADR
   that both residuals are now positive (ADR-0039's D2 floor is moot).
3. **Re-run** `python run.py --stage 5` (watch the printed Nate r/MAE + gate), then `--stage 6b`,
   `--stage 8`, `--stage 9`. Feed printed r/MAE back into params and re-run s05 once so parquet + params
   agree.
4. **Tests (`pytest -q` green):** `test_s05_true_stoppage_estimator` asserts the sum identity (passes once
   params match parquet). **ADD a new gate** `lower_bound_s + silent_marked_s ≤ total dead` (runtime check
   in `s05_incident.py:main` alongside the existing gate, + a `tests/test_pipeline.py` test). Update
   `test_s08_decay_endpoints` constants to the freshly-regenerated grid values (record before→after in the
   ADR; do NOT loosen tolerance to hide a move). Pool counts (166/148) unaffected.
5. **Size the REAL headline from the s08 grid** (full before→after block like ADR-0039: scoreline central
   + 95% CI, flip central + CI, 2H_only, lead band, joint envelope, decay rails, gross-up, PRE/POST
   natural-experiment rates). Worked check: Egypt mid=3922240 P1 silent_marked_s 330 → ~73 s (drops the
   257 s injury overlap); Senegal-CIV mid=3922242 owed drops most (max overlap 15 min).
6. **Write ADR-0040** in `docs/decisions.md` (supersede only the moved ADR-0039 fields; keep the delta
   explicit). **Re-lock ONLY if the human approves the new X%.** If approved, update `CLAUDE.md §1/§2` and
   run the **full README §7 sync** (headline, both CIs, assumption band, joint envelope, one-page table;
   `grep -nE '23\.3|12\.1|20\.1|27\.3|0\.089|0\.075' README.md` to be sure no old numbers survive; repoint
   the latest `docs/substack_post_v*.md` + its changelog with minimal number-only edits per the live-doc
   memory; refresh `docs/numbers_ledger.md` (s09-regenerated), `docs/Methodology.md`,
   `docs/limitations_additions.md`). Update THIS pointer (mark DONE with final numbers) and the memory
   `project_statsbomb_injury_pairing.md` (or a new sibling). STOP.

**Guardrails / scope:** Do NOT commit unless the human asks. Do NOT touch `config/tournaments.yaml`, the
WC2026/Sky lane (`src/sky_wc2026/*`, `data/processed/sky_wc2026/*`), or any prior ADR's recorded numbers.
`s03/bip.py` stays the validated total-dead rule (fix (A) leaves it untouched; fix (B) must prove it
doesn't move BIP). If the regenerated headline moves MORE than Phase 0 predicted or the PRE/POST story
inverts, STOP and bring it to the human before re-locking.

### Secondary (fold in or spin off — lower priority, non-lock-touching)
- **Validation exhibit (cheap, high value):** every top-owed match has 7–11 min of *actually-played*
  added time (Morocco 11.2 min P1, Senegal 7.0 P2, Gambia 10.1 P2) — near-independent corroboration that
  the injury windows are real. Add a short owed-vs-played table to `docs/statsbomb_data_quality.md` from
  `src/audit_statsbomb_top5_owed.py`. No number change; can be its own session.
- **Cosmetic (note only, no number change):** the injury component label bundles the trailing sub/restart
  (Morocco's window contains the Player Off; Gambia's contains a card). Union-merge makes totals correct;
  mention only if per-component attribution is ever published.
- **Do NOT** tighten `max_injury_s` / the injury rule — England-Iran's genuine 7m15s and Morocco's
  7m51s→sub prove long windows are real; the 600 s cap is appropriately non-binding.

---

## ✅ DONE (2026-07-17, ADR-0039) — Fixed the injury→ball-drop mis-pairing in s05; headline RE-LOCKED to 23.3% / 12.1%

> **Phase 0 (read-only pressure test) + Phase 1 (implement + re-lock) both COMPLETE and human-approved
> (2026-07-17).** The s05 injury window was re-keyed from the inconsistently-logged `Referee Ball-Drop`
> to the **next s03 in-play segment start (the next live ball), rule `inplay` (D1)**; both era residuals
> were re-fit and **floored at 0 (D2)**: PRE `residual_silent_pre_s` 94.1→25.9, POST `residual_silent_s`
> 24.2→0.0 (raw refit −47.7 is an incoherent negative remainder → floored). Calibration improved: WC2018
> r 0.875→**0.870**, MAE 1.77→**1.67**. **Headline RE-LOCKED (ADR-0039): scoreline 24.4%→23.3% [20.1%,
> 27.3%], flip 12.9%→12.1% [10.4%, 14.2%]** (−1.1 / −0.8 pp; surfaced + approved at the ">1 pp → human"
> guardrail). Pools UNCHANGED (PRE 166 / POST 148); natural experiment preserved and directional (PRE
> 20.6% vs POST 26.5% scoreline). Mean owed 17.4→17.0 min; POST `true_stoppage` no longer byte-identical
> (POST residual moved to 0 — intended). **Checkpoint complete:** `docs/decisions.md` ADR-0039,
> `CLAUDE.md §1` re-lock block, `config/params.yaml` constants, full README §7 sync, `docs/Methodology.md`
> + `docs/limitations_additions.md` refreshed, `docs/substack_post_v4.md` minimal number-only edits + new
> `docs/substack_v4_changes_adr0039.md` changelog, `docs/flip_split_sensitivity.md` +
> `docs/team_quality_flip_test.md` regenerated, `docs/numbers_ledger.md` regenerated (s09), pytest green.
> **NOT committed** (awaiting the human's explicit go). The full Phase-0/Phase-1 spec is retained below
> for provenance.

**This is a change to the LOCKED StatsBomb pipeline (headline 24.4% / 12.9%, ADR-0035).** Per CLAUDE.md
§6 it is a two-session unit with a HARD human checkpoint between them. **Do Phase 0 (the expert
pressure test) first as read-only ANALYSIS, STOP, and only implement (Phase 1) after the human
signs off** on the design that survives the pressure test. Full audit context in memory:
`project_statsbomb_injury_pairing.md`.

### The finding (2026-07-16 manual audit)
The `injury` component in `src/s05_incident.py` is the only one of five keyed to the next
`Referee Ball-Drop` (capped `max_injury_s`=600). StatsBomb logs `Referee Ball-Drop`
inconsistently; when the matching drop is missing, `_next_resume` grabs the next *distant* drop
(often 11–41 min away / a different half) and the window clips to the 600 s cap. `intersect-with-dead`
then credits ~5–6 min of ordinary throw-in/goal-kick dead time across that 10-min window as
"injury stoppage" — routine dead time, not addable stoppage. Confirmed on match_id 3939992
(Costa Rica 2-1 Paraguay, Copa 2024): all 8 injury windows mis-paired; the whole 2nd half has ONE
ball-drop (43:11) that four separate injuries each grab. **Proposed fix:** bracket injury to the
next **restart** (like `sub`/`card` already do), not to `Referee Ball-Drop`. On 3939992 that gives
28.1 min (vs 42.2 current; vs 19–25 if injuries dropped entirely — next-restart is the most correct
since it keeps the *genuine* injury dead time). Scale (conservative, cap-hits only): POST mean owed
21.29→19.08, PRE 14.02→13.06; **POST-concentrated** (Copa −5.7, AFCON −3.1 mean min), which matters
because it inflates the treated side of the PRE/POST natural experiment.

### PHASE 0 — expert StatsBomb pressure test (READ-ONLY; standalone script, NO pipeline writes)
**Role for this phase:** you are a senior sports-data scientist with deep StatsBomb open-data
expertise, brought in cold to red-team this fix *before* a single line of the locked pipeline
changes. Your job is to find what we've missed. Work in a throwaway script (pattern:
`src/bip_headline_sensitivity.py` writes to a scratch dir); read the production parquet, write only a
short markdown/print report. Do **not** touch `src/s05_incident.py`, `params.yaml`, any
`data/processed/*.parquet`, `tournaments.yaml`, or any ADR. Interrogate at least these, from the data:

1. **Ball-Drop semantics (is the fix *more* principled, or just different?).** Under the Laws, a
   dropped ball only restarts play when the ref stopped it with no clear possession — many injuries
   occur with the ball already out, so the correct restart IS a throw-in/goal-kick/free-kick and
   `Referee Ball-Drop` is *legitimately* absent, not merely unlogged. Quantify: of all `Injury
   Stoppage` events across the six tournaments, what share have a genuine nearby (`≤`~120 s)
   `Referee Ball-Drop` vs none? That share tells you whether ball-drop was ever a workable key.
2. **Earliest-resumption rule, not blind next-restart.** A real dropped-ball restart may be logged as
   `Referee Ball-Drop` (a *type*) with the following event carrying `Regular Play` (not a `From …`
   restart pattern) — so a naive "next restart pattern" could *overshoot* a genuine ball-drop
   resumption. Test whether the robust rule is **end = the EARLIEST of {next restart play_pattern,
   next Referee Ball-Drop}**, capped. Show cases where these differ.
3. **Late/loose injury markers.** Does StatsBomb log `Injury Stoppage` at the instant play stops, or
   sometimes while play continues (advantage)? If the marker can precede a long live phase, next-restart
   could span live play — check how often, and confirm `intersect-with-dead` fully neutralises it (it
   should, but verify on real windows).
4. **Calibration integrity — THE BIG ONE.** The estimator's `residual_silent_s` / `residual_silent_pre_s`
   were FROZEN by fitting the WC2018 (all-PRE) estimator to Nate Silver's `expected` (r/MAE gate in
   s05). Changing injury pairing changes `lower_bound_s` on the 32 WC2018 matches. **Measure the WC2018
   r/MAE shift under the new rule**, and determine whether the over-credit was partly *baked into the
   frozen residual* (i.e. the residual silently compensated for it on the calibration set). If so, the
   residual must be **re-fit / re-anchored to Nate** — decide and document; this is what propagates the
   change to the headline. Report what refit (if any) restores the Nate anchor.
5. **Is the POST concentration real football or a logging artifact?** Cross-check against
   `docs/statsbomb_data_quality.md`. If Copa/AFCON simply log ball-drops worse than the WCs/Euros, the
   fix corrects a data-quality bias (good) — but confirm it isn't *introducing* a competition-dependent
   bias of its own. Report per-tournament ball-drop-presence rates.
6. **Union / gate interactions.** Confirm the new (shorter) injury windows keep the s05 gate
   (`lower_bound_s ≤ total dead`) safe, and that folding injury into the union doesn't disturb
   `restart_excess`/`sub`/`card` credit (it shouldn't — union merges — but show it).
7. **Anything else a StatsBomb expert would flag** — e.g. `Referee Ball-Drop` vs `injury_present`
   flag usage, ET periods, own-goal/penalty edge cases, matches with zero injury events. Surface it.

**Phase 0 deliverable:** a short report recommending the exact pairing rule (plain next-restart vs
earliest-of-{restart, ball-drop}; cap value), the residual-refit decision with the Nate r/MAE
evidence, the projected before→after on the WC2018 calibration set AND the six-tournament pools, and
a go / no-go. Write it as a proposed **ADR-0039** draft. **Then STOP for the human checkpoint** — do
not implement.

### >>> PHASE 1 — IMPLEMENT the injury re-pairing (TURNKEY PROMPT; this is the authoritative next unit)

**Read this whole section before touching anything.** This is a LOCK-TOUCHING change to the six-tournament
StatsBomb pipeline (headline 24.4% scoreline / 12.9% flip, ADR-0035). It is ONE modular session
(CLAUDE.md §6): make the change, re-run the affected stages, size the real headline move from the s08
grid, write ADR-0039, and — only if the human approves the new number — re-lock + README §7 sync. Then
STOP. Do NOT chain any other unit into this session.

**Role.** You are the pipeline owner making a surgical, well-understood estimator change that Phase 0
already pressure-tested and a human already approved in design. Precision and traceability over speed
(CLAUDE.md §1: every number traces to a script + a checkpointed table + a documented assumption).

**Pre-flight (do first, abort if any fails):**
1. Confirm the human has signed off on the ADR-0039 draft's **D1 = `inplay`**, **D2 = floor both
   residuals at 0**, **D3 = GO**. If sign-off is ambiguous, ASK before editing locked files.
2. `git status` should be clean-ish; know your starting point so the before→after diff is auditable.
3. Re-read `docs/ADR-0039-draft-injury-pairing.md` (the full evidence + decisions) and the memory
   `project_statsbomb_injury_pairing.md`. Optionally re-run the Phase-0 exhibit to refresh the target
   numbers in your head: `python -m src.injury_pairing_pressure_test` (READ-ONLY; writes only
   `docs/injury_pairing_pressure_test.md`).

**The rule to implement (`inplay`): injury window ends at the next s03 IN-PLAY segment start** — the
Opta-calibrated live-ball boundary, needing NO event-type marker. This is the user's "measure to the
next live ball-in-play event," and Phase 0 showed it is the best-calibrated candidate (WC2018 r 0.870
≈ locked 0.875; MAE **1.67 < locked 1.77**) and structurally credits at most one dead segment per
injury (cannot over-credit).

#### Step 1 — code change in `src/s05_incident.py` (ONE function, `main()`)
- **s05 already loads `bip_segments.parquet`** at `:108` and builds `dead_seg[(mid,per)]` at `:117-119`.
  Right after that loop, add a sibling lookup of in-play segment starts:
  ```python
  inplay_start: dict[tuple[int, int], "np.ndarray"] = {}
  for (mid, per), gg in seg[seg["in_play"]].groupby(["match_id", "period"]):
      inplay_start[(int(mid), int(per))] = np.sort(gg["start_s"].to_numpy())
  ```
  (add `import numpy as np` at the top — it isn't imported yet.)
- In the per-(match,period) loop, fetch this period's array once (near where `dead` is fetched):
  `ips = inplay_start.get((int(mid), int(period)), np.array([]))`.
- Replace the **injury branch** (`:159-163`). Currently:
  ```python
  if typ == "Injury Stoppage":
      injury_present = True
      r = _next_resume(clocks, patterns, types, i, want_type="Referee Ball-Drop")
      if r is not None:
          comp["injury"].append((t0, min(r, t0 + p["max_injury_s"])))
  ```
  New:
  ```python
  if typ == "Injury Stoppage":
      injury_present = True
      later = ips[ips > t0]
      r = float(later[0]) if len(later) else None
      if r is not None:
          comp["injury"].append((t0, min(r, t0 + p["max_injury_s"])))
  ```
  Keep the 600 s cap (now non-binding — a harmless guard). `_next_resume`/`_merge`/`_intersect_total`
  and every other component (celebration/sub/card/restart_excess) are UNCHANGED. Update the module
  docstring's `injury` line (`:10`) to reflect the new rule.
- Reference implementation of exactly this logic lives in
  `src/injury_pairing_pressure_test.py::_period_components` (the `injury_rule == "inplay"` branch) and
  its `compute()` builds the same `inplay_start` dict — mirror it so semantics stay byte-identical.

#### Step 2 — refit the two residual constants and write them to `config/params.yaml`
The residuals are frozen constants mean-anchored to WC2018 Nate `expected` (13.16 min). Changing injury
pairing changes WC2018 `lower_bound_s`, so they MUST be refit (per D2), then **floored at 0**:
- **PRE** (`residual_silent_pre_s`): fit on WC2018 with the PRE/excess celebration convention →
  **≈ 25.9 s** (was 94.1). Positive, use as-is.
- **POST** (`residual_silent_s`): fit on WC2018 with the FULL-gap celebration convention → refit is
  **−47.7 s (incoherent)** → **floor to 0.0** (was 24.2).
- Get the exact refit values from the Phase-0 script (its "refit PRE/POST residual … inplay=…" line) or
  recompute inline with the same mean-anchor (`60*(mean_nate − mean_lbms)` over the 32 WC2018 ids). Use
  the script's printed values as the source of truth so the ADR and params agree to the decimal.
- Also update `estimator_pearson_r` **0.875 → ~0.870** and `estimator_mae_min` **1.77 → ~1.67** to the
  values s05 prints under the new rule (read them from the s05 run in Step 3, then write them).
- NOTE the semantic shift worth a one-line ADR mention: POST `true_stoppage` is **no longer byte-stable**
  (it was under ADR-0035) because POST residual moves 24.2 → 0 — this is intended (D2).

#### Step 3 — re-run the affected stages, regenerate artifacts
- `python run.py --stage 5` — recomputes `interim/incident_stoppage.parquet` + `interim/true_stoppage.parquet`.
  Watch the printed `nate.report` r/MAE (expect ~0.870 / ~1.67) and the "s05 gate PASSED" line. Feed the
  printed r/MAE back into `params.yaml` (Step 2) if they differ from your estimate, then re-run s05 once
  more so parquet + params agree.
- Then `python run.py --stage 6b`, `--stage 8`, `--stage 9` (s06b VAR fallback → s08 grid → s09 figures +
  ledger). s06a (played-in-stoppage) and s01–s04/s07 are UNAFFECTED by the injury rule — but if unsure,
  a full `python run.py` is safe (idempotent, CLAUDE.md §3). Regenerates `data/processed/*.parquet`,
  `figures/*`, `docs/numbers_ledger.md`.

#### Step 4 — tests
- `pytest -q` must be green. Expected touch points:
  - `tests/test_pipeline.py::test_s05_true_stoppage_estimator` reads the residuals from params, so it
    passes automatically once params match parquet (it asserts the identity, not a hard number).
  - `test_s05_lower_bound_below_dead` / `test_s05_silent_marked_within_all` — should stay green (shorter
    injury windows only shrink the union; Phase-0 P6 showed 0 gate violations).
  - `test_s08_decay_endpoints` (`:175-177`) pins 1H+2H/2H_only endpoints **0.238 / 0.173 / 0.098** with
    ±0.004 tolerance. These MAY move (the headline shifts down slightly). If they move outside tolerance,
    update the three constants to the freshly-regenerated grid values AND record the before→after in the
    ADR — do NOT loosen the tolerance to hide a move.
  - `tests/test_lib.py` pool counts (166/148) are unaffected (tournament set unchanged).

#### Step 5 — size the REAL headline move from the s08 grid (do NOT extrapolate from mean-owed)
The Phase-0 mean-owed shift (PRE −0.51, POST −0.33 min) does **NOT** map 1:1 to X% — X% depends on
true_stoppage in ADDED TIME per half, run through the counterfactual. Read the regenerated grid and
report the full before→after block exactly like ADR-0035 does:
- **Scoreline X%** central + 95% CI (window 1H+2H, central knob_set `silent_marked|overall|pooled_all|hl=4.0|on`),
  vs locked 24.4% [21.1, 28.3].
- **Outcome-flip** central + CI vs locked 12.9% [11.2, 15.0].
- 2H_only scoreline + flip; lead one-factor band; full joint envelope; decay rails (h2/h4/h8);
  gross-up off/on/geom; PRE/POST natural-experiment rates (locked 0.089 / 0.075).
- Worked check: match 3939992 true_stoppage should read ~25.4 min (was 42.2).

#### Step 6 — write ADR-0039, then checkpoint
- Promote the draft to a real **ADR-0039** entry in `docs/decisions.md` (supersede the ADR-0035 numbers
  only for the fields that moved; keep the ADR-0035 → 0039 delta explicit like the existing re-lock
  blocks). Cite `inplay` (D1), floored residuals PRE 25.9 / POST 0 (D2), the refit r/MAE, and the
  before→after headline from Step 5.
- **Re-lock only if the human approves the new X%** (this is a headline change → it's a lock decision,
  not an automatic one). If approved, update `CLAUDE.md §1/§2` (the LOCKED block + estimator-constants
  note) and the params are already updated.
- **README §7 sync pass (REQUIRED — this touches the public narrative if X% moved):** update the
  headline, both CIs, assumption band, joint envelope, one-page results table; grep the OLD numbers to
  be sure none survive (e.g. `grep -nE '24\.4|12\.9|21\.1|28\.3|0\.089|0\.075' README.md`); repoint/
  re-mirror the latest `docs/substack_post_v*.md` (currently v4 → if you spin a v5 for this change,
  repoint every reference) and update its changelog (`docs/substack_v4_changes_adr0035.md` pattern —
  minimal number-only edits per the live-doc feedback memory). Also refresh `docs/numbers_ledger.md`
  (already regenerated by s09), `docs/Methodology.md`, `docs/limitations_additions.md` if they cite the
  moved numbers.
- Update THIS `next_session.md` pointer (mark Phase 1 DONE with the final numbers), update the memory
  `project_statsbomb_injury_pairing.md`, and STOP.

**Guardrails / scope:**
- Do NOT commit anything unless the human explicitly asks.
- Do NOT touch `config/tournaments.yaml`, the WC2026/Sky lane (`src/sky_wc2026/*`,
  `data/processed/sky_wc2026/*`), or any prior ADR's recorded numbers.
- s03/bip.py is NOT touched (BIP = total dead time stays the validated rule; we only re-key which dead
  time the injury component *claims*). The change is confined to s05's injury bracket + the two residual
  constants + downstream regeneration.
- If the regenerated headline moves MORE than Phase 0 predicted (e.g. scoreline shifts >1 pp, or the
  PRE/POST story inverts), STOP and bring it to the human before re-locking — Phase 0 predicted a small,
  roughly-symmetric down-move; a large or asymmetric move means something in the refit/rerun is off.

---

## ✅ DONE (2026-07-16) — Manual audit of owed windows, top-5 high-owed high-discrepancy WC2026 matches

Read-only audit COMPLETE. Audited Canada v Qatar, Sweden v Tunisia, Jordan v Argentina, USA v
Australia, Germany v Paraguay. Provenance clean on all 5 (candidate ΣD == `Stoppage_Summary`).
Verdict: the model credits TRUE stoppages in the high-discrepancy tail — no window rests on a soft
open-play marker; bare Type-27/28 delays are legit owed (hydration). Found ONE real defect — the
half-time-substitution false positive — now folded into Unit #1 (the estimator upgrade) below as
component 3. Full findings in memory: `project_wc2026_top5_audit.md` + `project_wc2026_halftime_sub_fix.md`.
Throwaway audit scripts: `src/sky_wc2026/audit_top5_windows.py`, `audit_swe_tun.py`.

---

## ✅ DONE + APPROVED (2026-07-16, ADR-0038) — Estimator boundary fixes: seam + lead-in recovery, half-time-sub removal

BUILT, reported, and **APPROVED by the human on 2026-07-16.** Feeds the chart re-render (next unit
below). WC2026 lane only — six-tournament headline (ADR-0035) and every locked artifact byte-stable.
Three boundary
fixes in `src/sky_wc2026/build_wc2026_inputs.py`:
1. **Inter-window seam** (ADDS): dead between two candidate windows with NO open-play event between →
   one stoppage Opta split in two. **+27.4 min** (362 seams). (The audit's 40.8 min counted all
   inter-window dead; the ~13 min difference is gaps where the ball genuinely restarted — correctly
   excluded.)
2. **Lead-in** (ADDS): ball-death (Foul/Out/Offside) → delay-window start; cap 180 s. **+43.9 min**
   (658 windows).
3. **Half-time-sub removal** (REMOVES): sub whose `Match clock` == period-start (P1 00:00 / P2 45:00 /
   P3 90:00 / P4 105:00) is pre-whistle → credit 0, route `D` to excluded. **−45.6 min** (58 windows).

**Before → after (ADR-0037 → ADR-0038, 96 matches):** mean OWED **19.65 → 19.91** (+0.26, +1.3%);
mean (OWED−PLAYED) **6.96 → 7.23**; **% OWED>PLAYED 100% → 100%** (PLAYED unchanged 12.69). Net
+0.26/match = +0.29 seam +0.46 lead-in −0.48 half-time-sub — the correct removal nearly cancels the
additions, so the Sky "before" estimate stands essentially unchanged. Worked examples verified to the
second: Canada v Qatar 50:43→57:07 (lead-in +12 s, seam +9 s); Germany v Paraguay P2 45:00 sub 142 s→0
(+ ET P3 90:00 77 s→0); Jordan v Argentina P2 45:00 sub 75 s→0. Gates all PASS; **G2 re-derived** to
compare OWED against a *broad* dead measure (`total_dead_broad_s` = summary_dead + seam + lead-in),
since seam/lead-in are dead seconds outside the candidate ΣD (max owed/broad-dead 0.59). agg_02
byte-unchanged. Full record: **`docs/decisions.md` ADR-0038**. **README: no change needed** (WC2026
lane still not in the public narrative). Memory `project_wc2026_halftime_sub_fix.md` /
`project_wc2026_owed_mechanics.md` are the frozen-baseline references. Workbook still git-ignored.

---

## >>> NEXT UNIT #1 (TOP PRIORITY — authoritative next session) — Re-render the two WC2026 charts from the APPROVED ADR-0038 tables

**Role / lane.** WC2026 (Sky / Opta) lane ONLY. Do NOT touch the locked StatsBomb pipeline, `config/*`,
`data/processed/*.parquet` (outside `data/processed/sky_wc2026/`), or any prior ADR. The workbook
`data/DONOTSHAREWorldCup_Stoppages.xlsx` is git-ignored and must NEVER be committed. Do NOT commit
anything unless the human explicitly asks. This is a small, self-contained RENDER-ONLY unit — do it,
eyeball the output, checkpoint, STOP.

**Context — why this unit exists.** The human APPROVED **ADR-0038** on 2026-07-16 (three
owed-estimator boundary fixes: inter-window seam recovery, lead-in recovery, half-time-sub removal —
see the DONE block just above and `docs/decisions.md` ADR-0038 for the full record). That ADR
regenerated `data/processed/sky_wc2026/agg01_estimate_vs_played.parquet`, so the two published WC2026
PNGs — rendered under the OLD ADR-0037 tables — are now stale and must be refreshed from the new
tables. **`agg02_productivity_by_bucket.parquet` is byte-UNCHANGED** (ADR-0038 touched OWED only), so
the bar chart will re-render identically; only the scatter actually changes.

**What actually changed in the numbers (so you know what to look for):**
- Mean OWED (`est_min`) **19.65 → 19.91 min**; mean PLAYED **12.69** (unchanged); % OWED>PLAYED
  **100%** (unchanged). Per-match `est_min` shifted a hair (e.g. Canada v Qatar 33.8 → 33.6), so the
  96 scatter dots move slightly, but no dot crosses the diagonal (still 100% red / under-awarded).
- The scatter FOOTER is computed live from the table (`render_wc2026_charts.py:33-35`, `.mean()` on
  `est_min`/`played_min`), **not hardcoded**, so it auto-updates on re-run. The only visible text
  change is **"stoppage owed 19.6 → 19.9 mins"**. Note the footer uses coarse rounding —
  played `{:.1f}` stays "12.7" and missing `{:.0f}` stays "nearly 7 mins" (6.96 and 7.23 both round
  to 7) — and the subtitle "100% of matches ended too early" (`{:.0%}` of `pct_above`) is unchanged.
  So expect EXACTLY ONE changed glyph on the scatter (19.6→19.9) plus imperceptible dot nudges.

**The task (no code edits needed — the render script already reads the tables):**
1. From the repo root, re-run the renderer. It uses package-absolute imports (`from src import
   figures_requested`, `from src.lib import config`) with NO `sys.path` shim, so it must run as a
   MODULE, not a plain script path:
   `python -m src.sky_wc2026.render_wc2026_charts`
   (If you instead run `python src/sky_wc2026/render_wc2026_charts.py` it will fail at
   `from src import figures_requested` because only the script's own dir lands on `sys.path` — use
   `-m`. The sibling `build_wc2026_inputs.py` runs as a plain path only because it has an explicit
   `sys.path.insert(ROOT)` at its top; the renderer does not.)
2. This overwrites `figures/sky_wc2026/agg_01_scatter_estimate_vs_played_wide.png` and
   `agg_02_productivity_by_bucket_bordered.png` (writes into `figures/sky_wc2026/`, a WC2026-only dir
   — the six-tournament StatsBomb figures are untouched; the shared builders in
   `src/figures_requested.py` take override kwargs that default to the old StatsBomb text).

**Verify, then STOP:**
- Open the scatter PNG and confirm the footer now reads **"stoppage owed 19.9 mins, played 12.7 mins,
  and nearly 7 mins missing"** and the title/subtitle ("100%") are unchanged.
- The bar-chart PNG should be visually identical to the ADR-0037 render (agg_02 unchanged) — a quick
  sanity glance is enough; no numbers moved there.
- Do NOT re-run `build_wc2026_inputs.py` or otherwise rebuild the tables; this is render-only.

**README (§7 check):** still **no change needed** — the WC2026/Sky lane is not part of the README's
public narrative (which is the six-tournament headline, ADR-0035, byte-stable). Confirm with
`grep -niE 'sky_wc2026|world cup 2026|wc 2026' README.md` (expect no lane references) and note
"README: no change needed" in the checkpoint.

**Checkpoint when done:** note in `docs/decisions.md` (or as an addendum to ADR-0038 / a short
provenance line) that the two `figures/sky_wc2026/*.png` were re-rendered from the ADR-0038 tables
(scatter footer 19.6→19.9; bar chart unchanged), update this `next_session.md` pointer to mark the
re-render DONE, and STOP. These are the charts the Sky journalists will see, so the footer number is
the one externally-visible change — double-check it reads 19.9.

---

## SUPERSEDED SPEC (kept for provenance) — Estimator upgrade (BUILT in ADR-0038 above)

**Goal:** update the WC2026 owed-stoppage estimator so it quantifies and CREDITS in `owed` both
sources of currently-dropped genuine stoppage time identified on 2026-07-16:
1. **Inter-window seam loss** — dead time BETWEEN two consecutive candidate windows where the ball
   never went live (no open-play event in the gap). Recurs 96/96 matches, ~40.8 min tournament-wide,
   no single seam >17s. Today it's in NEITHER dead nor owed.
2. **Lead-in loss** — dead time between the actual ball-death event (Foul / Out / etc.) and the start
   of the first candidate window of a stoppage (candidates currently start at the Type 27 delay, not
   at the foul). ~12s in the Canada v Qatar example; not yet quantified tournament-wide.
3. **Half-time-substitution false positives (REMOVES owed — opposite direction to 1 & 2)** — the
   model currently credits owed for substitutions made DURING the half-time interval, BEFORE the
   second-half whistle. These are NOT in-play stoppages and must add zero to owed. Surfaced by the
   2026-07-16 top-5 audit: the `P2 45:00→45:00` windows in Germany v Paraguay (142s, ladder: sub) and
   Jordan v Argentina (75s, ladder: sub) are half-time sub clusters wrongly credited. **The test
   (human-verified on Germany v Paraguay):** read the `Match clock` column in the `Match_Event_Log`
   tab for each substitution event. If a sub's `Match clock` reads `45:00` (i.e. the period-start
   time, before the second-half whistle), the sub happened during the half-time interval → EXCLUDE it
   from the owed calculation (credit 0 for that sub). Only subs that occur after the whistle (Match
   clock strictly past the period-start value) count toward owed.

**Why this matters / constraints:**
- An owed-vs-played estimate from the CURRENT ("before") iteration was **already sent to the Sky
  journalist team**. So this change MUST produce an explicit before→after delta the human can show
  them. Report per-match and pooled: mean OWED, mean OWED−PLAYED, %OWED>PLAYED, and the size of each
  new component, exactly like the ADR-0037 before→after block did.
- Direction is known to be **conservative** for components 1 & 2: both losses push OWED UP, widening
  OWED−PLAYED. Expect a modest increase (inter-window ≈ +0.4 min/match; lead-in TBD). Component 3
  (half-time subs) pushes OWED DOWN by removing false positives; it is small (≈75–142s in the two
  flagged matches, only where a half-time sub was mis-credited) and correct in the sham-skeptical
  direction. Report all three components separately in the before→after so the net move is transparent.
- This is a NEW ADR (propose ADR-0038). Do NOT touch the locked StatsBomb model/config/parquet/ADRs.
  Workbook stays git-ignored.

**Design pointers (`src/sky_wc2026/build_wc2026_inputs.py`):**
- Read `project_wc2026_owed_mechanics.md` in memory first — it's the frozen "before" baseline.
- Inter-window: after `_stitch_windows`, for each consecutive window pair within a (fixture, period),
  compute the gap seconds and check `Match_Event_Log` for any OPEN-PLAY event (families: `Open play /
  pass`, `Open play`, `Open play / challenge`, `Shot / restart`) strictly inside the gap. If none, the
  ball stayed dead — either (a) fold the gap into a merged window (preferred: a second-pass stitch
  that merges across interior delay/card/VAR/sub events), or (b) credit the gap directly. Decide and
  document which; (a) also fixes the "one stoppage shows as two windows" artifact.
- Lead-in: for each stoppage-onset candidate window, walk BACK in `Match_Event_Log` from the window
  start to the last live-ball event (the Foul/Out that killed the ball) and credit that intervening
  dead time. Cap sensibly and require a real ball-death marker so open-play noise isn't swept in.
- Half-time subs (component 3, REMOVES owed): the sub branch in `compute_owed` (`:289`, the
  `SUB_EVT`/`Substitution`-family check) currently credits any candidate gap whose boundary event is a
  `Player off/on` — including half-time subs made before the second-half whistle. Load the `Match clock`
  column from `Match_Event_Log` (currently unread; the log reader is `build_wc2026_inputs.load_workbook_tables`
  / the `Match_Event_Log` pass) and, when a window's owed credit is driven by substitution events, drop
  any sub whose `Match clock == "45:00"` (period-2 start; generalize to the period-start clock for each
  period — P1 `00:00`, P2 `45:00`, P3 `90:00`, P4 `105:00`) from the owed-triggering set. If removing the
  pre-whistle subs leaves a window with no other owed marker, that window credits 0. Verify the fix on
  Germany v Paraguay `P2 45:00→45:00` (should drop from 142s→0) and Jordan v Argentina `P2 45:00→45:00`
  (75s→0), and confirm no legitimate post-whistle sub loses credit. The bare 3-min delays like Sweden v
  Tunisia `#2 21:58→25:10` (Type 27/28, human-confirmed as owed — almost certainly a hydration break)
  are NOT affected by this change and must stay fully credited.
- Preserve all existing gates (G1 played vs Sheet1, G2 OWED≤total-dead — NOTE: crediting seam/lead-in
  time may push OWED above `Stoppage_Summary` dead, since those seconds aren't in the candidate ΣD;
  G2 may need to compare against a broader dead measure or be re-derived — think this through and
  document). Regenerate agg01/agg02/ledger, run the ledger gates, and write the before→after delta.
- README: WC2026 lane is still not in the public narrative → likely "README: no change needed", but
  run the §7 check.

---

## APPROVED (2026-07-16, ADR-0037) — WC2026 OWED redesign: delay windows now credited in full

**Human APPROVED ADR-0037** (2026-07-16). The two WC2026 charts have now been rendered from the
approved inputs — see the "DONE — RENDER the two WC2026 charts" block below. Original OWED-redesign
record retained here for provenance.

The OWED redesign below was **BUILT and reported, then reviewed at the human checkpoint before it fed
the charts.** `src/sky_wc2026/build_wc2026_inputs.py` now stitches temporally-contiguous candidate
gaps into maximal dead windows (`_stitch_windows`, exact contiguity) and credits **in FULL** any
window touching an Opta delay marker (type 27 Start delay / 28 End delay / 65 Contentious), to a new
`delay` OWED component. Regenerated `data/processed/sky_wc2026/{agg01,agg02,ledger.md}` (agg_02
UNCHANGED — OWED-only change). **Before → after (96 matches):** mean OWED **14.85 → 19.65 min**
(+4.80, +32%); mean (OWED−PLAYED) **2.16 → 6.96**; **% OWED>PLAYED 82.3% → 100%**; excluded silent
baseline **14.9% → 6.1% of dead**; delay component 1023.5 min (481 windows) = 54.3% of owed. France v
Senegal P2 window flipped **0 → 194.5 s** as specified. Gates G1–G4 + X-check PASS (G2 now binding,
max owed/dead ratio 0.62). +4.80/match decomposes as +370.9 min genuinely-excluded delay time (the
core fix, ≈ the ~365 prior) + 89.9 min from full-window-D superseding capped/excess per-gap credits.
Full record + methodology-revisit recommendation (keep the shipped hybrid; defer a full window-first
rewrite): **`docs/decisions.md` ADR-0037**. Nothing in the locked StatsBomb model/config/parquet or
any prior ADR touched; workbook git-ignored. **README: no change needed** (WC2026 lane still not in
the public narrative). **NEXT after the human OKs ADR-0037 → the "RENDER the two WC2026 charts" unit
below (now unblocked — `est_min` has changed).**

---

## SUPERSEDED SPEC (kept for provenance) — the WC2026 OWED redesign task, now DONE in ADR-0037

**Role.** You are an expert data scientist / data engineer + soccer (Opta/StatsBomb) event-data analyst.
This is a WC2026-lane-only unit (ADR-0036 lane): touch NOTHING in the locked StatsBomb pipeline,
`config/tournaments.yaml`, `config/params.yaml` (READ-ONLY), any `data/processed/*.parquet` outside
`data/processed/sky_wc2026/`, or any prior ADR. The 68 MB workbook
`data/DONOTSHAREWorldCup_Stoppages.xlsx` is git-ignored — **never commit or share it.** All work lives
in `src/sky_wc2026/build_wc2026_inputs.py` + `data/processed/sky_wc2026/`. This is a MODEL change to the
WC2026 OWED estimate, so it is a **human-checkpoint unit**: build it, regenerate the ledger, report the
before/after, and STOP for review before it feeds the charts. (The chart-render unit — demoted below —
runs only AFTER this lands, because `est_min` will change.)

### Why we're reopening the WC2026 OWED calc (findings from the 2026-07-15/16 investigation)

The require-a-marker OWED logic in `build_wc2026_inputs.py:compute_owed` (loop `:223-261`) walks each
pre-segmented dead gap from `Stoppage_Candidates` through an 8-step first-match-wins precedence
(hydration → injury → sub → card → celebration → restart-ladder excess → keeper → **rule 8 = excluded,
credited 0**). We audited what actually lands in rule 8 (`excluded_silent_s`, ledger G4):

- **Rule 8 excluded = 37,843 s = 630.7 min = 14.9% of all dead time** (per-match ~6.6 min).
- **57.8% of that excluded mass — 21,870 s / 364.5 min — is "delay-bounded"**: a gap whose boundary
  event is an Opta **type 27 (Start delay)**, **type 28 (End delay)**, or **type 65 (Contentious
  referee decision)**. These are real, referee-caused stoppages (injury, VAR review, ball inspection,
  melee) that Opta flags as a delay but that carry NO restart qualifier and NO incident event, so
  `resolve_restart` (`:194-207`) returns `None` and they fall to rule 8. This is the single largest
  reason time is being dropped from OWED.
- Opta has **no VAR event type**; type 65 "Contentious referee decision" is the closest proxy and
  appears only 62× tournament-wide (gaps overlapping one = 74.7 min = 11.8% of excluded). So we CANNOT
  label these windows "VAR" — only "referee-caused delay of unspecified cause." But per Law 7 that time
  (injury AND VAR review) is exactly what must be added back, and today it's credited 0. **This is a
  genuine downward bias in `est_min` concentrated in matches with long stoppages.**

**Opta event-flag source of truth (use this; if incomplete, corroborate with official Stats Perform /
Opta docs or other credible soccer-analytics references):**
`https://raw.githubusercontent.com/eddwebster/football_analytics/master/data/opta/reference/opta_event_types.csv`
Confirmed from it: **27 = Start delay** ("stoppage in play such as a player injury"), **28 = End delay**
("stoppage ends and play resumes"), **30 = End** (period end), **43 = Deleted event**, **65 =
Contentious referee decision**. ("Administrative" family in this workbook = types 43/40/37/34 — Opta
data-maintenance records, not football stoppages.)

### The worked example that defines the required behavior — France v Senegal, P2, 57:42 → 60:58

Raw candidate gaps (all three are CONTIGUOUS — one continuous dead window, no football between them):

| # | window | D | family | start evt | end evt | today |
|---|---|---|---|---|---|---|
| 1 | 57:42→59:28 | 106 s | Ball out of play | `Out` (5) | `Type 27` Start delay | rule 8 → **0** |
| 2 | 59:28→60:44 |  76 s | Other/unclassified | `Type 65` Contentious | `Type 28` End delay | rule 8 → **0** |
| 3 | 60:44→60:57 |  13 s | Other/unclassified | `Type 28` End delay | `Deleted event` (43) | rule 8 → **0** |

The ball goes out at 57:42; a ~3-minute delay (idx 268–270 = Start delay → Contentious decision → End
delay: the textbook VAR-review signature) runs until 60:44; football resumes with a pass at 60:59.
**Today all 195 s is credited 0. The required behavior: the ENTIRE contiguous dead window 57:42→60:58
is OWED stoppage and must be credited in full** — not just the single gap that touches the delay flag.

### The task

1. **Credit every Opta delay as genuine stoppage.** Any dead gap flagged as a delay (a `27`/`28`
   boundary — and decide, reasoning from the data + Law 7, whether a lone `65` contentious event with
   no 27/28 also qualifies) is addable stoppage credited in FULL (the whole gap D, no allowance
   subtracted — a delay is not a routine restart).
2. **Credit the ENTIRE contiguous dead window that CONTAINS a delay, not just the flagged gap.** The
   `Stoppage_Candidates` sheet over-segments a single stoppage into several gaps at each logged
   non-football event (the France window = 3 gaps). Design a window-stitching step: merge temporally
   contiguous candidate gaps (gap_i.end ≈ gap_{i+1}.start, no live football between) into one dead
   window; if ANY constituent gap is a delay, the whole window's summed D is OWED. Watch the
   interactions: (a) don't double-count a window that ALSO contains a hydration/celebration/injury/etc.
   already credited by steps 1–5 — decide the precedence between "delay-window-full-credit" and the
   existing per-gap credits, and cap OWED ≤ window D (never credit a second past the wall-clock dead);
   (b) keep gate G2 (OWED ≤ total dead per match) intact; (c) the France window has a `65` at its
   interior, so interior flags — not just boundary flags — must trigger the merge.
3. **Revisit whether the steps 1–7 precedence is even the right frame now.** This is the deeper ask:
   given what we now understand about the Opta feed (explicit delay markers, wall-clock gaps,
   over-segmentation), reason from first principles about whether the require-a-marker ladder is the
   best OWED methodology, or whether a window-first model (segment the half into maximal dead windows,
   then classify each window's ADDABLE share) is cleaner and less leaky. Explore expert alternatives;
   surface the trade-offs; recommend. Do NOT silently rewrite the whole thing — bring the recommended
   redesign to the human checkpoint with evidence.

### Guardrails, deliverables, gates

- **Scope lock:** only `src/sky_wc2026/*` + `data/processed/sky_wc2026/*`. `params.yaml` read-only
  (the Nate allowance ladder + caps stay frozen). Do not touch the locked StatsBomb model, its parquet,
  tournaments.yaml, or any ADR. Nothing here changes the six-tournament headline (ADR-0035: 24.4%/12.9%).
- **Quantify the move.** Report before/after mean OWED, mean (OWED−PLAYED), % OWED>PLAYED, the
  excluded-baseline share of dead (should drop sharply from 14.9%), and the France v Senegal window as
  a worked check (expect its ~195 s to flip from 0 to fully credited). Order-of-magnitude prior:
  crediting delay windows adds ≈365 min across 96 matches (~3.8 min/match) — a MATERIAL move, hence the
  checkpoint.
- **Gates:** keep G1 (PLAYED vs Sheet1 ≤30 s non-ET), G2 (OWED ≤ total dead, per match — now the binding
  constraint), G3 (hydration ≤1/half), and the ΣD X-check. Add a new ledger section breaking OWED delay
  credit out as its own component + the residual (post-fix) excluded baseline by family.
- **Checkpoint & write-up:** regenerate `data/processed/sky_wc2026/{agg01,agg02,ledger.md}`, write a new
  ADR (ADR-0037) recording the delay-crediting rule + the window-stitching design + the
  methodology-revisit recommendation, update this pointer, and run the README §7 sync pass (note "no
  change needed" if the WC2026 lane still isn't in the public narrative). Then STOP for human review.

---

## DONE (2026-07-16, ADR-0037 lane) — RENDERED the two WC2026 charts from the built inputs

Render-only (no table rebuild). New `src/sky_wc2026/render_wc2026_charts.py` reads the two ADR-0037
tables and feeds them to the existing publication builders in `src/figures_requested.py`
(`_scatter_estimate_pub`, `_bar_buckets_pub`), overriding every StatsBomb-specific text element with
the WC2026 numbers. To keep the six-tournament StatsBomb charts byte-identical, the two builders (+
`_save`/`_save_hpad`) gained optional `title`/`subtitle`/`source`/`out_dir` kwargs that DEFAULT to
their prior hardcoded StatsBomb text — the StatsBomb `main()` calls are unchanged. Outputs written to
a NEW dir `figures/sky_wc2026/`:
- `agg_01_scatter_estimate_vs_played_wide.png` — est (OWED) vs played, all 96 dots (periods 1–4).
  Title "under-awarded in **100%** of matches"; typical (median) ~12 played / ~19 owed; footer means
  owed **19.6** / played **12.7** / nearly **7** missing; **Source: Opta**.
- `agg_02_productivity_by_bucket_bordered.png` — goals/live-min by stage, regulation P1+P2. 2H-added
  0.081 vs regular-play avg 0.046 (1.76× — "nearly twice"); 1H-added 0.027; **Source: Opta**.
NOTE (design inherited from the StatsBomb chart, data-faithful for WC2026): the 1H-added bar (0.027)
sits BELOW the regular-play average — the "increases dramatically" story is carried by 2H added time,
which the annotation targets. Flag if you want the title/1H-bar treatment reconsidered for WC2026.
**README: no change needed** (WC2026 lane still not in the public narrative). Workbook still git-ignored.

### Original spec (for provenance)
Rendering only — feed the two tables to the existing figure builders, eyeball the PNGs, STOP:
- `data/processed/sky_wc2026/agg01_estimate_vs_played.parquet` → `src/figures_requested.py:_scatter_estimate_pub`
  (needs `est_min` [y=OWED] + `played_min` [x=PLAYED]; both present, plus `played_reg_min` if you want
  the regulation-comparable variant that drops the 6 ET knockouts).
- `data/processed/sky_wc2026/agg02_productivity_by_bucket.parquet` → `_bar_buckets_pub`
  (needs `bucket`/`goals`/`live_min`/`rate`; 12 buckets in the repo `BUCKET_ORDER`).
Do NOT re-run the loader or touch the locked StatsBomb pipeline. The workbook is git-ignored — do not
commit it. Read `data/processed/sky_wc2026/ledger.md` first for the QA context.

## DONE (2026-07-15, ADR-0036) — WC2026 (Sky/Opta) chart-input lane: two data tables built, NO model change

Self-contained WC2026 lane, DATA INPUTS ONLY (charts next session). Built `src/sky_wc2026/build_wc2026_inputs.py`
off the Sky-supplied Opta F24 workbook (`data/DONOTSHAREWorldCup_Stoppages.xlsx`, 68 MB — **DO NOT
commit/share**, now git-ignored via `data/DONOTSHARE*.xlsx`). Wrote `agg01_estimate_vs_played` (96
matches: OWED `est_min` vs PLAYED `played_min`) + `agg02_productivity_by_bucket` (12 buckets, goals/
live-min + Poisson CI) to `data/processed/sky_wc2026/` (+ `ledger.md`). Methodology (user-decided, in
ADR-0036): require-a-marker for OWED, NO residual constant (StatsBomb-specific), no StatsBomb parity
check (methodology trusted; ledger is eyeball-only), ignore the 4th-official board (x = PLAYED),
hydration full ≤1/half, celebration FULL (POST-directive), agg_01 includes ET (periods 1–4, shootout
excluded) while agg_02 stays regulation P1+P2. QA: mean OWED 14.85 / PLAYED 12.69 min, 82.3% OWED>PLAYED,
excluded silent baseline 14.9% of dead; gates G1–G4 + X-check PASS; 2H-stop rate 0.0814. **Nothing in
the locked StatsBomb model, config, parquet, or prior ADR touched; pytest 26/26 green. README: no change
needed** (no WC2026 lane references in the public narrative yet — charts + narrative land next session).

**Deferred (out of canonical scope — user's call).** `docs/substack_post_v1..v3.md`, every `*.html`
render, and the `docs/model_review*` exhibits still carry the pre-ADR-0035 numbers (24.8% / 13.0%,
pools 115 / 199). Left untouched deliberately — the live piece tracks `docs/substack_post_v4.md` and
its changelog `docs/substack_v4_changes_adr0035.md`. Refresh the older drafts only if asked.

---

## DONE (2026-07-09, ADR-0035) — RECLASSIFIED EURO 2024 POST → PRE across the whole project

**What & why.** UEFA declined to implement the 2022 Collina/FIFA stoppage directive at Euro 2024, so
coding it `group: POST` mislabelled the treatment. Moved Euro 2024 (51 matches) POST → PRE everywhere,
re-ran the model, and re-locked under **ADR-0035**. Pools **PRE 115 → 166 / POST 199 → 148** (total 314
unchanged). Celebration crediting is era-conditional (ADR-0030), so the flip applies excess-only crediting
to Euro 2024 → lowers its `true_stoppage`; the whole move is PRE-driven and POST `true_stoppage` is
byte-identical.

**OLD → NEW (ADR-0031 → ADR-0035):**
- Scoreline X%: **24.8% [21.7, 28.6] → 24.4% [21.1, 28.3]** (−0.4 pp; 1H+2H, central
  `silent_marked|overall|pooled_all|hl=4.0|on`).
- Different-result flip: **13.0% [11.3, 15.1] → 12.9% [11.2, 15.0]**.
- Lead band **21.4–27.3 → 21.1–26.7**; joint envelope **18.9–28.6 → 18.1–28.2**; 2H-only central
  **17.0 → 16.8** (its lead band 15.4–18.5 → **14.4–18.3**); sampling CI width **6.9 → 7.2**.
- Decay rails **23.3 / 24.8 / 26.1 → 23.0 / 24.4 / 25.7**; natural-experiment PRE/POST
  **0.086 (24/279) / 0.080 (49/615) → 0.089 (37/415) / 0.075 (36/479)**; owed **17.6 → 17.4**,
  omitted **8.8 → 8.7**.

**Scope (user instruction: canonical only + minimal v4 diff).** Model + gates: config,
`tests/test_lib.py` (166/148), `tests/test_pipeline.py` decay endpoints (0.238 / 0.173 / 0.098),
s01 + s05–s09 regenerated, `data/processed/*.parquet` + `figures/*` refreshed. Docs: `docs/decisions.md`
(ADR-0035), `docs/numbers_ledger.md`, `CLAUDE.md §1/§2/§4`, `README.md` (full §7 sync), `docs/Methodology.md`,
`docs/limitations_additions.md`. `docs/substack_post_v4.md` got **minimal number-only edits**; the exact
before→after map is the NEW **`docs/substack_v4_changes_adr0035.md`** (paste-guide for the live Substack).
pytest **26 passed**.

**Three flags left for the user** (detailed in the changelog): (A) v4 line-92 "barely moved" wording is
now a stretch — 0.089 vs 0.075 is ≈16% apart, twice the old ~7% — recommend softening; (B) v4 line-128
"roughly 19 → roughly 21" (removing low-owed Euro 2024 RAISES POST mean owed to ≈21.3 — counter-intuitive
but correct); (C) v4 line-9 "96% / 8 min" left UNCHANGED — a pre-existing discrepancy (fresh recompute
≈98% / ~9 min), user to verify against the original figure-11 source before publishing.

**Editorial prose changed beyond pure numbers** (README + Methodology, so you're aware): natural-experiment
sentence reworked ("barely moved" → "moved only modestly"; dropped the now-false "more than twice the live
minutes" — POST live-min 479 is only 1.15× PRE 415); honest-limitation line reframed from "the headline
mostly lives POST" → "the lone calibration tournament (WC2018) is PRE while the headline pools all six
across the directive"; the 97% vs 96% frac-omitted split harmonized down to **96%** (conservative floor).

---

## DONE (2026-07-01, ADR-0034) — Team-quality / Elo test for the outcome-flip — LOCK UNCHANGED

Settled the reviewer objection that team quality should push `p_trail` below 0.5 and shrink the 13.0%
flip. Ran both analyses (standalone `src/team_quality_flip.py`, ANALYSIS ONLY — no parquet/grid/figure/
params touched; faithfulness gate reproduced locked flip `0.12976`). **(A)** only **39%** of the flip is
`p_trail`-sensitive (tied 7.86 pp immune + lead_by_1 5.12 pp sensitive); tied floor = 32% of the 24.8%
scoreline; `flip/scoreline = 0.524` is a state-census identity. **(B)** sourced pre-match World Football
Elo (eloratings.net) for all 314 (score-integrity checked); lead_by_1 mean `Δ = −38` Elo (leader
stronger 60% — modest); logit β_Δ = **+0.33/100 Elo (p<0.001)** — quality significant in the crossover
DIRECTION, crossover `Δ* ≈ −146`; `corr(Δ,μ) ≈ 0` and μ-weighting nudges `p_trail` UP; re-weighted flip
**12.9%–13.4%** (max move **0.38 pp** < 0.5 pp gate). **Decision: `p_trail=0.5` / flip 13.0% UNCHANGED**,
no s08 row — Substack pre-empt. Exhibit `docs/team_quality_flip_test.md`; full record `docs/decisions.md`
**ADR-0034**. New sourcing: `src/fetch_elo.py`, `src/lib/elo.py`, `data/raw/elo/*.tsv`. README: no change
(0.548 split pre-empt already stands). Headline scoreline 24.8% untouched by construction.

## NEXT UNIT (editorial, NOT modeling) — refresh hand-authored prose/figures to 24.8%/13.0%

The editorial refresh below — re-render prose/figures still hard-coding the OLD 23.6%/12.1% — remains
queued (see the DONE + RE-LOCKED block). Do as its own session per CLAUDE.md §6.

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
