"""
src/data_sources/schedule.py
==============================
Automatically pulls today's MLB schedule, starting pitchers,
lineups, and park info. No API key required.

Main functions:
    get_todays_games()           -> list of all games today
    get_starting_pitcher()       -> pitcher stats for a team in a game
    get_lineup()                 -> confirmed batting order for a team
    enrich_hitter_matchup()      -> auto-fills one hitter's matchup fields
    enrich_all_hitters()         -> auto-fills entire roster
"""

import json
import time
import datetime
import requests
from pathlib import Path

CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MLB_API = "https://statsapi.mlb.com/api/v1"

TEAM_ABBR = {
    108: "LAA", 109: "ARI", 110: "BAL", 111: "BOS", 112: "CHC",
    113: "CIN", 114: "CLE", 115: "COL", 116: "DET", 117: "HOU",
    118: "KC",  119: "LAD", 120: "WSH", 121: "NYM", 133: "OAK",
    134: "PIT", 135: "SD",  136: "SEA", 137: "SF",  138: "STL",
    139: "TB",  140: "TEX", 141: "TOR", 142: "MIN", 143: "PHI",
    144: "ATL", 145: "CWS", 146: "MIA", 147: "NYY", 158: "MIL",
}


def _get(url: str, params: dict = None) -> dict:
    """Make a GET request with error handling."""
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print(f"  [error] Request timed out: {url}")
        return {}
    except requests.exceptions.HTTPError as e:
        print(f"  [error] HTTP {e.response.status_code}: {url}")
        return {}
    except Exception as e:
        print(f"  [error] Request failed: {e}")
        return {}


def get_todays_games(date: str = None) -> list:
    """
    Fetch all MLB games scheduled for today.

    Args:
        date: "YYYY-MM-DD" string, defaults to today

    Returns list of game dicts with:
        game_id, home_team, away_team, home_abbr, away_abbr,
        venue, game_time, status
    """
    if date is None:
        date = datetime.date.today().isoformat()

    cache_file = CACHE_DIR / f"schedule_{date}.json"
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < 1800:  # Cache valid for 30 minutes
            print(f"  [cache] Schedule loaded from cache for {date}")
            with open(cache_file) as f:
                return json.load(f)

    print(f"  Fetching MLB schedule for {date}...")
    data = _get(
        f"{MLB_API}/schedule",
        params={"sportId": 1, "date": date, "hydrate": "team,venue"}
    )

    if not data:
        return []

    games = []
    for date_entry in data.get("dates", []):
        for g in date_entry.get("games", []):
            home = g["teams"]["home"]["team"]
            away = g["teams"]["away"]["team"]
            games.append({
                "game_id":   g["gamePk"],
                "status":    g["status"]["detailedState"],
                "game_time": g.get("gameDate", ""),
                "venue":     g.get("venue", {}).get("name", ""),
                "home_id":   home["id"],
                "home_team": home["name"],
                "home_abbr": TEAM_ABBR.get(home["id"], "?"),
                "away_id":   away["id"],
                "away_team": away["name"],
                "away_abbr": TEAM_ABBR.get(away["id"], "?"),
            })

    with open(cache_file, "w") as f:
        json.dump(games, f, indent=2)

    print(f"  [ok] {len(games)} games found for {date}")
    return games


def _fetch_pitcher_stats(pitcher_id: int) -> dict:
    """Fetch full season stats for a pitcher by player ID."""
    data = _get(
        f"{MLB_API}/people/{pitcher_id}",
        params={"hydrate": "stats(group=pitching,type=season)"}
    )

    if not data or not data.get("people"):
        return {}

    person = data["people"][0]
    stats_groups = person.get("stats", [])

    stats = {}
    if stats_groups:
        splits = stats_groups[0].get("splits", [])
        if splits:
            s = splits[-1].get("stat", {})

            def safe_float(val, default=None):
                try:
                    return round(float(val), 2) if val not in (None, "", "-") else default
                except (ValueError, TypeError):
                    return default

            stats = {
                "era":          safe_float(s.get("era")),
                "whip":         safe_float(s.get("whip")),
                "k_per_9":      safe_float(s.get("strikeoutsPer9Inn")),
                "bb_per_9":     safe_float(s.get("walksPer9Inn")),
                "avg_against":  safe_float(s.get("avg")),
                "innings":      safe_float(s.get("inningsPitched")),
            }

    return {
        "id":   pitcher_id,
        "name": person.get("fullName", "Unknown"),
        "hand": person.get("pitchHand", {}).get("code", "R"),
        **stats
    }


