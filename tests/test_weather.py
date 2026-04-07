"""
tests/test_weather.py
Tests for the weather module.
Mocks OpenWeather API so no real calls made during CI.
"""

import pytest
from unittest.mock import patch, MagicMock
from src.models import Hitter
from src.data_sources import weather


MOCK_WEATHER_RESPONSE = {
    "main": {
        "temp":       72.5,
        "feels_like": 70.1,
        "humidity":   65,
    },
    "wind": {
        "speed": 12.0,
        "deg":   180,
    },
    "weather": [
        {"main": "Clear", "description": "clear sky"}
    ]
}


@pytest.fixture(autouse=True)
def clear_cache(tmp_path, monkeypatch):
    """Redirect cache to temp dir for all tests."""
    monkeypatch.setattr(weather, "CACHE_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def mock_api_key(monkeypatch):
    """Inject a fake API key so weather calls aren't skipped."""
    monkeypatch.setitem(weather.CONFIG, "openweather_api_key", "fake_key_123")


def test_get_park_weather_success(mock_api_key):
    with patch("src.data_sources.weather.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = MOCK_WEATHER_RESPONSE
        mock_get.return_value.raise_for_status = MagicMock()
        result = weather.get_park_weather("Wrigley Field")
    assert result["temp_f"] == 72.5
    assert result["wind_mph"] == 12.0
    assert result["conditions"] == "Clear"
    assert "hitter_score" in result


def test_get_park_weather_no_api_key(monkeypatch):
    """Should return empty dict when no API key configured."""
    monkeypatch.setitem(weather.CONFIG, "openweather_api_key", "")
    result = weather.get_park_weather("Wrigley Field")
    assert result == {}


def test_get_park_weather_unknown_park(mock_api_key):
    """Unknown park should return empty dict."""
    result = weather.get_park_weather("Fake Stadium")
    assert result == {}


def test_hitter_score_warm_blowing_out():
    score = weather._compute_hitter_weather_score(
        temp_f=82,
        wind_mph=15,
        wind_impact="blowing_out",
        conditions="Clear",
        humidity=60
    )
    assert score > 60


def test_hitter_score_cold_blowing_in():
    score = weather._compute_hitter_weather_score(
        temp_f=45,
        wind_mph=18,
        wind_impact="blowing_in",
        conditions="Clear",
        humidity=50
    )
    assert score < 40


def test_hitter_score_rain():
    score = weather._compute_hitter_weather_score(
        temp_f=65,
        wind_mph=8,
        wind_impact="calm",
        conditions="Rain",
        humidity=90
    )
    assert score < 45


def test_hitter_score_dome():
    """Dome with neutral conditions — only temp and humidity adjustments apply."""
    score = weather._compute_hitter_weather_score(
        temp_f=72,
        wind_mph=0,
        wind_impact="dome",
        conditions="Clear",
        humidity=50
    )
    # temp=72 -> +4, dome wind -> 0, Clear -> +3, humidity neutral -> 0
    # 50 + 4 + 0 + 3 + 0 = 57
    assert score == 57.0


def test_hitter_score_clamped():
    """Score should never go below 0 or above 100."""
    score_high = weather._compute_hitter_weather_score(
        temp_f=100, wind_mph=25, wind_impact="blowing_out",
        conditions="Clear", humidity=80
    )
    score_low = weather._compute_hitter_weather_score(
        temp_f=20, wind_mph=30, wind_impact="blowing_in",
        conditions="Snow", humidity=20
    )
    assert 0 <= score_high <= 100
    assert 0 <= score_low <= 100


def test_wind_impact_dome():
    impact = weather._get_wind_impact(20, 180, "fixed")
    assert impact == "dome"


def test_wind_impact_calm():
    impact = weather._get_wind_impact(3, 180, "open")
    assert impact == "calm"


def test_wind_impact_blowing_out():
    impact = weather._get_wind_impact(15, 180, "open")
    assert impact == "blowing_out"


def test_wind_impact_blowing_in():
    impact = weather._get_wind_impact(15, 10, "open")
    assert impact == "blowing_in"


def test_enrich_hitter_weather(mock_api_key):
    hitter = Hitter(name="Freddie Freeman", team="LAD", park="Wrigley Field")
    with patch("src.data_sources.weather.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = MOCK_WEATHER_RESPONSE
        mock_get.return_value.raise_for_status = MagicMock()
        result = weather.enrich_hitter_weather(hitter)
    assert result.notes is not None
    assert "°F" in result.notes


def test_enrich_hitter_no_park():
    """Hitter with no park set should be returned unchanged."""
    hitter = Hitter(name="Test Player", team="LAD")
    result = weather.enrich_hitter_weather(hitter)
    assert result.notes is None


def test_get_weather_summary_no_key(monkeypatch):
    monkeypatch.setitem(weather.CONFIG, "openweather_api_key", "")
    summary = weather.get_weather_summary("Wrigley Field")
    assert summary == "Weather unavailable"
