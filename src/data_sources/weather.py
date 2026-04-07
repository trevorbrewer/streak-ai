"""
src/data_sources/weather.py
==============================
Fetch game-time weather for MLB ballparks using OpenWeather API.
Requires OPENWEATHER_API_KEY in .env

Weather factors that affect hitting:
    Temperature:  Cold air = less carry, warm air = more carry
    Wind speed:   High wind = more variance
    Wind direction: Blowing out = hitter boost, in = pitcher boost
    Humidity:     Higher humidity = slightly more carry
    Conditions:   Rain/dome affects game pace

Usage:
    from src.data_sources.weather import get_park_weather
    weather = get_park_weather("Wrigley Field")
    print(weather["wind_impact"])  -> "blowing_out"
"""

import json
import time
import requests
from pathlib import Path
from src.config import CONFIG

CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

OWM_API = "https://api.openweathermap.org/data/2.5/weather"

# City lookup per park — OpenWeather needs city,country
PARK_CITIES = {
    "Coors Field":                  "Denver,US",
    "Great American Ball Park":     "Cincinnati,US",
    "Fenway Park":                  "Boston,US",
    "Wrigley Field":                "Chicago,US",
    "Camden Yards":                 "Baltimore,US",
    "Yankee Stadium":               "New York,US",
    "Globe Life Field":             "Arlington,US",
    "Minute Maid Park":             "Houston,US",
    "Dodger Stadium":               "Los Angeles,US",
    "Oracle Park":                  "San Francisco,US",
    "Petco Park":                   "San Diego,US",
    "Angel Stadium":                "Anaheim,US",
    "T-Mobile Park":                "Seattle,US",
    "Chase Field":                  "Phoenix,US",
    "Busch Stadium":                "St. Louis,US",
    "PNC Park":                     "Pittsburgh,US",
    "American Family Field":        "Milwaukee,US",
    "Target Field":                 "Minneapolis,US",
    "Kauffman Stadium":             "Kansas City,US",
    "Progressive Field":            "Cleveland,US",
    "Comerica Park":                "Detroit,US",
    "Guaranteed Rate Field":        "Chicago,US",
    "Tropicana Field":              "St. Petersburg,US",
    "Truist Park":                  "Atlanta,US",
    "loanDepot Park":               "Miami,US",
    "Citi Field":                   "New York,US",
    "Citizens Bank Park":           "Philadelphia,US",
    "Nationals Park":               "Washington,US",
    "Rogers Centre":                "Toronto,CA",
    "Oakland Coliseum":             "Oakland,US",
}

# Wind directions in degrees and their MLB impact
# 0/360 = North, 90 = East, 180 = South, 270 = West
# This is simplified — real impact depends on stadium orientation
WIND_THRESHOLDS = {
    "calm":         (0, 5),
    "light":        (5, 10),
    "moderate":     (10, 15),
    "strong":       (15, 20),
    "very_strong":  (20, 999),
}


def _get_wind_impact(wind_mph: float, wind_deg: float, roof: str) -> str:
    """
    Classify wind impact on hitting.
    Returns one of: blowing_out, blowing_in, crosswind, calm, dome
    """
    if roof in ("fixed", "retractable"):
        return "dome"
    if wind_mph < 5:
        return "calm"
    # Simplified — blowing out is roughly between 90-270 degrees
    # (this varies hugely by park orientation in reality)
    if 45 <= wind_deg <= 225:
        return "blowing_out" if wind_mph >= 10 else "light_out"
    return "blowing_in" if wind_mph >= 10 else "light_in"


