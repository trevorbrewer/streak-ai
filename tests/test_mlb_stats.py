"""
tests/test_mlb_stats.py
Tests for the MLB Stats API module.
Uses mocking so no real API calls are made during testing.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from src.data_sources import mlb_stats


MOCK_SEARCH_RESPONSE = {
    "people": [
        {
            "id": 501303,
            "fullName": "Freddie Freeman",
            "active": True,
            "primaryPosition": {"abbreviation": "1B"},
            "currentTeam": {"name": "Los Angeles Dodgers"}
        }
    ]
}

MOCK_SEASON_RESPONSE = {
    "people": [
        {
            "stats": [
                {
                    "splits": [
                        {
                            "stat": {
                                "avg": ".302",
                                "obp": ".390",
                                "slg": ".510",
                                "ops": ".900",
                                "woba": ".375",
                                "babip": ".315",
                                "hits": 142,
                                "atBats": 470,
                                "homeRuns": 22,
                                "rbi": 89,
                                "stolenBases": 8,
                                "baseOnBalls": 72,
                                "strikeOuts": 95,
                                "gamesPlayed": 145,
                                "plateAppearances": 550,
                            }
                        }
                    ]
                }
            ]
        }
    ]
}

MOCK_RECENT_RESPONSE = {
    "stats": [
        {
            "splits": [
                {"date": "2026-04-20", "stat": {"hits": "3", "atBats": "4"}},
                {"date": "2026-04-21", "stat": {"hits": "1", "atBats": "4"}},
                {"date": "2026-04-22", "stat": {"hits": "2", "atBats": "4"}},
                {"date": "2026-04-23", "stat": {"hits": "0", "atBats": "3"}},
                {"date": "2026-04-24", "stat": {"hits": "1", "atBats": "4"}},
                {"date": "2026-04-25", "stat": {"hits": "2", "atBats": "4"}},
                {"date": "2026-04-26", "stat": {"hits": "0", "atBats": "3"}},
            ]
        }
    ]
}


@pytest.fixture(autouse=True)
def clear_cache(tmp_path, monkeypatch):
    """Redirect cache to temp dir so tests don't pollute real cache."""
    monkeypatch.setattr(mlb_stats, "CACHE_DIR", tmp_path)
    return tmp_path


def test_search_player_found():
    with patch("src.data_sources.mlb_stats._get", return_value=MOCK_SEARCH_RESPONSE):
        result = mlb_stats.search_player("Freddie Freeman")
    assert result["id"] == 501303
    assert result["full_name"] == "Freddie Freeman"
    assert result["active"] is True


def test_search_player_not_found():
    with patch("src.data_sources.mlb_stats._get", return_value={"people": []}):
        result = mlb_stats.search_player("Nobody Real")
    assert result == {}


def test_get_batter_season_stats():
    with patch("src.data_sources.mlb_stats._get") as mock_get:
        mock_get.side_effect = [MOCK_SEARCH_RESPONSE, MOCK_SEASON_RESPONSE]
        result = mlb_stats.get_batter_season_stats("Freddie Freeman")
    assert result["avg"] == 0.302
    assert result["obp"] == 0.390
    assert result["slg"] == 0.510
    assert result["hits"] == 142
    assert result["home_runs"] == 22


def test_get_batter_season_stats_no_player():
    with patch("src.data_sources.mlb_stats._get", return_value={"people": []}):
        result = mlb_stats.get_batter_season_stats("Ghost Player")
    assert result == {}


def test_get_batter_recent_stats():
    with patch("src.data_sources.mlb_stats._get",
               return_value=MOCK_SEARCH_RESPONSE):
        with patch("src.data_sources.mlb_stats.requests.get") as mock_req:
            mock_resp = MagicMock()
            mock_resp.json.return_value = MOCK_RECENT_RESPONSE
            mock_resp.raise_for_status = MagicMock()
            mock_req.return_value = mock_resp
            result = mlb_stats.get_batter_recent_stats("Freddie Freeman")
    assert "l7" in result
    assert 0.200 <= result["l7"] <= 0.500


def test_season_stats_caching(tmp_path, monkeypatch):
    """Second call should use cache, not hit the API again."""
    monkeypatch.setattr(mlb_stats, "CACHE_DIR", tmp_path)
    call_count = 0

    def counting_get(url, params=None):
        nonlocal call_count
        call_count += 1
        if "search" in url or "names" in str(params):
            return MOCK_SEARCH_RESPONSE
        return MOCK_SEASON_RESPONSE

    with patch("src.data_sources.mlb_stats._get", side_effect=counting_get):
        mlb_stats.get_batter_season_stats("Freddie Freeman")
        first_count = call_count
        mlb_stats.get_batter_season_stats("Freddie Freeman")

    assert call_count == first_count


def test_enrich_hitter_stats():
    from src.models import Hitter
    hitter = Hitter(name="Freddie Freeman", team="LAD")
    assert hitter.avg == 0.0
    assert hitter.woba is None

    with patch("src.data_sources.mlb_stats._get") as mock_get:
        mock_get.side_effect = [
            MOCK_SEARCH_RESPONSE,
            MOCK_SEASON_RESPONSE,
            MOCK_SEARCH_RESPONSE,
        ]
        with patch("src.data_sources.mlb_stats.requests.get") as mock_req:
            mock_resp = MagicMock()
            mock_resp.json.return_value = MOCK_RECENT_RESPONSE
            mock_resp.raise_for_status = MagicMock()
            mock_req.return_value = mock_resp
            result = mlb_stats.enrich_hitter_stats(hitter)

    assert result.avg == 0.302  


def test_safe_float_handles_dash():
    """Stats API sometimes returns '-' for missing values."""
    with patch("src.data_sources.mlb_stats._get") as mock_get:
        dash_response = {
            "people": [{
                "stats": [{
                    "splits": [{
                        "stat": {
                            "avg": "-", "obp": ".350", "slg": ".450",
                            "ops": ".800", "woba": None, "babip": "-",
                            "hits": 100, "atBats": 350, "homeRuns": 15,
                            "rbi": 60, "stolenBases": 5, "baseOnBalls": 40,
                            "strikeOuts": 80, "gamesPlayed": 110,
                            "plateAppearances": 400,
                        }
                    }]
                }]
            }]
        }
        mock_get.side_effect = [MOCK_SEARCH_RESPONSE, dash_response]
        result = mlb_stats.get_batter_season_stats("Test Player")

    assert result["avg"] is None
    assert result["obp"] == 0.350
