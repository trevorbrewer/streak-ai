"""
tests/test_lineup_confirmation.py
Tests for lineup confirmation logic.
"""

import pytest
from unittest.mock import patch
from src.models import Hitter
from src.data_sources import schedule


FULL_LINEUP = [
    {"id": i, "name": f"Player {i}", "batting_order": i, "position": "OF"}
    for i in range(1, 10)
]

EMPTY_LINEUP = []
PARTIAL_LINEUP = [
    {"id": 1, "name": "Player 1", "batting_order": 1, "position": "SS"}
]

MOCK_SCHEDULE = {
    "dates": [{
        "games": [
            {
                "gamePk": 12345,
                "status": {"detailedState": "Scheduled"},
                "gameDate": "2026-04-15T21:40:00Z",
                "venue": {"name": "Petco Park"},
                "teams": {
                    "home": {"team": {"id": 135, "name": "San Diego Padres"}},
                    "away": {"team": {"id": 119, "name": "Los Angeles Dodgers"}},
                }
            },
        ]
    }]
}


@pytest.fixture(autouse=True)
def clear_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(schedule, "CACHE_DIR", tmp_path)
    return tmp_path


def test_is_lineup_confirmed_full():
    """Full lineup of 9 should be confirmed."""
    with patch("src.data_sources.schedule.get_lineup", return_value=FULL_LINEUP):
        assert schedule.is_lineup_confirmed(12345, "LAD") is True


def test_is_lineup_confirmed_empty():
    """Empty lineup should not be confirmed."""
    with patch("src.data_sources.schedule.get_lineup", return_value=EMPTY_LINEUP):
        assert schedule.is_lineup_confirmed(12345, "LAD") is False


def test_is_lineup_confirmed_partial():
    """Partial lineup under 8 players should not be confirmed."""
    with patch("src.data_sources.schedule.get_lineup", return_value=PARTIAL_LINEUP):
        assert schedule.is_lineup_confirmed(12345, "LAD") is False


def test_is_lineup_confirmed_exactly_eight():
    """Exactly 8 players should be considered confirmed."""
    eight_players = FULL_LINEUP[:8]
    with patch("src.data_sources.schedule.get_lineup", return_value=eight_players):
        assert schedule.is_lineup_confirmed(12345, "LAD") is True


def test_get_confirmed_games_both_confirmed():
    """Game where both lineups are posted should be returned."""
    with patch("src.data_sources.schedule._get", return_value=MOCK_SCHEDULE):
        with patch("src.data_sources.schedule.get_lineup", return_value=FULL_LINEUP):
            confirmed = schedule.get_confirmed_games("2026-04-15")
    assert len(confirmed) == 1
    assert confirmed[0]["both_confirmed"] is True


def test_get_confirmed_games_none_confirmed():
    """Game where no lineups are posted should be excluded."""
    with patch("src.data_sources.schedule._get", return_value=MOCK_SCHEDULE):
        with patch("src.data_sources.schedule.get_lineup", return_value=EMPTY_LINEUP):
            confirmed = schedule.get_confirmed_games("2026-04-15")
    assert len(confirmed) == 0


def test_get_confirmed_games_one_side_missing():
    """Game where only one lineup is posted should be excluded."""
    call_count = 0

    def alternating_lineup(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return FULL_LINEUP if call_count % 2 == 1 else EMPTY_LINEUP

    with patch("src.data_sources.schedule._get", return_value=MOCK_SCHEDULE):
        with patch("src.data_sources.schedule.get_lineup",
                   side_effect=alternating_lineup):
            confirmed = schedule.get_confirmed_games("2026-04-15")
    assert len(confirmed) == 0


def test_enrich_hitter_matchup_marks_unconfirmed():
    """Hitter should be marked LINEUP_UNCONFIRMED when lineup not posted."""
    hitter = Hitter(name="Freddie Freeman", team="LAD")
    with patch("src.data_sources.schedule._get", return_value=MOCK_SCHEDULE):
        with patch("src.data_sources.schedule.get_lineup",
                   return_value=EMPTY_LINEUP):
            result = schedule.enrich_hitter_matchup(hitter)
    assert "LINEUP_UNCONFIRMED" in (result.notes or "")


def test_enrich_hitter_matchup_confirmed_clears_flag():
    """Confirmed lineup should remove LINEUP_UNCONFIRMED flag."""
    hitter = Hitter(
        name="Player 1", team="LAD",
        notes="some note | LINEUP_UNCONFIRMED"
    )
    with patch("src.data_sources.schedule._get", return_value=MOCK_SCHEDULE):
        with patch("src.data_sources.schedule.get_lineup",
                   return_value=FULL_LINEUP):
            result = schedule.enrich_hitter_matchup(hitter)
    assert "LINEUP_UNCONFIRMED" not in (result.notes or "")


def test_pipeline_filters_unconfirmed(monkeypatch):
    """Pipeline step should exclude hitters with LINEUP_UNCONFIRMED."""
    from src import pipeline

    confirmed_hitter = Hitter(name="Player A", team="LAD", notes="")
    unconfirmed_hitter = Hitter(
        name="Player B", team="NYY",
        notes="LINEUP_UNCONFIRMED"
    )

    with patch("src.pipeline.enrich_all_hitters",
               return_value=[confirmed_hitter, unconfirmed_hitter]):
        result = pipeline.step_enrich_matchups(
            [confirmed_hitter, unconfirmed_hitter], "2026-04-15"
        )

    assert len(result) == 1
    assert result[0].name == "Player A"


def test_pipeline_excludes_all_unconfirmed(monkeypatch):
    """Pipeline should return empty list if all lineups unconfirmed."""
    from src import pipeline

    hitters = [
        Hitter(name="Player A", team="LAD", notes="LINEUP_UNCONFIRMED"),
        Hitter(name="Player B", team="NYY", notes="LINEUP_UNCONFIRMED"),
    ]

    with patch("src.pipeline.enrich_all_hitters", return_value=hitters):
        result = pipeline.step_enrich_matchups(hitters, "2026-04-15")

    assert result == []
