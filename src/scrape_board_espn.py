"""Scrape per-half added (stoppage) time from ESPN's public match API.

The fourth-official board number is not in StatsBomb. ESPN's soccer summary endpoint
carries minute-stamped commentary; the "First Half ends" / "Second Half ends" entries are
stamped like ``45'+8'`` / ``90'+9'``, i.e. the added minute at which the half closed. That
is the actual added time played, which slightly OVER-estimates the announced board number
(play completes the minute in progress). For the s08 counterfactual that is the safe,
conservative direction: omitted = max(0, true_stoppage - board) shrinks, so the headline
cannot be inflated by this source.

Run:  python -m src.scrape_board_espn         (writes data/raw/board/board_added_time.csv)
Then: python run.py --stage 06a               (joins onto matches; reference-band check)

This is a network scrape against a high-quality public source. It is idempotent and writes
only the small CSV; nothing else lands on disk.
"""
from __future__ import annotations

import time
import unicodedata
from datetime import date as _date, timedelta

import pandas as pd
import requests
from tqdm import tqdm

from src.lib import config

LEAGUE = {
    "wc_2018": "fifa.world",
    "wc_2022": "fifa.world",
    "euro_2020": "uefa.euro",
    "euro_2024": "uefa.euro",
    "copa_america_2024": "conmebol.america",
    "afcon_2023": "caf.nations",
}
SB = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

# StatsBomb name -> normalized token used for matching. Only the awkward ones; the
# accent/punctuation normalizer handles the rest.
ALIAS = {
    "cote d'ivoire": "ivory coast",
    "ivory coast": "ivory coast",
    "korea republic": "south korea",
    "ir iran": "iran",
    "china pr": "china",
    "usa": "united states",
    "united states": "united states",
    "czech republic": "czechia",
    "czechia": "czechia",
    "cape verde islands": "cape verde",
    "cabo verde": "cape verde",
    "turkiye": "turkey",
    "turkey": "turkey",
    "north macedonia": "north macedonia",
    "republic of ireland": "ireland",
    "dr congo": "congo dr",
    "congo dr": "congo dr",
    "equatorial guinea": "equatorial guinea",
}


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    s = "".join(ch for ch in s if ch.isalnum() or ch == " ").strip()
    return ALIAS.get(s, s)


def _get(session: requests.Session, url: str, params: dict | None = None, tries: int = 3):
    for k in range(tries):
        try:
            r = session.get(url, params=params, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(0.5 * (k + 1))
    return None


def _expand_dates(dates) -> list[str]:
    """Each date plus its +/-1 neighbours -- kickoffs near UTC midnight (esp. Copa America
    in US evening slots) land on the adjacent calendar day on ESPN's scoreboard."""
    out: set[str] = set()
    for d in dates:
        y, m, day = (int(x) for x in str(d).split("-"))
        base = _date(y, m, day)
        for off in (-1, 0, 1):
            out.add((base + timedelta(days=off)).isoformat())
    return sorted(out)


def _scoreboard_index(session, slug, dates) -> dict:
    """{(date, frozenset(norm teams)): (event_id, home_norm, away_norm, hs, as)}."""
    idx = {}
    for d in _expand_dates(dates):
        ds = d.replace("-", "")
        js = _get(session, f"{SB}/{slug}/scoreboard", {"dates": ds})
        if not js:
            continue
        for ev in js.get("events", []):
            comp = (ev.get("competitions") or [{}])[0]
            cs = comp.get("competitors", [])
            home = next((c for c in cs if c.get("homeAway") == "home"), None)
            away = next((c for c in cs if c.get("homeAway") == "away"), None)
            if not home or not away:
                continue
            hn = _norm(home.get("team", {}).get("displayName", ""))
            an = _norm(away.get("team", {}).get("displayName", ""))
            try:
                hs, as_ = int(home.get("score")), int(away.get("score"))
            except (TypeError, ValueError):
                hs = as_ = None
            idx[(d, frozenset((hn, an)))] = (ev["id"], hn, an, hs, as_)
        time.sleep(0.15)
    return idx


def _added_minutes(session, slug, event_id) -> dict:
    """{1: board_1h, 2: board_2h} from the half-end commentary markers."""
    js = _get(session, f"{SB}/{slug}/summary", {"event": event_id})
    out: dict[int, int] = {}
    if not js:
        return out
    for e in js.get("commentary", []):
        text = (e.get("text") or "").strip().lower()
        dv = (e.get("time") or {}).get("displayValue") or ""
        period = 1 if text.startswith("first half ends") else (2 if text.startswith("second half ends") else None)
        if period is None or "+" not in dv:
            continue
        try:
            added = int(dv.split("+")[1].replace("'", "").strip())
        except (IndexError, ValueError):
            continue
        out[period] = added
    return out


def main() -> None:
    config.ensure_dirs()
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    session = requests.Session()

    rows, unmatched = [], []
    for tourn, mt in matches.groupby("tournament"):
        slug = LEAGUE[tourn]
        dates = sorted(mt["date"].unique())
        idx = _scoreboard_index(session, slug, dates)
        for r in tqdm(mt.itertuples(index=False), total=len(mt), desc=f"board {tourn}", unit="match"):
            hn, an = _norm(r.home), _norm(r.away)
            near = _expand_dates([r.date])
            hit = next((idx[(d, frozenset((hn, an)))] for d in near
                        if (d, frozenset((hn, an))) in idx), None)
            if hit is None:  # fall back: nearby date, score match, any one team overlaps
                for (d, teams), v in idx.items():
                    if d in near and (hn in teams or an in teams) \
                            and v[3] == int(r.home_score) and v[4] == int(r.away_score):
                        hit = v
                        break
            if hit is None:
                unmatched.append((r.date, r.home, r.away))
                continue
            event_id = hit[0]
            added = _added_minutes(session, slug, event_id)
            time.sleep(0.15)
            for period in (1, 2):
                if period in added:
                    rows.append({
                        "date": r.date, "home": r.home, "away": r.away,
                        "period": period, "board_min": added[period], "source": "espn",
                    })

    out = pd.DataFrame(rows, columns=["date", "home", "away", "period", "board_min", "source"])
    out.to_csv(config.RAW_BOARD / "board_added_time.csv", index=False)

    n_matches_with_data = out.groupby(["date", "home", "away"]).ngroups
    print(f"\n  scraped board rows: {len(out)}  matches with data: {n_matches_with_data}/{len(matches)}")
    if unmatched:
        print(f"  {len(unmatched)} matches did not map to an ESPN event:")
        for d, h, a in unmatched[:15]:
            print(f"    {d}  {h} vs {a}")
    # quick reference-band sniff (total per match, both halves)
    per = out.groupby(["date", "home", "away"])["board_min"].sum()
    print(f"  mean total board/match: {per.mean():.1f} min  (n={len(per)})")


if __name__ == "__main__":
    main()
