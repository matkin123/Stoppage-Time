# CLAUDE.md — Stoppage Time contract

Read this every session. The processed parquet tables + `docs/decisions.md` are the
source of truth — never notebooks, never chat history.

## 1. Goal & standard of proof
Headline target: **"Stoppage time is a sham; measured properly, X% of matches would end
differently."** `X%` is the one modeled claim — it ships with a confidence interval and a
sensitivity table, not a point estimate.

**LOCKED (ADR-0039, 2026-07-17): X% = 23.3% [95% CI 20.1%, 27.3%]**, window 1H+2H, central
knob_set `silent_marked|overall|pooled_all|hl=4.0|on`. Framing: *if stoppage time were measured
and awarded per the rulebook, ~23% of matches would have ended with a DIFFERENT SCORELINE* (≥1
extra goal in the omitted added time). The stricter "different RESULT" (winner/draw flips) is
**12.1% [10.4%, 14.2%]** — always reported separately. Lead assumption band 20.2%–25.6%; full
joint envelope 17.3%–27.0%. The modeling pipeline is DONE; `docs/decisions.md` is authoritative.

> **Re-locked 2026-07-17 (ADR-0039):** re-keys the s05 injury dead-time window to end at the next
> s03 in-play segment start (the next live ball), rule `inplay`, instead of the inconsistently-logged
> `Referee Ball-Drop` (present near only ~29% of injury flags) which fabricated ~10-min windows and
> over-credited routine dead time. Residuals re-fit on WC2018 and floored ≥0 (`residual_silent_pre_s`
> 94.1 → 25.9; `residual_silent_s` 24.2 → 0, raw refit −47.7s is an incoherent negative remainder).
> Supersedes the ADR-0035 lock (24.4% / 12.9%); the −1.1 pp scoreline / −0.8 pp flip move is the
> removed injury over-credit and stays inside the prior published envelope. Estimator re-fit r 0.875 →
> 0.870, MAE 1.77 → 1.67 (improves). `s03/bip.py` untouched — goals and live-minutes are unchanged, so
> productivity rates (PRE 0.089 / POST 0.075) are byte-identical; only owed/`true_stoppage` moved.
> POST `true_stoppage` is NO LONGER byte-identical to ADR-0035 (POST residual moved 24.2 → 0).
> `data/processed/*.parquet`, `figures/`, and `docs/numbers_ledger.md` regenerated; pytest green.

Standard of proof: **every number traces to a script + a checkpointed table + a documented
assumption.** If a figure can't be traced that way, it doesn't go in the article.

## 2. Locked decisions
- **Six tournaments**, PRE vs POST the 2022 stoppage directive:
  - PRE (166): WC 2018, Euro 2020, Euro 2024.
  - POST (148): WC 2022, Copa América 2024, AFCON 2023.
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
- **s01** match counts per competition == tournaments.yaml checksums (166 / 148).
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
`decisions.md`, **sync `README.md` per §7**, and update `next_session.md`), then end the
session to save compute.

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

## 7. README sync — part of every session's definition of done (non-negotiable)
**`README.md` is a derivative artifact and must never drift from the locked findings.** Before
ending ANY session that touched the model, the headline, the bands/CIs, the sensitivity grid,
a knob default, the calibration, the tournament set, the pipeline stages/gates, or the public
narrative, do a README consistency pass and update it in the same session. A session is not
"done" until the README reflects that session's changes.

The check (run it at checkpoint, even if you think nothing relevant changed):
- **Headline + bands.** README's headline, both CIs (scoreline + result), assumption band, full
  joint envelope, and the one-page results table all match the current lock in
  `docs/decisions.md` (newest ADR) and `docs/numbers_ledger.md`. Grep the old numbers to be sure
  none survive (e.g. `grep -nE '23\.6|12\.1|20\.6|27\.4' README.md` after a re-lock).
- **Structure mirrors the latest write-up.** The README's narrative sections (headline, the data,
  how it's measured, the four numbered objections, results & sensitivity) must mirror the
  STRUCTURE of the highest-numbered `docs/substack_post_v*.md`, and the README must link to that
  exact (latest) file. When a new `substack_post_v{N+1}.md` lands, repoint every README reference
  from `v{N}` to `v{N+1}` and re-mirror any changed section.
- **No broken links.** Every `docs/...md` and `figures/...png` the README references must exist
  (artifacts get renamed/removed — verify, don't assume).
- **Acceptance gates / stage table.** If a stage, gate, or knob changed, the pipeline table and
  the per-stage gates in §4 / the README stay consistent.

If the session genuinely changed nothing the README depends on, note "README: no change needed"
in the checkpoint and move on. The default posture is **assume it needs a look** — the headline
lives in two places (lock + README) and only the lock is authoritative, so the README is the one
that silently rots.
