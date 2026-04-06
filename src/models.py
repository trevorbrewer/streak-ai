"""
src/models.py
==============
Hitter data model. Every field the system tracks lives here.
"""

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Hitter:
    name: str
    team: str
    hand: str = "R"
    avg: float = 0.0
    obp: float = 0.0
    slg: float = 0.0
    l7: Optional[float] = None
    l14: Optional[float] = None
    l30: Optional[float] = None
    woba: Optional[float] = None
    babip: Optional[float] = None
    exit_velo: Optional[float] = None
    hard_pct: Optional[float] = None
    opp: Optional[str] = None
    pitcher: Optional[str] = None
    phand: Optional[str] = None
    era: Optional[float] = None
    park: Optional[str] = None
    park_factor: Optional[float] = None
    home_away: Optional[str] = None
    batting_order: Optional[int] = None
    score: Optional[int] = None
    confidence: Optional[str] = None
    reasoning: Optional[str] = None
    key_factor: Optional[str] = None
    scored_at: Optional[str] = None
    notes: Optional[str] = None
    id: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> dict:
        """Convert to plain dict for JSON serialization."""
        return {
            "id":            self.id,
            "name":          self.name,
            "team":          self.team,
            "hand":          self.hand,
            "avg":           self.avg,
            "obp":           self.obp,
            "slg":           self.slg,
            "l7":            self.l7,
            "l14":           self.l14,
            "l30":           self.l30,
            "woba":          self.woba,
            "babip":         self.babip,
            "exit_velo":     self.exit_velo,
            "hard_pct":      self.hard_pct,
            "opp":           self.opp,
            "pitcher":       self.pitcher,
            "phand":         self.phand,
            "era":           self.era,
            "park":          self.park,
            "park_factor":   self.park_factor,
            "home_away":     self.home_away,
            "batting_order": self.batting_order,
            "score":         self.score,
            "confidence":    self.confidence,
            "reasoning":     self.reasoning,
            "key_factor":    self.key_factor,
            "scored_at":     self.scored_at,
            "notes":         self.notes,
        }
