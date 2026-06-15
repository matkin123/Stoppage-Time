#!/usr/bin/env python3
"""Stoppage Time pipeline runner.

Usage:
    python run.py --stage 1            # run s01
    python run.py --stage 3            # run s03
    python run.py --stage 6a           # run s06a
    python run.py --all                # run s01..s09 in build order
    python run.py --list               # list stages

Each stage is idempotent: it reads the prior stage's parquet and writes its own.
Re-running is safe and cheap. The processed parquet tables + docs/decisions.md
are the source of truth -- not chat history, not notebooks.
"""
from __future__ import annotations

import argparse
import importlib
import sys
import time

# Build order from the spec (section 6). Human checkpoints: after s03 (calibration)
# and after s08 (sensitivity grid).
STAGES = [
    ("01", "s01_ingest", "Ingest StatsBomb match + event JSON -> parquet"),
    ("02", "s02_normalize", "Normalize events with cumulative match clock"),
    ("03", "s03_bip", "Ball-in-play reconstruction (CALIBRATION GATE)"),
    ("04", "s04_goals_state", "Goals, stoppage flags, match state at 45/90"),
    ("05", "s05_incident", "Incident-stoppage lower bound"),
    ("06a", "s06a_board", "Board added time (external source)"),
    ("06b", "s06b_var", "VAR review log (external + fallback)"),
    ("07", "s07_productivity", "Productivity & descriptive tables"),
    ("08", "s08_counterfactual", "Counterfactual Monte Carlo (HEADLINE)"),
    ("09", "s09_figures", "Figures & numbers ledger"),
]
STAGE_BY_ID = {sid: (mod, desc) for sid, mod, desc in STAGES}


def run_stage(stage_id: str) -> None:
    if stage_id not in STAGE_BY_ID:
        sys.exit(f"Unknown stage '{stage_id}'. Known: {', '.join(STAGE_BY_ID)}")
    mod_name, desc = STAGE_BY_ID[stage_id]
    print(f"\n=== s{stage_id}  {desc} ===")
    t0 = time.time()
    mod = importlib.import_module(f"src.{mod_name}")
    if not hasattr(mod, "main"):
        sys.exit(f"src.{mod_name} has no main() entrypoint")
    mod.main()
    print(f"--- s{stage_id} done in {time.time() - t0:.1f}s ---")


def main() -> None:
    p = argparse.ArgumentParser(description="Stoppage Time pipeline runner")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--stage", help="stage id, e.g. 1, 03, 6a")
    g.add_argument("--all", action="store_true", help="run all stages in build order")
    g.add_argument("--list", action="store_true", help="list stages and exit")
    args = p.parse_args()

    if args.list:
        for sid, _, desc in STAGES:
            print(f"  s{sid:<3} {desc}")
        return

    if args.all:
        for sid, _, _ in STAGES:
            run_stage(sid)
        return

    # normalize "1" -> "01"
    sid = args.stage.lower().strip()
    if sid.isdigit() and len(sid) == 1:
        sid = "0" + sid
    run_stage(sid)


if __name__ == "__main__":
    main()
