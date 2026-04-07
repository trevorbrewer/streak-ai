"""
tests/test_park_factors.py
Tests for the park factors database.
No API calls — pure data validation.
"""

from src.data_sources.park_factors import (
    get_park_factor,
    get_park_factor_by_team,
    is_hitter_friendly,
    park_impact_score,
    PARK_FACTORS,
    TEAM_TO_PARK,
)


def test_all_parks_have_required_fields():
    """Every park must have hits_factor, hr_factor, team, city."""
    required = ["hits_factor", "hr_factor", "doubles_factor", "team", "city"]
    for park_name, data in PARK_FACTORS.items():
        for field in required:
            assert field in data, f"{park_name} missing field: {field}"


def test_hits_factors_are_reasonable():
    """All hits factors should be between 0.75 and 1.40."""
    for park_name, data in PARK_FACTORS.items():
        factor = data["hits_factor"]
        assert 0.75 <= factor <= 1.40, (
            f"{park_name} hits factor {factor} outside expected range"
        )


def test_coors_field_is_highest():
    """Coors Field should be the most hitter friendly park."""
    coors = PARK_FACTORS["Coors Field"]["hits_factor"]
    for name, data in PARK_FACTORS.items():
        if name != "Coors Field":
            assert coors >= data["hits_factor"], (
                f"{name} has higher hits factor than Coors: {data['hits_factor']}"
            )


def test_get_park_factor_exact_match():
    result = get_park_factor("Coors Field")
    assert result["hits_factor"] == 1.22
    assert result["team"] == "COL"
    assert result["park_name"] == "Coors Field"


def test_get_park_factor_fuzzy_match():
    """Partial name should still find the park."""
    result = get_park_factor("Coors")
    assert result["team"] == "COL"


def test_get_park_factor_unknown_returns_neutral():
    result = get_park_factor("Some Fake Stadium")
    assert result["hits_factor"] == 1.00
    assert result["hr_factor"] == 1.00


def test_get_park_factor_empty_string():
    result = get_park_factor("")
    assert result["hits_factor"] == 1.00


def test_get_park_factor_by_team():
    result = get_park_factor_by_team("LAD")
    assert result["team"] == "LAD"
    assert result["hits_factor"] == 0.97


def test_get_park_factor_by_team_unknown():
    result = get_park_factor_by_team("ZZZ")
    assert result["hits_factor"] == 1.00


def test_is_hitter_friendly_true():
    assert is_hitter_friendly("Coors Field") is True
    assert is_hitter_friendly("Fenway Park") is True


def test_is_hitter_friendly_false():
    assert is_hitter_friendly("Oracle Park") is False
    assert is_hitter_friendly("Petco Park") is False


def test_park_impact_score_range():
    """All scores should be between 0 and 100."""
    for park_name in PARK_FACTORS:
        score = park_impact_score(park_name)
        assert 0 <= score <= 100, (
            f"{park_name} score {score} outside 0-100 range"
        )


def test_coors_has_highest_impact_score():
    coors_score = park_impact_score("Coors Field")
    for park_name in PARK_FACTORS:
        if park_name != "Coors Field":
            assert coors_score >= park_impact_score(park_name)


def test_team_to_park_coverage():
    """Every team abbreviation in TEAM_TO_PARK should map to a real park."""
    for team, park in TEAM_TO_PARK.items():
        assert park in PARK_FACTORS, (
            f"Team {team} maps to unknown park: {park}"
        )
