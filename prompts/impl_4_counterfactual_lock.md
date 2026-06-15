# IMPL-4 — Propagate estimator error into s08; re-run s07→s09; lock X% (HUMAN CHECKPOINT)

**Read first:** `CLAUDE.md` (§6, and §4 acceptance gates) and
`prompts/silent_component_findings.md`. Prereq: IMPL-3 done (estimator rebuilt + validated vs
Nate `expected`; residual constant frozen). This is the second human checkpoint — the headline
X% is locked here, eyes open. Do ONLY this unit.

## Task
1. Propagate the per-match estimator error (the IMPL-3 MAE, ~±2 min) into the s08 bootstrap so
   the headline CI reflects estimator uncertainty, not just sampling. The current `[2.6–2.8%]`
   band is too tight. Only close (tied / 1-goal) matches flip the outcome — prioritise estimator
   accuracy and error propagation there.
2. Re-run downstream in order: `python run.py --stage 07` → `--stage 08` → `--stage 09`.

## Gate (CLAUDE.md §4)
- **s07:** every productivity cell reports `n_events` AND `live_minutes` alongside the rate.
- **s08:** the full sensitivity grid is produced — **READ it before locking X%** (do not commit
  to a single number until you have seen the grid).
- **s09:** deterministic figures + numbers ledger; every figure traces to a script + a
  checkpointed table + a documented assumption.

## Lock, then STOP
- With the user, lock the headline **X% + confidence interval + sensitivity band** in
  `docs/decisions.md`, eyes open. This is the one modeled claim — it ships with the CI and the
  sensitivity table, never as a bare point estimate.
- ADR in `docs/decisions.md`; update `next_session.md` (silent-component work complete).
- End the session.
