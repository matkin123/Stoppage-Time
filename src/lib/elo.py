"""Parse cached eloratings.net per-team histories into pre-match ratings (ADR-0034 support).

Raw files live in `data/raw/elo/<stem>.tsv` (see `src/fetch_elo.py`). Each row is one match:

    col 0..2  year mon day
    col 3,4   HOME AWAY  (eloratings 2-letter codes)
    col 5,6   home_score away_score
    col 7     match type (F, WQ, WC, EC, CA, AF, ...)
    col 8     host code (blank if played in the home team's country)
    col 9     signed Elo change of the HOME team (zero-sum: away change = -this)
    col 10,11 home_elo_after, away_elo_after

So pre-match ratings come straight from a single row (no previous-row bookkeeping):

    home_pre = col10 - col9      away_pre = col11 + col9

A team plays at most one match per calendar day, so a (team-file, date) key is unique. We read the
HOME team's file, locate the match by date (with a +/-1 day tolerance for TZ drift), and read both
pre-match ratings off that one row. `owner_code` (the code present in every row of a file) tells us
which side of the row the file's team is on, so we can orient to StatsBomb home/away regardless of
the neutral-venue orientation eloratings used.
"""
from __future__ import annotations

import datetime as dt
import functools

import pandas as pd

from src.lib import config

ELO_DIR = config.RAW / "elo"

ALIAS = {
    "Côte d'Ivoire": "Ivory_Coast",
    "Congo DR": "DR_Congo",
    "Cape Verde Islands": "Cape_Verde",
    "Czech Republic": "Czechia",
    "South Korea": "South_Korea",
    "United States": "United_States",
}


def file_stem(team: str) -> str:
    return ALIAS.get(team, team.replace(" ", "_"))


@functools.lru_cache(maxsize=128)
def load_team(team: str) -> pd.DataFrame:
    """One team's full match history with per-row pre-match ratings for both sides."""
    path = ELO_DIR / f"{file_stem(team)}.tsv"
    df = pd.read_csv(path, sep="\t", header=None, usecols=range(12), dtype=str,
                     names=["y", "m", "d", "home", "away", "hs", "as_", "type", "host",
                            "dhome", "home_after", "away_after"])
    df["date"] = pd.to_datetime(df["y"] + "-" + df["m"] + "-" + df["d"], errors="coerce")
    for c in ("hs", "as_", "dhome", "home_after", "away_after"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["date", "dhome", "home_after", "away_after"]).reset_index(drop=True)
    df["home_pre"] = df["home_after"] - df["dhome"]
    df["away_pre"] = df["away_after"] + df["dhome"]
    return df


def owner_code(df: pd.DataFrame) -> str:
    """The 2-letter code present in every row = the team whose file this is."""
    common = set(df["home"]) & set(df["away"])
    if len(common) != 1:
        # fall back to the most frequent code across both columns
        counts = pd.concat([df["home"], df["away"]]).value_counts()
        return str(counts.index[0])
    return next(iter(common))


def match_pre_elos(home: str, away: str, date, tol_days: int = 1):
    """Pre-match (home_elo, away_elo, meta) for a StatsBomb match, oriented to home/away.

    Reads the HOME team's file; falls back to the AWAY team's file. Returns None if neither has a
    row within `tol_days` of `date`. `meta` carries the eloratings score for an integrity check.
    """
    target = pd.Timestamp(date).normalize()

    def from_file(team: str, want: str):
        df = load_team(team)
        oc = owner_code(df)
        cand = df[(df["date"] - target).abs() <= pd.Timedelta(days=tol_days)].copy()
        if cand.empty:
            return None
        cand["gap"] = (cand["date"] - target).abs()
        row = cand.sort_values("gap").iloc[0]
        owner_is_home = row["home"] == oc
        owner_pre = row["home_pre"] if owner_is_home else row["away_pre"]
        opp_pre = row["away_pre"] if owner_is_home else row["home_pre"]
        owner_score = row["hs"] if owner_is_home else row["as_"]
        opp_score = row["as_"] if owner_is_home else row["hs"]
        if want == "home":
            return owner_pre, opp_pre, owner_score, opp_score, row["date"]
        return opp_pre, owner_pre, opp_score, owner_score, row["date"]

    res = from_file(home, "home")
    if res is None:
        res = from_file(away, "away")
    if res is None:
        return None
    home_pre, away_pre, hs, as_, mdate = res
    return {"home_elo": float(home_pre), "away_elo": float(away_pre),
            "elo_hs": None if pd.isna(hs) else int(hs),
            "elo_as": None if pd.isna(as_) else int(as_),
            "elo_date": mdate.date().isoformat()}
