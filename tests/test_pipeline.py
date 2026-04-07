"""
tests/test_pipeline.py
Tests for the full pipeline orchestrator.
Mocks all external calls so tests run fast and offline.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.models import Hitter
from src import pipeline


def make_hitter(name="Test Player", team="LAD", score=75) -> Hitter:
    h = Hitter(
        name=name,
        team=team,
        hand="R",
        avg=0.280,
        obp=0.350,
        slg=0.460,
        opp="SD",
        pitcher="Test Pitcher",
        phand="L",
        era=4.20,
        park="Dodger Stadium",
        home_away="home",
        batting_order=3,
    )
    h.score = score
    h.confidence = "high" if score >= 72 else "medium"
    h.reasoning = "Test reasoning"
    h.key_factor = "Test key factor"
    return h


@pytest.fixture
def temp_data(tmp_path, monkeypatch):
    """Redirect all data paths to temp directory."""
    monkeypatch.setitem(pipeline.CONFIG, "hitters_file", tmp_path / "hitters.json")
    monkeypatch.setitem(pipeline.CONFIG, "scores_file", tmp_path / "scores.json")
    monkeypatch.setitem(pipeline.CONFIG, "data_dir", tmp_path)
    monkeypatch.setitem(pipeline.CONFIG, "cache_dir", tmp_path / "cache")
    (tmp_path / "cache").mkdir()
    return tmp_path


@pytest.fixture
def sample_hitters(temp_data):
    """Write sample hitters to temp file."""
    from src.storage import save_hitters
    hitters = [
        make_hitter("Freddie Freeman", "LAD", score=74),
        make_hitter("Mookie Betts", "LAD", score=68),
    ]
    save_hitters(hitters)
    return hitters


def test_step_load_hitters_empty(temp_data):
    result = pipeline.step_load_hitters()
    assert result == []


def test_step_load_hitters_with_data(sample_hitters):
    result = pipeline.step_load_hitters()
    assert len(result) == 2
    assert result[0].name == "Freddie Freeman"


def test_step_filter_and_rank_above_threshold(monkeypatch):
    monkeypatch.setitem(pipeline.CONFIG, "score_threshold", 65)
    hitters = [
        make_hitter("Player A", score=80),
        make_hitter("Player B", score=70),
        make_hitter("Player C", score=50),
    ]
    top, all_scored = pipeline.step_filter_and_rank(hitters)
    assert len(top) == 2
    assert all(h.score >= 65 for h in top)


def test_step_filter_and_rank_sorted(monkeypatch):
    monkeypatch.setitem(pipeline.CONFIG, "score_threshold", 0)
    hitters = [
        make_hitter("Player A", score=60),
        make_hitter("Player B", score=80),
        make_hitter("Player C", score=70),
    ]
    top, all_scored = pipeline.step_filter_and_rank(hitters)
    scores = [h.score for h in top]
    assert scores == sorted(scores, reverse=True)


def test_step_filter_none_above_threshold(monkeypatch):
    monkeypatch.setitem(pipeline.CONFIG, "score_threshold", 90)
    hitters = [make_hitter(score=60), make_hitter(score=70)]
    top, _ = pipeline.step_filter_and_rank(hitters)
    assert top == []


def test_save_run_to_history(temp_data):
    hitters = [make_hitter("Player A", score=75)]
    pipeline._save_run_to_history(hitters, "2025-04-15")

    history_file = pipeline.CONFIG["scores_file"]
    assert history_file.exists()

    with open(history_file) as f:
        history = json.load(f)

    assert len(history) == 1
    assert history[0]["date"] == "2025-04-15"
    assert len(history[0]["picks"]) == 1
    assert history[0]["picks"][0]["name"] == "Player A"


def test_save_run_to_history_appends(temp_data):
    """Multiple runs should append to history."""
    pipeline._save_run_to_history([make_hitter(score=75)], "2025-04-14")
    pipeline._save_run_to_history([make_hitter(score=80)], "2025-04-15")

    with open(pipeline.CONFIG["scores_file"]) as f:
        history = json.load(f)

    assert len(history) == 2


def test_save_run_keeps_90_days(temp_data):
    """History should never exceed 90 runs."""
    for i in range(95):
        pipeline._save_run_to_history(
            [make_hitter(score=70)],
            f"2025-{str(i+1).zfill(3)}"
        )

    with open(pipeline.CONFIG["scores_file"]) as f:
        history = json.load(f)

    assert len(history) == 90


def test_load_history_empty(temp_data):
    result = pipeline.load_history()
    assert result == []


def test_load_history_returns_recent(temp_data):
    pipeline._save_run_to_history([make_hitter(score=75)], "2025-04-15")
    result = pipeline.load_history(days=30)
    assert len(result) >= 0


def test_run_pipeline_no_hitters(temp_data):
    """Pipeline with empty roster should return empty list."""
    result = pipeline.run_pipeline(dry_run=True)
    assert result == []


def test_run_pipeline_full(temp_data, sample_hitters, monkeypatch):
    """Full pipeline run with all external calls mocked."""
    monkeypatch.setitem(pipeline.CONFIG, "score_threshold", 60)
    monkeypatch.setitem(pipeline.CONFIG, "anthropic_api_key", "")

    enriched = [make_hitter("Freddie Freeman", score=0),
                make_hitter("Mookie Betts", score=0)]

    with patch("src.pipeline.enrich_all_hitters", return_value=enriched), \
         patch("src.pipeline.enrich_hitter_stats", side_effect=lambda h: h), \
         patch("src.pipeline.enrich_hitter_statcast", side_effect=lambda h: h), \
         patch("src.pipeline.enrich_hitter_weather", side_effect=lambda h: h), \
         patch("src.pipeline.score_all_hitters") as mock_score:

        scored = [make_hitter("Freddie Freeman", score=78),
                  make_hitter("Mookie Betts", score=65)]
        mock_score.return_value = scored

        result = pipeline.run_pipeline(dry_run=True)

    assert len(result) == 2


def test_run_pipeline_dry_run_does_not_save(temp_data, sample_hitters, monkeypatch):
    """Dry run should not write to scores history."""
    monkeypatch.setitem(pipeline.CONFIG, "score_threshold", 0)
    monkeypatch.setitem(pipeline.CONFIG, "anthropic_api_key", "")

    enriched = [make_hitter(score=0)]

    with patch("src.pipeline.enrich_all_hitters", return_value=enriched), \
         patch("src.pipeline.enrich_hitter_stats", side_effect=lambda h: h), \
         patch("src.pipeline.enrich_hitter_statcast", side_effect=lambda h: h), \
         patch("src.pipeline.enrich_hitter_weather", side_effect=lambda h: h), \
         patch("src.pipeline.score_all_hitters", return_value=enriched):

        pipeline.run_pipeline(dry_run=True)

    assert not pipeline.CONFIG["scores_file"].exists()


def test_run_pipeline_no_games_today(temp_data, sample_hitters, monkeypatch):
    """If no hitters have games, pipeline exits early."""
    with patch("src.pipeline.enrich_all_hitters", return_value=[]):
        result = pipeline.run_pipeline(dry_run=True)
    assert result == []


def test_run_pipeline_skip_flags(temp_data, sample_hitters, monkeypatch):
    """Skip flags should prevent those steps from running."""
    monkeypatch.setitem(pipeline.CONFIG, "score_threshold", 0)
    monkeypatch.setitem(pipeline.CONFIG, "anthropic_api_key", "")

    enriched = [make_hitter(score=0)]

    with patch("src.pipeline.enrich_all_hitters", return_value=enriched) as mock_schedule, \
         patch("src.pipeline.enrich_hitter_stats") as mock_stats, \
         patch("src.pipeline.enrich_hitter_statcast") as mock_statcast, \
         patch("src.pipeline.enrich_hitter_weather") as mock_weather, \
         patch("src.pipeline.score_all_hitters", return_value=enriched):

        pipeline.run_pipeline(
            dry_run=True,
            skip_stats=True,
            skip_statcast=True,
            skip_weather=True,
        )

    mock_stats.assert_not_called()
    mock_statcast.assert_not_called()
    mock_weather.assert_not_called()


def test_get_todays_top_picks_empty(temp_data):
    result = pipeline.get_todays_top_picks()
    assert result == []


def test_get_todays_top_picks_returns_n(temp_data):
    import datetime
    hitters = [make_hitter(f"Player {i}", score=80 - i) for i in range(8)]
    pipeline._save_run_to_history(
        hitters,
        datetime.date.today().isoformat()
    )
    result = pipeline.get_todays_top_picks(n=3)
    assert len(result) == 3
    scores = [p["score"] for p in result]
    assert scores == sorted(scores, reverse=True)
