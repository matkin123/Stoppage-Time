# Findings — measuring the "silent component" of true stoppage

**Status:** research deliverable (recommendation + sourcing plan). NOT implemented.
Produced by running `prompts/silent_component_search.md` on 2026-06-15. Review before
implementing; implementation prompts live in `next_session.md`.

---

## Bottom-line recommendation

The highest-value fix needs **no new data source** — it lives inside the StatsBomb JSON
already pulled in s02. The silent-gap conflation exists only because the current rule
(`src/lib/bip.py:60`, `gap >= max_live_gap_s`) credits every long event-gap as dead
**without checking whether the ball actually went out of play**. StatsBomb stamps a discrete,
machine-readable **ball-out-of-play marker at the leading edge of every genuinely dead ball**
(`pass.outcome = "Out"`, the `out=true` flag on passes/carries/shots, `Foul Committed`, a shot
leaving the field, a goal, `Injury Stoppage`, `Substitution`/`Player Off`, `Bad Behaviour`,
`Referee Ball-Drop`, `Half End`). A live-but-sparse stretch — slow build-up, off-camera
passage, keeper holding under no pressure — has **none** of these markers and no restart
`play_pattern` at its trailing edge.

**The fix:** reclassify a silent gap as dead only when its leading edge carries an out-of-play
marker (or its trailing edge a restart pattern); otherwise treat it as live. This attaches to
the existing event spine, is schema-identical across all six tournaments, requires zero
scraping, and targets exactly the Germany–Sweden / Russia–Egypt / Uruguay–Saudi failure
signature. Nate's 2018 table is the **validation/calibration arm** (and the place to freeze a
small residual-silent constant); everything external (Opta BIP, broadcast OCR, tracking feeds)
is at best a coverage-limited cross-check, not a production estimator.

---

## 1. Ranked candidate signals + disambiguation mechanism

### (A) ★ StatsBomb intrinsic ball-out-of-play markers — production estimator
**Fields (already in the s02 JSON):** `out` boolean on Pass/Carry/Ball Receipt*/Shot;
`pass.outcome = "Out"` and `"Injury Clearance"`; shot outcomes that leave the field
(`Off T`, `Saved Off T`, `Wayward`, `Blocked`, `Goal`); `Foul Committed` (+`card`), `Offside`,
`Bad Behaviour`, `Substitution`/`Player Off`, `Injury Stoppage` → `Referee Ball-Drop`,
`Half End`.
**Mechanism:** a real stoppage is *initiated* by one of these markers and *resolved* by a
restart `play_pattern` on the next possession. Replace the duration-only silent rule with:
a ≥20s gap is **dead** iff bracketed by an out-of-play marker at the lead edge OR a restart
pattern at the trail edge; if it sits inside one continuous possession with no out-marker and
resumes on Regular Play, it is **live but sparsely logged** → credit nothing.
**Caveat:** s02 currently projects only `play_pattern, type, card, shot_outcome` (see
`s05_incident.py`). The `out` flag and `pass.outcome` are in the raw JSON but **not yet carried
through normalization** — implementing (A) means projecting those fields through s02.

### (B) ★ Goalkeeper-held / possession events — refinement within (A)
**Fields:** `Goalkeeper` type ∈ {Collected, Smother, Pick-up, Save}, `goalkeeper.outcome`.
**Mechanism:** a `Goalkeeper: Collected/Smother` with no subsequent `out` and a long gap is the
keeper legally holding a *live* ball (6-second rule) — must NOT be credited as dead. Directly
targets the "keeper holding under no pressure" false-dead named in the problem statement.

### (C) VAR / injury / substitution explicit logs — necessary but insufficient (already partly used)
`Injury Stoppage`, `Referee Ball-Drop`, `Substitution`/`Player Off`, `card`/`Bad Behaviour`
(all already consumed by s05). This is *why* the injury-dominated matches are accurate. But
StatsBomb has **no explicit VAR event type** in open data, and `Injury Stoppage` is populated
**inconsistently** (s05 already flags matches with none) — so (C) cannot resolve the low-injury
matches alone. It is the complement of (A), not a substitute.