def get_park_weather(park_name: str) -> dict:
    """
    Fetch current weather conditions for a ballpark.

    Args:
        park_name: Full park name e.g. "Wrigley Field"

    Returns dict with:
        temp_f, feels_like_f, humidity, wind_mph, wind_deg,
        wind_impact, conditions, description, hitter_score
    Returns {} if API key not set or request fails.
    """
    api_key = CONFIG.get("openweather_api_key", "")
    if not api_key:
        print(f"  [warn] No OpenWeather API key — skipping weather for {park_name}")
        return {}

    cache_file = CACHE_DIR / f"weather_{park_name.lower().replace(' ', '_')}.json"
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < 1800:  # Cache valid 30 minutes
            with open(cache_file) as f:
                return json.load(f)

    city = PARK_CITIES.get(park_name)
    if not city:
        # Try fuzzy match
        park_lower = park_name.lower()
        for name, c in PARK_CITIES.items():
            if park_lower in name.lower():
                city = c
                break

    if not city:
        print(f"  [warn] No city mapping for park: {park_name}")
        return {}

    print(f"  Fetching weather for {park_name} ({city})...")
    try:
        response = requests.get(
            OWM_API,
            params={
                "q":     city,
                "appid": api_key,
                "units": "imperial",
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print(f"  [error] Invalid OpenWeather API key")
        else:
            print(f"  [error] Weather API error: {e}")
        return {}
    except Exception as e:
        print(f"  [error] Weather fetch failed: {e}")
        return {}

    temp_f      = round(data["main"]["temp"], 1)
    feels_like  = round(data["main"]["feels_like"], 1)
    humidity    = data["main"]["humidity"]
    wind_mph    = round(data["wind"]["speed"], 1)
    wind_deg    = data["wind"].get("deg", 0)
    conditions  = data["weather"][0]["main"]
    description = data["weather"][0]["description"]

    # Get roof type from park factors
    from src.data_sources.park_factors import get_park_factor
    park_data = get_park_factor(park_name)
    roof = park_data.get("roof", "open")

    wind_impact = _get_wind_impact(wind_mph, wind_deg, roof)
    hitter_score = _compute_hitter_weather_score(
        temp_f, wind_mph, wind_impact, conditions, humidity
    )

    result = {
        "park_name":    park_name,
        "city":         city,
        "temp_f":       temp_f,
        "feels_like_f": feels_like,
        "humidity":     humidity,
        "wind_mph":     wind_mph,
        "wind_deg":     wind_deg,
        "wind_impact":  wind_impact,
        "conditions":   conditions,
        "description":  description,
        "roof":         roof,
        "hitter_score": hitter_score,
    }

    with open(cache_file, "w") as f:
        json.dump(result, f, indent=2)

    print(
        f"  [ok] Weather: {temp_f}°F, wind {wind_mph}mph "
        f"({wind_impact}), {description}"
    )
    return result


def _compute_hitter_weather_score(
    temp_f: float,
    wind_mph: float,
    wind_impact: str,
    conditions: str,
    humidity: int
) -> float:
    """
    Compute a 0-100 weather score for hitters.
    50 = neutral conditions, >50 = favors hitting, <50 = hurts hitting.
    """
    score = 50.0

    # Temperature — warm air carries ball farther
    if temp_f >= 80:
        score += 8
    elif temp_f >= 70:
        score += 4
    elif temp_f >= 60:
        score += 0
    elif temp_f >= 50:
        score -= 4
    elif temp_f < 50:
        score -= 8

    # Wind impact
    wind_adjustments = {
        "blowing_out": 10,
        "light_out":    5,
        "calm":         0,
        "crosswind":    0,
        "dome":         0,
        "light_in":    -5,
        "blowing_in": -10,
    }
    score += wind_adjustments.get(wind_impact, 0)

    # Conditions
    if conditions in ("Rain", "Drizzle", "Thunderstorm"):
        score -= 10
    elif conditions == "Snow":
        score -= 15
    elif conditions in ("Clear", "Sunny"):
        score += 3

    # Humidity — slightly helps carry
    if humidity >= 70:
        score += 2
    elif humidity <= 30:
        score -= 2

    return round(max(0.0, min(100.0, score)), 1)


def get_weather_summary(park_name: str) -> str:
    """
    Return a one-line human readable weather summary.
    Used in email reports and AI scoring prompts.
    """
    w = get_park_weather(park_name)
    if not w:
        return "Weather unavailable"
    return (
        f"{w['temp_f']}°F, {w['description']}, "
        f"wind {w['wind_mph']}mph ({w['wind_impact'].replace('_', ' ')}), "
        f"humidity {w['humidity']}%"
    )


def enrich_hitter_weather(hitter) -> object:
    """
    Add weather context to a Hitter object via their park.
    Appends weather summary to hitter notes.
    """
    if not hitter.park:
        return hitter

    weather = get_park_weather(hitter.park)
    if not weather:
        return hitter

    summary = get_weather_summary(hitter.park)
    existing = hitter.notes or ""
    if "°F" not in existing:
        hitter.notes = f"{existing} | {summary}".strip(" |")

    return hitter


def clear_weather_cache():
    """Clear all cached weather files."""
    cleared = 0
    for f in CACHE_DIR.glob("weather_*.json"):
        f.unlink()
        cleared += 1
    print(f"  [cache] Cleared {cleared} weather cache files")


if __name__ == "__main__":
    print("Testing weather module...\n")

    parks_to_test = [
        "Wrigley Field",
        "Coors Field",
        "Dodger Stadium",
    ]

    for park in parks_to_test:
        print(f"\n{park}:")
        weather = get_park_weather(park)
        if weather:
            print(f"  Temp:        {weather['temp_f']}°F")
            print(f"  Wind:        {weather['wind_mph']} mph ({weather['wind_impact']})")
            print(f"  Conditions:  {weather['description']}")
            print(f"  Hitter score: {weather['hitter_score']}/100")
        else:
            print("  No weather data available")

    print("\nPark factors test:")
    from src.data_sources.park_factors import get_park_factor, park_impact_score
    for park in parks_to_test:
        factor = get_park_factor(park)
        score = park_impact_score(park)
        print(f"  {park}: hits={factor['hits_factor']} score={score}")
