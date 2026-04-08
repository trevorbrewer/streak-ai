# STREAK·AI — Beat the Streak Prediction System

[![CI Tests](https://github.com/trevorbrewer/streak-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/trevorbrewer/streak-ai/actions/workflows/ci.yml)
[![Daily Pipeline](https://github.com/trevorbrewer/streak-ai/actions/workflows/daily_picks.yml/badge.svg)](https://github.com/trevorbrewer/streak-ai/actions/workflows/daily_picks.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> AI-powered MLB hit prediction system for ESPN Beat the Streak.
> Automatically pulls daily schedules, enriches hitter matchups,
> engineers advanced features, and delivers ranked picks via
> email every morning — fully automated via GitHub Actions.

**Live Dashboard:** [trevorbrewer.github.io/streak-ai](https://trevorbrewer.github.io/streak-ai)

---

## What it does

STREAK·AI runs a full machine learning pipeline every day at 10 AM ET:

1. Pulls today's MLB schedule and starting pitchers automatically
2. Fetches real season stats and recent form from the MLB Stats API
3. Pulls Statcast metrics from Baseball Savant (exit velocity, xBA, hard hit%)
4. Fetches game-time weather per ballpark from OpenWeather
5. Engineers 30+ features including platoon advantage, BABIP luck, momentum delta
6. Scores each hitter 0–100 using Claude AI with detailed reasoning
7. Ranks and filters picks by confidence threshold
8. Sends a formatted HTML email with today's top picks
9. Commits results to the repo — dashboard updates automatically

---

## Architecture

Data sources feed into the feature engineering pipeline, which feeds Claude AI, which produces ranked picks delivered by email and shown on the dashboard.

- **src/data_sources/schedule.py** auto-enriches all hitter matchups daily from the free MLB Stats API — opponent, starting pitcher, ERA, park, home/away, batting order. Zero manual entry required.
- **src/features.py** combines all data sources into a flat labeled feature vector with 30+ engineered features.
- **src/scorer.py** sends the feature vector to Claude AI and parses a structured JSON response with score, confidence, reasoning, and key factors.
- **src/pipeline.py** orchestrates all 10 steps with timestamped logging, dry run support, and skip flags for faster iteration.
- **GitHub Actions** runs the full pipeline on a cron schedule and commits results back to the repo automatically.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| AI Scoring | Anthropic Claude (claude-sonnet) |
| Schedule & Stats | MLB Stats API (free, no key) |
| Advanced Metrics | pybaseball / Baseball Savant |
| Email Delivery | SendGrid |
| Weather | OpenWeather API |
| CI/CD | GitHub Actions |
| Dashboard | GitHub Pages |
| Testing | pytest (80+ tests) |

---

## Project Structure
```
streak-ai/
├── src/
│   ├── config.py              # Central config loader
│   ├── models.py              # Hitter dataclass
│   ├── storage.py             # JSON roster CRUD
│   ├── features.py            # Feature engineering pipeline
│   ├── scorer.py              # Claude AI scoring engine
│   ├── pipeline.py            # Full pipeline orchestrator
│   ├── email_reporter.py      # SendGrid HTML email
│   └── data_sources/
│       ├── schedule.py        # MLB schedule + matchup automation
│       ├── mlb_stats.py       # Season batting stats
│       ├── statcast.py        # Statcast advanced metrics
│       ├── weather.py         # Per-park weather
│       └── park_factors.py    # All 30 MLB park factors
├── data/
│   ├── hitters.json           # Your roster
│   └── scores_history.json    # 90-day pick history (auto-updated)
├── docs/
│   ├── index.html             # Live dashboard (GitHub Pages)
│   ├── ARCHITECTURE.md        # Full architecture documentation
│   └── FEATURES.md            # Feature engineering documentation
├── tests/                     # 80+ unit tests
├── .github/workflows/
│   ├── ci.yml                 # Tests on every push
│   └── daily_picks.yml        # Daily 10 AM ET automation
├── streak_ai.py               # CLI entry point
└── requirements.txt
```

## Feature Engineering

The system engineers 30+ features across 8 categories before scoring:

| Category | Features |
|---|---|
| Raw stats | AVG, OBP, SLG, wOBA, BABIP |
| Derived batting | OPS, ISO, contact proxy |
| Momentum | L7/L14/L30 delta, hot/cold streak, accelerating |
| BABIP luck | Luck adjustment, regression expected |
| Platoon | Advantage flag, multiplier, switch hitter handling |
| Pitcher matchup | ERA quality score, favorable matchup, elite pitcher flag |
| Park factors | Hits factor, HR factor, surface, roof, elevation |
| Statcast | Exit velocity, hard hit%, elite/weak contact tiers |

---

## Quick Start
```bash
# 1. Clone and install
git clone https://github.com/trevorbrewer/streak-ai.git
cd streak-ai
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your API keys

# 3. Add hitters to your roster
python3 streak_ai.py --add-hitter

# 4. Run the pipeline
python3 streak_ai.py --run-now

# 5. Test without sending email
python3 streak_ai.py --dry-run --skip-statcast
```

---

## CLI Reference
```bash
python3 streak_ai.py --run-now          # Full pipeline
python3 streak_ai.py --dry-run          # Run without saving or emailing
python3 streak_ai.py --list             # Show roster with latest scores
python3 streak_ai.py --add-hitter       # Add a hitter interactively
python3 streak_ai.py --last-run         # Show last pipeline summary
python3 streak_ai.py --schedule         # Start daily scheduler locally
python3 streak_ai.py --skip-statcast    # Skip Statcast fetch (faster)
python3 streak_ai.py --skip-weather     # Skip weather fetch
python3 streak_ai.py --date 2025-04-15  # Run for a specific date
```

---

## Configuration

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude AI scoring |
| `SENDGRID_API_KEY` | For email | Daily picks delivery |
| `EMAIL_FROM` | For email | Verified sender address |
| `EMAIL_RECIPIENTS` | For email | Comma-separated recipients |
| `OPENWEATHER_API_KEY` | Optional | Per-park weather data |
| `SCORE_THRESHOLD` | Optional | Min score to include (default: 65) |
| `STREAK_MODE` | Optional | conservative / balanced / aggressive |

---

## Running Tests
```bash
python3 -m pytest                    # All tests
python3 -m pytest tests/test_features.py -v   # Specific module
python3 -m pytest --tb=short         # Short traceback on failure
```

---

## Roadmap

| Chunk | Description | Status |
|---|---|---|
| 1 | Repo setup & project scaffold | ✅ Done |
| 2 | Python environment & config | ✅ Done |
| 3 | Hitter data model & storage | ✅ Done |
| 4 | GitHub Actions CI pipeline | ✅ Done |
| 5 | MLB Stats API — season stats | ✅ Done |
| 6 | Daily schedule & matchup puller | ✅ Done |
| 7 | Statcast & advanced metrics | ✅ Done |
| 8 | Weather & park factors | ✅ Done |
| 9 | Feature engineering pipeline | ✅ Done |
| 10 | Claude AI scoring engine | ✅ Done |
| 11 | Full pipeline orchestrator | ✅ Done |
| 12 | GitHub Actions daily automation | ✅ Done |
| 13 | Email report module | ✅ Done |
| 14 | Web dashboard (GitHub Pages) | ✅ Done |
| 15 | README, docs & portfolio polish | ✅ Done |

---

## License

MIT — see [LICENSE](LICENSE)

---

*Not affiliated with ESPN. For research and entertainment purposes only.*
