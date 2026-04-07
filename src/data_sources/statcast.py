"""
src/data_sources/statcast.py
==============================
Pull Statcast advanced metrics for batters using pybaseball.
Data sourced from Baseball Savant (baseballsavant.mlb.com).

Metrics pulled:
    exit_velo_avg    Average exit velocity (mph)
    exit_velo_l30    Exit velocity last 30 days
    hard_hit_pct     Hard hit percentage (exit velo >= 95 mph)
    xba              Expected batting average
    launch_angle     Average launch angle
    sprint_speed     Sprint speed (ft/sec) — proxy for leg hits

Main functions:
    get_statcast_batter(name)     -> dict of advanced metrics
    enrich_hitter_statcast(h)     -> fills Hitter object with metrics
"""

import json
import time
import datetime
from pathlib import Path

CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

PYBASEBALL_AVAILABLE = False
try:
    import pybaseball as pb
    pb.cache.enable()
    PYBASEBALL_AVAILABLE = True
except ImportError:
    print("  [warn] pybaseball not installed — Statcast metrics unavailable")
except Exception as e:
    print(f"  [warn] pybaseball failed to load: {e}")


def _lookup_player_id(last: str, first: str) -> int | None:
    """
    Look up a player's MLB AM id using pybaseball.
    Returns the integer id or None if not found.
    """
    if not PYBASEBALL_AVAILABLE:
        return None
    try:
        results = pb.playerid_lookup(last, first)
        if results.empty:
            return None
        # Filter to active players first
        active = results[results["mlb_played_last"] >= datetime.date.today().year - 1]
        if not active.empty:
            return int(active.iloc[0]["key_mlbam"])
        return int(results.iloc[0]["key_mlbam"])
    except Exception as e:
        print(f"  [warn] Player ID lookup failed for {first} {last}: {e}")
        return None


def _parse_name(full_name: str) -> tuple[str, str]:
    """
    Split a full name into first and last.
    Handles names like 'Freddie Freeman' -> ('Freeman', 'Freddie')
    Handles suffixes like 'Vladimir Guerrero Jr.' -> ('Guerrero', 'Vladimir')
    """
    parts = full_name.strip().split()
    if len(parts) < 2:
        return full_name, ""
    # Strip common suffixes
    suffixes = {"jr.", "sr.", "ii", "iii", "iv"}
    while parts and parts[-1].lower() in suffixes:
        parts.pop()
    if len(parts) < 2:
        return full_name, ""
    first = parts[0]
    last = " ".join(parts[1:])
    return last, first


def get_statcast_batter(name: str, days_back: int = 365) -> dict:
    """
    Pull Statcast metrics for a batter by full name.

    Args:
        name:      Full player name e.g. "Freddie Freeman"
        days_back: How many days of data to pull (default full season)

    Returns dict with:
        exit_velo_avg, exit_velo_l30, hard_hit_pct,
        xba, launch_angle, sprint_speed
    Returns {} if pybaseball unavailable or player not found.
    """
    if not PYBASEBALL_AVAILABLE:
        print(f"  [warn] pybaseball unavailable — skipping Statcast for {name}")
        return {}

    cache_file = CACHE_DIR / f"statcast_{name.lower().replace(' ', '_')}.json"
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < 3600:  # Cache valid for 1 hour
            with open(cache_file) as f:
                return json.load(f)

    last, first = _parse_name(name)
    print(f"  Looking up Statcast data for {name}...")

    player_id = _lookup_player_id(last, first)
    if not player_id:
        print(f"  [warn] Could not find player ID for {name}")
        return {}

    today = datetime.date.today()
    season_start = datetime.date(today.year, 3, 1)
    thirty_days_ago = today - datetime.timedelta(days=30)

    try:
        print(f"  Fetching Statcast data (player_id={player_id})...")

        # Full season data
        season_data = pb.statcast_batter(
            str(season_start),
            str(today),
            player_id=player_id
        )

        if season_data is None or season_data.empty:
            print(f"  [warn] No Statcast data found for {name}")
            return {}

        # Last 30 days subset
        recent_data = season_data[
            season_data["game_date"] >= str(thirty_days_ago)
        ]

        def safe_mean(series, decimals=1):
            try:
                val = series.dropna().mean()
                return round(float(val), decimals) if val == val else None
            except Exception:
                return None

        # Exit velocity
        exit_velo_avg = safe_mean(season_data["launch_speed"])
        exit_velo_l30 = safe_mean(recent_data["launch_speed"]) if not recent_data.empty else None

        # Hard hit % (exit velo >= 95 mph)
        hard_hit_pct = None
        if "launch_speed" in season_data.columns:
            valid = season_data["launch_speed"].dropna()
            if len(valid) > 0:
                hard_hit_pct = round(
                    float((valid >= 95).sum() / len(valid) * 100), 1
                )

        # Expected batting average
        xba = None
        if "estimated_ba_using_speedangle" in season_data.columns:
            xba = safe_mean(season_data["estimated_ba_using_speedangle"], decimals=3)

        # Launch angle
        launch_angle = safe_mean(season_data["launch_angle"])

        result = {
            "name":          name,
            "player_id":     player_id,
            "exit_velo_avg": exit_velo_avg,
            "exit_velo_l30": exit_velo_l30,
            "hard_hit_pct":  hard_hit_pct,
            "xba":           xba,
            "launch_angle":  launch_angle,
        }

        # Remove None values for cleaner output
        result = {k: v for k, v in result.items() if v is not None}

        with open(cache_file, "w") as f:
            json.dump(result, f, indent=2)

        print(f"  [ok] Statcast for {name}: EV={exit_velo_avg} Hard%={hard_hit_pct} xBA={xba}")
        return result

    except Exception as e:
        print(f"  [error] Statcast fetch failed for {name}: {e}")
        return {}


