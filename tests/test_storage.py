"""
tests/test_storage.py
Tests for the storage layer — load, save, add, remove, update.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch
from src.models import Hitter
from src import storage


def make_hitter(name="Test Player", team="LAD", id=999):
    """Helper to create a test hitter quickly."""
    return Hitter(
        id=id,
        name=name,
        team=team,
        hand="R",
        avg=0.275,
        obp=0.340,
        slg=0.450,
    )


@pytest.fixture
def temp_roster(tmp_path, monkeypatch):
    """
    Redirect all storage operations to a temp file for testing.
    This means tests never touch your real data/hitters.json.
    """
    temp_file = tmp_path / "hitters.json"
    monkeypatch.setitem(storage.CONFIG, "hitters_file", temp_file)
    return temp_file


def test_load_hitters_empty(temp_roster):
    """Loading from a nonexistent file returns empty list."""
    result = storage.load_hitters()
    assert result == []


def test_save_and_load(temp_roster):
    """Hitters saved to disk can be loaded back correctly."""
    hitter = make_hitter()
    storage.save_hitters([hitter])
    loaded = storage.load_hitters()
    assert len(loaded) == 1
    assert loaded[0].name == "Test Player"
    assert loaded[0].team == "LAD"


def test_add_hitter(temp_roster):
    """Adding a hitter increases roster size by one."""
    h = make_hitter()
    roster = storage.add_hitter(h)
    assert len(roster) == 1
    assert roster[0].name == "Test Player"


def test_add_duplicate_raises(temp_roster):
    """Adding the same player twice raises ValueError."""
    h = make_hitter()
    storage.add_hitter(h)
    with pytest.raises(ValueError, match="already in the roster"):
        storage.add_hitter(h)


def test_remove_hitter(temp_roster):
    """Removing a hitter by name works correctly."""
    storage.add_hitter(make_hitter(name="Player One", id=1))
    storage.add_hitter(make_hitter(name="Player Two", id=2))
    roster = storage.remove_hitter("Player One")
    assert len(roster) == 1
    assert roster[0].name == "Player Two"


def test_remove_nonexistent_raises(temp_roster):
    """Removing a player not in the roster raises ValueError."""
    with pytest.raises(ValueError, match="not found"):
        storage.remove_hitter("Ghost Player")


def test_get_hitter_found(temp_roster):
    """get_hitter returns the correct hitter by name."""
    storage.add_hitter(make_hitter(name="Freddie Freeman"))
    result = storage.get_hitter("Freddie Freeman")
    assert result is not None
    assert result.name == "Freddie Freeman"


def test_get_hitter_not_found(temp_roster):
    """get_hitter returns None when player doesn't exist."""
    result = storage.get_hitter("Nobody Here")
    assert result is None


def test_get_hitter_case_insensitive(temp_roster):
    """get_hitter should find players regardless of name casing."""
    storage.add_hitter(make_hitter(name="Freddie Freeman"))
    result = storage.get_hitter("freddie freeman")
    assert result is not None


def test_update_hitter(temp_roster):
    """Updating a hitter replaces the record correctly."""
    original = make_hitter(name="Test Player", id=1)
    storage.add_hitter(original)
    updated = make_hitter(name="Test Player", id=1)
    updated.avg = 0.350
    storage.update_hitter(updated)
    result = storage.get_hitter("Test Player")
    assert result.avg == 0.350


def test_clear_roster(temp_roster):
    """clear_roster removes all hitters."""
    storage.add_hitter(make_hitter(id=1))
    storage.clear_roster()
    assert storage.load_hitters() == []


def test_hitters_persisted_as_json(temp_roster):
    """Verify the file on disk is valid JSON after saving."""
    storage.add_hitter(make_hitter())
    with open(temp_roster) as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert data[0]["name"] == "Test Player"