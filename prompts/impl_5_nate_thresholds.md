# IMPL-5 — Make the s05 true-stoppage estimator more precise (Nate's restart thresholds + marker refinements). HUMAN CHECKPOINT.

**Read first:** `CLAUDE.md` (§6 — one self-contained unit, then STOP), the IMPL-3 section of
`next_session.md` + `ADR-0016`, and the "Why we are here" block below. This is a human
checkpoint: bring the validation table to the user before re-running IMPL-4. Do ONLY this unit.

## Why we are here (the IMPL-4 finding that triggered this)
IMPL-4 wired the silent-treatment knob into s08 and ran the grid. The headline is **NOT robust
to the silent assumption** — X% (% of matches that would end differently) roughly triples across
the knob:

| silent knob | X% range (across lambda conditioning × source) |
|-------------|--------------------------------------------------|
| `silent_none`   | 2.9 – 4.0%  |
| `silent_marked` | 7.4 – 9.9%  (IMPL-3 central) |
| `silent_all`    | 9.6 – 12.7% |

A headline that swings 3%→12% on one assumption cannot be locked. So we go back and make the
**per-match** estimator more precise before locking X%. **IMPL-4's code is complete and tested
(23 green), but X% is deliberately UNLOCKED.** After this unit lands, re-run IMPL-4 (s08→s09) in
a *separate* session to see if the grid tightened / the central moved.

## Scope (unchanged guardrails — do not relitigate)
- **s05 only.** `src/lib/bip.py` and s03 stay FROZEN (ADR-0014/0015 — the validated TOTAL-dead-
  time duration rule; BIP r=0.943, do NOT re-tune to chase this). This unit changes only the
  ADDABLE-stoppage estimator: `src/s05_incident.py`, possibly `src/lib/silent.py`, and constants
  in `config/params.yaml`.
- Validate against Nate's **`expected`** column (32 WC2018) via
  `src/lib/nate.report(pred, "expected", label)`. Do NOT cross columns (bip→s03 BIP,
  expected→this estimator, actual→board). Nate is WC2018-only; POST is validated indirectly via
  the frozen-on-2018 constants + the s03 WC2022 Opta BIP gate.
- Any new constant is FIT ON 2018 and FROZEN, then applied to all six tournaments.

## What is credited TODAY (so the gap is visible)
The s03 gap method splits each match-period's dead time into disjoint dead segments. The current
estimator (`true_stoppage = lower_bound + marker-gated silent + residual`, ADR-0016) credits:
1. **lower_bound** — union of celebration/sub/card/injury incident windows, each ∩ s03 dead
   segments (`src/s05_incident.py`, `comp = {...}`). Small, stable, validated — keep as-is.
2. **marker-gated silent** — NON-restart gaps ≥20s whose lead edge carries an out-of-play marker
   (`silent.marked_silent_intervals`). `silent.py:74` EXCLUDES restart-boundary gaps by design.
3. **residual constant** — `silent.residual_silent_s = 114.0` (1.9 min), frozen on 2018 to pull
   the marked-central mean to Nate's 13.16.

**The gap this unit attacks:** routine **restart** time-wasting — a throw-in dragged to 50s, a
goal kick to 40s, with NO foul/sub/injury — is credited **zero in every knob today**: `silent.py`
skips restart gaps, and `lower_bound` only catches them where they happen to overlap a foul/sub
window. Nate counts the excess over a normal restart. That is signal we currently throw away.

## Task A — Nate's per-restart time-wasting thresholds (the primary ask)

Nate's "how long routine events should take" table (verbatim) and the StatsBomb `play_pattern`
each maps to:

| Nate event        | normal (s) | StatsBomb signal                          | use in A? |
|-------------------|-----------:|-------------------------------------------|-----------|
| Throw-ins         | 20 | `play_pattern == "From Throw In"`                 | YES |
| Goal kicks        | 30 | `play_pattern == "From Goal Kick"`                | YES |
| Corner kicks      | 45 | `play_pattern == "From Corner"`                   | YES |
| Free kick         | 60 | `play_pattern == "From Free Kick"`                | YES |
| Warnings          | 30 | a `card` shown (Foul Committed / Bad Behaviour)   | optional* |
| Penalty kick      | 60 | Shot sub-type Penalty / penalty award             | optional* |
| Altercations      | 30 | `type == "Bad Behaviour"`                         | optional* |
| Arguing w/ referee| 30 | (no clean StatsBomb signal)                        | skip |

`From Kick Off` (post-goal) is already credited by the celebration component — EXCLUDE it here to
avoid double-counting. `From Keeper` has no Nate category (keeper distribution is largely live) —
EXCLUDE. \*Optional rows overlap the existing `card`/`celebration` lower_bound components — do
NOT add them naively (double-count). Attempt them ONLY as an ablation after the 4 core restarts,
and only if they beat the bar; the core deliverable is the 4 clean restart types.

