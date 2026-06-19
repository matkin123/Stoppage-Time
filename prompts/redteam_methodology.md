# RED-TEAM — adversarial methodology review before the X% lock

**Goal:** pressure-test the Stoppage Time methodology hard enough that the headline claim is defensible
in a major publication (The Athletic / Silver Bulletin-FiveThirtyEight tier or an academic referee).
**Run this BEFORE `prompts/lock_headline.md`.** It is READ-ONLY research + critique — change NO code,
NO params, NO tables. Deliverable is a findings doc, like the other `prompts/research_*_findings.md`.

You wear THREE hats in one session (or split into three if the user prefers). For each finding, do not
just list a worry — **steel-man the strongest version of the attack, then grade it**:
`FATAL` (claim collapses) / `SERIOUS` (materially moves X% or its honesty) / `COSMETIC` (framing/
footnote) — and state whether the current docs ALREADY pre-empt it (several attacks are anticipated:
the silent band, the productivity-premium band, the outcome-flip secondary, the WC2018-only coverage
flag). Be a hostile referee, not a cheerleader. If something is indefensible, say so plainly.

## The claim and the method (what you are attacking)
- **Headline:** "Stoppage time is a sham; measured properly, **X%** of matches would have ended with a
  different SCORELINE" — X% = mean over matches of **P(≥1 extra goal in the omitted stoppage)**.
  Central **23.8% [CI 20.3–28.0%]** (1H+2H); productivity-premium band **16.3–23.8%**; outcome-flip
  (different WINNER/draw) secondary **12.2%**.
- **Chain** (full spec `docs/redesign.md`; decisions `docs/decisions.md` ADR-0011→0023):
  1. **BIP (s03)** gap-method: dead = gap from a possession's last event to the next restart
     play_pattern; any silent gap ≥`max_live_gap_s`=20s w/o a restart is dead. Calibrated to Opta
     WC2022 58:04 ±90s; r=0.943 vs Nate 2018 BIP.
  2. **true_stoppage (s05)** = lower_bound (celebration/sub/card/injury ∩ dead) + restart_excess
     (Nate allowances throw-in 20/goal-kick 30/corner 45/free-kick 60s; credit max(0, gap−allow)) +
     marker-gated silent (≥20s non-restart gap credited only if its lead edge carries an out-of-play
     marker) + residual 24.2s. Validated vs Nate "expected" **r=0.825, MAE 2.44 min — WC2018 ONLY**.
  3. **played_in_stoppage** = period_end_s − 2700 (StatsBomb Half-End whistle). r=0.992 vs Nate "actual".
  4. **omitted** = max(0, true_stoppage − played); **omitted_live** = omitted × live_share.
  5. **λ** = two-team goals per live-minute: 2H-stoppage 0.0816, regular 0.0427, 1H 0.0478; pooled PRE+POST.
  6. **Counterfactual (s08):** μ = Σ_h λ_h·omitted_live_h; **P(change)=1−exp(−μ)**; X%=mean. Closed-form,
     deterministic; seed only for the CI bootstrap (Jeffreys Gamma λ posterior + estimator-MAE draw).
  7. Knobs/bands: silent none/marked/all; conditioning overall/tied_nontied; λ source pooled_all/pre/
     post/regime_matched; productivity-premium observed/open_play; O3 time-waste gross-up off/on.
- **Sample:** 314 matches (PRE 115 / POST 199); ~73 2H-stoppage goals over 894.5 live-min. PRE=WC2018+
  Euro2020; POST=WC2022+Euro2024+Copa2024+AFCON2023. The 2022 Collina added-time directive is the PRE/POST divide.

## Read first (source of truth — not chat history)
`docs/redesign.md` (full spec + O1–O3, DC1–DC3); `docs/decisions.md` (ADR-0011 board, 0016/0017
estimator, 0018 D1–D4, 0019 remodel, 0021 framing+band, 0023 build); `docs/numbers_ledger.md`;
`config/params.yaml`. Tables in `data/processed/` (productivity, counterfactual_summary,
timewasting_descriptive, stoppage_live_share) and `data/interim/` (true_stoppage, played_in_stoppage,
match_state, goals). The Nate ground truth + harness: `src/lib/nate.py`, `data/raw/nate_2018/`.
You MAY re-run read-only queries against the parquet to check a claim; do not regenerate anything.

## HAT 1 — Mathematician / statistician
Attack the inference, not the soccer. Cover at least:
- **Poisson validity** of goals in a 2–5 min, extreme-score-state window: homogeneity, over-dispersion,
  time-inhomogeneity. Is 1−exp(−μ) the right object? (cf. classic soccer-goal Poisson/bivariate-Poisson
  results — do they license THIS use or only match-level totals?)
