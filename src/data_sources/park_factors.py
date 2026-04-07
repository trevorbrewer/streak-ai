"""
src/data_sources/park_factors.py
==================================
Built-in park factors database for all 30 MLB stadiums.
Data sourced from FanGraphs park factors (3-year rolling average).

hits_factor:  >1.0 favors hitters, <1.0 favors pitchers
hr_factor:    home run park factor
doubles_factor: doubles park factor

Usage:
    from src.data_sources.park_factors import get_park_factor
    factor = get_park_factor("Coors Field")
    print(factor["hits_factor"])  -> 1.22
"""

PARK_FACTORS = {
    "Coors Field": {
        "team": "COL",
        "city": "Denver",
        "hits_factor":    1.22,
        "hr_factor":      1.35,
        "doubles_factor": 1.18,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   5200,
        "notes":          "Highest elevation in MLB, massive hitter boost",
    },
    "Great American Ball Park": {
        "team": "CIN",
        "city": "Cincinnati",
        "hits_factor":    1.10,
        "hr_factor":      1.18,
        "doubles_factor": 1.08,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   490,
        "notes":          "Small park, strong HR environment",
    },
    "Fenway Park": {
        "team": "BOS",
        "city": "Boston",
        "hits_factor":    1.08,
        "hr_factor":      0.97,
        "doubles_factor": 1.24,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   20,
        "notes":          "Green Monster creates many doubles",
    },
    "Wrigley Field": {
        "team": "CHC",
        "city": "Chicago",
        "hits_factor":    1.05,
        "hr_factor":      1.04,
        "doubles_factor": 1.02,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   595,
        "notes":          "Wind off Lake Michigan is huge factor",
    },
    "Camden Yards": {
        "team": "BAL",
        "city": "Baltimore",
        "hits_factor":    1.07,
        "hr_factor":      1.11,
        "doubles_factor": 1.05,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   10,
        "notes":          "Hitter friendly, short RF",
    },
    "Yankee Stadium": {
        "team": "NYY",
        "city": "New York",
        "hits_factor":    1.03,
        "hr_factor":      1.22,
        "doubles_factor": 0.98,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   55,
        "notes":          "Short RF porch boosts HR, not hits",
    },
    "Globe Life Field": {
        "team": "TEX",
        "city": "Arlington",
        "hits_factor":    0.98,
        "hr_factor":      1.05,
        "doubles_factor": 0.96,
        "surface":        "grass",
        "roof":           "retractable",
        "elevation_ft":   551,
        "notes":          "Retractable roof controls weather",
    },
    "Minute Maid Park": {
        "team": "HOU",
        "city": "Houston",
        "hits_factor":    1.02,
        "hr_factor":      1.09,
        "doubles_factor": 1.05,
        "surface":        "grass",
        "roof":           "retractable",
        "elevation_ft":   43,
        "notes":          "Tal's Hill gone but still hitter friendly",
    },
    "Dodger Stadium": {
        "team": "LAD",
        "city": "Los Angeles",
        "hits_factor":    0.97,
        "hr_factor":      0.92,
        "doubles_factor": 0.95,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   512,
        "notes":          "Pitcher friendly, large foul territory",
    },
    "Oracle Park": {
        "team": "SF",
        "city": "San Francisco",
        "hits_factor":    0.89,
        "hr_factor":      0.72,
        "doubles_factor": 0.91,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   10,
        "notes":          "McCovey Cove suppresses power heavily",
    },
    "Petco Park": {
        "team": "SD",
        "city": "San Diego",
        "hits_factor":    0.90,
        "hr_factor":      0.82,
        "doubles_factor": 0.92,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   20,
        "notes":          "Marine layer suppresses offense",
    },
    "Angel Stadium": {
        "team": "LAA",
        "city": "Anaheim",
        "hits_factor":    0.96,
        "hr_factor":      0.94,
        "doubles_factor": 0.97,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   160,
        "notes":          "Slight pitcher lean",
    },
    "T-Mobile Park": {
        "team": "SEA",
        "city": "Seattle",
        "hits_factor":    0.93,
        "hr_factor":      0.88,
        "doubles_factor": 0.94,
        "surface":        "grass",
        "roof":           "retractable",
        "elevation_ft":   17,
        "notes":          "Marine air suppresses offense",
    },
    "Chase Field": {
        "team": "ARI",
        "city": "Phoenix",
        "hits_factor":    1.04,
        "hr_factor":      1.08,
        "doubles_factor": 1.03,
        "surface":        "grass",
        "roof":           "retractable",
        "elevation_ft":   1082,
        "notes":          "Elevation helps offense when roof open",
    },
    "Busch Stadium": {
        "team": "STL",
        "city": "St. Louis",
        "hits_factor":    0.95,
        "hr_factor":      0.88,
        "doubles_factor": 0.96,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   466,
        "notes":          "Slight pitcher lean",
    },
    "PNC Park": {
        "team": "PIT",
        "city": "Pittsburgh",
        "hits_factor":    0.96,
        "hr_factor":      0.91,
        "doubles_factor": 0.98,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   730,
        "notes":          "Beautiful park, slight pitcher lean",
    },
    "American Family Field": {
        "team": "MIL",
        "city": "Milwaukee",
        "hits_factor":    1.01,
        "hr_factor":      1.06,
        "doubles_factor": 0.99,
        "surface":        "grass",
        "roof":           "retractable",
        "elevation_ft":   635,
        "notes":          "Neutral to slight hitter lean",
    },
    "Target Field": {
        "team": "MIN",
        "city": "Minneapolis",
        "hits_factor":    0.97,
        "hr_factor":      0.96,
        "doubles_factor": 0.98,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   830,
        "notes":          "Cold weather early season suppresses offense",
    },
    "Kauffman Stadium": {
        "team": "KC",
        "city": "Kansas City",
        "hits_factor":    1.00,
        "hr_factor":      0.93,
        "doubles_factor": 1.02,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   750,
        "notes":          "Neutral park, large outfield",
    },
    "Progressive Field": {
        "team": "CLE",
        "city": "Cleveland",
        "hits_factor":    0.98,
        "hr_factor":      0.95,
        "doubles_factor": 1.00,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   653,
        "notes":          "Neutral park",
    },
    "Comerica Park": {
        "team": "DET",
        "city": "Detroit",
        "hits_factor":    0.95,
        "hr_factor":      0.88,
        "doubles_factor": 0.97,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   585,
        "notes":          "Large outfield suppresses power",
    },
    "Guaranteed Rate Field": {
        "team": "CWS",
        "city": "Chicago",
        "hits_factor":    1.03,
        "hr_factor":      1.10,
        "doubles_factor": 1.01,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   595,
        "notes":          "Slight hitter lean",
    },
    "Tropicana Field": {
        "team": "TB",
        "city": "St. Petersburg",
        "hits_factor":    0.94,
        "hr_factor":      0.96,
        "doubles_factor": 0.93,
        "surface":        "artificial",
        "roof":           "fixed",
        "elevation_ft":   10,
        "notes":          "Dome suppresses offense, catwalk in play",
    },
    "Truist Park": {
        "team": "ATL",
        "city": "Atlanta",
        "hits_factor":    1.02,
        "hr_factor":      1.05,
        "doubles_factor": 1.01,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   1050,
        "notes":          "Elevation gives slight boost",
    },
    "loanDepot Park": {
        "team": "MIA",
        "city": "Miami",
        "hits_factor":    0.91,
        "hr_factor":      0.87,
        "doubles_factor": 0.92,
        "surface":        "grass",
        "roof":           "retractable",
        "elevation_ft":   6,
        "notes":          "Retractable roof, pitcher friendly",
    },
    "Citi Field": {
        "team": "NYM",
        "city": "New York",
        "hits_factor":    0.96,
        "hr_factor":      0.90,
        "doubles_factor": 0.97,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   20,
        "notes":          "Large park, slight pitcher lean",
    },
    "Citizens Bank Park": {
        "team": "PHI",
        "city": "Philadelphia",
        "hits_factor":    1.06,
        "hr_factor":      1.12,
        "doubles_factor": 1.04,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   20,
        "notes":          "Hitter friendly, strong HR environment",
    },
    "Nationals Park": {
        "team": "WSH",
        "city": "Washington",
        "hits_factor":    0.99,
        "hr_factor":      1.01,
        "doubles_factor": 0.98,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   25,
        "notes":          "Neutral park",
    },
    "Fenway Park": {
        "team": "BOS",
        "city": "Boston",
        "hits_factor":    1.08,
        "hr_factor":      0.97,
        "doubles_factor": 1.24,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   20,
        "notes":          "Green Monster creates many doubles",
    },
    "Rogers Centre": {
        "team": "TOR",
        "city": "Toronto",
        "hits_factor":    1.01,
        "hr_factor":      1.04,
        "doubles_factor": 0.99,
        "surface":        "artificial",
        "roof":           "retractable",
        "elevation_ft":   287,
        "notes":          "Turf boosts groundball hits",
    },
    "Oakland Coliseum": {
        "team": "OAK",
        "city": "Oakland",
        "hits_factor":    0.92,
        "hr_factor":      0.85,
        "doubles_factor": 0.93,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   25,
        "notes":          "Large foul territory, marine air",
    },
}

