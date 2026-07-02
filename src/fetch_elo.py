"""Fetch World Football Elo per-team match histories (eloratings.net) into the raw cache.

ANALYSIS-SUPPORT sourcing for ADR-0034 (team-quality / outcome-flip test). eloratings.net serves
a full per-team match history as `http://eloratings.net/<Name>.tsv` where <Name> is the site's
country name with spaces -> underscores. Each row is one match:

    year mon day HOME AWAY hs as type host |dElo| home_elo_after away_elo_after ...

Elo is zero-sum so column 10 is the shared magnitude; columns 11/12 are the post-match ratings of
home/away. Pre-match rating for a team = its elo_after in its PREVIOUS row (ratings only move on
match days). We cache the raw TSVs immutably; parsing lives in `src/lib/elo.py`.

Run: python -m src.fetch_elo
"""
from __future__ import annotations

import time
import urllib.parse
import urllib.request

import pandas as pd

from src.lib import config

# StatsBomb team name -> eloratings.net file stem. Default rule = spaces to underscores; only the
# genuine spelling divergences are listed here (verified live against the site, 2026-07-01).
ALIAS = {
    "Côte d'Ivoire": "Ivory_Coast",
    "Congo DR": "DR_Congo",
    "Cape Verde Islands": "Cape_Verde",
    "Czech Republic": "Czechia",
    "South Korea": "South_Korea",
    "United States": "United_States",
}
DEST = config.RAW / "elo"


def file_stem(team: str) -> str:
    return ALIAS.get(team, team.replace(" ", "_"))


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    matches = pd.read_parquet(config.INTERIM / "matches.parquet")
    teams = sorted(set(matches["home"]) | set(matches["away"]))
    ok, failed = [], []
    for team in teams:
        stem = file_stem(team)
        out = DEST / f"{stem}.tsv"
        if out.exists() and out.stat().st_size > 500:
            ok.append(team)
            continue
        url = "http://eloratings.net/" + urllib.parse.quote(stem) + ".tsv"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read()
            if len(body) < 500 or b"404 Not Found" in body[:400]:
                failed.append((team, stem, "empty/404"))
                continue
            out.write_bytes(body)
            ok.append(team)
            print(f"  fetched {team:24s} -> {stem}.tsv  ({len(body)} bytes)")
            time.sleep(0.3)
        except Exception as e:  # noqa: BLE001
            failed.append((team, stem, str(e)))
    print(f"\n  ok={len(ok)}  failed={len(failed)}")
    for team, stem, why in failed:
        print(f"  FAILED {team!r} (tried {stem!r}): {why}")


if __name__ == "__main__":
    main()