def get_starting_pitcher(game_id: int, team_abbr: str) -> dict:
    """
    Fetch the confirmed or probable starting pitcher for a team.

    Args:
        game_id:   MLB game ID
        team_abbr: team abbreviation e.g. "LAD"

    Returns dict with: id, name, hand, era, whip, k_per_9, bb_per_9
    Returns {} if pitcher not yet announced.
    """
    cache_file = CACHE_DIR / f"pitcher_{game_id}_{team_abbr}.json"
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < 1800:
            with open(cache_file) as f:
                return json.load(f)

    # Try probable pitchers endpoint first — available earlier in the day
    print(f"  Fetching probable pitcher for {team_abbr}...")
    data = _get(
        f"{MLB_API}/schedule",
        params={"gamePk": game_id, "hydrate": "probablePitcher"}
    )

    pitcher_id = None
    for date_entry in data.get("dates", []):
        for g in date_entry.get("games", []):
            for side in ["home", "away"]:
                team = g["teams"][side]
                abbr = TEAM_ABBR.get(team["team"]["id"], "?")
                if abbr == team_abbr:
                    pp = team.get("probablePitcher")
                    if pp:
                        pitcher_id = pp["id"]
                    break

    if not pitcher_id:
        print(f"  [warn] No pitcher announced yet for {team_abbr}")
        return {}

    result = _fetch_pitcher_stats(pitcher_id)

    if result:
        with open(cache_file, "w") as f:
            json.dump(result, f, indent=2)
        print(f"  [ok] Pitcher: {result.get('name')} ({result.get('hand')}HP) ERA {result.get('era')}")

    return result


def get_lineup(game_id: int, team_abbr: str) -> list:
    """
    Fetch the confirmed batting lineup for a team.

    Returns list of player dicts: {name, id, batting_order, position}
    Returns [] if lineup not yet posted.
    """
    cache_file = CACHE_DIR / f"lineup_{game_id}_{team_abbr}.json"
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < 900:  # Cache valid for 15 minutes
            with open(cache_file) as f:
                return json.load(f)

    data = _get(f"{MLB_API}/game/{game_id}/boxscore")
    if not data:
        return []

    lineup = []
    teams_data = data.get("teams", {})

    for side in ["home", "away"]:
        team_info = teams_data.get(side, {})
        abbr = TEAM_ABBR.get(
            team_info.get("team", {}).get("id", 0), "?"
        )
        if abbr != team_abbr:
            continue

        batting_order = team_info.get("battingOrder", [])
        all_players = team_info.get("players", {})

        for order_idx, player_id in enumerate(batting_order):
            pid_key = f"ID{player_id}"
            player_data = all_players.get(pid_key, {})
            person = player_data.get("person", {})
            position = player_data.get("position", {}).get("abbreviation", "")
            lineup.append({
                "id":            player_id,
                "name":          person.get("fullName", ""),
                "batting_order": order_idx + 1,
                "position":      position,
            })
        break

    if lineup:
        with open(cache_file, "w") as f:
            json.dump(lineup, f, indent=2)

    return lineup


def find_game_for_team(team_abbr: str, date: str = None) -> dict:
    """
    Find today's game for a given team abbreviation.

    Returns the game dict or {} if the team has no game today.
    """
    games = get_todays_games(date)
    for g in games:
        if g["home_abbr"] == team_abbr or g["away_abbr"] == team_abbr:
            return g
    return {}


def enrich_hitter_matchup(hitter, date: str = None) -> object:
    """
    Auto-populate a Hitter object's matchup fields by looking up
    their team's game in today's MLB schedule.

    Fills in:
        opp, pitcher, phand, era, park, home_away, batting_order
        plus pitcher whip, k_per_9, bb_per_9

    Args:
        hitter: a Hitter dataclass object with at least name and team set
        date:   "YYYY-MM-DD" string, defaults to today

    Returns:
        The same Hitter object with matchup fields filled in.
    """
    team = (hitter.team or "").upper()
    if not team:
        print(f"  [warn] No team set for {hitter.name} — skipping matchup")
        return hitter

    print(f"\n  Looking up game for {hitter.name} ({team})...")

    game = find_game_for_team(team, date)
    if not game:
        print(f"  [warn] {team} has no game today")
        hitter.notes = (hitter.notes or "") + " | NO GAME TODAY"
        return hitter

    # Determine home or away
    is_home = game["home_abbr"] == team
    opp_abbr = game["away_abbr"] if is_home else game["home_abbr"]

    hitter.opp       = opp_abbr
    hitter.park      = game["venue"]
    hitter.home_away = "home" if is_home else "away"

    print(f"  Matchup: {team} {'vs' if is_home else '@'} {opp_abbr} at {game['venue']}")

    # Get opposing starting pitcher
    pitcher = get_starting_pitcher(game["game_id"], opp_abbr)
    if pitcher:
        hitter.pitcher  = pitcher.get("name", "TBD")
        hitter.phand    = pitcher.get("hand", "R")
        hitter.era      = pitcher.get("era")
    else:
        hitter.pitcher = "TBD"
        print(f"  [warn] Pitcher not yet announced for {opp_abbr}")

    # Get batting order slot if lineup is posted
    lineup = get_lineup(game["game_id"], team)
    if lineup:
        for player in lineup:
            if hitter.name.lower() in player["name"].lower():
                hitter.batting_order = player["batting_order"]
                print(f"  Batting {hitter.batting_order}th in the order")
                break

    return hitter


