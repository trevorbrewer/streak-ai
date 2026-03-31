"""
tests/test_config.py
Tests for the config module.
"""

from src.config import CONFIG, validate_config
from pathlib import Path


def test_config_loads():
    """CONFIG dict exists and has expected keys."""
    assert isinstance(CONFIG, dict)
    assert "anthropic_api_key" in CONFIG
    assert "score_threshold" in CONFIG
    assert "streak_mode" in CONFIG


def test_score_threshold_is_int():
    """Score threshold should always be an integer."""
    assert isinstance(CONFIG["score_threshold"], int)
    assert 0 <= CONFIG["score_threshold"] <= 100


def test_streak_mode_is_valid():
    """Streak mode must be one of three valid options."""
    valid_modes = {"conservative", "balanced", "aggressive"}
    assert CONFIG["streak_mode"] in valid_modes


def test_data_paths_are_path_objects():
    """Data paths should be Path objects, not strings."""
    assert isinstance(CONFIG["data_dir"], Path)
    assert isinstance(CONFIG["cache_dir"], Path)
    assert isinstance(CONFIG["hitters_file"], Path)


def test_data_dirs_created():
    """Config should auto-create data directories on import."""
    assert CONFIG["data_dir"].exists()
    assert CONFIG["cache_dir"].exists()


def test_email_recipients_is_list():
    """Email recipients should always be a list."""
    assert isinstance(CONFIG["email_recipients"], list)


def test_validate_config_returns_list():
    """validate_config() should return a list (even if empty)."""
    result = validate_config()
    assert isinstance(result, list)