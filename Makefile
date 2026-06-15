.PHONY: help setup test clean s01 s02 s03 s04 s05 s06a s06b s07 s08 s09 all
PY ?= python

help:
	@echo "Stoppage Time pipeline"
	@echo "  make setup      create venv .venv and install pinned requirements"
	@echo "  make s01 .. s09 run a single stage (e.g. make s03)"
	@echo "  make all        run the full pipeline in build order"
	@echo "  make test       run pytest acceptance gates"
	@echo "  make clean      remove interim/processed/figures outputs (keeps raw/)"

setup:
	$(PY) -m venv .venv
	./.venv/bin/python -m pip install --upgrade pip
	./.venv/bin/python -m pip install -r requirements.txt
	@echo "Activate with: source .venv/bin/activate"

s01:  ; $(PY) run.py --stage 01
s02:  ; $(PY) run.py --stage 02
s03:  ; $(PY) run.py --stage 03
s04:  ; $(PY) run.py --stage 04
s05:  ; $(PY) run.py --stage 05
s06a: ; $(PY) run.py --stage 06a
s06b: ; $(PY) run.py --stage 06b
s07:  ; $(PY) run.py --stage 07
s08:  ; $(PY) run.py --stage 08
s09:  ; $(PY) run.py --stage 09
all:  ; $(PY) run.py --all

test:
	$(PY) -m pytest -q

clean:
	rm -rf data/interim/* data/processed/* figures/*
	@echo "Cleaned interim/, processed/, figures/. raw/ left immutable."