### (D) Tracking in-play flags (SkillCorner / Second Spectrum / 360) — valid but not obtainable; decline
Perfect disambiguation in principle, but SkillCorner/Second Spectrum are commercial and
unavailable for these open-data tournaments; StatsBomb 360 is event-anchored freeze-frames (no
continuous in/out timing) and out of scope (disk budget).

### (E) Broadcast clock / added-time OCR / video timing — coverage-limited; decline for production
Broadcast clocks don't pause for stoppages; the on-screen board reports only total added time
per half (circular with what we're reconstructing). Item 1 already found ESPN's second-level
clock corrupt on ~half the boundary markers. Per-match video re-timing across 314 matches is
high-effort with ToS exposure. Coarse per-half cross-check only.

### (F) Third-party BIP feeds (Opta public, FBref, WhoScored, FlashScore) — aggregate cross-check only
Opta publishes occasional public BIP, but per-match second-level BIP for all six tournaments is
not freely/consistently available; FBref/WhoScored (Opta-derived) don't expose BIP; FlashScore
has none. Aggregate sanity check at best, coverage-limited.

---

## 2. Recommendation with trade-offs (both hats)

| Rank | Option | Valid? | Obtainable? |
|---|---|---|---|
| 1 | (A)+(B)+(C) StatsBomb intrinsic out-of-play reclassification | Resolves the conflation; targets named failure signature; principled | Best — already in JSON; identical schema all six; only cost is projecting `out`/`pass.outcome` through s02 |
| 2 | Nate 2018 as calibration/validation arm | Gold-standard video ground truth; freezes residual-silent constant | In-repo, but **WC2018 only** — calibration arm, not POST estimator |
| 3 | Opta public BIP + broadcast added-time board | Independent aggregate cross-check | Coverage-limited / high-effort; never per-gap |

**Frank limitation of (A):** a residual remains (dead time with no logged marker; ball drifting
out off-camera before the `out`-flagged touch; melee with no event). After (A), credit a small
**calibrated residual-silent constant frozen on 2018** (the "calibrated-silent" term in
solution-b). *Hypothesis to confirm:* the residual will be far smaller and more homogeneous than
today's raw silent bucket, because the systematic low-injury inflation is removed.

---

## 3. Validation plan (Nate's 32 WC2018 matches)

> **Column mapping (do not cross these):** the true-stoppage estimator validates against Nate's
> **`expected`** column (the "should-be-added" model, mean ~13.2 min — e.g. Germany–Sweden 8:56 ≈
> the "8.9" in the problem statement). Nate's **`actual`** column is what the ref added and is the
> *board* target (already validated, r=0.992). BIP validates against Nate's **`bip`** column
> (r=0.943 today). All three arms are wired in `src/lib/nate.py`.

1. **Per-match:** Pearson r + MAE (min) vs Nate's **`expected`**. Beat current r ≈ 0.73–0.77 (target ≳0.85).
2. **Aggregate:** 32-match mean corrected stoppage vs Nate's `expected` mean — must stay ≈13 min level.
3. **Diagnostic (decisive):** shrink error on Germany–Sweden (17.4 vs 8.9), Russia–Egypt,
   Uruguay–Saudi WITHOUT breaking Belgium–Panama, Tunisia–England (already within 1–2 min).
   Report per-match before/after for all five.
4. **Ablation:** r/MAE for (A) alone → (A)+(B) → +residual-constant, so each piece is traceable.
5. **Coverage flag:** Nate covers WC2018 only → calibration/validation arm; POST tournaments are
   validated only indirectly via the frozen 2018 calibration + s03's WC2022 Opta BIP gate.

---

## 4. Sourcing plan (recommended option)

- **Where:** already local — the six competitions' event JSON fetched in-memory in s02. No new
  pull, scrape, API, ToS, or rate-limit exposure.
- **How:** project `out`, `pass.outcome` (and `Goalkeeper` type/outcome for (B)) through s02
  normalization into `events_norm.parquet`, then rewrite the silent rule.
- **Match key:** trivial — everything already keyed by `match_id`.
- **Nate arm:** 32-match table already transcribed in-repo (Item 1); re-transcribe from
  `~/Downloads/nate silver WC stoppage 2018.jpg` if needed.
- **Effort:** small-to-moderate — one s02 field-projection + one rule rewrite + the 2018
  validation harness. One self-contained unit; do not chain into the full estimator rebuild.

---

## 5. Coverage matrix (recommended sources × six tournaments)

| Source / signal | WC2018 | Euro2020 | WC2022 | Euro2024 | Copa2024 | AFCON2023 | Role |
|---|:--:|:--:|:--:|:--:|:--:|:--:|---|
| (A) StatsBomb `out`/`pass.outcome`/boundary markers | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Production estimator |
| (B) Goalkeeper-held events | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Refinement within (A) |
| (C) Injury/sub/card markers | ✅ | ✅ | ✅ | ✅ | ✅ | ✅* | Complement (*inconsistent Injury Stoppage) |
| VAR explicit log | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | No VAR event type in open data |
| Nate Silver 2018 ground truth | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | Calibration/validation arm only |
| Opta public BIP | ⚠️ | ⚠️ | ✅(s03 gate) | ⚠️ | ⚠️ | ⚠️ | Aggregate cross-check, partial |
| SkillCorner / Second Spectrum / 360 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Unavailable / out of scope |
| Broadcast clock OCR | ⚠️ corrupt | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | Per-half only, declined |

✅ available · ⚠️ partial/unreliable · ❌ unavailable.
**Speculation labels:** residual-constant magnitude and expected r-improvement are hypotheses to
confirm in validation; the StatsBomb `out`/`pass.outcome`/goalkeeper schema, the absence of a
VAR event type, and the absence of free per-match Opta BIP are established facts about the spec.

---

## Design decision (DECIDED 2026-06-15): one ball-state classifier, in bip.py

> **SUPERSEDED 2026-06-15 (ADR-0014 + ADR-0015).** The "one classifier in bip.py" decision below
> was FALSIFIED in IMPL-2: marker-gating regresses the validated BIP (r 0.943→≤0.92) because BIP
> needs the unmarked silent gaps (they are genuinely dead). BIP = TOTAL dead; stoppage = ADDABLE
> dead — different questions, different definitions. `bip.py`/s03 stay the validated duration rule;
> marker-gating is applied ONLY to the s05 stoppage silent term (IMPL-3). The text below is
> retained for history — do NOT implement it.

The marker-gating reclassification changes which gaps count as dead, and those dead segments feed
**both** s03 BIP and s05 true-stoppage. We are improving the live/dead methodology, so the
improvement belongs **everywhere**: marker-gating becomes THE classifier in `src/lib/bip.py`,
replacing the `gap >= max_live_gap_s` rule, and both BIP and the estimator read it. (This does
not collapse BIP and stoppage into one number — true stoppage stays
`dead − normal-restart-excess + injury/sub/goal credit` in s05, on top of the shared classifier.)

**Why this is safe despite "s03 BIP is validated (r=0.94)":** the silent over-count is the same
absolute seconds in both metrics. On BIP (~55 min base) it's a ~15% perturbation → r stayed at
0.94 with the flaw present. On stoppage (~13 min base) the same seconds are ~65% → r=0.73.
Marker-gating removes them from both: a small nudge UP on BIP (toward 538's truth), a big jump on
stoppage. A correct classifier improves both; if it ever improves stoppage while regressing BIP,
the marker logic is wrong — debug, do not ship.

**Guardrail (re-calibration, not "don't touch"):** s03's gap constants were tuned to hit Opta's
WC2022 3484s; marker-gating moves seconds dead→live so pooled BIP rises and likely breaches the
±90s gate on first run. That is expected → re-tune (you may not need `max_live_gap_s` at all).
Promote to bip.py only when, after re-tuning: WC2022 BIP hits Opta ±90s AND per-match BIP r vs
538 holds ≥ 0.94. If BIP cannot re-validate, stop and bring it to the user — do not fall back to
a quiet estimator-only patch.