def get_sprint_speed(name: str, season: int = None) -> float | None:
    """
    Get a player's sprint speed (ft/sec) from Baseball Savant.
    Higher sprint speed = more infield hits.

    Returns float or None if unavailable.
    """
    if not PYBASEBALL_AVAILABLE:
        return None

    if season is None:
        season = datetime.date.today().year

    cache_file = CACHE_DIR / f"sprint_{name.lower().replace(' ', '_')}_{season}.json"
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < 86400:  # Cache valid for 24 hours
            with open(cache_file) as f:
                data = json.load(f)
                return data.get("sprint_speed")

    last, first = _parse_name(name)
    player_id = _lookup_player_id(last, first)
    if not player_id:
        return None

    try:
        speed_data = pb.statcast_sprint_speed(season)
        if speed_data is None or speed_data.empty:
            return None

        player_row = speed_data[speed_data["player_id"] == player_id]
        if player_row.empty:
            return None

        speed = round(float(player_row.iloc[0]["sprint_speed"]), 1)

        with open(cache_file, "w") as f:
            json.dump({"sprint_speed": speed}, f)

        print(f"  [ok] Sprint speed for {name}: {speed} ft/sec")
        return speed

    except Exception as e:
        print(f"  [warn] Sprint speed fetch failed for {name}: {e}")
        return None


def enrich_hitter_statcast(hitter) -> object:
    """
    Auto-populate a Hitter object with Statcast metrics.
    Only fills in fields that are currently None.

    Args:
        hitter: a Hitter dataclass object

    Returns:
        The same Hitter object with Statcast fields filled in.
    """
    print(f"  Fetching Statcast metrics for {hitter.name}...")

    statcast = get_statcast_batter(hitter.name)

    if not statcast:
        print(f"  [warn] No Statcast data available for {hitter.name}")
        return hitter

    if hitter.exit_velo is None:
        hitter.exit_velo = statcast.get("exit_velo_avg")

    if hitter.hard_pct is None:
        hitter.hard_pct = statcast.get("hard_hit_pct")

    # Store xBA and launch angle in notes if no dedicated field
    extras = []
    if statcast.get("xba"):
        extras.append(f"xBA={statcast['xba']}")
    if statcast.get("launch_angle"):
        extras.append(f"LA={statcast['launch_angle']}")
    if statcast.get("exit_velo_l30"):
        extras.append(f"EV_L30={statcast['exit_velo_l30']}")

    if extras:
        existing_notes = hitter.notes or ""
        statcast_note = " | ".join(extras)
        if statcast_note not in existing_notes:
            hitter.notes = f"{existing_notes} | {statcast_note}".strip(" |")

    return hitter


def clear_statcast_cache():
    """Clear all cached Statcast files."""
    cleared = 0
    for f in CACHE_DIR.glob("statcast_*.json"):
        f.unlink()
        cleared += 1
    for f in CACHE_DIR.glob("sprint_*.json"):
        f.unlink()
        cleared += 1
    print(f"  [cache] Cleared {cleared} Statcast cache files")


if __name__ == "__main__":
    print("Testing Statcast module...\n")

    if not PYBASEBALL_AVAILABLE:
        print("pybaseball is not installed.")
        print("Run: pip install pybaseball --no-cache-dir")
    else:
        name = "Freddie Freeman"
        print(f"Fetching Statcast data for {name}...\n")

        stats = get_statcast_batter(name)
        if stats:
            print("\nStatcast metrics:")
            for k, v in stats.items():
                print(f"  {k}: {v}")
        else:
            print("No data returned.")

        speed = get_sprint_speed(name)
        if speed:
            print(f"\nSprint speed: {speed} ft/sec")