**Crediting rule (excess only):** for each routine restart, credit `max(0, gap − normal)` where
`gap` = (restart event clock − prior possession's last event clock). The credited portion is the
*tail* of the dead gap beyond the allowance: interval `[last + normal, restart]`.

**Integration — fold into the existing union, do NOT sum a new column blindly:** add a
`restart_excess` member to `comp` and let the existing union-then-intersect machinery dedupe it
against the incident windows. This (a) prevents double-counting a foul→free-kick that the `card`
window already covers, and (b) keeps the gate `lower_bound_s ≤ total dead` true by construction
(every excess interval ⊂ its dead gap ⊂ s03 dead). Mirror `silent.py`'s restart-boundary test:

```python
ALLOWANCE = {"From Throw In": 20.0, "From Goal Kick": 30.0,
             "From Corner": 45.0, "From Free Kick": 60.0}
# ... inside the per-period loop, alongside the celebration/sub/card/injury passes:
for i in range(len(clocks) - 1):
    if poss[i + 1] != poss[i] and patterns[i + 1] in ALLOWANCE:
        gap = float(clocks[i + 1]) - float(clocks[i])
        allow = ALLOWANCE[patterns[i + 1]]
        if gap > allow:
            comp["restart_excess"].append((float(clocks[i]) + allow, float(clocks[i + 1])))
```
Then `restart_excess` flows through `all_intervals → _intersect_total(..., dead)` like the other
components. Because it is *identifiable* (restart-tagged), not silent, it belongs in
`lower_bound_s` — which also raises the `silent_none` floor in s08 (the hard lower bound becomes
less extreme). Put the allowances in `params.yaml:incident` (new `restart_normal_s` block) so the
change is an ADR'd parameter, not a magic number.

**Re-fit the residual after adding restart-excess.** Adding credit raises the estimator mean, so
re-fit `silent.residual_silent_s` on 2018 to hold the marked-central mean ≈ Nate's 13.16
(`residual = mean(Nate expected) − mean(lower_bound + marked_silent)` over the 32 matches, as in
ADR-0016). Freeze the new value. Update `silent.estimator_mae_min` to the NEW MAE (IMPL-4's 2H
sigma reads it).

## Task B — marker refinements (the lever for the silent BAND; do if A alone doesn't beat the bar)
Restart-excess improves per-match accuracy and raises the floor, but it does **not** narrow the
`silent_none`→`silent_all` envelope — that width is `all_silent` (the non-restart silent bucket),
which only better SILENT classification can shrink. Two cheap refinements to `src/lib/silent.py`,
each an ablation validated vs Nate:
1. **Lead-WINDOW marker test** (currently single-event `marker[i]`): StatsBomb sometimes logs the
   out-of-play marker a touch before/after the true gap edge. Test whether ANY of the last K
   events (K≈2–3) before the gap carries a marker. Could lift the ~25% marked coverage → tighten
   `silent_marked` toward `silent_all` and improve r. Guard against over-crediting (re-check the
   Germany–Sweden / low-injury matches don't re-inflate).
2. **Trail-edge / resume gating** (precision): additionally require the FIRST event after the gap
   to be a restart `play_pattern` (the ball demonstrably came back via a restart). Tightens — may
   drop false positives. Test r/MAE both ways.

Keep whichever ablation(s) beat the bar; drop the rest. Do not ship a refinement that doesn't
measurably help — "more defensible but flat r" is a judgment call to bring to the user, not an
automatic keep.

## Validate vs Nate (numbers to bring to the user)
- **Per-match Pearson r + MAE (min) vs `expected`.** Current best is **r=0.768, MAE 2.75**
  (ADR-0016). **The bar is to BEAT that** (higher r and/or lower MAE) — or report honestly that
  restart-excess is absorbed by the residual re-fit (the "small and stable" hypothesis confirmed)
  and r is flat. ~0.77 was the silent-coverage ceiling; restart-excess attacks a *different* axis
  (restart excess is not capped by silent-marker coverage), so a real lift is plausible.
- **Aggregate:** 32-match mean stays ≈13 min (held by the residual re-fit).
- **Diagnostic (auto-printed by `nate.report`):** error must still SHRINK on the low-injury three
  (Germany–Sweden, Russia–Egypt, Uruguay–Saudi) WITHOUT breaking the injury-dominated two
  (Belgium–Panama, Tunisia–England).
- **Ablation table** (each piece traceable, CLAUDE.md standard of proof):
  lower_bound → +restart_excess → +marked_silent → +residual, and each Task-B variant.

## Honest expectations (state these to the user; do not overclaim)
- Restart-excess → better per-match r/MAE + a higher `silent_none` floor; credits routine
  time-wasting we currently miss. It does **not** by itself narrow the none↔all sensitivity band.
- Marker refinements (Task B) → the lever that can narrow the silent band (shrink `all_silent` vs
  `marked`). If the band stays wide after both, the honest conclusion is that the silent
  uncertainty is irreducible with free StatsBomb data and X% must ship as a band — which is a
  legitimate, publishable finding, not a failure.

## Gate, checkpoint, STOP
- **Gate:** `s05` green — `lower_bound_s ≤ total dead` for every match still holds (it must, by
  construction); `pytest` still green (tests read params, so re-fit constants don't break them —
  verify `test_s05_true_stoppage_estimator` / `test_s05_silent_marked_within_all`); r/MAE table
  produced and compared to 0.768/2.75.
- **Checkpoint:** write **ADR-0017** in `docs/decisions.md` with the full ablation/diagnostic
  table and the re-fit constants (`restart_normal_s`, new `residual_silent_s`, new
  `estimator_mae_min`); freeze them in `params.yaml`. Update `next_session.md`: mark IMPL-5 DONE,
  point to **re-running IMPL-4** (`prompts/impl_4_counterfactual_lock.md`) as the next unit.
- **Bring the r/MAE/diagnostic/ablation table to the user.** Do NOT touch s07/s08/s09 this
  session — re-running IMPL-4 is the NEXT session (CLAUDE.md §6: one unit, then stop).
