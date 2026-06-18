# Scrape `board_announced` (SofaScore) → IMPL-7 Part A.1 under-allocation Δ

**Self-contained, turnkey unit (CLAUDE.md §6: one unit, validate, STOP).** DEFERRED out of the
IMPL-7 build session (ADR-0023) because it is a long, rate-limited network scrape, not deterministic
local compute. The plumbing it feeds is ALREADY built; this session only fills `board_announced` and
adds the descriptive under-allocation Δ. **It does NOT touch the X% headline** (Δ is descriptive only).

## Context (read first)
- The announced 4th-official board (the "+X" minutes shown at 45'/90') is DISTINCT from
  `played_in_stoppage` (= `period_end_s − 2700`, the time actually PLAYED in added time, ADR-0011).
  This unit sources the ANNOUNCED number and contrasts it with the estimated `true_stoppage`.
- Source confirmed free for ALL SIX tournaments in R1 (ADR-0020): SofaScore unofficial JSON API.
  Full findings: `prompts/research_board_findings.md`. Durable pointer: memory
  `reference_board_announced.md`.
- The s05 `true_stoppage` estimator (r=0.825, FROZEN) and the s08 headline are UNCHANGED by this unit.

## API (from ADR-0020 / research_board_findings.md)
- Incidents per match: `GET https://api.sofascore.com/api/v1/event/{eventId}/incidents`
  → one incident per half: `{"length":9,"time":90,"incidentType":"injuryTime"}`.
  `length` = announced board minutes (int); `time` 45 → 1H board, `time` 90 → 2H board.
- Event discovery per tournament season:
  `GET …/unique-tournament/{ut}/season/{seasonId}/events/last/{page}` (paginate).
  Known nav IDs: WC ut=16 (2018 season 15586, 2022 season 41087); AFCON ut=270 (2023 season 56021).
  Euro/Copa: discover via `…/search/all?q=<tournament name>` then read the unique-tournament + season.
- **Verified live populated** (sanity targets to reproduce before trusting a tournament): WC2018
  KOR–GER (event 7659904) 1H+3 / 2H+9; AFCON2023 NGA–CMR (event 11940739) 1H+6 / 2H+10.
- **Caveats:** unofficial/undocumented; Cloudflare rate-limits (~1 req / 25–30 s). Set a real
  User-Agent and `sleep`. ToS gray area. ~314 matches × (≥1 event-list + 1 incidents) calls →
  budget ~3 h. CACHE every raw JSON response under `data/raw/board_announced/` (immutable cache,
  CLAUDE.md §3) so a re-run never re-hits the network.

## Do
1. **New scraper** `src/scrape_board_announced.py`:
   - For each of the six tournaments, list events for the season, then fetch incidents per event.
   - Parse `injuryTime` incidents → `board_1h_min`, `board_2h_min` (ints; missing → NaN, flag).
   - Join SofaScore events to our matches by **normalized team pair + date** (reuse the
     name-normalization approach in `src/lib/nate.py:reconcile` — 538/SofaScore spell and order
     teams differently; match on the UNORDERED, normalized pair within ±1 day of `matches.date`).
   - Read our match key from `interim/matches.parquet` (cols `match_id, tournament, date, home, away`;
     314 rows). Write `interim/board_announced.parquet` with columns:
     `match_id, period (1|2), board_announced_s (= board_min×60), source="sofascore", sofa_event_id`.
   - Politeness: real UA, `time.sleep(~28s)` between calls, cache raw JSON to `data/raw/board_announced/`,
     resume from cache on re-run. Log coverage per tournament (matched / total).
2. **Fidelity spot-check:** print ~5 `board_announced` values and reconcile against BBC/Guardian live
   text manually (confirm it's the announced MINIMUM, not a derived value). Record the 5 in the ADR.
3. **Wire the descriptive under-allocation Δ** (NOT the headline):
   - In `src/s07_productivity.py` (or a small `s06c`/`s07` block), if `interim/board_announced.parquet`
     exists: join `true_stoppage` (from `interim/true_stoppage.parquet`, per match per half) and
     compute `under_alloc_s = true_stoppage_s − board_announced_s` per (match, half). Write
     `processed/board_underallocation_descriptive.parquet`. Print pooled + PRE/POST mean min/match.
   - In `src/s09_figures.py:write_ledger`, REPLACE the deferred note (the line "board_announced …
     DEFERRED … still NULL") with the computed under-allocation Δ section (pooled + PRE/POST,
     coverage %). Keep it under a clear "DESCRIPTIVE — not in the X% counterfactual" heading.

## Gate
- `interim/board_announced.parquet` exists; coverage logged per tournament; the two verified sanity
  events reproduce (KOR–GER +3/+9; NGA–CMR +6/+10).
- `board_announced_s ≥ 0`; `under_alloc_s` finite where both sides present.
- `pytest` green (add a guard: board_announced non-negative + coverage > 0 per tournament present).
- s09 ledger shows the under-allocation Δ section (no longer "DEFERRED/NULL").

## Checkpoint
- ADR in `docs/decisions.md` (coverage table, the 5-match fidelity check, pooled/PRE/POST Δ).
- Update `next_session.md`: mark Part A.1 DONE; the only remaining unit is the final X% LOCK.
- STOP. **Do NOT re-run s08 or touch the X% headline** — Δ is descriptive; the band is already built.
