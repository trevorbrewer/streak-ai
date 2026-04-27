"""
src/data_sources/mlb_stats.py
===============================
Pull player season batting stats from the free MLB Stats API.
No API key required.

Main functions:
    search_player(name)              -> player id and basic info
    get_batter_season_stats(name)    -> full season batting stats dict
    get_batter_recent_stats(name)    -> last 7, 14, 30 day averages
    enrich_hitter_stats(hitter)      -> fills in all stats on a Hitter object
"""

import json
import time
import datetime
import requests
from pathlib import Path

CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MLB_API = "https://statsapi.mlb.com/api/v1"
CURRENT_SEASON = datetime.date.today().year


def _get(url: str, params: dict = None) -> dict:
    """Make a GET request to the MLB Stats API with error handling."""
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print(f"  [error] Request timed out: {url}")
        return {}
    except requests.exceptions.HTTPError as e:
        print(f"  [error] HTTP error {e.response.status_code}: {url}")
        return {}
    except Exception as e:
        print(f"  [error] Request failed: {e}")
        return {}


def search_player(name: str) -> dict:
    """
    Search for a player by name and return their basic info.

    Returns dict with: id, full_name, position, team, active
    Returns {} if not found.

    Example:
        player = search_player("Freddie Freeman")
        print(player["id"])  -> 501303
    """
    cache_file = CACHE_DIR / f"player_search_{name.lower().replace(' ', '_')}.json"
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < 86400:  # Cache valid for 24 hours
            with open(cache_file) as f:
                return json.load(f)

    print(f"  Searching MLB API for: {name}")
    data = _get(f"{MLB_API}/people/search", params={"names": name, "sportId": 1})

    if not data or not data.get("people"):
        print(f"  [warn] Player not found: {name}")
        return {}

    # Take the first active match
    people = data["people"]
    active = [p for p in people if p.get("active", False)]
    person = active[0] if active else people[0]

    result = {
        "id":        person["id"],
        "full_name": person.get("fullName", name),
        "position":  person.get("primaryPosition", {}).get("abbreviation", ""),
        "team":      person.get("currentTeam", {}).get("name", ""),
        "active":    person.get("active", False),
    }

    with open(cache_file, "w") as f:
        json.dump(result, f, indent=2)

    return result


def get_batter_season_stats(name: str, season: int = None) -> dict:
    """
    Get full season batting stats for a player by name.

    Returns dict with all standard batting stats.
    Returns {} if player not found or no stats available.

    Example:
        stats = get_batter_season_stats("Freddie Freeman")
        print(stats["avg"])   -> 0.302
        print(stats["woba"])  -> 0.375
    """
    if season is None:
        season = CURRENT_SEASON

    cache_file = CACHE_DIR / f"season_stats_{name.lower().replace(' ', '_')}_{season}.json"
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < 3600:  # Cache valid for 1 hour
            with open(cache_file) as f:
                return json.load(f)

    player = search_player(name)
    if not player:
        return {}

    player_id = player["id"]
    print(f"  Fetching {season} season stats for {name} (id: {player_id})")

    data = _get(
        f"{MLB_API}/people/{player_id}",
        params={"hydrate": f"stats(group=hitting,type=season,season={season})"}
    )

    if not data or not data.get("people"):
        return {}

    person = data["people"][0]
    stats_groups = person.get("stats", [])

    if not stats_groups:
        print(f"  [warn] No season stats found for {name}")
        return {}

    raw = stats_groups[0].get("splits", [])
    if not raw:
        return {}

    s = raw[-1].get("stat", {})

    def safe_float(val, default=None):
        try:
            return round(float(val), 3) if val not in (None, "", "-") else default
        except (ValueError, TypeError):
            return default

    def safe_int(val, default=0):
        try:
            return int(val) if val not in (None, "") else default
        except (ValueError, TypeError):
            return default

    result = {
        "name":       name,
        "player_id":  player_id,
        "season":     season,
        "avg":        safe_float(s.get("avg")),
        "obp":        safe_float(s.get("obp")),
        "slg":        safe_float(s.get("slg")),
        "ops":        safe_float(s.get("ops")),
        "woba":       safe_float(s.get("woba")),
        "babip":      safe_float(s.get("babip")),
        "hits":       safe_int(s.get("hits")),
        "at_bats":    safe_int(s.get("atBats")),
        "home_runs":  safe_int(s.get("homeRuns")),
        "rbi":        safe_int(s.get("rbi")),
        "stolen_bases": safe_int(s.get("stolenBases")),
        "walks":      safe_int(s.get("baseOnBalls")),
        "strikeouts": safe_int(s.get("strikeOuts")),
        "games":      safe_int(s.get("gamesPlayed")),
        "plate_appearances": safe_int(s.get("plateAppearances")),
    }

    with open(cache_file, "w") as f:
        json.dump(result, f, indent=2)

    print(f"  [ok] {name}: AVG={result['avg']} OBP={result['obp']} SLG={result['slg']}")
    return result