# Team abbreviation to park name lookup
TEAM_TO_PARK = {v["team"]: k for k, v in PARK_FACTORS.items()}


def get_park_factor(park_name: str) -> dict:
    """
    Get park factors for a ballpark by name.

    Does fuzzy matching so partial names work:
        get_park_factor("Coors")  -> Coors Field data
        get_park_factor("Petco")  -> Petco Park data

    Returns the park factor dict or a neutral default if not found.
    """
    if not park_name:
        return _neutral_park()

    # Exact match first
    if park_name in PARK_FACTORS:
        return {"park_name": park_name, **PARK_FACTORS[park_name]}

    # Fuzzy match — check if any key contains the search string
    park_lower = park_name.lower()
    for name, data in PARK_FACTORS.items():
        if park_lower in name.lower() or name.lower() in park_lower:
            return {"park_name": name, **data}

    # No match found
    print(f"  [warn] Park not found: '{park_name}' — using neutral factors")
    return _neutral_park(park_name)


def get_park_factor_by_team(team_abbr: str) -> dict:
    """
    Get park factors for a team's home stadium by team abbreviation.

    Example:
        get_park_factor_by_team("LAD")  -> Dodger Stadium data
    """
    park_name = TEAM_TO_PARK.get(team_abbr.upper())
    if not park_name:
        print(f"  [warn] No park found for team: {team_abbr}")
        return _neutral_park()
    return get_park_factor(park_name)


