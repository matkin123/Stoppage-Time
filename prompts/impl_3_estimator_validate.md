# IMPL-3 — Rebuild true-stoppage estimator + validate vs Nate (HUMAN CHECKPOINT)

**Read first:** `CLAUDE.md` (§6) and `prompts/silent_component_findings.md`. Prereq: IMPL-2 done
(marker-gated classifier is live in `bip.py`, s03 re-validated). This is a human checkpoint —
bring the validation table to the user before proceeding. Do ONLY this unit; STOP at the gate.

## Task
1. Rebuild the true-stoppage estimator (s05 / the corrected-excess method) as
   `restart-excess + marker-gated-silent + calibrated-residual + explicit injury/sub/goal credit`.
   - Keep restart-excess as-is (small and stable — do NOT re-derive it).
   - The silent term now comes from the IMPL-2 marker-gated classifier (shared with BIP).
   - Keep the explicit injury/sub/goal credit.
2. Fit ONE **residual-silent constant** on 2018 (the irreducible unobserved dead time left after
   marker-gating). Freeze it in `config/params.yaml`; apply the SAME constant to all six
   tournaments (POST has no ground truth to fit on).

## Validate against Nate (the numbers to report to the user)
Use the in-repo harness — the estimator validates against Nate's **`expected`** column (the
should-be-added model, ~13.2 min mean). NOT `actual` (that is the board target, already done).
```
from src.lib import nate
pred = { ... }              # {match_id: estimator minutes} for the 32 WC2018 matches
nate.report(pred, "expected", "estimator")     # prints r, MAE, and the low/high diagnostic
```
**Gate:**
- **Per-match:** Pearson r + MAE (min) vs `expected`. Beat current r≈0.73–0.77 (target ≳0.85),
  MAE down.
- **Aggregate:** 32-match mean estimator vs Nate's `expected` mean — stays ≈13 min level.
- **Diagnostic:** error SHRINKS on the three low-injury matches (Germany–Sweden, Russia–Egypt,
  Uruguay–Saudi) WITHOUT breaking the two injury-dominated ones (Belgium–Panama, Tunisia–England).
  `nate.report` prints these automatically (LOW must shrink / HIGH must hold).
- **Ablation table:** r/MAE for (A) marker-gated alone → (A)+(B) keeper-held → +residual-constant,
  so each piece is traceable (CLAUDE.md standard of proof).
- **Coverage flag:** state plainly — Nate validates WC2018 ONLY; POST is validated indirectly via
  the frozen 2018 calibration + the s03 WC2022 Opta BIP gate.

## Checkpoint, then STOP
- ADR in `docs/decisions.md` with the full validation table; freeze the residual constant in
  `params.yaml`.
- Update `next_session.md`: mark IMPL-3 DONE, point to IMPL-4 (`prompts/impl_4_counterfactual_lock.md`).
- **Bring the r/MAE/diagnostic/ablation table to the user before IMPL-4.** End the session.
