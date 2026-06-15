# TRANSFER — session handoff

## Where you are
Repo scaffolded and the full pipeline (s01–s09) is implemented. **Nothing has been run
yet** — no parquet exists under `data/`. Code is written but UNVERIFIED against real data
(see "Known risks").

## What's built
- Contract + docs: CLAUDE.md, docs/{decisions,data_dictionary,numbers_ledger placeholder}.
- Config: config/tournaments.yaml (six tournaments, IDs verified 2026-06-15, checksums
  115/199/314), config/params.yaml (BIP threshold, phase cutoffs, MC knobs/seed).
- Libs: src/lib/{config,clock,bip,stats}.py.
- Stages: src/s01..s09 with acceptance gates baked in; run.py + Makefile drive them.
- Tests: tests/test_lib.py (pure unit, run now), tests/test_pipeline.py (gates, skip until
  outputs exist).

## Immediate next steps
1. **Fix the environment.** Base anaconda has NumPy 2.4.4 vs pandas/pyarrow built for
   NumPy 1.x → the data stack is broken. Create the pinned venv:
   `make setup` (creates `.venv` from requirements.txt, NumPy held <2), then
   `source .venv/bin/activate`.
2. `python -m pytest tests/test_lib.py -q` — should be green (no data needed).
3. `python run.py --stage 1` then `--stage 2` then `--stage 3`.
4. **STOP at s03.** Confirm the WC2022 calibration number yourself. If the gate fails,
   tune `params.yaml:bip.min_dead_gap_s` and re-run s03. Record the final value in ADR-0003.
5. Continue s04 → s05 → s07 (eyeball PRE/POST gap) → s06a (needs board CSV) → s06b →
   finalize s07 → s08 (read the sensitivity grid) → s09.

## Known risks (untested code)
- Disk: ~2.7 GB free at setup. s02 streams events in-memory (no large disk writes), but
  watch `df -h` during the venv install.
- StatsBomb open data may have fewer matches than the official tournament totals for some
  competitions; if s01's gate fails, confirm whether the data is incomplete before editing
  checksums.
- s06a requires a hand-curated `data/raw/board/board_added_time.csv` (board numbers are not
  in StatsBomb). s08 depends on it.
- The s03 gap method and s04/s05 nested-field parsing are the most likely places for
  real-data surprises (StatsBomb populates Injury Stoppage / Referee Ball-Drop / cards
  inconsistently). Inspect the first WC2022 match end-to-end before trusting pooled numbers.