- **λ stationarity / transportability.** Applying observed stoppage-time λ to COUNTERFACTUAL omitted
  minutes assumes equal scoring intensity. The played stoppage minutes are not a random sample of the
  omitted ones (selection/survivorship). Does the open_play LOWER rail bracket this honestly, or is even
  the floor too high? Is the "live_share cancels → goals-per-CLOCK-min" reframing legitimate?
- **Independence (O1):** 1H and 2H omitted windows treated as independent in the "anywhere" metric; and
  per-match P(change) averaged as if matches are exchangeable. Within-match / within-tournament correlation.
- **CI completeness.** The bootstrap mixes Jeffreys-Gamma λ uncertainty + estimator-MAE draws but the
  SILENT band is reported OUTSIDE the CI. Is that defensible, or is the headline CI falsely tight?
  Estimator MAE (2.44, full-match) scaled to windows — heteroskedasticity, does it transfer?
- **Multiplicity / researcher d.o.f.** A 96-cell knob grid: is the central cell a principled prior or a
  post-hoc pick? Garden-of-forking-paths risk.
- **Framing-vs-measurement gap.** "Ended differently" colloquially = different WINNER (12.2%), but the
  headline number is different SCORELINE (23.8%). Is leading with 23.8% under that verb honest?

## HAT 2 — Soccer quant / domain expert
Attack the football. Cover at least:
- **BIP/effective-playing-time definition** vs Opta/StatsBomb/IFAB and the effective-playing-time
  literature (Siegle & Lames; Linke, Lames et al.). Is the 20s gap rule + restart method a credible
  operationalization? Where does it bias?
- **The end-game productivity premium** (2H-stoppage λ 0.0816 ≈ 1.4× open-play). How much is penalties,
  own goals, and a handful of high-leverage chases? Would the OMITTED minutes (often in already-decided
  games) plausibly sustain that rate? Is penalties' treatment in λ correct?
- **PRE/POST confounding.** Is the 23.8% an artifact of POST tournament composition (AFCON/Copa climate,
  refereeing, team strength, event-logging density) rather than the directive? Does pooling λ (D3) hide
  a real regime difference, or correctly avoid spurious precision?
- **StatsBomb logging density** as the silent-gap method's weak point (the Germany–Sweden over-count
  signature). Does it vary systematically by tournament in a way that biases POST?
- **Sample thinness:** 73 goals, conditioning into tied/non-tied sub-cells. Is the band wide enough?

## HAT 3 — Literature / prior-art reviewer
Anchor on HIGH-CREDIBILITY sources only — academic journals (e.g. *Journal of Sports Sciences*,
*J. Quantitative Analysis in Sports*, IJCSS), and major outlets (The Athletic, Silver Bulletin /
FiveThirtyEight, Opta/Stats Perform analytics, The Upshot). Use web search; cite each source.
- **Prior public stoppage/added-time work**, esp. Nate Silver / 538's 2018 piece (the ground truth
  here) and the WC2022 added-time-spike coverage — do their numbers/methods corroborate or contradict ours?
- **Effective playing time & ball-in-play** research and Opta's published BIP — are our levels (≈58 min
  WC2022 BIP) consistent with the literature?
- **Goal-scoring models & score-state effects on tempo** (Dixon–Coles, Maher, Karlis–Ntzoufras; late-game
  goal inflation / "score effects"). Do they support or undercut the premium and the Poisson use?
- **Counterfactual / "expected points lost to time-wasting" style analyses** — has anyone published this?
  What is genuinely NOVEL here vs already-known, and does any prior result conflict with an assumption?
- Flag any source that suggests our method is non-standard or our number out of line, and say how to
  defend or caveat it.

## Deliverable
Write **`prompts/redteam_methodology_findings.md`**:
1. **Verdict** (1 paragraph): is the headline publishable as-is, publishable with caveats, or does
   something need rework before the lock?
2. **Prioritized findings table**: each = the steel-manned attack, grade (FATAL/SERIOUS/COSMETIC),
   whether docs already address it, and the concrete fix or caveat (incl. which knob/rail/wording).
3. **Recommended pre-lock actions** — what (if anything) the lock session should change in the framing,
   the central knob choice, the band, or the caveats list. Distinguish "must fix" from "nice to have."
4. **Literature appendix**: cited sources (with what each supports/undercuts).
- Be specific and quantitative; tie every claim to a file/table/ADR or a cited source.
- You MAY use subagents (e.g. Explore for the repo, web search for the literature) and run read-only
  parquet queries. **Do NOT modify the pipeline, params, tables, or the ADR log.**

## Gate + checkpoint
- `prompts/redteam_methodology_findings.md` exists with all four sections; every finding graded and
  sourced; no pipeline files changed (`git status` clean except the new findings doc).
- Bring the verdict + the FATAL/SERIOUS findings to the user. Update `next_session.md`: red-team DONE,
  list any must-fix items the lock must absorb. Then the lock (`prompts/lock_headline.md`) runs. STOP.
