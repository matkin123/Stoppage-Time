# IMPL-1 — Plumb out-of-play markers through s02 normalization

**Read first:** `CLAUDE.md` (esp. §6 — ONE self-contained unit per session, then stop) and
`prompts/silent_component_findings.md` (the reviewed recommendation). This is session 1 of 4
(IMPL-1→IMPL-4). Do ONLY this unit; validate its gate; checkpoint; STOP.

## Why
The "silent component" over-counts stoppage because `src/lib/bip.py:60` credits every long
event-gap as dead without checking whether the ball actually left play. StatsBomb stamps an
explicit out-of-play marker at the lead edge of every genuinely dead ball. To use those markers
(IMPL-2) they must first be carried through normalization — they currently are not.

## Task (data prep only — no behavior change yet)
In `src/s02_normalize.py` (and the shared event-normalization code it calls), project these raw
StatsBomb event fields into `interim/events_norm.parquet`, one column each:
- `out` — bool, the `out` flag on Pass / Carry / Ball Receipt* / Shot.
- `pass_outcome` — str, `pass.outcome.name` (e.g. "Out", "Injury Clearance", "Incomplete", "Offside").
- `gk_type` — str, `goalkeeper.type.name` (e.g. "Collected", "Smother", "Save", "Pick-up").
- `gk_outcome` — str, `goalkeeper.outcome.name`.
Keep all existing columns and gates intact. Do not consume the new columns anywhere yet.

## Gate (done only when green)
1. Re-run `python run.py --stage 2`; s02's existing gates pass (clock monotonic within match;
   recovered period lengths sane).
2. Re-run `python run.py --stage 3`; BIP is UNCHANGED (these columns are not yet consumed) —
   confirm the s03 calibration still passes identically.
3. New-column sanity (print + record in the ADR): `out=True` on a non-trivial fraction of
   Pass/Carry rows; `pass_outcome` includes "Out"; `gk_type` populated for goalkeeper events;
   non-null rates plausible in ALL SIX tournaments (spot-check one match each — same schema must
   mean same population). Quick check:
   `python3 -c "import pandas as pd; e=pd.read_parquet('data/interim/events_norm.parquet'); print(e[['out','pass_outcome','gk_type']].notna().mean()); print(e['pass_outcome'].value_counts().head())"`

## Checkpoint, then STOP
- Add an ADR in `docs/decisions.md`: fields carried through s02, why, the spot-check numbers.
- Update `next_session.md`: mark IMPL-1 DONE, point to IMPL-2 (`prompts/impl_2_reclassify_bip.md`).
- End the session. Do NOT start IMPL-2.
