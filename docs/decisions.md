# Decisions (ADR log)

Every methodology choice gets an entry here. Newest at top. The counterfactual headline
number and its band must be locked here (with the chosen knob_set) before publishing.

---

## ADR-0032 — Outcome-flip 50/50 team-split is empirically validated and non-load-bearing — LOCK UNCHANGED (2026-06-25)

**Analysis session, not a build or a lock.** Triggered by a user/consultant interrogation of the one
assumption in the **outcome-flip** secondary metric (`s08 outcome_flip`, locked 13.0% / ADR-0031): when
a team leads by one at 90', the flip credits the trailing team with a fixed **half** of the total
omitted-time goals — `P(flip) = 1 − exp(−μ·p_trail)`, `p_trail = 0.5`. The headline **scoreline** metric
(24.8%) does NOT use this split (it asks "≥1 extra goal by either team" and rides the total μ), so this
ADR cannot move the headline — only the flip. No parquet, no s08 grid, no figure, no params touched.
Standalone `src/flip_split_sensitivity.py` READS production parquet and writes `docs/flip_split_sensitivity.md`
(pattern: `src/method2_samehalf.py`; guardrail: ADR-0031 lock + CLAUDE.md §6).

**The question.** Is an equal trailing/leading split fair? Prior (game-state effects): trailing teams
throw numbers forward in stoppage time and might score >½ of late goals (which would make 13.0%
conservative); but the leading team's counter against a committed-forward opponent is a real countervailing
channel. Resolve it from the event data rather than assume.

