"""
src/storage.py
===============
Load, save, add, update, and remove hitters from the
local JSON roster file (data/hitters.json).
"""

import json
import time
from pathlib import Path
from src.models import Hitter
from src.config import CONFIG


def load_hitters() -> list[Hitter]:
    """
    Load all hitters from the JSON roster file.
    Returns an empty list if the file doesn't exist yet.
    """
    path: Path = CONFIG["hitters_file"]
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    return [Hitter(**h) for h in data]


def save_hitters(hitters: list[Hitter]) -> None:
    """Save the full hitter list to the JSON roster file."""
    path: Path = CONFIG["hitters_file"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump([h.to_dict() for h in hitters], f, indent=2)


def add_hitter(hitter: Hitter) -> list[Hitter]:
    """
    Add a new hitter to the roster.
    Raises ValueError if a hitter with the same name already exists.
    """
    hitters = load_hitters()
    names = [h.name.lower() for h in hitters]
    if hitter.name.lower() in names:
        raise ValueError(f"{hitter.name} is already in the roster.")
    hitters.append(hitter)
    save_hitters(hitters)
    return hitters


def remove_hitter(name: str) -> list[Hitter]:
    """
    Remove a hitter by name from the roster.
    Raises ValueError if the hitter is not found.
    """
    hitters = load_hitters()
    original_count = len(hitters)
    hitters = [h for h in hitters if h.name.lower() != name.lower()]
    if len(hitters) == original_count:
        raise ValueError(f"{name} not found in roster.")
    save_hitters(hitters)
    return hitters


def get_hitter(name: str) -> Hitter | None:
    """Find and return a single hitter by name, or None if not found."""
    hitters = load_hitters()
    for h in hitters:
        if h.name.lower() == name.lower():
            return h
    return None


def update_hitter(updated: Hitter) -> list[Hitter]:
    """
    Replace an existing hitter record with an updated version.
    Matches by hitter id. Raises ValueError if not found.
    """
    hitters = load_hitters()
    for i, h in enumerate(hitters):
        if h.id == updated.id:
            hitters[i] = updated
            save_hitters(hitters)
            return hitters
    raise ValueError(f"Hitter with id {updated.id} not found.")


def clear_roster() -> None:
    """Remove all hitters from the roster. Use with caution."""
    save_hitters([])