def get_batter_recent_stats(name: str) -> dict:
    """
    Get last 7, 14, and 30 game batting averages for a player.
    Uses game log (actual games played) instead of calendar date
    ranges for accuracy.

    Returns dict with: l7, l14, l30
    Returns {} if not available.
    """
    cache_file = CACHE_DIR / f"recent_stats_{name.lower().replace(' ', '_')}.json"
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < 3600:
            with open(cache_file) as f:
                return json.load(f)

    player = search_player(name)
    if not player:
        return {}

    player_id = player["id"]
    season = CURRENT_SEASON

    try:
        url = f"{MLB_API}/people/{player_id}/stats"
        params = {
            "stats": "gameLog",
            "group": "hitting",
            "season": season,
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  [warn] Game log fetch failed for {name}: {e}")
        return {}

    splits = data.get("stats", [{}])[0].get("splits", [])
    if not splits:
        print(f"  [warn] No game log data for {name}")
        return {}

    result = {}

    for days, key in [(7, "l7"), (14, "l14"), (30, "l30")]:
        games = splits[-days:] if len(splits) >= days else splits
        if not games:
            continue

        total_h  = 0
        total_ab = 0
        for g in games:
            s = g.get("stat", {})
            try:
                total_h  += int(s.get("hits", 0) or 0)
                total_ab += int(s.get("atBats", 0) or 0)
            except (ValueError, TypeError):
                continue

        if total_ab >= 3:
            avg = round(total_h / total_ab, 3)
            # Sanity check
            if 0.000 <= avg <= 0.600:
                result[key] = avg
            else:
                print(f"  [warn] {key} avg {avg} out of range — skipping")

    if result:
        with open(cache_file, "w") as f:
            json.dump(result, f, indent=2)
        print(f"  [ok] Recent stats for {name} (game log): {result}")

    return result


def enrich_hitter_stats(hitter) -> object:
    """
    Auto-populate a Hitter object with current season stats
    and recent averages pulled from the MLB Stats API.

    Only fills in fields that are currently None — won't
    overwrite stats you've manually set.

    Args:
        hitter: a Hitter dataclass object

    Returns:
        The same Hitter object with stats filled in.
    """
    print(f"\n  Enriching stats for {hitter.name}...")

    # Season stats
    season = get_batter_season_stats(hitter.name)
    if season:
        if hitter.avg == 0.0 or hitter.avg is None:
            hitter.avg = season.get("avg") or hitter.avg
        if hitter.obp == 0.0 or hitter.obp is None:
            hitter.obp = season.get("obp") or hitter.obp
        if hitter.slg == 0.0 or hitter.slg is None:
            hitter.slg = season.get("slg") or hitter.slg
        if hitter.woba is None:
            hitter.woba = season.get("woba")
        if hitter.babip is None:
            hitter.babip = season.get("babip")

    # Recent averages
    recent = get_batter_recent_stats(hitter.name)
    if recent:
        if hitter.l7 is None:
            hitter.l7 = recent.get("l7")
        if hitter.l14 is None:
            hitter.l14 = recent.get("l14")
        if hitter.l30 is None:
            hitter.l30 = recent.get("l30")

    return hitter


def clear_stats_cache():
    """Clear all cached stats files. Useful at start of each day."""
    cleared = 0
    for f in CACHE_DIR.glob("season_stats_*.json"):
        f.unlink()
        cleared += 1
    for f in CACHE_DIR.glob("recent_stats_*.json"):
        f.unlink()
        cleared += 1
    print(f"  [cache] Cleared {cleared} stats cache files")


if __name__ == "__main__":
    # Quick test — run this file directly to verify it works
    print("Testing MLB Stats API...\n")

    player = search_player("Freddie Freeman")
    print(f"Player found: {player}\n")

    stats = get_batter_season_stats("Freddie Freeman")
    print(f"Season stats: {stats}\n")

    recent = get_batter_recent_stats("Freddie Freeman")
    print(f"Recent stats: {recent}\n")
