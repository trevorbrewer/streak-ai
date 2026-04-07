"""
tests/test_schedule.py
Tests for the schedule and matchup enrichment module.
Uses mocking so no real API calls are made during CI.
"""

import pytest
from unittest.mock import patch
from src.models import Hitter
from src.data_sources import schedule


MOCK_SCHEDULE = {
    "dates": [{
        "games": [
            {
                "gamePk": 12345,
                "status": {"detailedState": "Scheduled"},
                "gameDate": "2025-04-15T21:40:00Z",
                "venue": {"name": "Petco Park"},
                "teams": {
                    "home": {"team": {"id": 135, "name": "San Diego Padres"}},
                    "away": {"team": {"id": 119, "name": "Los Angeles Dodgers"}},
                }
            },
            {
                "gamePk": 12346,
                "status": {"detailedState": "Scheduled"},
                "gameDate": "2025-04-15T19:05:00Z",
                "venue": {"name": "Fenway Park"},
                "teams": {
                    "home": {"team": {"id": 111, "name": "Boston Red Sox"}},
                    "away": {"team": {"id": 147, "name": "New York Yankees"}},
                }
            }
        ]
    }]
}

MOCK_PROBABLE_PITCHER = {
    "dates": [{
        "games": [{
            "gamePk": 12345,
            "teams": {
                "home": {
                    "team": {"id": 135},
                    "probablePitcher": {"id": 999}
                },
                "away": {
                    "team": {"id": 119},
                    "probablePitcher": {"id": 888}
                }
            }
        }]
    }]
}

MOCK_PITCHER_STATS = {
    "people": [{
        "fullName": "Yu Darvish",
        "pitchHand": {"code": "R"},
        "stats": [{
            "splits": [{
                "stat": {
                    "era": "3.85",
                    "whip": "1.12",
                    "strikeoutsPer9Inn": "9.2",
                    "walksPer9Inn": "2.1",
                    "avg": ".245",
                    "inningsPitched": "180.0",
                }
            }]
        }]
    }]
}

MOCK_LINEUP = {
    "teams": {
        "away": {
            "team": {"id": 119},
            "battingOrder": [660271, 501303],
            "players": {
                "ID660271": {
                    "person": {"fullName": "Shohei Ohtani"},
                    "position": {"abbreviation": "DH"}
                },
                "ID501303": {
                    "person": {"fullName": "Freddie Freeman"},
                    "position": {"abbreviation": "1B"}
                }
            }
        },
        "home": {
            "team": {"id": 135},
            "battingOrder": [],
            "players": {}
        }
    }
}


@pytest.fixture(autouse=True)
def clear_cache(tmp_path, monkeypatch):
    """Redirect cache to temp dir for all tests."""
    monkeypatch.setattr(schedule, "CACHE_DIR", tmp_path)
    return tmp_path


def test_get_todays_games():
    with patch("src.data_sources.schedule._get", return_value=MOCK_SCHEDULE):
        games = schedule.get_todays_games("2025-04-15")
    assert len(games) == 2
    assert games[0]["home_abbr"] == "SD"
    assert games[0]["away_abbr"] == "LAD"
    assert games[0]["venue"] == "Petco Park"


def test_get_todays_games_empty():
    with patch("src.data_sources.schedule._get", return_value={}):
        games = schedule.get_todays_games("2025-04-15")
    assert games == []


def test_find_game_for_team_home():
    with patch("src.data_sources.schedule._get", return_value=MOCK_SCHEDULE):
        game = schedule.find_game_for_team("SD")
    assert game["game_id"] == 12345
    assert game["home_abbr"] == "SD"


def test_find_game_for_team_away():
    with patch("src.data_sources.schedule._get", return_value=MOCK_SCHEDULE):
        game = schedule.find_game_for_team("LAD")
    assert game["game_id"] == 12345
    assert game["away_abbr"] == "LAD"


def test_find_game_for_team_no_game():
    with patch("src.data_sources.schedule._get", return_value=MOCK_SCHEDULE):
        game = schedule.find_game_for_team("COL")
    assert game == {}


def test_get_starting_pitcher():
    with patch("src.data_sources.schedule._get") as mock_get:
        mock_get.side_effect = [MOCK_PROBABLE_PITCHER, MOCK_PITCHER_STATS]
        pitcher = schedule.get_starting_pitcher(12345, "SD")
    assert pitcher["name"] == "Yu Darvish"
    assert pitcher["hand"] == "R"
    assert pitcher["era"] == 3.85


def test_get_starting_pitcher_not_announced():
    empty_probable = {"dates": [{"games": [{"gamePk": 12345, "teams": {
        "home": {"team": {"id": 135}},
        "away": {"team": {"id": 119}}
    }}]}]}
    with patch("src.data_sources.schedule._get", return_value=empty_probable):
        pitcher = schedule.get_starting_pitcher(12345, "SD")
    assert pitcher == {}


def test_get_lineup():
    with patch("src.data_sources.schedule._get", return_value=MOCK_LINEUP):
        lineup = schedule.get_lineup(12345, "LAD")
    assert len(lineup) == 2
    assert lineup[0]["name"] == "Shohei Ohtani"
    assert lineup[0]["batting_order"] == 1
    assert lineup[1]["name"] == "Freddie Freeman"
    assert lineup[1]["batting_order"] == 2


def test_enrich_hitter_matchup_full():
    hitter = Hitter(name="Freddie Freeman", team="LAD")
    with patch("src.data_sources.schedule._get") as mock_get:
        mock_get.side_effect = [
            MOCK_SCHEDULE,
            MOCK_PROBABLE_PITCHER,
            MOCK_PITCHER_STATS,
            MOCK_LINEUP,
        ]
        result = schedule.enrich_hitter_matchup(hitter)
    assert result.opp == "SD"
    assert result.park == "Petco Park"
    assert result.home_away == "away"
    assert result.pitcher == "Yu Darvish"
    assert result.phand == "R"
    assert result.era == 3.85
    assert result.batting_order == 2


def test_enrich_hitter_matchup_no_game():
    hitter = Hitter(name="Someone", team="COL")
    with patch("src.data_sources.schedule._get", return_value=MOCK_SCHEDULE):
        result = schedule.enrich_hitter_matchup(hitter)
    assert "NO GAME TODAY" in (result.notes or "")


def test_enrich_hitter_no_team():
    hitter = Hitter(name="No Team Player", team="")
    result = schedule.enrich_hitter_matchup(hitter)
    assert result.opp is None


def test_enrich_all_hitters_filters_no_game():
    hitters = [
        Hitter(name="Freddie Freeman", team="LAD"),
        Hitter(name="Someone Else", team="COL"),
    ]
    with patch("src.data_sources.schedule._get") as mock_get:
        mock_get.side_effect = [
            MOCK_SCHEDULE,
            MOCK_SCHEDULE,
            MOCK_PROBABLE_PITCHER,
            MOCK_PITCHER_STATS,
            MOCK_LINEUP,
            MOCK_SCHEDULE,
        ]
        active = schedule.enrich_all_hitters(hitters)
    names = [h.name for h in active]
    assert "Freddie Freeman" in names
    assert "Someone Else" not in names
