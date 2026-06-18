# R1 findings — sourcing the announced 4th-official board (free?)

**Verdict: YES — available free for ALL SIX tournaments via SofaScore's unofficial JSON API.**
This is better than the redesign assumed (it scoped `board_announced` as "possibly NULL,
WC2022-only"). Under-allocation Δ = `true_stoppage − board_announced` is computable for the
full sample, not just WC2022. Spot-check a sample against broadcast before relying.

## Ranked routes

### 1. SofaScore incidents API — RECOMMENDED (verified live this session)
Endpoint: `https://api.sofascore.com/api/v1/event/{eventId}/incidents`
Each half emits a clean incident:
`{"length":9,"time":90,"incidentType":"injuryTime"}` → `length` = announced board minutes
(integer), `time` 45 = 1H board, `time` 90 = 2H board. Exactly the variable we want.

- **Coverage — confirmed populated for the oldest and least-mainstream cases:**
  - WC2018, KOR–GER (event 7659904): 1H +3, 2H +9.
  - AFCON2023, NGA–CMR (event 11940739): 1H +6, 2H +10.
  - A 2024-era match (event 9576070): 1H +2, 2H +4.
  - Tournament/season navigation works for all six: `…/unique-tournament/{ut}/season/{s}/events/last/{page}`.
    WC ut=16 (2018 s=15586, 2022 s=41087); AFCON ut=270 (2023 s=56021). Euro / Copa
    discoverable via `…/search/all?q=`. Strong inference: all six covered (verify Euro2020,
    Euro2024, Copa2024 with the same one-event check before trusting).
- **Free / structured:** free, JSON, no key. Per-half integer — no NLP needed.
- **Difficulty: LOW.** Caveats: unofficial/undocumented; Cloudflare rate-limits (~1 req/25–30s,
  set a UA + sleep); ToS gray area. Join SofaScore events to our StatsBomb matches by
  teams+date. Python wrappers exist (`datafc`, `LanusStats`) exposing `added_time`.
- **Fidelity check:** `length` should be the announced minimum board, not a derived value.
  Values look right (KOR–GER's famous long 2H = +9). Spot-check ~5 vs BBC/Guardian text.

### 2. Live text commentary — BACKUP / cross-validation
BBC MBM, Guardian MBM, ESPN gamecast all verbally report the board ("the fourth official
indicates a minimum of X minutes" — Collina's big WC2022 boards were widely quoted).
- **Coverage:** WC + Euros excellent; Copa2024/AFCON2023 partial (English MBM thinner).
- **Difficulty: HIGH** — HTML scrape per match + regex/NLP to extract the integer; URLs not
  guessable. Use only to validate SofaScore or fill any gaps it leaves.

### 3. FotMob / Flashscore — redundant, harder
Both show a "+X" added-time marker in the timeline (same datum as SofaScore). FotMob's API is
now auth-gated (`x-mas` header → 404 without it); Flashscore is a heavy JS scrape. No
advantage over route 1.

## Confirmed UNAVAILABLE / not the board
- **StatsBomb open data** — no announced board. It carries only Half-End timestamps = time
  *played* in stoppage, i.e. exactly today's `played_in_stoppage`. (Consistent with CLAUDE.md.)
- **Wikipedia** — verified: match articles record goals/cards/subs and total/ET only, never
  the +X board.
- **API-Football (api-sports.io)** — `fixtures/events.time.extra` is an event's minute-offset
  (e.g. 90+3), NOT the announced board. No board field.
- **Results DBs** — football-data.co.uk, football-data.org, worldfootball.net, RSSSF,
  transfermarkt: scores/results only.
- **FIFA official** — the exact added time lives in the non-public referee report; FIFA's
  public match center / Training Centre exposes no clean board field. WC2022 got heavy
  press coverage of big boards but not as a dataset.

## Known partial lead (per prompt)
ESPN's **WC2018** commentary carried an explicit announced-board entry; the format changed
after 2018. Now moot for primary sourcing since SofaScore covers WC2018 fully — keep only as
an extra WC2018 cross-check.

## Recommendation for IMPL-7
Populate `board_announced` from SofaScore `injuryTime.length` (×60 → seconds) for all six
tournaments; match by teams+date; cache responses (rate-limit). Validate a ~5-match sample
against BBC/Guardian text. Then Δ_underalloc = `true_stoppage − board_announced` is a
full-sample distortion, not a WC2022-only one.
