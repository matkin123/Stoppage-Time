"""Shared paths and config loaders. Single source for directory layout + yaml params."""
from __future__ import annotations

import functools
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
DATA = ROOT / "data"
RAW = DATA / "raw"
RAW_SB = RAW / "statsbomb"
RAW_BOARD = RAW / "board"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
FIGURES = ROOT / "figures"
DOCS = ROOT / "docs"


@functools.lru_cache(maxsize=1)
def tournaments() -> dict:
    with open(CONFIG / "tournaments.yaml") as f:
        return yaml.safe_load(f)


@functools.lru_cache(maxsize=1)
def params() -> dict:
    with open(CONFIG / "params.yaml") as f:
        return yaml.safe_load(f)


def ensure_dirs() -> None:
    for d in (RAW_SB, RAW_BOARD, INTERIM, PROCESSED, FIGURES):
        d.mkdir(parents=True, exist_ok=True)