def _neutral_park(park_name: str = "Unknown") -> dict:
    """Return neutral park factors when a park isn't found."""
    return {
        "park_name":      park_name,
        "team":           "?",
        "city":           "?",
        "hits_factor":    1.00,
        "hr_factor":      1.00,
        "doubles_factor": 1.00,
        "surface":        "grass",
        "roof":           "open",
        "elevation_ft":   0,
        "notes":          "Neutral — park not found in database",
    }


def is_hitter_friendly(park_name: str, threshold: float = 1.03) -> bool:
    """Return True if the park's hits factor exceeds the threshold."""
    factor = get_park_factor(park_name)
    return factor["hits_factor"] >= threshold


def park_impact_score(park_name: str) -> float:
    """
    Compute a single 0-100 park impact score for hitters.
    50 = neutral, >50 = hitter friendly, <50 = pitcher friendly.
    """
    factor = get_park_factor(park_name)
    hits = factor["hits_factor"]
    score = (hits - 0.80) / (1.30 - 0.80) * 100
    return round(max(0.0, min(100.0, score)), 1)


if __name__ == "__main__":
    print("Park Factors Database\n")
    print(f"{'Park':<35} {'Hits':>6} {'HR':>6} {'Score':>6}")
    print("-" * 58)
    sorted_parks = sorted(
        PARK_FACTORS.items(),
        key=lambda x: x[1]["hits_factor"],
        reverse=True
    )
    for name, data in sorted_parks:
        score = park_impact_score(name)
        print(
            f"{name:<35} "
            f"{data['hits_factor']:>6.2f} "
            f"{data['hr_factor']:>6.2f} "
            f"{score:>6.1f}"
        )