def enrich_all_hitters(hitters: list, date: str = None) -> list:
    """
    Enrich an entire roster with today's matchup data.

    Hitters with no game today are removed from the returned list
    so they don't get scored for a game that isn't happening.

    Args:
        hitters: list of Hitter dataclass objects
        date:    "YYYY-MM-DD" string, defaults to today

    Returns:
        Filtered list of Hitter objects with matchup fields filled in.
    """
    if not hitters:
        print("  [warn] No hitters to enrich")
        return []

    print(f"\n[schedule] Enriching {len(hitters)} hitters with today's matchups...")
    games = get_todays_games(date)
    print(f"[schedule] {len(games)} games on the slate\n")

    active = []
    no_game = []

    for h in hitters:
        h = enrich_hitter_matchup(h, date)
        if "NO GAME TODAY" in (h.notes or ""):
            no_game.append(h.name)
        else:
            active.append(h)

    if no_game:
        print(f"\n[info] No game today for: {', '.join(no_game)}")
        print("[info] These hitters will be excluded from scoring.")

    print(f"\n[ok] {len(active)} hitters ready to score")
    return active


def print_todays_slate(date: str = None):
    """Pretty print today's full game slate. Useful for debugging."""
    games = get_todays_games(date)
    date_str = date or datetime.date.today().isoformat()
    print(f"\n{'='*52}")
    print(f"  MLB Schedule — {date_str}")
    print(f"{'='*52}")
    if not games:
        print("  No games found.")
    for g in games:
        time_str = g["game_time"][11:16] if len(g["game_time"]) > 10 else ""
        print(f"  {g['away_abbr']:4} @ {g['home_abbr']:4}  {g['venue'][:28]:28}  {time_str}")
    print()


def clear_schedule_cache(date: str = None):
    """Clear cached schedule, pitcher, and lineup files."""
    target = date or datetime.date.today().isoformat()
    cleared = 0
    for f in CACHE_DIR.glob(f"schedule_{target}.json"):
        f.unlink()
        cleared += 1
    for f in CACHE_DIR.glob("pitcher_*.json"):
        f.unlink()
        cleared += 1
    for f in CACHE_DIR.glob("lineup_*.json"):
        f.unlink()
        cleared += 1
    print(f"  [cache] Cleared {cleared} schedule cache files")

def get_top_of_order_hitters(date: str = None, slots: tuple = (1, 2, 3, 4)) -> list:
    """
    Pull every player batting in slots 1-4 across all of today's games.
    Returns a list of Hitter objects ready for enrichment and scoring.
    Does not save to hitters.json — fresh slate every day.

    Args:
        date:  "YYYY-MM-DD" string, defaults to today
        slots: batting order slots to include, default (1, 2, 3, 4)

    Returns:
        list of Hitter objects with name, team, opp, pitcher,
        phand, era, park, home_away, batting_order populated.
    """
    from src.models import Hitter

    if date is None:
        date = datetime.date.today().isoformat()

    games = get_todays_games(date)
    if not games:
        print("  [warn] No games found for auto-roster")
        return []

    print(f"\n[auto-roster] Scanning lineups for slots {slots} across {len(games)} games...")

    hitters = []
    seen_ids = set()

    for game in games:
        game_id   = game["game_id"]
        home_abbr = game["home_abbr"]
        away_abbr = game["away_abbr"]

        for side, team_abbr, opp_abbr in [
            ("home", home_abbr, away_abbr),
            ("away", away_abbr, home_abbr),
        ]:
            lineup = get_lineup(game_id, team_abbr)
            if not lineup:
                continue

            pitcher = get_starting_pitcher(game_id, opp_abbr)

            for player in lineup:
                if player["batting_order"] not in slots:
                    continue
                if player["id"] in seen_ids:
                    continue
                if not player["name"]:
                    continue

                seen_ids.add(player["id"])

                h = Hitter(
                    id=player["id"],
                    name=player["name"],
                    team=team_abbr,
                    opp=opp_abbr,
                    park=game["venue"],
                    home_away=side,
                    batting_order=player["batting_order"],
                    pitcher=pitcher.get("name") if pitcher else "TBD",
                    phand=pitcher.get("hand", "R") if pitcher else "R",
                    era=pitcher.get("era") if pitcher else None,
                )
                hitters.append(h)
                print(
                    f"  [auto] #{player['batting_order']} "
                    f"{player['name']} ({team_abbr}) "
                    f"vs {pitcher.get('name', 'TBD') if pitcher else 'TBD'}"
                )

    print(f"\n[auto-roster] Found {len(hitters)} hitters batting 1-4 today")
    return hitters


if __name__ == "__main__":
    print_todays_slate()

    print("Testing matchup enrichment for Freddie Freeman (LAD)...\n")
    from src.models import Hitter
    hitter = Hitter(name="Freddie Freeman", team="LAD")
    result = enrich_hitter_matchup(hitter)
    print(f"\nResult:")
    print(f"  Opponent:       {result.opp}")
    print(f"  Pitcher:        {result.pitcher}")
    print(f"  Pitcher hand:   {result.phand}")
    print(f"  ERA:            {result.era}")
    print(f"  Park:           {result.park}")
    print(f"  Home/Away:      {result.home_away}")
    print(f"  Batting order:  {result.batting_order}")
