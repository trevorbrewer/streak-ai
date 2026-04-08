# STREAK·AI — Architecture

## Overview

STREAK·AI is a daily automated pipeline that scores MLB hitters
for the ESPN Beat the Streak game. It runs entirely on GitHub
Actions with no server required.

## Pipeline Flow
┌─────────────────────────────────────────────────────────┐
│                   GitHub Actions (10 AM ET)              │
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐   │
│  │  Step 1  │    │  Step 2  │    │    Steps 3-5     │   │
│  │  Load    │───►│ Matchup  │───►│   Data Fetch     │   │
│  │  Roster  │    │ Enrich   │    │ Stats/Statcast/  │   │
│  └──────────┘    └──────────┘    │    Weather       │   │
│                                  └────────┬─────────┘   │
│                                           │              │
│  ┌──────────┐    ┌──────────┐    ┌────────▼─────────┐   │
│  │  Step 9  │    │  Step 8  │    │     Step 6       │   │
│  │   Save   │◄───│  Rank &  │◄───│    Feature       │   │
│  │ Results  │    │  Filter  │    │  Engineering     │   │
│  └────┬─────┘    └──────────┘    └────────┬─────────┘   │
│       │                                   │              │
│  ┌────▼─────┐                   ┌────────▼─────────┐   │
│  │ Step 10  │                   │     Step 7       │   │
│  │  Email   │                   │   Claude AI      │   │
│  │  Report  │                   │    Scoring       │   │
│  └──────────┘                   └──────────────────┘   │
└─────────────────────────────────────────────────────────┘
│
▼
┌─────────────────┐
│  GitHub Pages   │
│   Dashboard     │
│  (auto-updates) │
└─────────────────┘

## Module Breakdown

### src/config.py
Central configuration loader. Reads all settings from environment
variables. Every other module imports CONFIG from here.

### src/models.py
Hitter dataclass with every field the system tracks — from basic
stats (AVG, OBP, SLG) to AI scoring outputs (score, confidence,
reasoning). Serializes to/from JSON via to_dict().

### src/storage.py
CRUD layer for the hitter roster. Loads and saves hitters.json.
All operations go through this module — nothing reads the JSON
file directly.

### src/data_sources/schedule.py
The automation backbone. Hits the free MLB Stats API to pull
today's full game slate, probable starting pitchers with full
stats, and confirmed lineups. Enriches the entire roster with
matchup data in one call — zero manual entry required.

### src/data_sources/mlb_stats.py
Pulls season batting stats and rolling averages (L7/L14/L30)
from the MLB Stats API. Results cached for 1 hour to avoid
repeat calls during development.

### src/data_sources/statcast.py
Pulls Statcast metrics from Baseball Savant via pybaseball.
Exit velocity, xBA, hard hit%, launch angle. Falls back
gracefully when pybaseball is unavailable.

### src/data_sources/weather.py
Fetches real-time weather per ballpark from OpenWeather.
Computes a hitter weather score accounting for temperature,
wind direction, conditions, and humidity.

### src/data_sources/park_factors.py
Built-in database of all 30 MLB parks with hits factor, HR
factor, doubles factor, surface, roof type, and elevation.
Fuzzy name matching so partial names always resolve correctly.

### src/features.py
The feature engineering pipeline. Takes a fully enriched Hitter
object and outputs a flat labeled feature dict. 8 feature groups,
30+ features, composite scores for contact, matchup, and momentum.

### src/scorer.py
Claude AI integration. Builds a detailed prompt from the feature
vector, sends to claude-sonnet, parses the structured JSON
response. 3 retry attempts, rate limit handling, mock mode for
testing without API costs.

### src/pipeline.py
The orchestrator. Runs all 10 steps in sequence with timestamped
logging. Supports dry_run, skip flags for faster iteration, and
date override for historical runs.

### src/email_reporter.py
Builds and sends the daily HTML email via SendGrid. Color-coded
scores, confidence badges, per-hitter reasoning. Plain text
fallback for clients that don't render HTML.

## Data Flow
hitters.json (roster)
│
▼
Hitter objects (src/models.py)
│
├── schedule.py  ──► adds opp, pitcher, park, home_away
├── mlb_stats.py ──► adds avg, obp, slg, l7, l30, woba
├── statcast.py  ──► adds exit_velo, hard_pct, xba
└── weather.py   ──► adds weather context to notes
│
▼
engineer_features(hitter) ──► feature dict (30+ features)
│
▼
score_hitter(hitter, features) ──► {score, confidence, reasoning}
│
▼
scores_history.json ──► GitHub Pages dashboard

## Caching Strategy

All external API calls are cached locally to avoid rate limits
and speed up development iteration:

| Data | Cache Duration |
|---|---|
| MLB schedule | 30 minutes |
| Probable pitchers | 30 minutes |
| Lineups | 15 minutes |
| Season stats | 1 hour |
| Recent stats (L7/L30) | 1 hour |
| Statcast metrics | 1 hour |
| Weather | 30 minutes |
| Player ID lookup | 24 hours |
| Sprint speed | 24 hours |

Cache files live in `data/cache/` and are gitignored.

## Testing Strategy

80+ unit tests across 10 test files. All external API calls
are mocked so tests run fast and offline. Tests use pytest
fixtures with temporary directories so they never touch real
data files.

CI runs on every push to main and every pull request via
GitHub Actions on Ubuntu.
