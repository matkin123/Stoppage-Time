# IMPL — goal-celebration ALLOWANCE, PRE tournaments ONLY (POST keeps the full gap). ADR-0030. HUMAN CHECKPOINT.

**One self-contained unit (CLAUDE.md §6). Do ONLY this, validate, checkpoint, STOP.** This changes the
per-match true-stoppage estimator (s05) for the PRE-directive tournaments only, then MEASURES the effect
on the LOCKED headline X% (ADR-0025). Adopting it is a human decision — bring the before/after to the
user; do NOT re-lock without approval.

**Read first (in order):**
1. `CLAUDE.md` — §1 (X% is LOCKED, ADR-0025; the PRE/POST 2022-directive split is the study's spine), §6.
2. `docs/decisions.md` — **ADR-0030** (this unit's finding + decision), ADR-0016 (celebration built as a
   full dead window), ADR-0017 (the restart allowance ladder; why `From Kick Off` is excluded),
   **ADR-0029** (Method 2 adopted in code, s08 re-run batched — the cross-session interaction below).
3. `prompts/celebration_allowance_findings.md` — the EVIDENCE (signatures, OLS exchange rates, sweep).
4. Run the faithful prototype: `python -m src.celebration_allowance_whatif` (read-only). allowance=0 MUST
   print r=0.825 / MAE 2.44 / mean 13.16 (== production) — proof the harness is faithful. Its matches are
   ALL WC2018 = all PRE, so its table IS the PRE story (POST is unchanged and not shown).

## THE CORE DECISION — era-conditional, not blanket (do not get this wrong)
Apply the celebration allowance **ONLY to PRE tournaments (WC2018, Euro2020)**. Leave **POST (WC2022,
Euro2024, Copa2024, AFCON2023) UNCHANGED** on the full goal→kickoff gap. Why: the **2022 stoppage
directive instructed referees to add the FULL goal-celebration time** — so post-directive the full gap is
the CORRECT addable quantity and our current credit already matches it. Pre-directive, celebrations were
not fully added (Nate's WC2018 confirms the over-credit), so excess-over-allowance is correct there.
**Consequence you must preserve: POST `true_stoppage` stays BYTE-IDENTICAL to current production.** If a
POST match's `true_stoppage_s` changes, you have a bug.

## NAMING — this is NOT the same-half "Method 2" (ADR-0028/0029). Disambiguate.
The user has said "method 2" for two unrelated things. THIS unit = the goal-celebration allowance, an
**s05 estimator** change. The OTHER "Method 2" (ADR-0028 analysis, ADR-0029 adoption,
`src/method2_samehalf.py`, `src/s08_counterfactual.py:same_half_factors`) is an **s08 gross-up** change,
already adopted in code. Different stage. Do NOT edit the Method 2 code here.

## Scope (do not relitigate)
- **s05 only**, plus the matching residual read in **s08** (because s08 recomputes `true_stoppage` from
  components — see the X% step). `src/lib/bip.py` / s03 stay FROZEN (BIP r=0.943). `src/lib/silent.py`
  UNCHANGED.
- Validate against Nate's **`expected`** column (32 WC2018 = all PRE) via `nate.report(pred,"expected",…)`.
  Do NOT cross columns. The allowance is FIT on WC2018 and FROZEN, applied to both PRE tournaments
  (Euro2020 is PRE but has no Nate truth — same "fit-on-2018, apply-to-era" basis the project already uses).

## The era map (how each match knows PRE vs POST)
`interim/matches.parquet` has a **`group`** column with values `"PRE"`/`"POST"` (keyed by `match_id`;
`config/tournaments.yaml` is the source: PRE = `wc_2018`,`euro_2020` = 115 matches; POST = the other four
= 199). Build `match_group = matches.set_index("match_id")["group"].to_dict()` once and use it in s05
(and s08). Do NOT hard-code match ids.

## The change — three edits, one landmine

### 1. New param — `config/params.yaml:incident`, beside `restart_normal_s`:
```yaml
  # Goal-celebration allowance (ADR-0030): PRE-DIRECTIVE tournaments ONLY. A normal pre-2022 post-goal
  # kickoff was not fully added to stoppage; credit only the EXCESS over this allowance,
  # [goal + allowance, next kickoff], matching the restart_normal_s ladder (the ADDABLE quantity, not the
  # full BIP gap). POST tournaments keep the full gap (2022 directive adds the whole celebration).
  # FIT/FROZEN on WC2018; central 60s (== free-kick allowance; r-curve plateaus 60-90s).
  celebration_normal_s: 60.0
```

### 2. Era-conditional residual — `config/params.yaml:silent`:
Keep `residual_silent_s: 24.2` AS-IS (it is now the **POST / full-gap** value — unchanged, so POST stays
identical). ADD a PRE value (re-fit in step 4; ~94s placeholder):
```yaml
  residual_silent_s: 24.2        # POST (directive era, full-gap celebration) — unchanged
  residual_silent_pre_s: 94.0    # PRE (pre-directive), celebration credited as excess; RE-FIT on WC2018 in step 4
```

### 3. `src/s05_incident.py` — apply the allowance only for PRE, and make the residual era-conditional.
Load the era map near the top of `main()` (after reading events/seg):
```python
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    match_group = matches.set_index("match_id")["group"].to_dict()
```
In the per-match loop you already have `mid`; set `is_pre = match_group.get(int(mid)) == "PRE"`. Change
ONLY the celebration block (currently ~lines 129-133) so the lower edge is the allowance for PRE and the
goal timestamp (full gap, unchanged) for POST:
```python
                # celebration -- PRE: excess over celebration_normal_s; POST: full gap (2022 directive).
                if (typ == "Shot" and shot_out[i] == "Goal") or typ == "Own Goal For":
                    r = _next_resume(clocks, patterns, types, i, want_patterns={"From Kick Off"})
                    if r is not None:
                        hi = min(r, t0 + p["max_celebration_s"])
                        lo = t0 + (p["celebration_normal_s"] if is_pre else 0.0)
                        if hi > lo:
                            comp["celebration"].append((lo, hi))
```
(For POST `lo == t0` → interval `[t0, hi]` = the current full-gap credit, bit-for-bit.) Everything else in
s05 (sub/card/injury/restart_excess, union∩dead, the gate) is UNCHANGED — the credit only ever DECREASES
for PRE, so `lower_bound_s ≤ total dead` holds by construction.

Then in the true-stoppage assembly (currently `residual_s = float(sil["residual_silent_s"])` →
`ts["true_stoppage_s"] = ts["lower_bound_s"] + ts["silent_marked_s"] + residual_s`), make the residual
per-match by era:
```python
    pre_resid_s = float(sil["residual_silent_pre_s"]); post_resid_s = float(sil["residual_silent_s"])
    ts["group"] = ts["match_id"].map(match_group)
    ts["residual_silent_s"] = ts["group"].map(lambda gr: pre_resid_s if gr == "PRE" else post_resid_s)
    ts["true_stoppage_s"] = ts["lower_bound_s"] + ts["silent_marked_s"] + ts["residual_silent_s"]
```
(`true_stoppage.parquet` schema is unchanged — `residual_silent_s` is still a column, now varying by era.)
The ablation/validation print at the bottom is WC2018-only = all PRE, so use `pre_resid_s` there.
Update the module docstring's celebration line to note the PRE-only excess rule + the era-conditional
residual.

### LANDMINE — do NOT add `"From Kick Off"` to `restart_normal_s`.
That re-expands to the full gap (the `restart_excess` loop would credit `[goal+allow, kickoff]`, the
celebration component already credits the rest, the union merges them → full gap, nothing changes). The
fix MUST live inside the celebration credit's lower edge, exactly as above. Leave `From Kick Off` out of
the ladder.

## 4. Re-fit the PRE residual on WC2018, update the validation constants
The PRE credit dropped → the PRE-2018 mean fell → re-anchor to Nate: `residual_silent_pre_s =
mean(Nate expected) − mean(lower_bound + marked_silent)` over the 32 WC2018 matches (the ADR-0016/0017
recipe; the s05 ablation print computes the pieces). Prototype value at 60s is **+1.57 min ≈ 94 s** — set
the precise re-fit and FREEZE it. Then update `silent.estimator_pearson_r: 0.825→~0.875` and
`silent.estimator_mae_min: 2.44→~1.77` (these are the WC2018=PRE validation; s08's CI propagation reads
`estimator_mae_min`). Leave `residual_silent_s: 24.2` untouched (POST).

## Validate vs Nate (bring this table to the user)
- **Per-match r + MAE vs `expected`** from the s05 ablation print. **Bar: BEAT 0.825 / 2.44** → expect
  ~0.875 / 1.77 at 60s. Full ablation (lower_bound → +restart_excess → +marked_silent → +residual).
- **Aggregate:** 32-match mean stays ≈13.16.
- **Diagnostic (`nate.report` auto-print):** the OVER blowouts shrink (Portugal–Spain, England–Panama,
  Argentina–Croatia) WITHOUT breaking injury-dominated matches. The UNDER side (Sweden–S.Korea etc.) is
  NOT addressed here and should be ~unchanged — that is expected (the findings doc shows recovering the
  unmarked bucket makes things WORSE; do not chase it).
- **POST byte-identical check (correctness gate):** confirm every POST match's `true_stoppage_s` equals
  its pre-change value (diff `interim/true_stoppage.parquet` against a pre-change copy / `git stash`).
  Any POST drift = bug in the `is_pre`/residual wiring.

## THEN measure the X% impact — human checkpoint, NOT auto-adopt
Only PRE `true_stoppage` changes, so the X% move is driven entirely by the **115 PRE matches**; POST is
inert. **Direction is genuinely ambiguous — MEASURE it:** high-scoring PRE matches lose celebration
credit (but `lead_by_2plus` blowouts mostly can't flip), while every PRE match gains ~70s of residual,
which can RAISE stoppage on the low-scoring close matches that actually flip. The PRE/POST split
(red-team 26.1/22.8) may narrow or widen.

**s08 wiring (required — s08 recomputes true_stoppage from components):** s08's
`ts_window_min = (lower_bound_s + silent_marked_s + residual_silent_s·fshare[h]) / 60` currently reads the
single scalar `residual_silent_s`. Make it era-conditional too: join `matches.group` and use
`residual_silent_pre_s` for PRE matches, `residual_silent_s` for POST, before the `fshare[h]` 2H-scaling.
(The lower_bound_s it reads already reflects the s05 celebration change once s05 is re-run.)

**Measure the SAFE way (mirror `src/method2_samehalf.py` / `src/bip_headline_sensitivity.py`):** prefer a
throwaway git branch you can revert, or a cloned s08 central-knob closed form, so you do NOT overwrite the
locked `processed/*.parquet` / figures. Reproduce the LOCKED central P first (must match
`processed/counterfactual.parquet`) BEFORE swapping in the new estimator — proves the harness is faithful.
- **`var_s` GOTCHA:** if you run the real pipeline, s05 resets `var_s=0`; re-run **s06b** before s08
  (`python run.py --stage 5 → 06b → 8 → 9`).
- **CROSS-SESSION CAVEAT (ADR-0029):** Method 2 is already adopted in `src/s08_counterfactual.py` but its
  s08→s09 re-run is BATCHED (processed/ still holds the OLD 23.6% artifacts; code path produces 25.305%).
  So a real `run.py --stage 8` now reflects **Method 2 AND this celebration change combined** — the result
  will NOT equal ADR-0029's 0.25305 and that is NOT a failure. To attribute this unit's STANDALONE delta,
  measure it in isolation with the temp-dir harness (celebration change only, Method 2 reverted), and
  report both: celebration-alone, and celebration+Method 2 combined.
- Report: central X% (scoreline 1H+2H and 2H_only, plus outcome-flip) before vs after; whether it stays
  inside the published joint envelope [18.6%, 27.3%]; and the PRE/POST split move.

## Gate, checkpoint, STOP
- **Gate:** `s05` green (`lower_bound_s ≤ total dead` holds by construction); POST `true_stoppage_s`
  unchanged; `pytest` green — CHECK `tests/test_pipeline.py::test_s05_true_stoppage_estimator` and
  `test_s05_silent_marked_within_all` (they read params; if either asserts the OLD r=0.825 / MAE 2.44
  numerically, update to the re-fit values). r/MAE beats 0.825 / 2.44.
- **Do NOT touch the lock.** `docs/decisions.md` ADR-0025 stays byte-for-byte; `processed/*.parquet` and
  s09 figures stay locked UNLESS the user approves adoption. If you ran the real pipeline to measure,
  revert to the locked state afterward (git) until the user decides.
- **Checkpoint:** APPEND the adoption record to **ADR-0030** in `docs/decisions.md` — the re-fit constants
  (`celebration_normal_s`, `residual_silent_pre_s`, new `estimator_pearson_r`/`estimator_mae_min`), the
  ablation/diagnostic table, the POST-identical confirmation, and the measured standalone + combined X%.
  Update `next_session.md`. **Bring the r/MAE/diagnostic table + the X% delta to the user; let them decide
  adopt vs keep-locked.** One unit, then STOP — do not chain into a re-lock.
```
