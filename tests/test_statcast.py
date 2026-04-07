"""
tests/test_statcast.py
Tests for the Statcast metrics module.
Mocks pybaseball so no real API calls are made during CI.
"""

import pytest
import json
import pandas as pd
from unittest.mock import patch, MagicMock
from src.models import Hitter
from src.data_sources import statcast


@pytest.fixture(autouse=True)
def clear_cache(tmp_path, monkeypatch):
    """Redirect cache to temp dir for all tests."""
    monkeypatch.setattr(statcast, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(statcast, "PYBASEBALL_AVAILABLE", True)
    return tmp_path


def make_mock_statcast_df():
    """Create a realistic mock Statcast DataFrame."""
    return pd.DataFrame({
        "game_date":   ["2025-04-01", "2025-04-02", "2025-04-03"] * 20,
        "launch_speed": [95.2, 88.1, 102.3, 91.5, 85.0, 97.8] * 10,
        "launch_angle": [12.1, 8.5, 22.3, 15.2, 5.1, 18.7] * 10,
        "estimated_ba_using_speedangle": [
            0.312, 0.245, 0.389, 0.298, 0.201, 0.356
        ] * 10,
    })


def make_mock_lookup_df():
    """Create a mock player lookup result."""
    return pd.DataFrame({
        "name_last":        ["Freeman"],
        "name_first":       ["Freddie"],
        "key_mlbam":        [501303],
        "mlb_played_last":  [2025],
    })


def test_parse_name_simple():
    last, first = statcast._parse_name("Freddie Freeman")
    assert last == "Freeman"
    assert first == "Freddie"


def test_parse_name_with_suffix():
    last, first = statcast._parse_name("Vladimir Guerrero Jr.")
    assert last == "Guerrero"
    assert first == "Vladimir"


def test_parse_name_single_word():
    last, first = statcast._parse_name("Ohtani")
    assert last == "Ohtani"


def test_lookup_player_id_found():
    with patch("src.data_sources.statcast.pb") as mock_pb:
        mock_pb.playerid_lookup.return_value = make_mock_lookup_df()
        result = statcast._lookup_player_id("Freeman", "Freddie")
    assert result == 501303


def test_lookup_player_id_not_found():
    with patch("src.data_sources.statcast.pb") as mock_pb:
        mock_pb.playerid_lookup.return_value = pd.DataFrame()
        result = statcast._lookup_player_id("Nobody", "Ghost")
    assert result is None


def test_get_statcast_batter_success():
    mock_df = make_mock_statcast_df()
    with patch("src.data_sources.statcast.pb") as mock_pb:
        mock_pb.playerid_lookup.return_value = make_mock_lookup_df()
        mock_pb.statcast_batter.return_value = mock_df
        result = statcast.get_statcast_batter("Freddie Freeman")
    assert "exit_velo_avg" in result
    assert "hard_hit_pct" in result
    assert "xba" in result
    assert isinstance(result["exit_velo_avg"], float)
    assert 0 <= result["hard_hit_pct"] <= 100


def test_get_statcast_batter_no_player():
    with patch("src.data_sources.statcast.pb") as mock_pb:
        mock_pb.playerid_lookup.return_value = pd.DataFrame()
        result = statcast.get_statcast_batter("Ghost Player")
    assert result == {}


def test_get_statcast_batter_empty_data():
    with patch("src.data_sources.statcast.pb") as mock_pb:
        mock_pb.playerid_lookup.return_value = make_mock_lookup_df()
        mock_pb.statcast_batter.return_value = pd.DataFrame()
        result = statcast.get_statcast_batter("Freddie Freeman")
    assert result == {}


def test_hard_hit_pct_calculation():
    """Hard hit is exit velo >= 95 mph."""
    mock_df = pd.DataFrame({
        "game_date":   ["2025-04-01"] * 10,
        "launch_speed": [95, 96, 94, 100, 88, 95, 92, 97, 85, 99],
        "launch_angle": [15.0] * 10,
        "estimated_ba_using_speedangle": [0.300] * 10,
    })
    with patch("src.data_sources.statcast.pb") as mock_pb:
        mock_pb.playerid_lookup.return_value = make_mock_lookup_df()
        mock_pb.statcast_batter.return_value = mock_df
        result = statcast.get_statcast_batter("Freddie Freeman")
    # 6 out of 10 balls >= 95 mph = 60%
    assert result["hard_hit_pct"] == 60.0


def test_statcast_caching(tmp_path, monkeypatch):
    """Second call should use cache, not hit pybaseball again."""
    monkeypatch.setattr(statcast, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(statcast, "PYBASEBALL_AVAILABLE", True)
    mock_df = make_mock_statcast_df()
    call_count = 0

    def counting_statcast(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_df

    with patch("src.data_sources.statcast.pb") as mock_pb:
        mock_pb.playerid_lookup.return_value = make_mock_lookup_df()
        mock_pb.statcast_batter.side_effect = counting_statcast
        statcast.get_statcast_batter("Freddie Freeman")
        first_count = call_count
        statcast.get_statcast_batter("Freddie Freeman")

    assert call_count == first_count


def test_enrich_hitter_statcast():
    """enrich_hitter_statcast fills in exit_velo and hard_pct."""
    hitter = Hitter(name="Freddie Freeman", team="LAD")
    assert hitter.exit_velo is None
    assert hitter.hard_pct is None

    mock_df = make_mock_statcast_df()
    with patch("src.data_sources.statcast.pb") as mock_pb:
        mock_pb.playerid_lookup.return_value = make_mock_lookup_df()
        mock_pb.statcast_batter.return_value = mock_df
        result = statcast.enrich_hitter_statcast(hitter)

    assert result.exit_velo is not None
    assert result.hard_pct is not None


def test_enrich_hitter_does_not_overwrite():
    """enrich_hitter_statcast should not overwrite existing values."""
    hitter = Hitter(name="Freddie Freeman", team="LAD")
    hitter.exit_velo = 99.9
    hitter.hard_pct = 55.5

    mock_df = make_mock_statcast_df()
    with patch("src.data_sources.statcast.pb") as mock_pb:
        mock_pb.playerid_lookup.return_value = make_mock_lookup_df()
        mock_pb.statcast_batter.return_value = mock_df
        result = statcast.enrich_hitter_statcast(hitter)

    assert result.exit_velo == 99.9
    assert result.hard_pct == 55.5


def test_pybaseball_unavailable(monkeypatch):
    """Module should return empty dict gracefully when pybaseball is missing."""
    monkeypatch.setattr(statcast, "PYBASEBALL_AVAILABLE", False)
    result = statcast.get_statcast_batter("Freddie Freeman")
    assert result == {}
