# CLAUDE.md — Stoppage Time contract

Read this every session. The processed parquet tables + `docs/decisions.md` are the
source of truth — never notebooks, never chat history.

## 1. Goal & standard of proof
Headline target: **"Stoppage time is a sham; measured properly, X% of matches would end
differently."** `X%` is the one modeled claim — it ships with a confidence interval and a
sensitivity table, not a point estimate.

Standard of proof: **every number traces to a script + a checkpointed table + a documented
assumption.** If a figure can't be traced that way, it doesn't go in the article.

## 2. Locked decisions
- **Six tournaments**, PRE vs POST the 2022 stoppage directive:
  - PRE (115): WC 2018, Euro 2020.
  - POST (199): WC 2022, Euro 2024, Copa América 2024, AFCON 2023.
  - IDs + checksums live in `config/tournaments.yaml` (verified vs open-data competitions.json).
- **No xG.** Metrics are goals per live-minute and shots / shots-on-target per live-minute.
- **Gap-method ball-in-play** (s03): dead time = gap from a possession's last event to the
  next restart play_pattern.
- **VAR is only for the s05 attribution.** For s03 ball-in-play and all productivity, VAR is
  already captured as dead time automatically — no labeling required.
- **Skip 360 data entirely.** Never `git clone` open-data (multi-GB). Pull only the six
  competitions' match + event JSON; parse to parquet; keep footprint to a few hundred MB.

## 3. Conventions
- **Parquet I/O** between stages; `raw/` is immutable cache; `interim/` and `processed/` are
  regenerable. Event JSON is fetched in-memory in s02 and never written to disk (disk budget).
- **Idempotent stages**: re-running is safe and cheap; each stage reads the prior stage's
  parquet and writes its own.
- **Deterministic seeds** (`params.yaml:counterfactual.seed`), **pinned versions**
  (`requirements.txt`, NumPy held <2 — see that file for why).
- Run a stage: `python run.py --stage 3` or `make s03`. List: `python run.py --list`.

## 4. Per-stage acceptance gates (a stage is done only when its pytest is green)
- **s01** match counts per competition == tournaments.yaml checksums (115 / 199).
- **s02** clock_s monotonic within match; recovered period lengths sane.
- **s03 (CALIBRATION — stop here)** pooled WC2022 regulation ball-in-play within ±90s of
  Opta 58:04 (3484s). If not, tune `params.yaml:bip.min_dead_gap_s` before trusting anything
  downstream. Secondary: pooled in-play share ~55–60%.
- **s04** WC2022 goals after 90:00 ~12–13%; reconstructed finals == matches.ft_score.
- **s05** lower_bound_s ≤ total dead time (s03) for every match.
- **s06a** PRE board mean ~7 min; POST WC2022 ~11–12 min.
- **s06b** var_s ≥ 0 (fallback estimator; primary scrape is a documented manual path).
- **s07** every productivity cell reports n_events and live_minutes alongside the rate.
- **s08** sensitivity grid produced; read it before locking a single X%.
- **s09** deterministic figures + numbers ledger.

## 5. Source of truth
Processed parquet + `docs/decisions.md` (ADR log). Notebooks are exploration only.

## 6. Work unit — MODULAR, STANDALONE SESSIONS (non-negotiable)
**Work one self-contained unit per session, then stop.** Do NOT chain stages or attempt
to "run everything to the end" in a single session. Each session: pick up the next unit
from `next_session.md`, do only that unit, validate its gate, checkpoint (write results to
`decisions.md` and update `next_session.md`), then end the session to save compute.

**Why this is a hard rule (learned the expensive way):** a prior session burned large
compute running s04–s09 while s01–s03 still had MAJOR structural issues — the true-stoppage
methodology was wrong, exposed only by an external cross-check against Nate Silver's 2018 WC
data. All that downstream work had to be reconsidered. Never build on or validate downstream
of an upstream stage until that upstream stage is confirmed correct against an EXTERNAL
ground truth, not just its own internal gate. Cheap, correct, and sequential beats fast,
broad, and wrong.

Two human checkpoints matter most: the **s03 calibration** and the **s08 sensitivity grid**
— decide the headline number and its band with eyes open, then lock it in `decisions.md`.

Build order: s01 → s02 → s03 (confirm calibration yourself) → s04 → s05 → s07 (eyeball the
PRE/POST gap, decide framing) → s06a/s06b → finalize s07 → s08 (run grid before committing
to X%) → s09. **`next_session.md` is the authoritative pointer to the current unit of work.**
