# R2 (research) — Cooling/water-break policy + per-match detection

**This session is RESEARCH ONLY — no pipeline changes, no code.** Deliverable is a findings doc saved
to `prompts/research_cooling_findings.md`. Deferred from the main thread to save compute; run it in its
own session. Read `docs/redesign.md` for how the result will be used (IMPL-7).

## Persona
You are an expert soccer (football) quant with encyclopedic knowledge of competition regulations and
publicly available match data. Give precise, SOURCED findings. Do REAL web research; do not rely on
memory alone.

## Context
Six tournaments: WC 2018 (Russia), Euro 2020, WC 2022 (Qatar), Euro 2024 (Germany), Copa America 2024
(USA), AFCON 2023 (Ivory Coast, played Jan-Feb 2024). We use StatsBomb open event data. Cooling /
drinks breaks (a pause of ~3 min, usually around the 30' and 75' marks, triggered when heat/humidity —
often a WBGT threshold — is high enough) add dead time our event-based estimator under-counts, because
in the event stream they just look like a long silent gap. We want to (a) understand the policy and
(b) detect per-match occurrence so we can add the break duration as PURE (non-live) stoppage, which
should improve match-level accuracy (r vs Nate Silver's observed WC2018 numbers).

## Questions
1. **Policy per tournament.** For each of the six: was there a cooling/drinks-break rule? Tournament-
   wide-mandatory, or match-specific and temperature-triggered (and if triggered, what threshold,
   e.g. WBGT >= 32C)? Standard timing (around 30'/75'?) and duration (really ~3 min, or 90s, or
   official discretion)? Verify the obvious priors: WC2022 Qatar (winter, air-conditioned stadiums —
   were breaks still used?); WC2018 Russia, Copa 2024 USA, AFCON 2023 (hot daytime matches); Euro
   2020/2024.
2. **Per-match detection from FREE data.** Can we tell whether a given match took a cooling break?
   Evaluate ESPN commentary/gamecasts, BBC/Guardian minute-by-minute, Wikipedia match reports, news
   recaps, FotMob/SofaScore timelines, official match reports — which explicitly log "cooling break"/
   "drinks break", and for which tournaments?
3. **Automation.** Could a heuristic flag them without manual reading — e.g. combining historical
   match-time temperature/WBGT data (what free weather source?) with a long unexplained dead gap near
   the 30'/75' marks in the event stream? Reliable enough, or is manual commentary-reading the only
   dependable route?

## Deliverable (-> `prompts/research_cooling_findings.md`)
(a) a per-tournament policy table (rule type, trigger/threshold, timing, duration) with sources;
(b) a ranked list of free per-match detection methods with a coverage verdict; (c) a verdict on
whether automatic detection is feasible. Concise and prioritized (aim under 600 words), with specific
URLs/sources.
