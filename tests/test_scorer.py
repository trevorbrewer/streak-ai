"""
tests/test_scorer.py
Tests for the Claude AI scoring engine.
Mocks the Anthropic API so no real calls made during CI.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from src.models import Hitter
from src.features import engineer_features
from src import scorer


MOCK_AI_RESPONSE = {
    "score":          78,
    "confidence":     "high",
    "reasoning":      "Freeman is on a hot streak with platoon advantage vs RHP Darvish. Park factor is slightly unfavorable but contact quality and recent form outweigh this concern. wOBA of .375 indicates elite production.",
    "key_factor":     "Hot streak combined with platoon advantage",
    "risk_factor":    "Pitcher-friendly park at Petco",
    "features_used":  ["l7_delta", "platoon_advantage", "park_hits_factor"],
    "recommendation": "strong_pick",
}


def make_hitter(**kwargs) -> Hitter:
    defaults = dict(
        name="Freddie Freeman",
        team="LAD",
        hand="L",
        avg=0.302,
        obp=0.390,
        slg=0.510,
        l7=0.340,
        l30=0.308,
        woba=0.375,
        babip=0.315,
        exit_velo=91.2,
        hard_pct=42.1,
        opp="SD",
        pitcher="Yu Darvish",
        phand="R",
        era=3.85,
        park="Petco Park",
        home_away="away",
        batting_order=3,
    )
    defaults.update(kwargs)
    return Hitter(**defaults)


@pytest.fixture
def mock_api_key(monkeypatch):
    monkeypatch.setitem(scorer.CONFIG, "anthropic_api_key", "fake-key-123")


@pytest.fixture
def mock_anthropic(mock_api_key):
    """Mock the entire Anthropic client."""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(MOCK_AI_RESPONSE))]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch("src.scorer.anthropic.Anthropic", return_value=mock_client):
        yield mock_client


def test_build_prompt_contains_hitter_name():
    hitter = make_hitter()
    features = engineer_features(hitter)
    prompt = scorer.build_prompt(hitter, features)
    assert "Freddie Freeman" in prompt


def test_build_prompt_contains_pitcher():
    hitter = make_hitter()
    features = engineer_features(hitter)
    prompt = scorer.build_prompt(hitter, features)
    assert "Yu Darvish" in prompt


def test_build_prompt_contains_era():
    hitter = make_hitter(era=3.85)
    features = engineer_features(hitter)
    prompt = scorer.build_prompt(hitter, features)
    assert "3.85" in prompt


def test_build_prompt_handles_none_fields():
    """Prompt builder should not crash when fields are None."""
    hitter = Hitter(name="Minimal Player", team="LAD")
    features = engineer_features(hitter)
    prompt = scorer.build_prompt(hitter, features)
    assert "Minimal Player" in prompt
    assert "N/A" in prompt


def test_build_prompt_shows_hot_streak():
    hitter = make_hitter(avg=0.250, l7=0.400)
    features = engineer_features(hitter)
    prompt = scorer.build_prompt(hitter, features)
    assert "HOT" in prompt


def test_build_prompt_shows_cold_streak():
    hitter = make_hitter(avg=0.320, l7=0.200)
    features = engineer_features(hitter)
    prompt = scorer.build_prompt(hitter, features)
    assert "COLD" in prompt


def test_score_hitter_with_api(mock_anthropic):
    hitter = make_hitter()
    features = engineer_features(hitter)
    result = scorer.score_hitter(hitter, features)
    assert result["score"] == 78
    assert result["confidence"] == "high"
    assert result["recommendation"] == "strong_pick"
    assert "reasoning" in result
    assert "key_factor" in result
    assert "risk_factor" in result


def test_score_hitter_clamps_score(mock_api_key):
    """Score outside 0-100 should be clamped."""
    mock_response = dict(MOCK_AI_RESPONSE)
    mock_response["score"] = 150

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(mock_response))]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch("src.scorer.anthropic.Anthropic", return_value=mock_client):
        hitter = make_hitter()
        features = engineer_features(hitter)
        result = scorer.score_hitter(hitter, features)

    assert result["score"] == 100


def test_score_hitter_no_api_key(monkeypatch):
    """Without API key should return mock score."""
    monkeypatch.setitem(scorer.CONFIG, "anthropic_api_key", "")
    hitter = make_hitter()
    features = engineer_features(hitter)
    result = scorer.score_hitter(hitter, features)
    assert isinstance(result["score"], int)
    assert 0 <= result["score"] <= 100
    assert "Mock" in result["reasoning"]


def test_score_hitter_retries_on_bad_json(mock_api_key):
    """Should retry up to 3 times on JSON parse failure."""
    bad_response = MagicMock()
    bad_response.content = [MagicMock(text="not valid json {{")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = bad_response

    with patch("src.scorer.anthropic.Anthropic", return_value=mock_client):
        with patch("src.scorer.time.sleep"):
            hitter = make_hitter()
            features = engineer_features(hitter)
            result = scorer.score_hitter(hitter, features)

    assert mock_client.messages.create.call_count == 3
    assert result["confidence"] == "low"


def test_score_hitter_populates_hitter_fields(mock_anthropic):
    """score_hitter result should be applicable to Hitter fields."""
    hitter = make_hitter()
    features = engineer_features(hitter)
    result = scorer.score_hitter(hitter, features)

    hitter.score      = result["score"]
    hitter.confidence = result["confidence"]
    hitter.reasoning  = result["reasoning"]
    hitter.key_factor = result["key_factor"]

    assert hitter.score == 78
    assert hitter.confidence == "high"
    assert hitter.reasoning is not None


def test_score_all_hitters(mock_anthropic):
    """score_all_hitters should return sorted list."""
    hitters = [
        make_hitter(name="Player One"),
        make_hitter(name="Player Two"),
        make_hitter(name="Player Three"),
    ]
    features_list = [engineer_features(h) for h in hitters]

    with patch("src.scorer.time.sleep"):
        scored = scorer.score_all_hitters(hitters, features_list)

    assert len(scored) == 3
    # Should be sorted descending by score
    scores = [h.score for h in scored]
    assert scores == sorted(scores, reverse=True)


def test_score_all_hitters_empty():
    """Empty list should return empty list."""
    result = scorer.score_all_hitters([], [])
    assert result == []


def test_score_all_hitters_sets_scored_at(mock_anthropic):
    """All hitters should have scored_at timestamp after scoring."""
    hitters = [make_hitter()]
    features_list = [engineer_features(h) for h in hitters]

    with patch("src.scorer.time.sleep"):
        scored = scorer.score_all_hitters(hitters, features_list)

    assert scored[0].scored_at is not None


def test_mock_score_uses_pre_ai_score(monkeypatch):
    """Mock scorer should use pre_ai_score as base."""
    monkeypatch.setitem(scorer.CONFIG, "anthropic_api_key", "")
    hitter = make_hitter()
    features = engineer_features(hitter)
    pre_ai = features.get("pre_ai_score", 55.0)
    result = scorer._mock_score(hitter, features)
    assert abs(result["score"] - pre_ai) <= 10


def test_fallback_score_returns_low_confidence():
    hitter = make_hitter()
    features = engineer_features(hitter)
    result = scorer._fallback_score(hitter, features)
    assert result["confidence"] == "low"
    assert result["recommendation"] == "neutral"
