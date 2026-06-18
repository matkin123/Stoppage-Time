# R1 (research) — Can the announced 4th-official board be sourced for free?

**This session is RESEARCH ONLY — no pipeline changes, no code.** Deliverable is a sourcing
recommendation saved to `prompts/research_board_findings.md`. Deferred from the main thread to save
compute; run it in its own session. Read `docs/redesign.md` for how the result will be used.

## Persona
You are an expert soccer (football) quant with encyclopedic knowledge of publicly available football
match data — every free dataset, API, and scrape-able source, and exactly what fields each carries.
Give a concrete sourcing assessment, not generalities. Do REAL web research to verify; do not rely on
memory alone.

## Context
Six tournaments: World Cup 2018, Euro 2020, World Cup 2022, Euro 2024, Copa America 2024, AFCON 2023.
We use StatsBomb open event data for play-by-play. StatsBomb does NOT contain the **announced added
time** — the number the fourth official puts on the board at 45' and 90' (e.g. "+7"). We currently
(wrongly) proxy it with time-actually-played-in-stoppage; IMPL-6 renames that to `played_in_stoppage`
and wants the REAL announced number as a separate variable.

## The question
Is the announced fourth-official added-time (the board number at 45' and 90') obtainable from any
FREE / public source for these six tournaments? Investigate broadly and concretely.

Evaluate (and any others you know): StatsBomb open data (confirm it truly lacks it), FBref/Opta,
football-data.co.uk, football-data.org API, API-Football (api-sports.io), Wikipedia match reports/
infoboxes, ESPN commentary & gamecasts, FotMob, SofaScore, WhoScored, FIFA/UEFA/CONMEBOL/CAF official
match reports & PDFs (FIFA Training Centre looked promising in an earlier quick pass), worldfootball.net,
RSSSF, transfermarkt, BBC/Guardian minute-by-minute. For each promising source: (1) does it actually
contain the announced board minutes (not just total match length)? (2) coverage — which tournaments,
per-match or partial? (3) free vs paid? (4) structured API vs HTML scrape vs manual PDF? (5) extraction
difficulty at scale?

## Why it matters (so you can judge "good enough")
We want to quantify two things, so partial coverage is still useful: (a) UNDER-ALLOCATION at 90' =
(time that SHOULD have been shown) - (announced board); (b) WITHIN-STOPPAGE time-wasting = (announced
board) - (minutes actually played in stoppage). WC2022 (Collina directive, very large boards) is the
most valuable single case.

## Deliverable (-> `prompts/research_board_findings.md`)
A ranked, concrete list of the best free routes to obtain announced board added-time per match, each
with a coverage verdict across the six tournaments and an extraction-difficulty note, with specific
URLs / dataset names / API endpoints. If it is genuinely unavailable for free, say so plainly and name
the single most attainable tournament. Concise and prioritized (aim under 600 words). Note the
WC2018-only "announced" board that exists in ESPN commentary (format changed afterward) as a known
partial lead.
