# Stoppage Time

Quant investigation of football stoppage time. Headline target:
**"Stoppage time is a sham; measured properly, X% of matches would end differently."**

Standard of proof: every number traces to a script + a checkpointed parquet table + a
documented assumption. The counterfactual `X%` is the only modeled claim and ships with a
confidence interval and a sensitivity grid. See `CLAUDE.md` for the full contract.

## Quick start
```bash
make setup                 # create .venv with pinned deps (NumPy held <2 on purpose)
source .venv/bin/activate
python -m pytest tests/test_lib.py -q   # unit tests, no data needed
python run.py --stage 1    # ingest match lists
python run.py --stage 2    # normalize events (streams JSON in-memory; ~few hundred MB)
python run.py --stage 3    # ball-in-play  <-- STOP and confirm the calibration gate
# ... s04, s05, s07, s06a (needs board CSV), s06b, s07, s08, s09
python run.py --list       # show all stages
make all                   # run the whole pipeline in build order
make test                  # all acceptance gates
```

## Pipeline (stage → output)
| stage | output | gate |
|---|---|---|
| s01 ingest | matches.parquet | match counts == checksums (115/199) |
| s02 normalize | events_norm.parquet | clock_s monotonic; sane period lengths |
| s03 ball-in-play | bip_segments, match_minutes | **WC2022 BIP within ±90s of Opta 58:04** |
| s04 goals/state | goals, match_state | after-90 share ~12–13%; finals match |
| s05 incident | incident_stoppage | lower_bound ≤ total dead time |
| s06a board | board_added_time | PRE ~7 min, POST WC2022 ~11–12 min |
| s06b VAR | (var_s filled) | var_s ≥ 0 (fallback estimator) |
| s07 productivity | productivity, stoppage_live_share | every cell has n + live_minutes |
| s08 counterfactual | counterfactual(+summary) | sensitivity grid produced |
| s09 figures | figures/*.png, numbers_ledger.md | deterministic |

## Layout
`config/` locked dataset + tunable params · `src/lib/` shared code · `src/s0*.py` stages ·
`data/{raw,interim,processed}` (gitignored) · `docs/` decisions, data dictionary, ledger,
transfer note · `tests/` acceptance gates.

## Data sources
StatsBomb open data (match + event JSON only — no 360, never cloned) for all six
tournaments. Board added time is the one external input: hand-curate
`data/raw/board/board_added_time.csv` (Sofascore → ESPN → FIFA priority).