**Method.** Per goal, reconstruct the pre-goal score (subtract the goal from `score_{home,away}_after` on
the scorer's side) → `margin_before` (scorer − opponent before the goal). Among goals scored while one side
led by exactly one (`|margin_before| = 1`): `margin_before = −1` ⇒ the **trailing** team scored (equalizer,
flip-relevant); `+1` ⇒ the **leading** team extended. `p_trail = #(−1)/#(|·|=1)`, Jeffreys 95% CIs.

**Result — p_trail ≈ 0.5 across every cut (the prior is NOT borne out).**

| population (lead-by-1 game-state) | n | trailing | leading | p_trail | 95% CI |
|---|---|---|---|---|---|
| **2H stoppage-time goals** (most relevant) | 31 | 17 | 14 | **0.548** | [0.375, 0.713] |
| all stoppage-time goals (1H+2H) | 41 | 22 | 19 | 0.537 | [0.386, 0.682] |
| 2H stoppage or after 80:00 | 70 | 33 | 37 | 0.471 | [0.358, 0.588] |
| all 2H goals after 75:00 | 91 | 43 | 48 | 0.473 | [0.372, 0.575] |
| **ALL goals** (1-goal-game anchor) | 287 | 146 | 141 | **0.509** | [0.451, 0.566] |

The directly-relevant added-time window leans *slightly* toward the trailing team (0.548), reverses toward
the leader in the broader late window (~0.47 after 75–80', the counter-attack channel), and the large-sample
anchor sits at 0.509. The two channels roughly cancel; **0.50 is well-calibrated, not a convenient guess.**

**Leverage — small.** Per-match μ recovered EXACTLY from the locked grid (`μ = −ln(1−p_change)`, central
knob_set, 1H+2H); re-running the flip over p_trail (harness check: `p_trail=0.5` reproduces the locked
`pct_outcome_flip` 0.12976 to |Δ|=0):

- p_trail 0.40 → **12.0%** · 0.471 → 12.7% · **0.50 → 13.0% (locked)** · 0.548 → **13.4%** · 0.60 → 13.9%.

lead_by_1 is the largest state bucket (121 of 314), so the split touches a big share of matches — but
because the measured value is so near 0.5, the most-relevant point estimate (0.548) moves the flip just
**+0.4 pp to ~13.4%**, and the full p∈[0.40,0.60] span is only 12.0%–13.9%. Tied matches (98) flip on any
goal regardless of p_trail; lead_by_2plus (95) are unflippable. Headline scoreline 24.8% unaffected at every
value.

**DECISION — lock UNCHANGED.** Keep `p_trail = 0.5` as the central; it is now a *traced* number
(measurement n=31 cleanest cut, CI containing 0.5, + the p-sweep band), not an unexamined constant —
satisfying the CLAUDE.md §1 standard of proof the same way every other knob does. **Honest caveat:** n is
small (added-time goals are rare; lead_by_1-at-the-time rarer), so the data is consistent with 0.5 but
cannot resolve 0.50 vs 0.55. If a single best-supported value were ever preferred over the round number, the
added-time-specific 0.548 gives ~13.4% — inside the flip CI [11.3%, 15.1%] either way. Suitable as a
pre-empt in the write-up. Exhibit: `docs/flip_split_sensitivity.md`; script: `src/flip_split_sensitivity.py`.

---

## ADR-0031 — HEADLINE RE-LOCKED at 24.8% scoreline / 13.0% flip (Method 2 + PRE celebration allowance ADOPTED) (2026-06-25)

**Human checkpoint, user-approved adoption (2026-06-25).** Supersedes ADR-0025's locked numbers.
The two upstream changes that had been measured-but-not-adopted are now BOTH production:
**ADR-0029 (Method 2 same-half live share + same-half gross-up z)** and **ADR-0030 (PRE-only
goal-celebration allowance, `residual_silent_pre_s=94.1`)**. Re-ran the pipeline end-of-tail
`--stage 5 → 06b → 8 → 9` against the source-of-truth tables; `counterfactual_summary.parquet`,
`figures/`, and `docs/numbers_ledger.md` are regenerated. `pytest` green (11 passed;
`test_s08_decay_endpoints` constants refreshed to the adopted combined rails 0.241/0.175/0.099 —
see below).

**Headline framing UNCHANGED.** *If stoppage time were measured and awarded per the rulebook, **X%
of matches would have ended with a DIFFERENT SCORELINE*** (≥1 extra goal in the omitted added time).
Metric unchanged (D1, ADR-0019): X% = mean(1 − exp(−μ)), μ = Σ_h λ_h · omitted_live_h.

**LOCKED VALUES (regenerated grid, group=all, window=1H+2H).**
- **Central: X% = 24.8% [95% CI 21.7%, 28.6%]**, knob_set `silent_marked|overall|pooled_all|hl=4.0|on`.
- **HEADLINE BAND (lead, one-factor-at-a-time over the legitimate knobs): 21.4%–27.3%** (width 5.9% ≈
  0.9× sampling). **Full joint envelope** (all legitimate knobs varied together): **18.9%–28.6%**
  (width 9.7% ≈ 1.4× sampling). Sampling CI width 6.9%.
- **Outcome-flip secondary (reported SEPARATELY): 13.0% [11.3%, 15.1%]** (1H+2H).
- 2H_only comparison: scoreline **17.0% [15.0%, 19.5%]**, flip **8.9% [7.9%, 10.3%]**.

**Legitimate-knob sensitivities (each swept with the others at central, 1H+2H, silent FIXED at the
calibrated marked point).**
- **Productivity-decay half-life** h∈[2,8], central h=4: **23.3% (h2) .. 24.8% (h4) .. 26.1% (h8)**.
- **In-stoppage gross-up** (central ON): off **21.4%** → **24.8% (ON, central)** → geometric ceiling **26.0%**.
- **λ source**: pooled_all **24.8%** (central) · pooled_pre 27.3% (sets lead-band top; wide CI, thin PRE) ·
  pooled_post 23.7% · regime_matched 24.9%.
- **Conditioning**: overall **24.8%** (central) · tied_nontied 24.5% (within noise).
- Endpoint regression (gross-up OFF) backs out the combined rails: 1H+2H h=inf 24.1% / h=0 17.1%;
  2H_only h=inf 17.5% / h=0 9.9%.

**Why the number moved (23.6% → 24.8%).** Two offsetting-but-net-positive forces: **Method 2 alone
re-centers +1.7 pp** (25.3%, ADR-0028/0029, same-half live share); the **PRE celebration allowance
alone is −0.5 pp** (it credits only the >60s excess for PRE, lowering PRE true_stoppage). Net adopted
central 24.8% / flip 13.0%. The move is entirely PRE-driven; POST `true_stoppage` is byte-identical to
the prior production (celebration unchanged for the directive era, max |Δ|=0.000000 over 199 POST
matches — the correctness gate). Both the central and the joint envelope stay INSIDE the previously
published outer bound [18.6%, 27.3%]→[18.9%, 28.6%]; this is a re-centering within the documented
uncertainty, not a new regime.

**Silent treatment, caveats, coverage — all carried forward UNCHANGED from ADR-0025** (silent reported
as the single Nate-WC2018-calibrated POINT, never a none/all band; outcome-flip always stated apart;
Nate validates WC2018=PRE only, POST validated indirectly via frozen estimator constants + WC2022 Opta
BIP). The s05 estimator improved with the allowance: **r 0.825 → 0.875, MAE 2.44 → 1.77 min** (WC2018 =
all PRE).

**Provenance.** params: `silent.residual_silent_pre_s=94.1` (PRE), `silent.residual_silent_s=24.2`
(POST, unchanged), `incident.celebration_normal_s=60.0`, `estimator_pearson_r=0.875`,
`estimator_mae_min=1.77`. Code: `src/s05_incident.py` + `src/s08_counterfactual.py` era-conditional
residual; `tests/test_pipeline.py::test_s05_true_stoppage_estimator` and `::test_s08_decay_endpoints`
updated. Ledger: `docs/numbers_ledger.md` regenerated. ADR-0025 below is retained as the historical
record but its numbers are SUPERSEDED by this entry.

---

## ADR-0030 — Goal-celebration ALLOWANCE, applied to PRE tournaments ONLY (POST keeps the full gap per the 2022 directive); FINDING + DECISION recorded, CODE PENDING a fresh session (2026-06-25)

**Decision (made with the user): give the goal celebration the same excess-over-allowance
treatment the other four restarts already get — but ONLY for the PRE-directive tournaments
(WC2018, Euro2020). POST (WC2022, Euro2024, Copa2024, AFCON2023) is left UNCHANGED on the full
goal→kickoff gap.** This session is FINDING + DECISION + handoff only; no code/params/parquet were
touched (user is batching compute across parallel sessions). Implement via
`prompts/impl_celebration_allowance.md` in a fresh session. **HUMAN CHECKPOINT before any re-lock.**

**The finding (evidence: `prompts/celebration_allowance_findings.md`; faithful read-only prototype
`python -m src.celebration_allowance_whatif`).** The f07 calibration panel sits at r=0.825 / MAE
2.44 vs Nate `expected` (32 WC2018). The single dominant per-match error is goal-celebration
OVER-credit. s05 credits the FULL goal→kickoff gap (`comp["celebration"] = [goal, next From Kick
Off]`, capped 180s, ∩ s03 dead) — but that is the **BIP / total-dead** quantity (s03 already counts
it). The estimator's target is **addable** stoppage = time beyond a *normal* restart. Every other
restart (throw-in 20s … free-kick 60s, `restart_normal_s`, ADR-0017) credits only `max(0, gap −
allowance)`; the goal kickoff is the lone restart still on the full-gap axis (historical: ADR-0016
built celebration as a plain dead window BEFORE the ADR-0017 allowance ladder, and `From Kick Off`
was excluded from that ladder to avoid double-counting the full-gap celebration). Diagnostics:
`corr(err, celebration)=+0.72`, `corr(err, goals)=+0.57` (the two strongest correlates); an OLS of
Nate `expected` on the six components gives celebration coef **0.24** — each credited celebration
minute buys only ~0.24 Nate-minutes, ~4× over-credit, and it scales with goals, so high-scoring
PRE matches over-predict (Portugal–Spain err +5.25, England–Panama +6.38, Argentina–Croatia +3.58).

**The what-if prize (WC2018, the validation set — which is entirely PRE).** Recompute the lower
bound changing ONLY the celebration rule to `max(0, gap − allowance)`, re-fitting the residual each
row so the 32-match mean stays anchored to Nate (apples-to-apples). `allowance=0` reproduces
production r=0.825 / MAE 2.44 / mean 13.16 EXACTLY ⇒ harness faithful.

| celeb allowance | r | MAE (min) | signed-err sd |
|---|---|---|---|
| **0s (current)** | 0.825 | 2.44 | 2.84 |
| 30s | 0.857 | 2.08 | 2.44 |
| 45s | 0.869 | 1.92 | 2.29 |
| **60s (central)** | **0.875** | **1.77** | 2.18 |
| 90s | 0.873 | 1.68 | 2.14 |
| 120s | 0.872 | 1.67 | 2.12 |

**Central = 60s** (round; equals the free-kick allowance — "~a minute per goal, credit the excess";
tops the r curve; plateaus 60–90s, not knife-edge). Prize on PRE: **r 0.825→0.875, MAE 2.44→1.77
(~28%), err sd 2.84→2.18.**

**Why PRE-only is the RIGHT model, not a hedge.** The 2022 stoppage directive — the exact event the
study's PRE/POST split is built on — instructed referees to add the FULL goal-celebration time to
stoppage. So post-directive the full goal→kickoff gap is the CORRECT addable quantity; our existing
full-gap credit already matches what POST referees were told to do. Pre-directive, celebrations were
NOT fully added (Nate's WC2018 numbers confirm the over-credit), so the excess-over-allowance rule is
correct there. Tying the celebration rule to the directive boundary makes the methodology *more*
defensible, and it lands the change exactly where we have ground truth: **Nate is WC2018-only = all
PRE**, so the allowance is fit AND validated precisely where it applies; POST is untouched, so it
needs no new validation.

**Consequences of the era-split (carry into implementation).**
- **POST is byte-identical to current production**: full-gap celebration + `residual_silent_s=24.2`.
  POST `true_stoppage` does not change ⇒ POST's contribution to X% is unchanged. (The 24.2s residual
  was fit on full-gap celebration, which POST still uses — it stays "with" that rule.)
- **PRE changes**: celebration → excess over `celebration_normal_s` (60s); the residual must be
  RE-FIT on WC2018 under the new rule (the credit dropped, so the residual rises to re-anchor the
  PRE-2018 mean to Nate 13.16 — prototype ~24.2s→**~94s**). The residual therefore becomes
  **era-conditional**: PRE ~94s, POST 24.2s.
- **X% impact is driven ENTIRELY by PRE (115 of 314 matches).** Direction is genuinely ambiguous and
  must be MEASURED, not assumed: high-scoring PRE matches LOSE celebration credit (but blowouts at
  `lead_by_2plus` mostly can't flip anyway), while every PRE match GAINS ~70s of residual — which can
  raise stoppage on the low-scoring close matches that actually flip. So PRE X% (and the PRE/POST
  split, red-team's 26.1/22.8) could move either way.
- **Validation constants** (`estimator_pearson_r`, `estimator_mae_min`) describe the WC2018=PRE
  estimator → update to ~0.875 / ~1.77. s08's CI propagation reads `estimator_mae_min`.

**Cross-session interaction with ADR-0029 (Method 2).** Both are X%-moving changes feeding s08
(Method 2 = s08 gross-up, already adopted in code, re-run batched; this = s05 `true_stoppage`).
ADR-0029's expected 25.305% assumes Method 2 is the ONLY change at re-run. If the celebration
allowance is ALSO adopted before `run.py --stage 8`, the regenerated grid reflects the COMBINED
move — expected, not a flow-through failure. Attribute each change's standalone delta via the
temp-dir harness (`src/bip_headline_sensitivity.py` / `src/method2_samehalf.py` pattern).

**Status: CODE PENDING.** Not implemented this session. The turnkey unit
(`prompts/impl_celebration_allowance.md`) makes the s05 change (era-conditional celebration +
residual via the `group` column on `matches.parquet`), re-validates vs Nate (beat 0.825/2.44),
MEASURES the X% delta without overwriting locked artifacts, and STOPS at the user decision. **Do NOT
re-lock ADR-0025 without the user.** This ADR records the finding + the agreed design; the adoption
record (with measured X%) is appended here when the fresh session runs it.

### ADOPTION RECORD — CODE BUILT + MEASURED (2026-06-25, fresh session). HUMAN CHECKPOINT — NOT re-locked.

The turnkey unit was implemented and measured. Locked DATA artifacts (`processed/*.parquet`,
`figures/`, ADR-0025 text, CLAUDE.md headline) are UNTOUCHED (verified byte-identical + mtimes). The
change lives in CODE + params only, awaiting the user's adopt-vs-keep-locked decision.

> **OUTCOME (2026-06-25): ADOPTED.** The user approved adoption; the headline is RE-LOCKED at 24.8%
> scoreline / 13.0% flip in [[ADR-0031]] (combined with Method 2). The "UNTOUCHED locked artifacts"
> note above describes the measurement session only — at adoption the pipeline was re-run
> (`06b → 8 → 9`) and `processed/`/`figures/`/ledger were regenerated. See ADR-0031 for the locked grid.

**Re-fit constants (frozen).**
- `incident.celebration_normal_s: 60.0` (NEW). PRE celebration credited as `[goal+60s, kickoff]` ∩ dead.
- `silent.residual_silent_pre_s: 94.1` (NEW, PRE). Re-fit on the 32 WC2018 matches:
  mean(Nate `expected`) − mean(lower_bound + silent_marked) = **94.09s** (frozen at 94.1).
- `silent.residual_silent_s: 24.2` — UNCHANGED (now the POST / full-gap value).
- `silent.estimator_pearson_r: 0.825 → 0.875`; `silent.estimator_mae_min: 2.44 → 1.77` (WC2018 = PRE).

**Validation vs Nate `expected` (32 WC2018 = all PRE), s05 ablation print:**

| step | r | MAE (min) |
|---|---|---|
| lower_bound (celeb/sub/card/injury) | 0.734 | 6.79 |
| + restart_excess | 0.840 | 5.30 |
| + marker-gated silent | 0.875 | 2.17 |
| + residual constant (**estimator**) | **0.875** | **1.77** |

BEATS the 0.825 / 2.44 bar on both axes (matches the prototype exactly). Aggregate 32-match mean
stays 13.16. s05 gate (`lower_bound ≤ total dead`) PASSED. `pytest` green except the pre-existing
EXPECTED-RED `test_s08_decay_endpoints` (it reads the stale locked parquet per ADR-0029; untouched
by this unit). `test_s05_true_stoppage_estimator` updated for the era-conditional residual.

**POST byte-identical (correctness gate) — CONFIRMED.** Diffed new vs pre-change
`true_stoppage.parquet`: over the 199 POST matches `max|Δtrue_stoppage_s| = 0.000000`. The 115 PRE
matches changed (mean Δ −31.2s: lost celebration credit > the +70s residual gain, on average).

**X% impact (closed-form central knob `silent_marked|overall|pooled_all|hl=4.0|on`, deterministic).**
Measured via a throwaway closed-form harness (method2_samehalf.py pattern); locked `processed/` NOT
touched. Faithful anchors reproduced EXACTLY: scenario A (old estimator + locked conversion) =
0.23612 / 2H_only 0.15993 (== `counterfactual.parquet`); scenario C (old estimator + Method 2
conversion) = 0.25305 / flip 0.13185 (== ADR-0029). Then:

| scenario (1H+2H scoreline / flip) | scoreline | 2H_only | flip 1H+2H | flip 2H_only |
|---|---|---|---|---|
| **A** locked baseline (ADR-0025) | 23.61% | 15.99% | 12.11% | 8.20% |
| **B** celebration-alone (Method 2 reverted) | 23.16% | 15.68% | 11.93% | 8.07% |
| **C** Method 2-alone (ADR-0029) | 25.31% | 17.39% | 13.18% | 9.09% |
| **D** combined celeb+M2 (= `run.py --stage 8` now) | **24.77%** | 17.01% | **12.98%** | 8.93% |

- **Direction resolved: the celebration allowance LOWERS X% modestly.** Celebration-alone −0.46 pp
  scoreline (23.61→23.16); on top of Method 2 (C→D) −0.54 pp (25.31→24.77). The lost celebration
  credit on high-scoring PRE matches outweighs the +70s residual gain on close matches.
- **POST is inert in production.** Under Method 2's per-(match,half) `z_half`, POST X% is IDENTICAL in
  C and D (scoreline 26.86%, flip 14.44%) — the entire move is PRE (22.61%→21.14% scoreline). (In the
  locked-conversion B, POST drifts a hair −0.09 pp only because that path's gross-up z is a single
  POOLED scalar recomputed across all matches; production Method 2 uses per-match z_half, so POST is
  exactly inert. The PRE/POST split WIDENS.)
- **Combined stays inside the published joint envelope [18.6%, 27.3%].** 24.77% scoreline, 12.98% flip.

**HUMAN CHECKPOINT — decision pending.** ADR-0025 NOT re-locked; the headline remains 23.6%/12.1%
until the user decides. If adopted, the re-lock follows ADR-0029's downstream checklist combined with
this change (run `--stage 5 → 06b → 8 → 9`; the combined central is 24.77%/12.98%, NOT ADR-0029's
25.305% — both changes are live). Interim `incident_stoppage`/`true_stoppage` parquet now hold the NEW
values (and s05 reset `var_s=0`; re-run s06b before s08 on adoption); `processed/` + figures stay locked.

---

## ADR-0029 — Method 2 ADOPTED into s08 as production behavior; CODE-ONLY this session, compute batched — re-lock + figures PENDING re-run (2026-06-25)

**Human decision (resolves the ADR-0028 checkpoint): adopt Method 2 — option (a).** The user
chose the more defensible same-half conversion over the locked 23.6%. Method 2 is now the
PRODUCTION path in `src/s08_counterfactual.py` (not a knob, not a standalone script). Rationale
is ADR-0028's: same-half conversion is calibrated to the teams on the day, rests on a 45+ min
base instead of a few skewed stoppage-window minutes, captures 2H fatigue/subs, and resolves the
ADR-0027 live-share/z asymmetry by sourcing BOTH factors from one reference period. The new
central sits inside the already-published joint envelope [18.6%, 27.3%], so this re-centers
rather than breaks the uncertainty story.

**SCOPE OF THIS SESSION = CODE + DOCS ONLY. No compute was run.** The user is batching other
changes across parallel Claude Code sessions and will regenerate grids/figures/parquet ONCE at
the end. So this session deliberately did NOT run `run.py --stage 8/9`, did NOT regenerate any
parquet, figure, or the numbers ledger. `processed/*.parquet` and `figures/` still hold the OLD
ADR-0025 (23.6%) artifacts. The purpose of this ADR is to (1) record the adoption and (2) give a
COMPLETE downstream-consequences checklist with EXPECTED deterministic values, so flow-through
can be verified after the batch re-run.

**What changed in code (this session).**
- `src/s08_counterfactual.py`:
  - new `same_half_factors(seg, incident)` → per-(match,window) `ls_half` (Σ in_play dur / Σ dur
    over the WHOLE played half, periods 1-2 in `bip_segments`) and `z_half` ((lower_bound_s +
    silent_marked_s)/Σ dead dur over the whole half, residual silent excluded).
  - window loop: `lsw` now = `ls_half[m,window]`; new `zw` = `z_half[m,window]` (both nan_to_num);
    `flw = lsw·(1+zw·(1−lsw))` gross-up ON, `= lsw` OFF; decay horizon `T2 = olive_2H/ls_half[2H]`.
  - λ-EXPOSURE live-minutes UNCHANGED (still the stoppage-window `live_min` table feeding
    `build_lambda_cells`) — this is the deliberate broken cancellation (ADR-0026/0028).
  - `_geom_ceiling(window, ci)` drops the scalar-`z` arg; uses per-match `ci["z1"]`/`ci["z2"]`.
  - `central_inputs` now carries `z1`,`z2`; `decay_profile` DataFrame gains a `z_half_2h` column
    and `live_share_2h` is now the SAME-HALF 2H share.
  - `genuine_stoppage_share` (pooled scalar z=0.382) kept ONLY as a printed diagnostic.
- `tests/test_pipeline.py::test_s08_decay_endpoints`: rails updated 0.238/0.171/0.097 →
  0.246/0.179/0.101 (Method 2 same-half). EXPECTED-RED until the s08 re-run (it reads the stale
  parquet); the green flip after re-run is itself a flow-through check. Other s08 tests
  (silent_knob_brackets, closed_form_p_change, avg_lambda_decay) are structural — unchanged.
- `src/method2_samehalf.py` + `docs/method2_samehalf.md` (ADR-0028 prototype) retained as an
  independent cross-check; not on the production path.

**Verification done WITHOUT touching locked artifacts.** The modified s08 was run in a throwaway
temp dir (config.PROCESSED redirected; pattern from `src/bip_headline_sensitivity.py`); the REAL
`processed/` was confirmed untouched (mtimes + git). The deterministic central reproduced the
ADR-0028 prototype: 1H+2H scoreline 0.25305, flip 0.13185 (prototype reported 0.2531/0.1318 —
same to 3 dp; tiny 4th-dp drift is just the prototype's reduced grid, both deterministic).

**EXPECTED post-re-run values (the verification targets). group=all, central knob_set
`silent_marked|overall|pooled_all|hl=4.0|on`, deterministic (no seed):**

| quantity | OLD (ADR-0025) | **Method 2 (expected)** |
|---|---|---|
| scoreline 1H+2H (headline) | 0.23612 | **0.25305** |
| scoreline 2H_only | 0.15993 | **0.17391** |
| outcome-flip 1H+2H | 0.121 | **0.13185** |
| outcome-flip 2H_only | — | **0.09091** |
| gross-up rail off → on → geom (1H+2H) | 0.211 / 0.236 / 0.242 | **0.2176 / 0.25305 / 0.26589** |
| decay band h2 / h4(central) / h8 (1H+2H) | — | **0.238 / 0.25305 / 0.267** |
| endpoint h=inf off (1H+2H / 2H_only) | 0.238 / 0.171 | **0.24573 / 0.17879** |
| endpoint h=0 off (2H_only, =floor) | 0.097 | **0.10071** |
| mean ls_half / mean z_half (diagnostic print) | — | **0.555 / 0.363** (vs scalar 0.382) |

CIs are bootstrap (seeded, deterministic) and WILL move with the higher center — they are NOT
yet recomputed; read them from the regenerated `counterfactual_summary.parquet` at re-lock and
record the refreshed [lo, hi] in a follow-up ADR-0025 update. Do NOT hand-edit CI numbers.

**DOWNSTREAM CONSEQUENCES CHECKLIST (verify each after `run.py --stage 8` then `--stage 9`).**
1. `processed/counterfactual.parquet` — per-match `p_change`. SCHEMA unchanged
   {match_id, window, knob_set, p_change}; every value recomputed. Central 1H+2H mean p_change
   → 0.25305.
2. `processed/counterfactual_summary.parquet` — SCHEMA unchanged; `pct_changed`,
   `pct_outcome_flip`, and all four CI columns refresh for every knob_set. Central row
   pct_changed=0.25305 / flip=0.13185; geometric-ceiling row (1H+2H)=0.26589.
3. `processed/decay_profile.parquet` — **SCHEMA CHANGE: new column `z_half_2h`**; `live_share_2h`
   now the SAME-HALF 2H share (higher than the old stoppage-window share); `omitted_2h_clock_min`
   (= grossed horizon T2) and `omitted_2h_live_min` recomputed. Any external reader must tolerate
   the added column.
4. `src/s09_figures.py` (run stage 9) derives headline/bands/flip DYNAMICALLY from #2/#3, so it
   auto-flows. Re-renders `figures/f05_sensitivity_grid.png` (grid shifts up to ~25.3% central)
   and `figures/f06_productivity_decay.png` (same-half live share & T2). The s09 numbers ledger
   auto-updates the headline X%, bands, and flip.
5. `tests/test_pipeline.py::test_s08_decay_endpoints` flips GREEN (asserts 0.246/0.179/0.101).
   Run the full pytest after re-gen; all s08 gates must be green (CLAUDE.md §4).
6. Requested/editorial figures that read the counterfactual outputs (`src/figures_requested.py`,
   `src/fig_*` scripts, `docs/model_review_*`, `docs/substack_post*`) must be RE-RENDERED and the
   23.6%/12.1% headline strings refreshed to the Method 2 numbers — these are hand-authored prose,
   NOT auto-derived, so grep for "23.6", "23.6%", "24%", "12.1" after re-gen and update.
7. `CLAUDE.md §1` and `ADR-0025` (the lock) carry the literal 23.6% / 12.1% headline — UPDATE to
   the Method 2 central + refreshed CIs once #2 is regenerated. This ADR adds a migration note to
   §1 now; the authoritative re-lock (with new CIs/envelope) is a follow-up once compute runs.

**Until the batch re-run, ADR-0025's 23.6% remains the artifact-backed number** (parquet/figures
still hold it). The code path, however, now produces 25.3%. Treat any 23.6% figure as STALE the
moment `run.py --stage 8` is executed.

**CROSS-SESSION CAVEAT (combined effects at re-run).** A parallel unit (the goal-celebration
ALLOWANCE, an s05 `true_stoppage` change; see `next_session.md` + `prompts/impl_celebration_allowance.md`)
is ALSO an X%-moving change feeding s08. The expected values in this ADR assume **Method 2 is the
ONLY change in the code at re-run time.** If the celebration allowance (or any other true_stoppage /
λ change) is ALSO adopted before `run.py --stage 8`, the regenerated grid reflects the COMBINED move
and will NOT equal 0.25305 — that is expected, NOT a flow-through failure. To attribute, re-measure
each change's standalone delta (the temp-dir harness in `src/bip_headline_sensitivity.py` /
`src/method2_samehalf.py` is the pattern). The celebration-allowance adoption takes the next ADR
number (**ADR-0030**); this ADR-0029 is the Method 2 adoption.

---

## ADR-0028 — Method 2 (same-half live share + same-half gross-up z) raises central X% to 25.3%, OUTSIDE the gross-up band — MATERIAL move, HUMAN CHECKPOINT, lock UNCHANGED (2026-06-25)

**Analysis session, not a build or a lock.** Executed `next_session.md`'s ACTIVE UNIT (Method 2), the
defensible alternative ADR-0027 queued. Standalone `src/method2_samehalf.py` READS the production
parquet, reuses the s08 closed form verbatim, and writes only a small report (`docs/method2_samehalf.md`
+ console). **No processed parquet, no s08 grid, no figure, no test, no `params.yaml` was touched** (pattern:
`src/bip_headline_sensitivity.py`; guardrail: ADR-0025 lock + CLAUDE.md §6). Unlike Method 1 (a sub-band
wiggle, ADR-0027), **Method 2 moves the headline OUT of the documented gross-up band — so it is flagged as a
MATERIAL move and brought to the human checkpoint rather than absorbed.**

**Harness faithfulness (gate before swapping in Method 2).** The script's `central` provider reproduces
`processed/counterfactual.parquet` for the central knob_set `silent_marked|overall|pooled_all|hl=4.0|on` to
**machine precision** (1H+2H 0.23612 = 0.23612; 2H_only 0.15993 = 0.15993; |Δ|=0). So the only thing that
moves the number is the Method 2 swap, nothing else.

**What Method 2 does.** For each omitted-stoppage window it assumes the omitted minutes look like the
average **SAME-HALF** minute (that half's regulation play *plus* its PLAYED added time, the whole period
in `bip_segments`, NOT clipped at 2700) for BOTH conversion factors at once:
- live share `ls_half[m,h] = Σ dur(in_play) / Σ dur` over the whole half (replaces the stoppage-window
  `lsw` in BOTH the gross-up factor and the decay horizon `T2`).
- gross-up `z_half[m,h] = (lower_bound_s + silent_marked_s) / Σ dur(dead)` over the whole half, residual
  silent EXCLUDED to match the pooled-z definition (replaces the pooled scalar `z=0.382`).
- `flw = ls_half·(1 + z_half·(1−ls_half))`, `olive = max(0, true_stoppage − played)·flw`, `T2 =
  olive_2H/ls_half[2H]`. **true_stoppage, played, and the pooled λ cells (lam1, obs2, floor2) are UNCHANGED**
  — Method 2 changes only the CLOCK→LIVE conversion + the decay horizon, not the goals-per-live-minute rates.

**Result (deterministic central point; group=all).**

| metric | locked (ADR-0025) | Method 1 (ADR-0027) | **Method 2** |
|---|---|---|---|
| scoreline 1H+2H | 23.6% | ~23.4% | **25.31%** |
| scoreline 2H_only | 16.0% | — | **17.39%** |
| outcome-flip 1H+2H | 12.1% | — | **13.18%** |
| outcome-flip 2H_only | — | — | **9.09%** |

**Band placement (the decisive line).** Method 2's 25.31% is **OUTSIDE the gross-up rail band [21.1%, 24.2%]**
(off → geometric, h=4) — the threshold `next_session.md` named for a MATERIAL move. BUT it is still **INSIDE
the lead one-factor band [21.1%, 26.1%]** AND **INSIDE the full joint legitimate-knob envelope [18.6%, 27.3%]**
(ADR-0025). So adopting Method 2 would **re-center** the headline ~+1.7 pp, not break the already-published
uncertainty envelope. The scoreline-vs-flip story is intact (25.3% ≫ 13.2%); nothing flips.

**Channel decomposition (1H+2H scoreline, +1.69 pp total).** Both channels push UP:
- **Live-share swap** (ls_half, pooled z) → 24.57% (**+0.96 pp**) — this is the deliberately BROKEN
  CANCELLATION. Method 2 raises the omitted-LIVE live share but NOT the λ-exposure live share (still
  stoppage-window live-minutes in `build_lambda_cells`), so μ ≈ G·omitted/total (ADR-0026) no longer
  self-cancels: matches whose stoppage window was unrepresentatively dead now contribute more omitted-live.
- **z swap** (lsw, z_half) → 24.33% (**+0.72 pp**). Counter-intuitive given pooled-mean z_half (0.363) <
  the 0.382 scalar — but z_half is higher in the **2H** (0.434), exactly where most omitted minutes live, so
  the gross-up factor grows where it matters. Interaction ≈ +0.01 pp.

**Spain–England (Euro 2024 final), state@90 = lead_by_1 — confirms the predicted direction and magnitude.**
Omitted clock 11.59 min (UNCHANGED); omitted **LIVE** minutes nearly double **3.95 → 7.70**; P scoreline
**19.6% → 34.64%** (M1 lowered it to 17.8%); P flip **10.3% → 19.15%** (M1 9.3%). Driver: its 2H whole-half
live share **0.528** ≫ its unrepresentatively-dead stoppage-window share **0.258** — Method 2 rejects the
"omitted minutes are as dead as the few wasted played ones" assumption (its 2H z_half 0.361 ≈ pooled 0.382,
so the move is almost entirely the live-share rejection, NOT z). This is the exact case Method 1 could not
rescue (its 2H deadness is UNMARKED, window z₂H=0.008), and where Method 2 most diverges from the lock.

**Diagnostics.** pooled-mean live share: 1H ls_half 0.577 vs lsw 0.567; 2H ls_half 0.533 vs lsw 0.505 (the
2H stoppage window is, on average, slightly deader than the whole half — and far deader in skewed matches
like Spain–England). pooled-mean z_half: 1H 0.292 / 2H 0.434 / overall 0.363 vs the 0.382 scalar.
**corr(ls_half, z_half) = −0.389** (deader halves carry a higher genuine-stoppage fraction — physically
sensible). λ rates unchanged: lam1=0.0478, obs2=0.0816, floor2=0.0427.

**DECISION — lock UNCHANGED; HUMAN CHECKPOINT (do NOT re-lock without the user).** Method 2 is the more
defensible *assumption* (calibrated to the specific teams on the day, captures 2H fatigue/subs, rests on a
45+ min base instead of a few skewed minutes, and resolves the ADR-0027 asymmetry by sourcing BOTH factors
from one reference period). It RAISES the headline with no agenda (faithful harness, same λ population). But
it is a genuine MODEL CHANGE that moves the central point out of the gross-up band, so per CLAUDE.md §6 it
stops here for a human decision rather than being absorbed silently. **The choice for the user:** (a) adopt
Method 2 → re-lock central ~25.3% scoreline / 13.2% flip (still inside the published [18.6%, 27.3%]
envelope), updating ADR-0025 + s08 + figures + ledger; or (b) keep the locked 23.6% and record Method 2 as a
documented upper-leaning sensitivity. Until the user decides, **ADR-0025 stands byte-for-byte.** Report:
`docs/method2_samehalf.md`; script: `src/method2_samehalf.py`.

---

## ADR-0027 — Gross-up live-share / z asymmetry examined; Method 1 (per-match window z) shifts X% ~−0.2 pp, inside band — LOCK UNCHANGED (2026-06-24)

**Analysis session, not a build or a lock.** Triggered by a user interrogation of how the s08
gross-up treats omitted added-time minutes. No parquet, no s08 grid, no figure, and no test was
touched. This ADR records the asymmetry the user identified, the result of the fix they proposed
("Method 1"), and why it does NOT justify reopening the LOCKED ADR-0025 artifact. It also seeds the
next session's test of a more defensible alternative ("Method 2" — see `next_session.md`).

**The asymmetry (real, and worth recording).** For each omitted-stoppage window the model converts
omitted CLOCK to omitted LIVE minutes with two factors that live at DIFFERENT scopes:
- **live share `lsw`** is **match- and window-specific** — the measured in-play fraction of *that
  match's* added-time window (`stoppage_live_share`, split at the 45:00/90:00 boundary, per
  `(match_id, phase)`).
- **gross-up `z`** (genuine-stoppage fraction of dead time, the `z·(1−lsw)` re-credit in ADR-0024)
  is a **single POOLED whole-match scalar = 0.382** (`genuine_stoppage_share`, regulation periods,
  `counted = Σ(lower_bound_s + silent_marked_s) ÷ Σ dead`). So a match-specific numerator (live
  share) is mixed with a global denominator-correction (z). The user's objection: gross up with the
  *same* estimator we use everywhere else, but applied to *this segment*.

**Method 1 = make z window-specific.** Re-run the s05 marker-gated attribution clipped to the
stoppage window only (`period_s > 2700`), so `z_window = counted_stoppage_in_window ÷ dead_in_window`,
keeping live share stoppage-specific as before. Recomputed for the two showcase finals:

| Final | window z (1H / 2H) | P(scoreline) old → M1 | P(flip) old → M1 |
|---|---|---|---|
| Euro 2024 — Spain–England | 0.345 / **0.008** | 19.6% → **17.8%** | 10.3% → **9.3%** |
| Euro 2020 — Italy–England | 0.035 / 0.444 | 29.6% → **29.9%** | ~unchanged |

**Surprising direction for the showcase match.** Method 1 *lowers* Spain–England, not raises it. Its
2H added time really was mostly dead (stoppage live share ≈ 0.26 vs its own regular-play 0.56–0.61),
but that deadness is **UNMARKED** — sparse logging / off-ball time the markers don't flag — so the
window estimator credits almost no identifiable stoppage there (2H z = 0.008) and the re-credit
shrinks. The user's "deader ⇒ more re-credited stoppage" instinct holds only *weakly* population-wide
(pooled window z = 0.356 ≈ the 0.382 scalar; corr(window z, live share) = **−0.26**); Spain–England
is the case that bucks it.

**Headline impact — negligible, by construction.** Pooled window z (0.356) ≈ the whole-match scalar
(0.382), so swapping one for the other moves central X% by **~−0.2 pp (23.6% → ~23.4%)**. That sits
inside the already-documented gross-up rail band **[21.1% (off) … 24.2% (geometric)]** (ADR-0024,
h=4) and is washed out by the live-share cancellation in aggregate: μ ≈ λ·omitted_live ≈
G·omitted_clock / total_clock, because live share scales BOTH the omitted-live numerator and the
λ-exposure denominator (same mechanism as ADR-0026's BIP non-load-bearing finding).

**DECISION — do not change the lock (user's verbatim conclusion):**
> Method 1 (per-match window-specific z) shifts central X% by ~−0.2pp (23.6% → ~23.4%), which sits
> well inside the already-documented gross-up band [21.1%, 24.2%] and is washed out by the live-share
> cancellation in aggregate (μ ≈ G·omitted_clock/total_clock). Changing a LOCKED artifact (ADR-0025)
> to chase a sub-band wiggle isn't worth it.

**Honest caveat that motivates Method 2.** Window z counts only *identifiable* (marker-gated)
stoppage, so it cannot rescue a match whose deadness is unmarked (exactly Spain–England) — it just
re-expresses the locked `silent_marked` vs `silent_all` axis at window scope, and that axis is a
calibrated POINT, not a band (ADR-0025). Method 1 also inherits low signal / high skew from a ~5–11
min window. The user's preferred fix is **Method 2**: assume omitted minutes look like the average
**SAME-HALF** minute — that half's regular play *plus* that half's PLAYED stoppage — for BOTH live
share and z. That calibrates to the specific teams on the day, captures 2H fatigue/subs, and rests on
a 45+ min base instead of a few skewed minutes. Method 2 is queued for the next session
(`next_session.md`); this ADR deliberately leaves the LOCKED headline untouched pending that test.

---

## ADR-0026 — BIP threshold propagated to the headline: confirmed non-load-bearing (robustness, NOT a knob) (2026-06-22)

**Closes the one gap the lock left open.** ADR-0009's `bip.max_live_gap_s` (20s) is the single global
knob behind ball-in-play, and ADR-0025's sensitivity story swept every modeling knob (silent, decay,
gross-up, λ-source, conditioning) but held BIP FIXED at 20s. The `bip_robustness` exhibit (ADR-0003/0009
follow-up) swept the threshold but stopped at BIP minutes + the cross-tournament ranking — it never
propagated through to X%. This ADR measures that propagation.

**Method (locked tables UNTOUCHED).** `src/bip_headline_sensitivity.py` — standalone, not a stage, not a
gate. Re-runs the REAL s03→s07→s08 at each threshold in the 12–30s sweep, writing every output to a
throwaway temp dir (production parquet + `decisions.md` numbers never touched; verified — processed/
mtimes unchanged, git shows only new files). The s08 grid is trimmed to the central silent/conditioning/
source axes (decay + gross-up axes kept so s08's band print still indexes h=2/4/8 and off/on), so the
central row is `silent_marked|overall|pooled_all|hl=4.0|on`. Central X% is closed-form/deterministic; only
the bootstrap CI depends on grid position.

**RESULT — the headline barely moves.**
- Central (20s): **scoreline 23.61% (≈ locked 23.6%), flip 12.11% (≈ locked 12.1%)** — reproduces ADR-0025.
- **Full sweep 12–30s: scoreline 23.51%–23.66%, flip 11.98%–12.11%** — max |Δ| = **0.10 pp**.
- **In-tolerance band 14–20s** (both Opta anchors within ±90s): scoreline **23.57%–23.62%**, max |Δ| =
  **0.04 pp** from the 20s central.
- Even the out-of-calibration 12s (WC2022 gate FAILS, −101s) only drags the headline to 23.51% (−0.10 pp).

**WHY (first principles, not just empirics).** BIP enters the counterfactual in two OFFSETTING places: the
per-live-minute scoring rate λ = G/L (live-minutes L in the denominator) and the omitted-live exposure
D·(L/T) (live-share in the numerator). So μ ≈ λ · omitted_live = G·D/T and the live-minutes L largely
**cancel** — the headline rides on owed-stoppage D and goals G, not on the absolute live-football level.
The residual ≤0.1 pp wobble is the second-order gross-up/decay nonlinearity (gross-up factor and decay
horizon T=olive/live_share are nonlinear in live-share, so the cancellation is first-order, not exact).

**Exhibit + traceability.** Full per-threshold table in `docs/bip_headline_sensitivity.md`; the CI lower
rail there reads ~20.4 vs the locked 20.6 purely from bootstrap RNG-stream position under the trimmed grid
(the deterministic point matches exactly). No change to the lock, the s08 grid, or any parquet. This
substantiates the methods-piece claim that the headline doesn't depend on getting BIP exactly right.

---

## ADR-0024 — IMPL-8: omitted-time productivity DECAY (Method A) replaces the premium rails; gross-up central → ON; silent → headline POINT (X% still NOT locked) (2026-06-19)

**Build session, not a lock.** Executed `prompts/impl_8_productivity_decay.md` against the processed
tables. Rebuilds s08's 2H productivity term as a per-minute exponential decay, flips two central knobs,
and regenerates the grid + figure for the human checkpoint. **X% is deliberately still NOT locked** (the
ADR-XXXX HEADLINE template stays blank; the lock is the next, separate session `prompts/lock_headline.md`).
Upstream FROZEN (s03 calibration; s05 estimator r=0.825; ADR-0019 remodel); s07 untouched.

**Why the decay (reviewer-preempt).** The observed 2H-stoppage λ (0.0816) is ~1.91× the open-play floor
(0.0427) only because it is measured over short, late, high-urgency windows. Counterfactual (unobserved)
added minutes should NOT inherit that full end-game premium — the more time we hypothetically add, the
less productive teams should be. So the λ applied to omitted **2H** minutes decays from the observed
stoppage rate toward the open-play floor as the omitted window grows. This **replaces** the binary
`productivity_premium_knobs: [observed, open_play]` rails, which are exactly the two limits of the decay.

**Model (Method A — exponential, half-life parametrized).** Per marginal omitted 2H minute t:
`lambda(t) = floor + (obs − floor)·0.5^(t/h)`, with closed-form window average over [0,T]
`avg_lambda(T,h) = floor + (obs − floor)·(1 − exp(−kT))/(kT)`, `k = ln2/h`. `obs` = the 2H-stoppage
cell rate (START); `floor` = the `__regular__` open-play cell (FLOOR); `h` = half-life (swept). Per match
`mu_2H = avg_lambda(T_match, h)·olive_2H`. **Decay horizon = the GROSSED-UP clock** (user decision):
`T_match = olive_2H / live_share_2H`, which self-consistently tracks the active gross-up (off→raw omitted
clock; on→one-pass grossed clock; geometric→clock/live_share) so horizon and live-minutes never drift.
Guarded `live_share>0`; recomputed per bootstrap draw (olive varies with the silent estimator-error draw).
**1H is UNCHANGED** (keeps the observed 1H-stoppage λ); decay applies to the 2H window only.

**Knob change** (`config/params.yaml`): `productivity_premium_knobs` → `productivity_decay_halflife_min:
[.inf, 8.0, 4.0, 2.0, 0.0]`. **Reported band = h ∈ [2,8] min; central h = 4** (user 2026-06-19).
`.inf`/`0.0` are regression-test endpoints ONLY (they back out the old two rails). knob_set string now
`"{silent}|{cond}|{source}|hl={h}|{gw}"`.

**Bootstrap honesty.** The 2H decay is a transform of TWO drawn rates, so each iteration draws BOTH the
73-goal 2H-stoppage cell AND the 675-goal `__regular__` floor cell (a second per-match cell index), then
combines via `avg_lambda`. CI now reflects sampling error in both endpoints.

**Two folded-in central flips (confirmed with user 2026-06-19).**
1. **Gross-up central = ON.** The directive's own logic says stoppage time must compensate for the
   stoppages within it, so OFF leaves in-stoppage time-wasting uncompensated. Central knob_set is now
   `silent_marked|overall|pooled_all|hl=4.0|on`. Also REPORTED (not a swept knob): the **geometric
   ceiling** — the z-discounted fixed point `ls/(1−z·(1−ls))` (see z-correction below), the upper rail
   above single-pass ON. Written into the summary as a `…|hl=4.0|geometric` row so the ledger traces to
   a table.
2. **Silent treatment is a POINT, not a band, in the headline.** `silent_none`/`silent_all` are
   KNOWN-WRONG (the model is calibrated to Nate at `silent_marked`); kept in the grid as bounds, but the
   headline reports `silent_marked` and bands only over the legitimate knobs (λ-source, decay half-life,
   gross-up). With silent fixed, assumption-vs-sampling uncertainty drops from **4.0× → 1.3×** (s09-computed;
   the prompt's ~1.6× pre-estimate, same direction).

**Gross-up z-correction (user interrogation, 2026-06-19).** The first build recurred the ENTIRE dead share
`r = 1−live_share ≈ 0.46` as compensable stoppage (implicit `z=1`), which ballooned the geometric ceiling to
`1/live_share` (34.0%) and over-credited single-pass ON. But most dead time is normal flow (throw-ins,
prompt goal kicks) that no ref adds back — only GENUINE stoppage recurs. Measured in regulation from
checkpointed tables: of **44.2 dead min/match**, the s05 estimator counts **16.9 min** as stoppage
(lower_bound + silent_marked), so the genuine-stoppage fraction is **z = 0.382** (`genuine_stoppage_share`
in s08; traces to bip_segments + incident_stoppage; residual silent excluded to match the chosen definition;
user chose `lb+silent_marked` over `lb`-only 0.288). The gross-up now recurs only `z·(1−live_share) ≈ 0.176`:
one-pass live factor `ls·(1 + z·(1−ls))`, geometric limit `ls/(1 − z·(1−ls))`. Because the recurring ratio
drops from ~0.46 to ~0.18, the geometric tail **collapses to just above ON** (the user's original instinct
that the stoppage-within-stoppage tail should be small). The `(1−live_share)` already uses the STOPPAGE-time
dead share (≈0.46 > regulation's 0.447), so the user's "scale up for added time" is automatic — no extra
multiplier. Gross-up OFF is unchanged (no compensation), so the endpoint-regression rails stay byte-identical.

**Results (group=all; not a lock, read before selecting).**
- **Central** `silent_marked|overall|pooled_all|hl=4.0|on`: **1H+2H 23.6% [CI 20.6%, 27.4%]**; 2H_only 16.0%; outcome-flip 12.1% [10.6%, 14.2%].
- **Decay half-life band (gross-up ON)**: 1H+2H h2 22.2% .. h4 23.6% .. h8 24.9%; 2H_only h2 14.4% .. h4 16.0% .. h8 17.4%.
- **Gross-up rails (h=4, z=0.382)**: 1H+2H off 21.1% → on 23.6% → geometric 24.2%; 2H_only off 14.1% → on 16.0% → geometric 16.4%.
- **Endpoint regression (gross-up OFF)** backs out the OLD rails byte-close: h=inf(=observed) 1H+2H 23.8% / 2H_only 17.1%; h=0(=open_play) 2H_only 9.7%. (h=0 1H+2H is **17.0%, not the old 16.3%** — by design the decay floors only the 2H window; 1H keeps observed.)
- Full reported grid range (legit knobs): 10.8% – 37.3%.

**Gate: PASSED.** Full `pytest` green (26/26): `test_s08_decay_endpoints` (endpoint regression + half-life
monotonicity) and `test_s08_avg_lambda_decay` (bounds/limits/monotonicity of `avg_lambda`);
`test_s08_silent_knob_brackets_headline` parses `hl` and drops the geometric row. The z-correction needed
NO test changes (gross-up OFF rails unchanged; ON/geometric carry no hard-coded assertions). s08 grid +
`decay_profile.parquet` regenerated; s09 figures (new permanent **f06_productivity_decay.png**) + ledger
updated; s07 unchanged.

**HUMAN CHECKPOINT next, then STOP — do NOT chain into the lock.** Half-life already decided (central 4,
band [2,8]); confirm the central X% + band visually and the gross-up-ON / silent-point framing. The lock
(`prompts/lock_headline.md`) is its own session.

---

## ADR-0023 — IMPL-7 Parts A.2 + C built: productivity-premium band, O3 gross-up, outcome-flip wired (X% still NOT locked) (2026-06-18)

**Build session, not a lock.** Executed `prompts/impl_7_board_cooling.md` Parts A.2 + C against the
processed tables (Part B de-scoped per ADR-0022; Part A.1 announced-board Δ DEFERRED — see below). The
ADR-0021 directional decisions are now wired into s07/s08/s09 and reproduce their targets exactly.
**X% is deliberately still NOT locked** (the ADR-XXXX template stays blank; the lock is the final,
separate session). Upstream FROZEN (bip.py/s03 r=0.943; s05 estimator r=0.825; ADR-0019 remodel).

**What was built.**
- **Two new knobs** in `params.yaml:counterfactual` → `productivity_premium_knobs: [observed, open_play]`
  and `timewaste_grossup_knobs: ["off", "on"]`. The grid is now 5-axis (silent × cond × source × prem ×
  gw), knob_set string `"{silent}|{cond}|{source}|{prem}|{gw}"`, 96 rows on the `all` group.
- **Productivity-premium band (ADR-0021 #2)** in s08: `open_play` swaps the per-window stoppage λ for the
  cohort's `regular`-play λ on the omitted minutes (helper `regular_lambda_cells`, cell key
  `("__regular__", cohort)`). live_share cancels in μ, so this is a λ choice; the rails are EXACT to
  ADR-0021: 1H+2H **16.3% (open_play floor) .. 23.8% (observed)**; 2H_only **9.7% .. 17.1%**.
- **O3 in-stoppage time-wasting gross-up (ADR-0021 #3)** in s08: `gw="on"` grosses up the omitted CLOCK
  by (1 + timewaste_rate), timewaste_rate = (1 − live_share), so the live factor becomes
  `lsw*(2−lsw)` vs `lsw`. Faithful, RAISES X% (user sign-off, no agenda): central 1H+2H **23.8 → 31.6%**,
  2H_only **17.1 → 23.6%**.
- **Outcome-flip secondary (ADR-0021 #1)** in s08: stricter "different OUTCOME" cut on `state_at_90` —
  tied flips on any extra goal (1−exp(−μ)); lead_by_1 flips when the trailing team (half-rate) equalizes+
  (1−exp(−μ/2)); lead_by_2plus unflippable. Per-knob `pct_outcome_flip`; central **12.2%** (1H+2H) /
  **8.8%** (2H_only). Matches ADR-0021's "≈12.7% illustrative."
- **A.2 time-wasting within played stoppage (Part A)** in s07: dead-ball minutes during the added time
  that WAS played = `played × (1 − live_share)` per (match, half) → `processed/timewasting_descriptive.parquet`.
  Pooled rate **50.6%** (dead/played); mean min/match PRE **3.26** / POST **5.19**. This is the same rate
  the s08 O3 gross-up consumes — one source, no double estimate.
- **s09**: f05 narrowed to the focused band figure (cond=overall, source=pooled_all, 12 rows labelled
  silent × prem × grossup); ledger gains Productivity-premium-band, O3-gross-up, Outcome-flip, and A.2
  sections. **CENTRAL** knob is now the 5-part `silent_marked|overall|pooled_all|observed|off` = 23.8%
  [CI 20.3%, 28.0%].

**Gate: PASSED.** `pytest` green (24/24; `test_s08_silent_knob_brackets_headline` updated to pivot the
5-part knob_set with prem+gw in the index so the none≤marked≤all monotonicity still holds per cell).

**DEFERRED (turnkey, separate session): Part A.1 announced-board under-allocation.** `board_announced`
stays NULL. The SofaScore incidents scrape (314 matches, ~3 h rate-limited, ADR-0020 API) is its own
unit — `prompts/scrape_board_announced.md`. When populated, Δ = `true_stoppage − board_announced`
becomes a full-sample DESCRIPTIVE distortion (never calibrated into the headline; same treatment as the
cooling sensitivity, ADR-0022). User chose "defer scrape; wire plumbing" to keep this session modular
and compute-light (CLAUDE.md §6).

---

## ADR-0022 — R2 resolved: cooling-break detection DE-SCOPED — no robust accuracy gain (2026-06-18)

**Research + read-only empirical check (`prompts/research_cooling.md`); no pipeline change.** The
redesign hypothesised that adding cooling-break duration as PURE stoppage would improve match-level r
vs Nate (IMPL-7 Part B). Tested against the processed tables; the hypothesis is **rejected**, so
cooling detection is **dropped from IMPL-7**. Full writeup: `prompts/research_cooling_findings.md`;
durable pointer in memory `reference_cooling_policy.md`.

**Policy context (why detection was ever in scope).** Mandatory-every-match breaks start at WC2026,
AFTER our sample. In-sample, breaks are rule-triggered: **AFCON2023** had two per match by CAF rule;
**WC2022** had ~none (winter + air-conditioned, WBGT threshold never met); **WC2018/Euro2020/Euro2024/
Copa2024** are temperature-variable (~32 °C WBGT/air trigger, ~30'/75' or ~25', 90s–3min by body).

**Empirical finding (the decisive part).**
1. **Already captured.** On AFCON2023 (breaks guaranteed), the clear break gaps (>120s in the 25'–40'
   window, n=36) average 168s, of which the s05 estimator (`restart_excess` + marker-gated silent)
   ALREADY credits **~122s (73%)**, missing only **~46s/break** (the per-restart allowance shaved off,
   ADR-0017). The "uncounted silent gap" premise is ≤27% true.
2. **No robust r gain (WC2018, the ONLY Nate-validated set; baseline r=0.825 / MAE 2.44).** WC2018
   barely had breaks (4/32 matches >120s gap, 2/32 >150s — the mild-venue prior). A naive "+3 min/break"
   DEGRADES (r→0.780, MAE +1.07) by double-counting the 73% already credited; the correct
   "missed-remainder only" (+~46s) moves r by +0.012–0.014 at strict thresholds but −0.016 at a loose
   one — sign flips with the threshold, i.e. within noise.
3. **Unvalidatable where it matters.** Breaks concentrate in POST (AFCON/Copa), which has no Nate
   ground truth; the one external check (WC2018) can't show a gain.

**Decision.** De-scope cooling detection from IMPL-7 (drop Part B). Do not build the weather-gating /
commentary pipeline. If ever wanted, represent cooling ONLY as a small, clearly-labeled POST-only
sensitivity (~46s/break × detected breaks ≈ ~1.5 min/match on AFCON), shown as a band, never
calibrated into the headline — same treatment as the announced-board under-allocation (ADR-0020).
This does NOT change the frozen s05 estimator or the headline; IMPL-7 now = board_announced
under-allocation (R1/ADR-0020) + Part C band-building (ADR-0021).

---

## ADR-0021 — Headline framing + productivity-premium band (pre-lock DIRECTION; X% still NOT locked) (2026-06-18)

A post-IMPL-6 (ADR-0019) discussion with the user resolved four modeling questions that steer IMPL-7
and the final lock. These are DIRECTIONAL decisions recorded as the source of truth; **X% is still
not locked** (that is the final session). Build the s08/s09 changes in IMPL-7, not before.

**1. Metric framing (extends D1).** Headline = "stoppage time is a sham; measured properly, X% of
matches would have ended with a DIFFERENT SCORELINE" — i.e. ≥1 extra goal in the omitted stoppage
(central 23.8% on the 1H+2H window). ALSO report the stricter "different OUTCOME" cut (winner/draw
status flips), ≈12.7% illustrative (only the 98 tied + 121 lead-by-1 matches can flip; per-team
half-rate split). **Report both; the headline number is scorelines.**

**2. Productivity-premium BAND (new committed sensitivity).** The end-game productivity premium
(final minutes run ~1.4× the match-average pace per clock-minute; observed 2H-stoppage λ=0.0816 vs
open-play 0.0427) reflects urgency that cannot be assumed for ALL the newly-added omitted minutes.
Ship the headline as a band over the λ applied to omitted time:
- **UPPER = observed stoppage λ** (today): 1H+2H **23.8%**, 2H-only 17.1%.
- **LOWER = open-play λ (0.0427)** on omitted minutes: 1H+2H **16.3%**, 2H-only 9.7%.
Honest headline band ≈ **16–24%**, truth nearer the top (omitted minutes are end-of-half, same game
state); 16.3% is the "zero-premium" floor (still ~1 in 6). NOTE: `live_share` CANCELS in mu (it
scales λ up and omitted_live down equally), so mu ≈ goals-per-CLOCK-min × omitted-CLOCK-min — the
band is driven by the λ choice, not by the live-share assumption.

**3. O3 time-wasting gross-up — RESOLVED: implement faithfully (IMPL-7).** Add back, to omitted
CLOCK time, the in-stoppage time-wasting that added time itself generates, then apply productivity to
the live portion. The user accepts this RAISES X% (opposite to the "predicts too many changes" worry)
— **measure faithfully, no agenda.** [[feedback-modeling-decisions]]

**4. First-goal hazard — minor, do NOT overengineer.** P(≥1)=1−P(0 goals) already depends only on the
pre-first-goal hazard, so "I don't care what happens after the first goal" is built into the closed
form (and is exactly why D1's any-goal metric beats the old W/D/L sim — it needs no post-goal state).
Observed λ is mildly inflated by the 8 of 73 2H-stoppage goals that are 2nd+ goals in the same window;
the open-play floor (#2) already brackets that, so leave it. Optional IMPL-7 nicety only: re-estimate
λ on pre-first-goal stoppage minutes.

---

## ADR-0020 — R1 resolved: announced 4th-official board sourceable free (SofaScore) for all six (2026-06-18)

**Research only (`prompts/research_board.md`); no pipeline change. Wiring is IMPL-7.** The redesign
left `board_announced` NULL "pending R1" (DC2); R1 now confirms the announced board (the +X minutes
the 4th official shows at 45'/90', distinct from the time-PLAYED measurement of ADR-0011) is
obtainable FREE for ALL SIX tournaments — better than the redesign assumed (it scoped this as
possibly-NULL / WC2022-only). Full writeup: `prompts/research_board_findings.md`; durable pointer in
memory `reference_board_announced.md`.

**Source = SofaScore unofficial JSON API.** `https://api.sofascore.com/api/v1/event/{id}/incidents`
emits one incident per half: `{"length":9,"time":90,"incidentType":"injuryTime"}` → `length` = the
announced board minutes (integer), `time` 45 = 1H, `time` 90 = 2H. Event IDs via
`…/unique-tournament/{ut}/season/{s}/events/last/{page}` (WC ut=16: 2018 s=15586, 2022 s=41087;
AFCON ut=270: 2023 s=56021; Euro/Copa via `…/search/all?q=`). **Verified populated live** for the
oldest + least-mainstream cases: WC2018 KOR–GER (7659904) 1H+3/2H+9; AFCON2023 NGA–CMR (11940739)
1H+6/2H+10; a 2024-era match (9576070) +2/+4. Strong inference all six covered — still spot-check
Euro2020/Euro2024/Copa2024 with one event each before relying.

This UPDATES ADR-0010's "Sofascore was Cloudflare-blocked" note: the *summary* path was blocked, but
the *incidents* path works. Caveats: unofficial/undocumented, Cloudflare rate-limits (~1 req/25–30s,
UA + sleep), ToS gray area; join to StatsBomb by teams+date; spot-check ~5 `length` values vs
BBC/Guardian live text to confirm it is the announced minimum, not derived. Confirmed dead ends:
StatsBomb (only Half-End timestamps = time played = `played_in_stoppage`), Wikipedia (verified —
goals/cards only), API-Football (`time.extra` = event minute-offset, not the board), results DBs,
and FIFA's public match center (exact figure lives in the non-public referee report).

**Implication for IMPL-7:** populate `board_announced` from `injuryTime.length` (×60 → seconds) for
all six; under-allocation Δ = `true_stoppage − board_announced` becomes a FULL-SAMPLE distortion, not
WC2022-only. The board=time-played MEASUREMENT (ADR-0011) is unchanged — this is the separate
announced number it was always distinct from.

## ADR-0019 — IMPL-6: core remodel built — closed-form any-extra-goal metric, pooled λ, 1H window, board renamed (2026-06-18)

**Human checkpoint — new sensitivity grid produced; X% still NOT locked** (the lock is the
post-IMPL-7 session; ADR-XXXX template below). Executed `prompts/impl_6_remodel.md` against
`docs/redesign.md`. Upstream FROZEN as planned (bip.py/s03 r=0.943; s05 estimator r=0.825 / MAE 2.44;
board=time-played MEASUREMENT ADR-0011, only renamed here; Nate harness). All 24 pytest green; the
re-run is deterministic (central is closed-form; only the CI bootstrap consumes the seed).

Built (D1–D4 + structural, from ADR-0018):
- **Metric (D1, O2).** s08 replaced the 10k W/D/L Monte Carlo with the deterministic closed form
  `mu = sum_h lambda_h*omitted_live_h`, `P(change)=1−exp(−mu)`, `X%=mean(P(change))`. **O2 resolved with
  the user = mean(1−exp(−μ))** (expected share), not count(μ≥1) — the latter is degenerate here (only 1
  match 2H-only / 3 matches 1H+2H reach μ≥1).
- **λ (D2/D3).** `build_lambda_cells` now keys (cohort, window, conditioning); `team_role`/`_role_of`
  DELETED. λ is the **TWO-TEAM rate** = goals-by-either-team / match-live-minute (NOT per-team — the
  per-team framing is a factor-of-2 trap; λ_2H = 73/894.5 = .0816, λ_1H = 23/481.2 = .0478). Central
  source = `pooled_all` (PRE+POST); pooled_pre / pooled_post / regime_matched are sensitivities;
  conditioning overall (default) + tied_nontied (sensitivity).
- **1H window (O1).** **Headline window = 1H+2H** ("≥1 extra goal anywhere"), confirmed with the user.
  Added a 1H-stoppage λ + 1H live-share; s08 computes true_stoppage / played / omitted / omitted_live per
  half. The full-match IMPL-3 residual (24.2s) and estimator σ (MAE·√(π/2)=3.06 min) are split across
  windows by addable share f2=0.628 / f1=0.372 — one shared estimator draw E, applied ts_1H+=E·f1,
  ts_2H+=E·f2 (reduces to the old 2H-only σ when 1H is dropped). O1 caveat stands: a 1H extra goal is a
  bonus increment; game state is NOT propagated.
- **Rename (DC2).** s06a writes `played_in_stoppage.parquet` (col `played_in_stoppage_min`, =
  period_end−2700, numerically identical to the old board_min — verified max|Δ|=0.000) + a NULL
  `board_announced` for the future 4th-official number (R1). s07/s08/s09/nate.py read the renamed file;
  raw CSV layer (board_statsbomb.py / board_added_time.csv) unchanged. board_statsbomb.py:38 confirms the
  "board" was always time-played, never the announced number — the misnomer is fixed.
- **DC1.** s07 rebuilds stoppage_live_share from segments SPLIT at the 45:00/90:00 boundary (the old code
  keyed on the segment-START phase label, mis-binning every straddling segment → 811 vs 894.5 2H team-min).
  A hard assert now guarantees live-share live-seconds == match_minutes ledger (max diff 0.00s), so λ
  exposure and productivity share ONE table.
- **DC3.** s09 f01 drops extra-time buckets (≥10) so the spurious minute-120 ET/penalty spike no longer
  reads as penalties contaminating regulation scoring.

New grid (group=all, window=1H+2H; X% = mean P[≥1 extra goal], CI = per-cell Jeffreys-Gamma λ +
silent_marked estimator-error bootstrap):
- **Central silent_marked | overall | pooled_all: 23.8% (95% CI 20.4–27.9%).** Same knob, 2H_only: 17.1%.
- By silent treatment (min–max across conditioning×source, 1H+2H): none 12.5–14.9%, marked 22.6–26.1%,
  all 32.1–36.4%. Full grid 12.5–36.4%.
- Monotonic none≤marked≤all in all 144 (window×group×cond×source) cells; every point sits inside its CI
  (the central estimate is analytic now, so the ADR-0008 two-stream "point a hair outside band" wart is gone).

Vs ADR-0017/0018: the marked↔all silent band is still the dominant uncertainty (≈ +10 pt none→marked→all)
— the remodel did NOT narrow it (expected; D4 keeps none/all as definitional rails, not estimates).
Conditioning barely moves X% (overall vs tied_nontied within ~0.3 pt → confirms D2). pooled vs pre/post is
modest (pre ~+2–3 pt with wide CIs from thin PRE counts → confirms D3). Adding the 1H window lifts the
headline ~+6.7 pt (17.1→23.8%) — a real previously-omitted window, not a knob artifact.

Still OPEN (not this session): O3 within-stoppage time-wasting + announced-board under-allocation +
cooling-break stoppage = IMPL-7, pending research R1/R2. X% LOCK = the session after IMPL-7.

## ADR-0001 — Core dataset locked (2026-06-15)
Six tournaments, all in StatsBomb open data with full events. PRE (under-adding,
pre-directive): WC 2018, Euro 2020 → 115 matches. POST (accurate/over-adding): WC 2022,
Euro 2024, Copa América 2024, AFCON 2023 → 199 matches. IDs verified against open-data
`competitions.json` on 2026-06-15 and stored in `config/tournaments.yaml`. AFCON 2023 is
named "African Cup of Nations" upstream (comp 1267 / season 107).

## ADR-0002 — No xG (2026-06-15)
Metrics are goals per live-minute (primary) and shots / shots-on-target per live-minute
(companion, higher event volume = variance reducer). Avoids xG model dependence.

## ADR-0003 — Gap-method ball-in-play, calibrated (2026-06-15)
Dead time = gap from a possession's last event to the next restart event, where restart
play_patterns are From Throw In / Corner / Free Kick / Goal Kick / Kick Off / Keeper
(`params.yaml:bip.restart_play_patterns`). Calibrated against Opta's published WC2022
58:04 (3484s). **s03 calibration gate PASSED**: pooled WC2022 regulation BIP = 3460s
(57.67 min), 24s under target (tolerance ±90s); in-play share 0.569 (sane 0.55–0.60).
Two structural rules together produce this (see ADR-0009): possession-boundary restart
detection + a 20s max-live-gap. `bip.min_dead_gap_s` stays 0.0; the load-bearing knob is
`bip.max_live_gap_s = 20.0`.

## ADR-0009 — Two BIP corrections to pass calibration (2026-06-15)
Two bugs/refinements were needed for s03 to calibrate:
1. **Possession-boundary restart detection.** StatsBomb sets `play_pattern` on *every*
   event of a possession, not just its restart. Reading the pattern per-event flagged
   nearly every intra-possession interval of a set-piece-originated possession as dead
   (BIP collapsed to 27.85 min). Fix: an interval is a restart-dead only at a possession
   boundary (`possession` changes) whose new possession begins with a restart pattern.
   This required carrying the `possession` column through s02.
2. **Max-live-gap rule.** Restart-pattern detection alone over-counted in-play (64.66 min)
   because long silent stretches (injury, VAR, slow restarts within a possession) carry no
   restart event. In active play StatsBomb logs an event every few seconds, so any
   inter-event gap ≥ `bip.max_live_gap_s` (20s) is treated as dead regardless of pattern.
   Swept 6–30s; G=20 → 3460s (24s under target). G∈[15,25] all land within tolerance, so
   the result is not knife-edge.

## ADR-0004 — Disk-safe ingest (2026-06-15)
Machine had ~2.7 GB free at setup. We never clone open-data and never touch 360 data.
s01 caches only the small per-tournament match-list JSON in `raw/statsbomb/`. s02 fetches
each match's event JSON **in memory** and discards it after parsing — nothing large lands
on disk. Trade-off: re-running s02 re-downloads events (cheap, idempotent) instead of
reading a local cache. Deviates from a literal "immutable raw event cache" for disk safety.

## ADR-0005 — Phase taxonomy includes extra_time (2026-06-15)
Spec lists phases {regular, 1H_stoppage, 2H_stoppage}. The dataset has knockout matches
with extra time; we add a fourth label `extra_time` (periods ≥ 3) so ET play is not
misattributed to regulation buckets. Productivity-in-stoppage analysis still focuses on
1H_stoppage / 2H_stoppage.

## ADR-0006 — events_norm carries two helper columns (2026-06-15)
Beyond the data-dictionary minimal columns, `events_norm` also carries `shot_outcome`
(for s04 goal detection) and `card` (for s05/s06b). This avoids re-fetching all event JSON
twice more over the network, at the cost of two extra columns.

## ADR-0007 — VAR fallback estimator only (2026-06-15)
s06b implements the spec's FALLBACK (decision-event excess over the tournament median
goal-celebration gap), not live commentary scraping. Decision events are limited to goals
and red/second-yellow cards (penalty awards and overturned offsides need nested fields not
carried), so `var_s` is itself a lower bound. VAR matters only for the s05 attribution.

## ADR-0008 — Counterfactual CI via Gamma-posterior bootstrap (2026-06-15)
Central per-match p_flip from N=10,000 seeded Poisson sims (per spec). The outer CI
bootstraps λ from its Jeffreys Gamma posterior (Gamma(count+0.5, exposure)) and uses the
exact analytic flip probability per draw (fast, avoids 10k×1k×matches sims). full_measure_538
true_stoppage knob is not yet wired to per-match 538 data and currently falls back to
lower_bound — revisit if 2018 538 per-match measures are sourced.

**Vectorization + two RNG streams (2026-06-15).** The original analytic flip prob was a
pure-Python i,j double sum called ~8.5M times → s08 ran 17+ min. Rewrote it as an
outer-product over truncated Poisson pmfs (k=0..14) with a precomputed sign/flip mask
(`_analytic_pflip`, verified identical to the loop within 1.3e-15), replaced the per-call
scipy pmf with a manual numpy pmf + cached factorials, and the bootstrap is now an einsum
over all matches per draw. Runtime: 17 min → 23 s. Critically, the headline central MC and
the CI bootstrap now draw from **two independent streams** (`seed` and `seed+1`): the
published X% must not move when bootstrap RNG consumption changes. Headline math unchanged.

## ADR-0010 — Board added time scraped from ESPN (2026-06-15)
The fourth-official board number is not in StatsBomb. Sourced it from ESPN's public soccer
summary API (`site.api.espn.com`): the "First Half/Second Half ends" commentary markers are
stamped `45'+X'` / `90'+Y'`, i.e. added minutes played — which slightly OVER-estimates the
announced board (play finishes the minute in progress). That is the conservative direction
for the counterfactual: omitted = max(0, true_stoppage − board) shrinks, so the headline
cannot be inflated by this source. (Sofascore was Cloudflare-blocked.) Matched 314/314 via
date+teamset with a ±1-day, score-validated fallback (US-evening Copa kickoffs land on the
adjacent UTC calendar day). Mean total board ≈ 9.9 min/match; PRE ≈ 8.0, WC2022 ≈ 12.4 —
within s06a reference bands. `src/scrape_board_espn.py`; cache `raw/board/board_added_time.csv`.
Caveat: true_stoppage (s05 lower_bound) UNDER-states real dead time while board OVER-states
the announced number, so measured omitted minutes (mean 1.5, positive in 49% of matches) are
doubly conservative — real omitted time is larger than what the headline X% reflects.

## ADR-0011 — Board redefined as precise time-played from StatsBomb half-end (2026-06-15)
Supersedes the board *source* in ADR-0010 (not its conservative-direction reasoning). Item 1
redefined the "board" as the precise time **actually played** in each regulation half (Nate
Silver's "ACTUAL" column), aligning with how Nate measured added time and giving one figure
available across all six tournaments.

The ESPN scrape cannot deliver this. ESPN freezes its match clock at 45:00 / 90:00 during
added time in *every* feed (commentary, summary keyEvents, core play-by-play) and only exposes
the rounded-up whole-minute label (`45'+3'`). That over-reads Nate by ~1.5 min (MAE 1.46,
bias +1.46) and caps correlation at **r=0.943** — `r` is invariant to any affine correction,
so no calibration can pass the Item 1 gate (r>0.95). ESPN's one second-level signal, the
broadcast `wallclock` on period-boundary markers, was overwritten on ~half the markers by an
2024-04-10 re-ingestion, leaving only 5/32 WC2018 matches with both halves intact (one already
negative). So precise played time is not recoverable from ESPN at the required resolution.

StatsBomb's `Half End` event carries a second-level whistle timestamp, and s02 already surfaces
it as `p1_end_s` / `p2_end_s` on matches.parquet (verified identical to the Half End `period_s`,
diff 0.0). Precise played board = `period_end_s − 2700`. Validated against Nate's 32 published
WC2018 matches: **MAE 0.135 min (~8s), bias +0.10 min, r=0.992, max abs err 0.78 min** — a
second-level, all-six-tournament, fully local source with no scrape and no external dependency
(the board is now regenerable, not "the one unavoidable external input"). New generator
`src/board_statsbomb.py`; cache `raw/board/board_added_time.csv` now holds float `board_min`
(minutes) with `source=statsbomb`. s06a unchanged: 314/314 matches join; PRE mean 6.8 min,
WC2022 11.4 min (both within reference bands). `scrape_board_espn.py` is retained only as an
optional sensitivity path (e.g. the 2018-only *announced* 4th-official board). s08/s09 NOT
re-run this session per the modular-session rule.

## ADR-0012 — Nate 538 ground truth checked in + shared validation harness (2026-06-15)

The silent-component fix (IMPL-1→IMPL-4) hinges on validating against Nate Silver's WC2018
numbers, but those numbers previously existed only in a session transcript and a JPG in
`~/Downloads`. Per CLAUDE.md §6 (validate against an EXTERNAL ground truth that is actually
durable), the 32-match table is now transcribed and checked in at
`data/raw/nate_2018/nate_wc2018.csv` (home, away, `bip`, `expected`, `actual`), so the project
no longer depends on the external file.

Shared harness `src/lib/nate.py` exposes the three validation arms and reconciliation. The
column→quantity mapping is load-bearing and easy to get wrong, so it is fixed here and in the
module docstring: **`bip` → s03 ball-in-play** (IMPL-2 promote-gate, r≥0.94); **`expected` →
true-stoppage estimator** (IMPL-3 gate — the "should-be-added" model, mean ~13.2 min, e.g.
Germany–Sweden 8:56); **`actual` → precise time-played board** (already validated, regression
guard). Crossing `expected`/`actual` would silently corrupt the estimator and the headline
counterfactual.

Reconciliation is on the UNORDERED, name-normalized team pair within wc_2018 — 538 flips some
home/away (its "Iceland–Nigeria" is StatsBomb "Nigeria–Iceland") and spells "S. Korea" where
StatsBomb has "South Korea"; `nate.reconcile()` raises if any of the 32 fails to map.
`tests/test_nate.py` (4 tests, green) guards: table parses + 538's printed DIFF is consistent;
`expected` mean is the ~13.2 min level (not `actual`); all 32 reconcile to distinct match_ids;
and the harness reproduces the validated board fit. Reproduced live: **BIP arm r=0.943,
MAE 1.25 min** (the IMPL-2 baseline) and **board arm r=0.992, MAE 0.134 min** (matches ADR-0011)
— i.e. the harness is correct against two independent ground-truth points before any IMPL
session runs. No pipeline stage re-run; this is scaffolding only.

## ADR-0013 — IMPL-1: out-of-play markers plumbed through s02 (2026-06-15)

The marker-gated silent reclassifier (IMPL-2) needs StatsBomb's intrinsic ball-out-of-play
signals, but s02 previously projected only `out`/`off_camera`/`shot_outcome`/`card`. IMPL-1 adds
three more raw fields to `interim/events_norm.parquet`, one column each — data prep only, nothing
consumes them yet:
- `pass_outcome` ← `pass.outcome.name` (e.g. "Out", "Injury Clearance", "Incomplete", "Offside").
- `gk_type` ← `goalkeeper.type.name` (e.g. "Collected", "Smother", "Save", "Shot Faced").
- `gk_outcome` ← `goalkeeper.outcome.name`.
(`out` was already projected at `s02_normalize.py:49`; left as-is.) All used the
`(e.get(x) or {}).get(y) or {}` guard so a present-but-null sub-object doesn't raise.

**Gates green.** s02 re-run (314 matches, 1,106,277 rows): clock monotonic, period lengths sane,
same 3 pre-existing P1-length warnings — gate PASSED. s03 re-run UNCHANGED: WC2022 pooled
regulation BIP 3460s (within ±90s of 3484s), in-play share 0.569 — calibration identical, since
the new columns are not yet consumed.

**Spot-check (recorded per gate).** Whole-corpus non-null: `pass_outcome` 5.2%, `gk_type` 0.85%,
`gk_outcome` 0.38%; `out` is bool, always present, True on 6,977 events. `pass_outcome`
value_counts: Incomplete 48,551 / **Out 5,471** / Unknown 1,895 / Pass Offside 897 / Injury
Clearance 305. The `out=True` flag lands mostly on Block/Clearance/Miscontrol (the ball physically
leaving), not on Pass/Carry as the prompt loosely framed it — expected for StatsBomb; IMPL-2's
marker set must therefore OR `out` together with `pass_outcome="Out"` etc., not rely on `out`
alone. `gk_type` is 100% non-null on the 9,454 `Goal Keeper`-type events (note: the event type is
"Goal Keeper" with a space). Per-tournament one-match spot-check confirmed the SAME populated
schema in all six (pass_outcome non-null ~3.5–6.9%, gk_type ~0.7–1.0%, "Out" present everywhere) —
e.g. wc_2018 m7525 had out=0 but "Out"=29, i.e. some matches encode out-of-play via `pass_outcome`
rather than the `out` flag, reinforcing the OR-the-signals requirement for IMPL-2.

## ADR-0014 — IMPL-2: marker-gated reclassifier BLOCKED — regresses validated BIP, NOT promoted (2026-06-15)

**Decision: do NOT promote marker-gating into `bip.py`. Pipeline left at the ADR-0013 baseline.
The IMPL-2 promotion gate cannot be met; this is a human checkpoint for the user.**

Built the marker-gated silent reclassifier per `prompts/impl_2_reclassify_bip.md`: a candidate
silent gap (no restart `play_pattern` at the trail edge, gap ≥ `silent.min_silent_gap_s`=20s) is
dead iff its LEAD edge carries an out-of-play marker (`out=True`; `pass_outcome∈{Out,Injury
Clearance}`; `shot_outcome∈{Off T, Saved Off Target, Wayward, Blocked, Goal}`; `type∈{Foul
Committed, Offside, Bad Behaviour, Substitution, Player Off, Injury Stoppage, Referee Ball-Drop,
Half End}`), with special-case (B) keeping a keeper-held live ball live. The function is drafted in
`src/lib/silent.py` (kept, unwired). The validation harness used below is `src/lib/nate.py`
(reproduced the documented baseline exactly: old `gap≥20` rule → r=0.943, MAE=1.25, pred mean 56.0).

**The promote-gate failed and cannot be re-tuned to pass.** Promoting marker-gating moves seconds
dead→live, so per-match WC2018 regulation BIP vs 538:

| classifier (WC2018, vs 538 `bip`) | pred mean (min) | r | MAE (min) | WC2022 pooled Δ vs Opta 3484s |
|---|---|---|---|---|
| baseline `gap≥20` (ADR-0013) | 56.0 | **0.943** | **1.25** | −24s ✅ |
| prescribed marker set only | 64.5 | 0.765 | 9.20 | +183s ✗ |
| + "Foul Won" added | 61.6 | 0.863 | 6.26 | +90s |
| + Foul Won + off_camera + residual gap R=45s | 59.1 | 0.920 | 4.00 | +32s ✅ |

Lowering `min_silent_gap_s` to 8s does not help (pooled BIP floors at +148s). Best achievable with
a generous, still-principled marker set is **r≈0.92, MAE≈4.0 — a clear regression** below the
required r≥0.94 / non-regressed gate. Per the prompt's explicit instruction ("if BIP cannot
re-validate, STOP — the marker logic is suspect — bring it to the user; do NOT fall back to an
estimator-only patch") I stopped and reverted `bip.py`, `s03_bip.py`, `config/params.yaml`,
`tests/test_lib.py` to HEAD. s03 re-verified green at the baseline (3460s, share 0.569).

**Root-cause finding (the important part).** The premise behind marker-gating is falsified *for
BIP*: 538's WC2018 regulation BIP mean is **55.3 min — BELOW** the old duration rule's 56.0 min, so
538 counts the long silent gaps as MORE dead, not less. Reclassifying them as live therefore moves
BIP AWAY from truth. Diagnostic over the 1,068 ≥20s non-restart gaps in WC2018: only **25% carry a
lead-edge marker** (12,137s); the other **75% (32,436s ≈ 17 min/match) are unmarked yet genuinely
dead**, led by `Foul Won` (260 — StatsBomb logs Foul Committed *and* Foul Won as a pair and Foul
Won is frequently the trailing event; the prompt's set listed only Foul Committed), `Goal Keeper`
non-hold (278), `Ball Receipt*`/`Miscontrol`/`Block`/`Clearance` (open-play actions where the ball
left play but no flag was set), and `Camera off` (20). StatsBomb simply does not stamp a
machine-readable marker on most genuinely-dead silent gaps, so a marker-gated definition that is
correct for the stoppage estimator is NOT automatically correct for BIP — the "one shared
classifier" hypothesis, as specified, does not hold. The smell-test step (OLD vs NEW per-match
silent totals) was not reached because the gate halts first.

**Follow-up investigation (user asked to dig deeper before deciding).** Decomposed regulation
dead time per WC2018 match into `restart` (normal-flow restart-boundary dead, ~28.9 min),
`silent_marked` (≥20s non-restart gaps WITH a lead-edge marker, ~3.7 min) and `silent_unmarked`
(≥20s non-restart gaps WITHOUT a marker, ~8.4 min), then correlated each against Nate's columns.
Two findings reframe the whole effort:

1. **The marker test is the WRONG tool for BIP but the RIGHT tool for the stoppage estimator.**
   r vs Nate `expected` (the should-be-added target, mean 13.2): `silent_marked` **+0.708**,
   `silent_unmarked` **+0.248** (a near-flat ~8.4 min baseline in every match, std 2.5 — noise for
   stoppage), `injury_s` +0.679, `lower_bound_s` +0.655, `restart` +0.150. The marker test cleanly
   SPLITS the silent bucket into a stoppage-predictive part (marked) and a flat non-addable
   baseline (unmarked).
2. **The over-count is an ATTRIBUTION error, not a live/dead error.** The unmarked silent gaps are
   genuinely dead (BIP needs them), but crediting them as *addable* stoppage adds a flat ~8.4 min
   to every match. Candidate stoppage estimators vs `expected` (mean 13.2): `lb + all silent`
   r=0.752 but **mean 19.7 (the over-counter — Germany-Sweden signature)**; `lb + marked silent`
   **r=0.768, MAE 3.15, mean 11.3**; `marked silent + calibrated constant` **r=0.708, MAE 2.22,
   mean 13.2**. Marker-gating the SILENT TERM removes the over-count and lifts r from ~0.61 to
   ~0.77 — but inside s05, not in bip.py.

**Recommendation:** abandon the bip.py promotion and the "one shared classifier" decision (BIP
wants *total* dead time; stoppage wants only the *addable* subset — genuinely different questions).
Apply marker-gating ONLY to the s05 stoppage silent term in IMPL-3 (`silent.py` is ready for this).
Note the IMPL-3 ceiling looks ~0.77, short of the findings' ≳0.85 hope — flag when scoping IMPL-3.

## ADR-0015 — Silent-component direction RATIFIED: bip.py frozen, marker-gating to s05, external data declined (2026-06-15)

**User ratified the ADR-0014 recommendation and rescoped the remaining work.** Three decisions:

1. **`src/lib/bip.py` and s03 are frozen as the validated duration rule.** The "one shared
   live/dead classifier" hypothesis (originally DECIDED in `silent_component_findings.md` §"one
   classifier in bip.py") is FALSIFIED and abandoned. BIP = TOTAL dead time; stoppage = ADDABLE
   dead time — different questions. BIP genuinely needs the unmarked silent gaps (538 WC2018 BIP
   55.3 < duration rule 56.0); marker-gating them regresses BIP (r 0.943→≤0.92). Do not re-open
   s03 calibration for this.

2. **Marker-gating (`src/lib/silent.py`) is applied ONLY to the s05 stoppage silent term (IMPL-3,
   rescoped).** This is the one validated win: it splits the silent bucket into a stoppage-
   predictive marked part (r=0.708 vs `expected`) and a flat non-addable unmarked baseline
   (r=0.248); `lb + marked silent` → r=0.768. **The IMPL-3 gate is RESET: target ~0.77, not the
   findings' ≳0.85** — StatsBomb marks only ~25% of silent gaps and never marks addable-ness, so
   ~0.77 is the realistic free-data ceiling. `prompts/impl_3_estimator_validate.md` and
   `next_session.md` rewritten accordingly.

3. **External datasets DECLINED for the silent-component goal.** Surveyed Wyscout/Pappalardo,
   FIFA effective-playing-time, CIES, DFL/IDSSE, Metrica, SkillCorner (saved to memory
   `reference_external_datasets.md`). Mechanics of the decline: these sources label ball-out
   *timing* (the BIP axis, already r=0.943), NOT addable-ness (the hard part); the one with a free
   per-gap marker StatsBomb lacks (Wyscout interruptions) covers WC2018 only — duplicating Nate's
   ground truth and never reaching the POST tournaments the headline depends on. Better ball-out
   timing would push more flat non-addable seconds INTO the silent bucket, the wrong direction for
   stoppage. Kept only as an optional triangulation footnote, not a model input.

**Honest ceiling statement (for the article):** the silent component cannot be measured precisely
with free data. Rather than ship a false-precision point estimate, IMPL-4 makes the silent
treatment an explicit s08 sensitivity knob (`silent_none` / `silent_marked` / `silent_all`) and
propagates the ~±2–3 min estimator MAE into the bootstrap CI. The decisive question becomes whether
the headline X% is robust to the silent assumption — if so, the residual uncertainty does not
threaten the claim; if not, it ships as a reported band. This is consistent with CLAUDE.md §1
(X% ships with a CI and sensitivity table, never as a bare point estimate).

## ADR-0016 — IMPL-3: marker-gated true-stoppage estimator built in s05, validated vs Nate (2026-06-16)

**Human checkpoint.** Built the corrected true-stoppage estimator IN s05 (not bip.py — s03 is
frozen, ADR-0015):
`true_stoppage = lower_bound (existing) + marker-gated silent + residual constant`. `bip.py`,
`s03_bip.py` UNCHANGED (verified clean); s03 still calibrated (test green). The estimator validates
against Nate's **`expected`** column (the should-be-added model, mean ~13.2 min), NOT `actual`.

**What was added.**
- `src/lib/silent.py:marked_silent_intervals` — of the ≥`silent.min_silent_gap_s` (20s) non-restart
  gaps, credit ONLY those whose LEAD edge carries an out-of-play marker (`out`; `pass_outcome∈{Out,
  Injury Clearance}`; `shot_outcome∈{Off T, Saved Off Target, Wayward, Blocked, Goal}`; `type∈{Foul
  Committed, Offside, Bad Behaviour, Substitution, Player Off, Injury Stoppage, Referee Ball-Drop,
  Half End}`), minus the keeper-holding-a-live-ball special case. Unmarked silent gaps are dropped —
  genuinely dead (s03 BIP keeps them) but a flat ~8.4 min/match non-addable baseline; crediting them
  is the over-count (the Germany–Sweden 19.8-vs-8.9 signature).
- The lower-bound components (celebration/sub/card/injury ∩ s03 dead) are UNCHANGED — s05 lower-bound
  gate still passes. `silent_marked_s` added per match-period to `incident_stoppage.parquet`; a new
  per-match `interim/true_stoppage.parquet` (lower_bound_s, silent_marked_s, residual_silent_s,
  true_stoppage_s) is the checkpointed estimator table.
- **Residual constant** `silent.residual_silent_s = 114.0` (1.90 min): fit on 2018 as
  mean(Nate `expected`) − mean(lower_bound + marked silent) over the 32 WC2018 matches (13.16 − 11.26).
  FROZEN; the SAME constant applies to all six tournaments (POST has no ground truth to fit on).

**Validation (32 WC2018 matches vs Nate `expected`, ablation):**

| estimator | r | MAE (min) | mean (min) |
|---|---|---|---|
| lower_bound only | 0.655 | 5.72 | 7.53 |
| + marker-gated silent | **0.768** | 3.15 | 11.26 |
| + residual constant (estimator) | **0.768** | **2.75** | **13.16** |
| *(ref) lower_bound + ALL silent (old over-counter)* | 0.752 | 6.60 | 19.69 |

Nate `expected` mean = 13.16. **Gate met:** beats the 0.61–0.73 baseline, lands the reset ~0.77
target (r=0.768); aggregate mean matches Nate at the ~13 min level. The residual is a flat constant,
so it does not change r; it centers the mean and cuts MAE 3.15→2.75.

**Diagnostic (the decisive test — vs the old over-counter):** marker-gating collapses the low-injury
over-count without breaking the injury-dominated matches.

| match | over-counter err | estimator err | Nate |
|---|---|---|---|
| Germany–Sweden (LOW) | +10.9 | +3.3 | 8.9 |
| Russia–Egypt (LOW) | +6.9 | −0.7 | 8.1 |
| Uruguay–Saudi (LOW) | +7.5 | +0.9 | 8.4 |
| Belgium–Panama (HIGH) | +6.1 | +0.2 | 14.3 |
| Tunisia–England (HIGH) | +8.7 | +3.3 | 17.6 |

The two residual over-shoots (Germany–Sweden, Tunisia–England, both +3.3) are the flat-constant
limitation: +1.9 min is added even to matches the marker term already nailed. This is the honest
price of a single calibrated constant and is well inside the band.

**Coverage flag (load-bearing for the article).** Nate validates **WC2018 ONLY**. The POST
tournaments (where the headline lives) are validated only INDIRECTLY — via the frozen 2018 residual
calibration + s03's WC2022 Opta BIP gate. The estimator's all-314-match mean is 16.8 min (POST runs
hotter than 2018, as expected). The silent component cannot be measured precisely with free data
(StatsBomb marks only ~25% of silent gaps and never marks addable-ness, capping r≈0.77); IMPL-4
turns the silent treatment into an explicit s08 sensitivity knob and propagates the ~±2.75 min MAE
into the CI, so X% ships with a band, not false precision (CLAUDE.md §1).

## ADR-0017 — IMPL-5: restart-excess folded into the s05 estimator; residual re-fit; Task B dropped (2026-06-17)

**Human checkpoint.** Made the s05 true-stoppage estimator more precise by crediting routine
**restart time-wasting** — the gap that swung X% 3%→12% across the silent knob (ADR-0016 / IMPL-4)
motivated tightening the per-match estimator before locking X%. `bip.py`/s03 stay FROZEN
(ADR-0014/0015); this changed only the ADDABLE-stoppage estimator (`src/s05_incident.py`,
`config/params.yaml`). `src/lib/silent.py` is UNCHANGED (Task B dropped — see below).

**Task A — Nate's per-restart allowances (KEPT).** A throw-in dragged to 50s or a goal kick to
40s with no foul/sub/injury was credited ZERO in every knob (silent.py EXCLUDES restart-boundary
gaps by design; lower_bound only caught them where they overlapped a foul/sub window). Added a
`restart_excess` component to s05's `comp`: for each routine restart-boundary gap, credit
`max(0, gap − allowance)` as the tail `[last + allowance, restart]`. Allowances
(`params.yaml:incident.restart_normal_s`, FIT/FROZEN on 2018, applied to all six):
Throw In 20s · Goal Kick 30s · Corner 45s · Free Kick 60s. `From Kick Off` (celebration) and
`From Keeper` (largely live) are EXCLUDED. It is identifiable (restart-tagged), so it folds into
the `lower_bound` union and rides the existing intersect-with-dead machinery — deduped against the
card/sub windows (no double-count of a foul→free-kick) and the gate `lower_bound_s ≤ total dead`
holds by construction (every excess interval ⊂ its dead gap ⊂ s03 dead). It belongs in
`lower_bound_s`, which also raises the `silent_none` floor in s08. `lower_bound_base_s`
(the ADR-0016 lower bound, sans restart_excess) is kept as a column for the ablation.

**Validation (32 WC2018 matches vs Nate `expected`, full-match totals, ablation):**

| estimator | r | MAE (min) | mean (min) |
|---|---|---|---|
| lower_bound (celeb/sub/card/injury) | 0.655 | 5.72 | 7.53 |
| + restart_excess | 0.754 | 4.28 | 9.03 |
| + marker-gated silent | **0.825** | 2.49 | 12.76 |
| + residual constant (estimator) | **0.825** | **2.44** | **13.16** |
| *(ADR-0016 estimator, no restart_excess)* | 0.768 | 2.75 | 13.16 |

**Gate BEATEN:** restart_excess lifts r 0.655→0.754 on its own axis (NOT capped by the ~0.77
silent-marker ceiling — it attacks restart time-wasting, a different signal), and the full
estimator hits **r=0.825 / MAE 2.44**, beating ADR-0016's 0.768 / 2.75 on BOTH axes. The residual
is a flat constant, so it does not change r; it re-centers the mean to Nate's 13.16.

**Diagnostic (estimator error, minutes) — low-injury shrinks, injury-dominated holds:**

| match | over-counter | ADR-0016 est | IMPL-5 est | Nate |
|---|---|---|---|---|
| Germany–Sweden (LOW) | +10.9 | +3.3 | +2.5 | 8.9 |
| Russia–Egypt (LOW) | +6.9 | −0.7 | +0.1 | 8.1 |
| Uruguay–Saudi (LOW) | +7.5 | +0.9 | +1.4 | 8.4 |
| Belgium–Panama (HIGH) | +6.1 | +0.2 | −0.6 | 14.3 |
| Tunisia–England (HIGH) | +8.7 | +3.3 | +3.0 | 17.6 |

**Task B — marker refinements (DROPPED; no variant beat the bar).** Tested vs Nate `expected`
(lb fixed with restart_excess; flat residual re-centered per variant). The single lead-edge marker
test (r=0.825) is the best; every refinement REGRESSES it:

| variant | r | MAE | marked cov (32-match) | why dropped |
|---|---|---|---|---|
| baseline (single lead edge) | **0.825** | 2.44 | 119 min | — (kept) |
| lead-window K=2 | 0.804 | 2.98 | 317 min | over-credits (false positives); re-inflates Ger–Swe +2.5→+3.9 |
| lead-window K=3 | 0.812 | 3.13 | 330 min | same — a marker on a *nearby* event ≠ this gap was dead |
| trail = restart pattern | 0.765 | 2.06 | 25 min | guts coverage; r below the 0.768 bar (most marked trails are "Regular Play", not restarts) |
| trail = possession change | 0.701 | 2.58 | 47 min | over-tightens; r collapses |
| lead-window + trail-poss combos | 0.70–0.73 | — | — | all below bar |

So the lever that could narrow the silent band (`silent_marked`→`silent_all`) did NOT pan out:
widening marker coverage pulls in sparse-logging false positives (the Germany–Sweden confound
returns) and tightening it drops genuine stoppage. **Honest conclusion (anticipated in the prompt):
the silent uncertainty is irreducible with free StatsBomb data.** restart_excess raises the
`silent_none` FLOOR (it is now identifiable lower_bound, not silent), which should tighten the band
from below — but the `marked`↔`all` width is unchanged. Whether the headline is now lockable is for
IMPL-4 to re-measure; X% likely still ships as a band, which is a legitimate, publishable finding.

**Re-fit + frozen constants (params.yaml).** Adding restart_excess raised the mean, so the residual
was re-fit on 2018 (`residual = mean(Nate expected) − mean(lower_bound + marked_silent)` =
13.160 − 12.757 min):
- `incident.restart_normal_s`: {Throw In 20, Goal Kick 30, Corner 45, Free Kick 60} s — NEW, frozen.
- `silent.residual_silent_s`: 114.0 → **24.2** s (re-fit).
- `silent.estimator_pearson_r`: 0.768 → **0.825**; `silent.estimator_mae_min`: 2.75 → **2.44**
  (IMPL-4 reads MAE as the 2H-scaled per-match sigma).

**Net effect / sanity.** WC2018 net restart credit +1.50 min/match (marked_silent 3.73); all-314
mean true_stoppage 16.8 → **17.78 min**; POST runs hot as expected (Copa 25.3, AFCON 23.5, WC2022
17.5) — consistent with more routine late-game restart management in recent tournaments. New columns
`restart_excess_s`, `lower_bound_base_s` on `incident_stoppage.parquet`; `true_stoppage.parquet`
now includes restart_excess via `lower_bound_s`. s05 gate green; s06b re-run to repopulate `var_s`
(s05 had reset it); **all 23 pytest green**.

**Coverage flag (unchanged, load-bearing).** Nate validates **WC2018 ONLY**. POST is validated
INDIRECTLY — frozen-on-2018 allowances + residual + the s03 WC2022 Opta BIP gate. The allowances
and residual are fit on 2018 and applied unchanged to all six.

**Next: re-run IMPL-4** (`prompts/impl_4_counterfactual_lock.md`) in a SEPARATE session — s08 grid
+ s09, to see if the tighter estimator (higher floor, r 0.768→0.825) moved the central / narrowed
the band, then lock X%.

## ADR-0018 — Headline model reopened at first principles; metric/λ redesigned; X% LOCK PAUSED (2026-06-17)

**Human checkpoint — DECISIONS recorded, NOT a number.** After the IMPL-4 re-run grid (silent_marked
~8.1–9.9% but the silent band did not narrow, ADR-0017), the user reopened the headline model at first
principles. X% is **deliberately NOT locked**; the ADR-XXXX headline template below stays blank until
the remodel (IMPL-6) + distortion add-ons (IMPL-7) are built and re-validated. Full spec:
`docs/redesign.md`. Sequencing + turnkey prompts: `next_session.md`. Upstream stays FROZEN (bip.py/s03
r=0.943; the s05 estimator r=0.825 — ADR-0014/0015/0016/0017; the board=time-played MEASUREMENT
ADR-0011, only RENAMED here, number unchanged; the Nate harness).

Decisions:
- **D1 — metric → any extra goal.** "Ends differently" = ≥1 additional goal in the omitted stoppage
  (3-1→3-2 counts). Replace the W/D/L 10k-sim with the closed form `mu = sum_h lambda_h*omitted_live_h`,
  `P(change)=1-exp(-mu)`, `X%=mean(P(change))`. The claim is about whether properly-played stoppage
  yields more goals, not who wins; the closed form is exact and drops the sim.
- **D2 — drop team_role; default overall; tied_nontied = sensitivity only.** team_role only served the
  W/D/L flip (which team scores). Under D1 only the total two-team rate enters mu. Data (2H-stoppage λ,
  goals/team-live-min): PRE all .0493 / tied .0716(n10) / nontied .0403(n14) / lead .0345(n6) /
  trail .0460(n8); POST all .0432 / tied .0391(n14) / nontied .0450(n35) / lead .0463(n18) /
  trail .0437(n17). Cells are within Poisson noise (6–18 goals each); tied vs nontied is not robustly
  different (PRE tied HIGHER — contradicts "non-tied scores faster"; pooled tied .0482 vs nontied
  .0436). Conditioning partitions a 73-goal sample into noisier sub-cells without moving the aggregate
  → that is why it "barely matters."
- **D3 — pool PRE+POST for λ; pre/post is a board/composition story.** The 2022 Collina directive
  changed how much goes on the BOARD (add real time for ALL stoppages, not just celebrations), not how
  the game is played per live minute. No first-principles reason λ-per-live-minute changes pre/post,
  and the data agrees (.0493 vs .0432, within noise). pre/post also conflates tournament composition.
  → pool for the central λ; pre/post is a sensitivity; the directive's effect lives in the bigger boards.
- **D4 — silent central = silent_marked + propagated estimator error; none/all guardrails only**
  (unchanged from the IMPL-4 settle; none/all are definitional rails, never calibration targets).

Plus structural: include the 1H stoppage window (`mu = mu_1H + mu_2H`); rename "board" →
`played_in_stoppage` and add a separate `board_announced` (NULL pending research R1); reconcile the λ
exposure denominator with the productivity live-minutes (DC1 — today 811 vs 894.5 2H team-min
disagree); fix the s09 f01 figure's extra-time/penalty spike (DC3). The distortion add-ons
(announced-board under-allocation; within-stoppage time-wasting) and cooling-break pure-stoppage are
IMPL-7, pending the deferred research sessions (`prompts/research_board.md`, `prompts/research_cooling.md`).

## ADR-0025 — HEADLINE NUMBER LOCKED (2026-06-19)

> **SUPERSEDED by [[ADR-0031]] (2026-06-25):** the locked numbers below (23.6% scoreline /
> 12.1% flip) were re-centered to **24.8% / 13.0%** when Method 2 (ADR-0029) + the PRE
> celebration allowance (ADR-0030) were adopted. This entry is retained as the historical
> record of the original lock + the silent-treatment decision (still authoritative); read
> ADR-0031 for the current numbers, bands, and knob breakdown.

**The single modeled claim of the article, locked WITH the user (human checkpoint, CLAUDE.md §1/§6).**
Ran `prompts/lock_headline.md` against the source-of-truth tables (`processed/counterfactual_summary.parquet`,
verified live, not chat history). No re-build, re-tune, or re-run of s08 to "improve" anything (the s08
grid is frozen from ADR-0024). Only s09's REPORTING + the figure were changed to reflect the silent
decision below; the grid/parquet are unchanged.

**Headline framing (the claim).** *If stoppage time were measured and awarded according to the rulebook,
**X% of matches would have ended with a DIFFERENT SCORELINE*** (≥1 extra goal somewhere in the omitted
added time). This is the one number that ships with a CI + a sensitivity table, never a bare point.

**Metric (D1, ADR-0019).** X% = mean over matches of P[≥1 extra goal in omitted stoppage] =
mean(1 − exp(−μ)), μ = Σ_h λ_h · omitted_live_h. Deterministic closed form, no Monte Carlo.

**LOCKED VALUES.**
- **HEADLINE BAND (lead): X% = 21.1%–26.1%**, central **23.6% (95% CI 20.6%–27.4%)**. Window **1H+2H**.
  The lead band is **one-factor-at-a-time** over the legitimate knobs (each swept while the other three sit
  at central; silent fixed at the calibrated point) — a "vary one assumption at a time" range that ships in
  the lead *alongside* the sensitivity table below. (2H_only = 14.1%–17.4%, central 16.0% [14.0%, 18.5%],
  reported as a comparison, not the headline.)
- **Central knob_set: `silent_marked|overall|pooled_all|hl=4.0|on`** (group=all).
- The wider **full joint envelope** (all legitimate knobs varied together) is **18.6%–27.3%**; the lead uses
  the tighter, more interpretable one-factor band, with the joint envelope reported as the outer bound.

**Silent treatment — a SINGLE CALIBRATED ESTIMATE, NOT a reported sensitivity (the lock's key decision,
user 2026-06-19).** silent_marked is calibrated to Nate's WC2018 ground truth (the only high-quality
external dataset we have; s05 estimator r=0.825, ADR-0017) and is reported as a **POINT**.
`silent_none`/`silent_all` are **known-wrong** bounds — they signal nothing useful precisely because we
know they are wrong — and are **NOT reported as a range anywhere**: not in the headline, not in the
sensitivity table, not in figures. They remain in the s08 grid ONLY as an internal monotonicity guardrail
(`test_s08_silent_knob_brackets_headline` checks none ≤ marked ≤ all per cell). **This REVISES red-team
must-fix #1** (which framed the silent axis 10.8%→37.3% as "the dominant uncertainty to name"): the user's
position, adopted here, is that none/all are not legitimate uncertainty — the calibrated point is the only
defensible treatment — so the headline's reported uncertainty comes from sampling + the legitimate
assumption knobs, NOT from the silent axis.

**Reported uncertainty = (a) sampling CI + (b) the legitimate assumption knobs (reported as ranges).**
- (a) Sampling: 95% CI **[20.6%, 27.4%]** (per-cell Jeffreys-Gamma λ + the silent_marked estimator-error bootstrap), width 6.7%.
- (b) Legitimate-knob sensitivities (each swept with the others at central, 1H+2H):
  - **Productivity-decay half-life** h∈[2,8], central h=4 (ADR-0024): **22.2% (h2) .. 23.6% (h4) .. 24.9% (h8)**.
  - **In-stoppage gross-up** (z=0.382 corrected; central ON): off **21.1%** (conservative rail) → **23.6% (ON, central)** → geometric ceiling **24.2%**.
  - **λ source**: pooled_all **23.6%** (central) · pooled_pre 26.1% · pooled_post 22.6% · regime_matched 23.8% (D3: no first-principles pre/post λ difference; data agrees within Poisson noise).
  - **Conditioning**: overall **23.6%** (central) · tied_nontied 23.4% (D2: within noise).
  - **Stage (group vs knockout) — robustness, NOT a knob.** Stoppage-time productivity does not differ
    between group-stage and elimination matches, so X% keeps a single pooled λ rather than a stage term.
    2H-stoppage goals/live-min: group **0.0847 [0.064, 0.110]** (n=56, 660.8 live-min) vs elim **0.0727
    [0.042, 0.117]** (n=17, 233.7 live-min); rate ratio group/elim = **1.17, binomial p=0.69**. CIs overlap
    in every phase/metric and the point estimate leans (non-significantly) *higher* in group stage — the
    opposite of the "knockouts are more frantic" intuition. Adding an elimination covariate would fit noise,
    shrink per-cell n, and add a researcher degree-of-freedom right at the lock; pooling is the defensible
    choice. (Exploration only, 2026-06-21; no code or grid change.)
  - **BIP threshold (`bip.max_live_gap_s`) — robustness, NOT a knob (ADR-0026, 2026-06-22).** Propagating
    the single ball-in-play knob across its full 12–30s sweep moves the headline by **≤0.10 pp** (scoreline
    23.51%–23.66%), and **≤0.04 pp** inside the calibrated 14–20s band — the 20s central reproduces 23.6%.
    BIP is held at the calibrated 20s; it is not a reported sensitivity axis because it does not move the
    number (μ ≈ G·D/T, the live-minutes cancel). Exhibit: `docs/bip_headline_sensitivity.md`.
  - **Full joint legitimate-knob envelope** (silent fixed at marked, cond×source×decay×gross-up): **18.6%–27.3%**.
- Assumption spread: the **lead one-factor band is 5.0% wide ≈ 0.7× sampling**; the **full joint envelope is
  8.7% ≈ 1.3× sampling**. Either way the model is robust — the assumptions do not dominate the sampling
  noise once silent is calibrated.

**Outcome-flip secondary — reported SEPARATELY from the scoreline headline (red-team must-fix #2, user
confirmed).** Scoreline ("≥1 extra goal") ≈ 24%, distinct from outcome ("the result actually flips",
winner/draw status changes): **12.1% [10.6%, 14.2%]** (1H+2H) / 8.2% [7.2%, 9.5%] (2H_only). `lead_by_2plus`
matches cannot flip; conflating "ended differently" with the 23.6% scoreline number is the most attackable
sentence, so the two are always stated apart.

**Caveats (carried verbatim; load-bearing).**
- **Silent calibration, not a band (ADR-0017).** The silent component cannot be measured precisely with free
  StatsBomb data; we ship the Nate-calibrated point, not a none↔all band (see the silent decision above).
- **1H counterfactual independence (O1).** A 1H extra goal is treated as a bonus increment; game state is not
  propagated across the 1H window.
- **Thin PRE counts.** pooled_pre rides wide CIs (few PRE matches); it is a sensitivity, not the central.
- **Coverage (must survive into the article).** Nate validates **WC2018 ONLY**. POST (where the headline
  lives; Copa ~25.3 / AFCON ~23.5 min true_stoppage, ~2× WC2018 silent) is validated only INDIRECTLY — via
  the frozen-2018 estimator constants + the WC2022 Opta BIP calibration point.
- **board_announced under-allocation Δ (A.1) is DEFERRED and DESCRIPTIVE-ONLY** — never in X%
  (`prompts/scrape_board_announced.md`; board_announced still NULL).

**Gate.** The locked claim is a BAND + CI + sensitivity table, not a bare point (CLAUDE.md §1). pytest stays
green (26/26; no s08 change; s09 reporting/figure edits assert nothing). **The modeling pipeline is DONE**;
the only optional remaining unit is the deferred descriptive board_announced scrape.
