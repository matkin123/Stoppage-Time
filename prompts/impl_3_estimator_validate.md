# IMPL-3 — Build the marker-gated true-stoppage estimator in s05 + validate vs Nate (HUMAN CHECKPOINT)

**Read first:** `CLAUDE.md` (§6), `prompts/silent_component_findings.md`, and ADR-0014 + ADR-0015
in `docs/decisions.md`. This is a human checkpoint — bring the validation table to the user
before proceeding. Do ONLY this unit; STOP at the gate.

## Scope correction (read this — it changed after IMPL-2)
IMPL-2 proved the marker-gating idea does NOT belong in `bip.py`. Marker-gating regresses the
validated BIP (r 0.943 → ≤0.92) because for the *total-dead-time* (BIP) question the unmarked
silent gaps are genuinely dead. **`src/lib/bip.py` STAYS the validated duration rule — do not
touch it.** Marker-gating is the right tool for ONE place only: the *addable-stoppage* silent term
inside s05. That is what this unit builds.

**Prereqs (already satisfied):** the marker test lives in `src/lib/silent.py` (written in IMPL-2,
kept but unwired). `interim/events_norm.parquet` already carries `out`, `pass_outcome`, `gk_type`,
`gk_outcome` (IMPL-1 / ADR-0013). The Nate harness `src/lib/nate.py` is wired and tested.

## Task
1. Build the corrected true-stoppage estimator **in s05** (do NOT change `bip.py` or s03):
   `restart/lower-bound credit + marker-gated-silent + calibrated-residual + explicit
   injury/sub/goal credit`.
   - Keep the existing `s05_incident.py` lower-bound components (celebration/sub/card/injury,
     each intersected with s03 dead segments) as-is — they are small and stable, do NOT re-derive.
   - Add a **marker-gated silent term**: of the ≥`silent.min_silent_gap_s` non-restart gaps,
     credit ONLY those whose lead edge carries an out-of-play marker (use `src/lib/silent.py`).
     Drop the *unmarked* silent gaps from the addable total — they are genuinely dead (BIP keeps
     them) but a flat, non-addable ~8.4 min/match baseline (r=0.248 vs `expected`); crediting them
     is the over-count (the Germany–Sweden 17.4-vs-8.9 signature).
2. Fit ONE **residual-silent constant** on 2018 (the irreducible unmarked-but-addable remainder
   left after marker-gating). Freeze it in `config/params.yaml`; apply the SAME constant to all six
   tournaments (POST has no ground truth to fit on).

## Validate against Nate (the numbers to report to the user)
Use the in-repo harness — the estimator validates against Nate's **`expected`** column (the
should-be-added model, ~13.2 min mean). NOT `actual` (that is the board target, already done).
```
from src.lib import nate
pred = { ... }              # {match_id: estimator minutes} for the 32 WC2018 matches
nate.report(pred, "expected", "estimator")     # prints r, MAE, and the low/high diagnostic
```

## Gate (RESET — read carefully, the old ≥0.85 target was falsified)
IMPL-2's investigation established the realistic ceiling with free StatsBomb data: StatsBomb marks
only ~25% of silent gaps and never marks "addable-ness" directly, so the marker-gated silent term
tops out around **r≈0.77**. The earlier ≳0.85 hope in the findings doc is NOT achievable and is no
longer the bar. Measured candidates from IMPL-2: `lb + marked silent` → r=0.768, MAE 3.15, mean
11.3; `marked silent + calibrated const` → r=0.708, MAE 2.22, mean 13.2.

- **Per-match:** Pearson r + MAE (min) vs `expected`. **Beat the ~0.61–0.73 baseline; target
  ~0.77.** Do not chase 0.85 — if you land ~0.77 with a clean ablation, that is success.
- **Aggregate:** 32-match mean estimator vs Nate's `expected` mean — stays ≈13 min level.
- **Diagnostic:** error SHRINKS on the three low-injury matches (Germany–Sweden, Russia–Egypt,
  Uruguay–Saudi) WITHOUT breaking the two injury-dominated ones (Belgium–Panama, Tunisia–England).
  `nate.report` prints these automatically (LOW must shrink / HIGH must hold).
- **Ablation table:** r/MAE for lower-bound alone → + marker-gated silent → + residual-constant,
  so each piece is traceable (CLAUDE.md standard of proof).
- **Coverage flag:** state plainly — Nate validates WC2018 ONLY; POST is validated indirectly via
  the frozen 2018 calibration + the s03 WC2022 Opta BIP gate.

## Checkpoint, then STOP
- ADR in `docs/decisions.md` with the full validation table; freeze the residual constant in
  `params.yaml`.
- Update `next_session.md`: mark IMPL-3 DONE, point to IMPL-4 (`prompts/impl_4_counterfactual_lock.md`).
- **Bring the r/MAE/diagnostic/ablation table to the user before IMPL-4.** End the session.
