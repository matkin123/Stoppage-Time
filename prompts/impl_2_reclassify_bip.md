# IMPL-2 — Marker-gated silent reclassification → promote into bip.py (the one classifier)

**Read first:** `CLAUDE.md` (§6 — one unit, then stop) and `prompts/silent_component_findings.md`
(esp. the "Design decision: one ball-state classifier, in bip.py" section). Prereq: IMPL-1 done
(the `out`/`pass_outcome`/`gk_type`/`gk_outcome` columns are on `events_norm.parquet`). Do ONLY
this unit; validate; checkpoint; STOP.

## Decision already made (do not re-open)
We are improving the live/dead methodology, so it changes EVERYWHERE: the marker-gating becomes
THE classifier in `src/lib/bip.py`, feeding both BIP and the estimator. This is NOT collapsing
BIP and stoppage into one number — true stoppage stays `dead − restart-excess + injury/sub/goal
credit` in s05, on top of the shared classifier.

## Task
1. Build the reclassifier (suggest `src/lib/silent.py`): for each candidate silent gap (no
   restart `play_pattern` at the trail edge, gap ≥ `silent.min_silent_gap_s`), classify **dead**
   iff its LEAD edge carries an out-of-play marker — any of: `out=True`;
   `pass_outcome ∈ {"Out","Injury Clearance"}`; a shot leaving the field
   (`shot_outcome ∈ {"Off T","Saved Off T","Wayward","Blocked","Goal"}`); `type ∈
   {"Foul Committed","Offside","Bad Behaviour","Substitution","Player Off","Injury Stoppage",
   "Referee Ball-Drop","Half End"}` — **else live**.
2. Special-case (B): `gk_type ∈ {"Collected","Smother","Pick-up"}` with NO subsequent `out`
   before the next touch ⇒ keeper holding a LIVE ball ⇒ gap is live (do not credit).
3. Put the marker set + threshold in `config/params.yaml` (e.g. `silent.min_silent_gap_s`,
   `silent.out_of_play_types`) — deterministic, pinned, documented.
4. **Promote into `bip.py`:** replace the `gap >= max_live_gap_s` rule (`bip.py:60`) with the
   marker-gated classifier so BIP and the estimator share one live/dead definition. Then
   **re-tune** the s03 calibration: marker-gating moves seconds dead→live, so pooled WC2022 BIP
   rises — adjust/remove the residual gap constant until the gate passes. A first-run breach of
   the ±90s gate is EXPECTED (re-tune), not a failure.

## Gate — promotion allowed only when BOTH external gates hold after re-tuning
- **s03 BIP must re-validate, not merely survive.** Run `python run.py --stage 3` (WC2022 pooled
  regulation BIP within ±90s of 3484s; in-play share 55–60%) AND per-match BIP r vs 538 ≥ 0.94:
  `python3 -c "from src.lib import nate; print(nate.metric(nate.regulation_bip_minutes(), nate.truth_minutes('bip')))"`
  Baseline today is r=0.943, MAE 1.25 — do not regress it. If BIP cannot re-validate, STOP: the
  marker logic is suspect — bring it to the user. Do NOT fall back to an estimator-only patch.
- **Smell test before IMPL-3.** Print, per WC2018 match, OLD vs NEW marker-gated silent total;
  confirm the new totals drop MOST on the low-injury matches (Germany–Sweden, Russia–Egypt,
  Uruguay–Saudi) and BARELY move on the injury-dominated ones (Belgium–Panama, Tunisia–England).

## Checkpoint, then STOP
- ADR in `docs/decisions.md`: reclassifier logic, marker set, the re-tuned s03 constant, and the
  before/after BIP-vs-538 + Opta numbers.
- Update `next_session.md`: mark IMPL-2 DONE, point to IMPL-3 (`prompts/impl_3_estimator_validate.md`).
- End the session.
