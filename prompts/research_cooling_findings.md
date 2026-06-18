# R2 findings — cooling/water-break policy + per-match detection

**Verdict in one line:** breaks are **rule-triggered, not universal** for our six tournaments (the
mandatory-every-match rule starts at WC2026, *after* our sample). Two tournaments collapse to a
prior with no detection needed (AFCON2023 = every match; WC2022 = none); the other four are
temperature-variable and need per-match flagging. A free **Open-Meteo weather gate + commentary
confirm** on the small shortlist is the dependable route; pure event-stream automation is feasible
but lower-precision.

## (a) Per-tournament policy

| Tournament | Governing rule | Trigger | Timing | Duration | Used? |
|---|---|---|---|---|---|
| WC2018 Russia | FIFA Medical (cooling-break protocol, since 2014) | match-by-match, **WBGT ≥ 32 °C** | ~30' / 75' | ~3 min | some hot day games (Samara/Volgograd/Kaliningrad-type venues) |
| Euro2020 (2021) | UEFA Medical Regs **Art. 11 / Annex D** | pitch-side air **≥ 32 °C** | ~25' into each half | **90 s** | sparse; hottest matches only |
| WC2022 Qatar | FIFA Medical, match-by-match | WBGT ≥ 32 °C | ~30' / 75' | ~3 min | **effectively none** — Nov/Dec + air-conditioned stadia, temps ~20–25 °C |
| Euro2024 Germany | UEFA Art. 11 / Annex D | air ≥ 32 °C (+ referee discretion below it) | ~25' | 90 s | a few, incl. **below threshold by ref call** — FRA–POL 28', NED–AUT 34' (~27–28 °C) |
| Copa2024 USA | CONMEBOL Medical | **WBGT ≥ 32 °C**, lower if both teams agree | ~30' / 75' | ~3 min | **widely used** — oppressive heat/humidity (e.g. Kansas City "felt like" 103 °F) |
| AFCON2023 Ivory Coast (Jan–Feb 2024) | CAF | **tournament-wide mandatory** (not temp-gated), extra breaks if extreme | **30' / 75'** | **~2 min** | **every match** |

Note the duration is not uniform: FIFA/CONMEBOL ~3 min, UEFA 90 s, CAF ~2 min. Use per-tournament
values, not a single constant. The "~30'/75'" timing is approximate — the referee triggers at the
next stoppage after the mark, so the real gap drifts a few minutes.

## (b) Free per-match detection, ranked

1. **Live text commentary (BBC/Guardian minute-by-minute, ESPN gamecast)** — only source that
   *explicitly* logs "drinks break"/"cooling break" at a minute. Coverage: WC & Euros excellent;
   Copa2024/AFCON2023 thinner in English but present. Effort **HIGH** (per-match HTML scrape +
   regex/NLP; URLs not guessable). Best dependable confirm.
2. **StatsBomb event stream (we already have it)** — no cooling-break marker; a break shows only as a
   long unexplained silent gap near 30'/75' (25' for UEFA). Free, but a *signal*, not a label —
   confounded by VAR/injury/sub gaps at the same minutes.
3. **SofaScore / FotMob timelines** — the incidents feed (R1's source) carries `injuryTime` but
   **not** cooling breaks as a discrete incident type. Don't expect a clean field here.
4. **Wikipedia match reports** — verified pattern: goals/cards/subs only, **no** cooling breaks. Skip.
5. **News recaps** — occasional mention, unreliable, not systematic.

Coverage verdict: no single free feed gives a clean per-match boolean. But the problem is smaller
than it looks — **AFCON2023 → apply to all matches; WC2022 → apply to none** by rule, leaving only
WC2018 / Euro2020 / Euro2024 / Copa2024 to flag individually (a modest N, concentrated in the hot ones).

## (c) Is automatic detection feasible?

**Partially — recommend a weather-gated hybrid, not pure automation.**
- **Weather gate (free, no key):** [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
  (hourly back to 1940, CC-BY) at each stadium's lat/lon + kickoff hour → temp + humidity → approximate
  WBGT. This cheaply kills most candidates (and confirms WC2022's ~no-break prior) and shortlists the
  matches near/over 32 °C. (Meteostat is an alternative but free tier caps at 500 req/mo.)
- **Event-stream confirm:** on the shortlist, look for a ≥~90–180 s silent gap near 30'/75' (25' UEFA)
  not explained by a logged VAR/injury/sub. Calibrate the gap threshold against a few known breaks.
- **Reliability:** the weather gate is reliable for *exclusion*; positive detection needs the gap
  detector OR a commentary read. Because the shortlist is small, **a manual commentary check on the
  flagged matches is cheap and is the most dependable confirm** — fully automatic (weather+gap, no
  reading) is workable but will mislabel some ref-discretion breaks (Euro2024) and gap false-positives.

**For IMPL-7:** add pure (non-live) stoppage = per-tournament break duration × (#breaks detected),
all to AFCON2023, none to WC2022, weather-gated + confirmed for the other four. Hypothesis: improves
match-level r vs Nate on WC2018's hot games.

## Sources
- [ESPN — why drinks breaks at WC2026 / history of the 32 °C threshold](https://www.espn.com/soccer/story/_/id/48945011/why-there-drinks-breaks-2026-world-cup-fifa-criticised)
- [The Conversation — extreme heat at the World Cup / WBGT thresholds](https://theconversation.com/extreme-heat-at-the-world-cup-are-fifas-safeguards-enough-282489)
- [All Football — cooling break rule text, WC2022 (32 °C, 30'/75', 3 min)](https://m.allfootballapp.com/news/EPL/Cooling-break-in-2022-World-Cup-Why-do-they-stop-in-the-middle-of-the-game/2957267)
- [UEFA Medical Regulations — Art. 11 Cooling and drinks breaks](https://documents.uefa.com/r/suImvqJRvmKAZT4o7JV_jw/ZfoNPQIgDZvHyp5tsouL7w)
- [Climate State — Euro 2024 (32 °C, 90 s, 25'; FRA–POL & NED–AUT below-threshold breaks)](https://climatestate.com/2024/07/10/germany-the-extreme-weather-during-the-soccer-euro-2024/)
- [SportsBrief — AFCON 2023 CAF cooling breaks (30'/75', every game)](https://sportsbrief.com/football/58417-afcon-2023-caf-disclose-teams-observe-cooling-breaks-games-competition/)
- [BeSoccer — AFCON to feature cooling breaks](https://www.besoccer.com/new/afcon-to-feature-cooling-breaks-657283)
- [ESPN — brutal heat at Copa América 2024](https://www.espn.com/soccer/story/_/id/40454071/brutal-heat-copa-america-2024-usmnt-uruguay-2026-world-cup-risk)
- [GiveMeSport — Copa América heat measures / cooling breaks](https://www.givemesport.com/how-copa-america-players-are-being-protected-from-extreme-heat/)
- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) · [Meteostat](https://dev.meteostat.net/api)
