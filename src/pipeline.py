"""
src/pipeline.py
================
Full pipeline orchestrator.

Wires all modules together into one daily run:
    1. Load hitters from roster
    2. Auto-enrich matchups from today's MLB schedule
    3. Fetch season stats from MLB Stats API
    4. Fetch Statcast advanced metrics
    5. Fetch weather per ballpark
    6. Engineer all features
    7. Score with Claude AI
    8. Rank and filter by threshold
    9. Save results to history

Usage:
    from src.pipeline import run_pipeline
    results = run_pipeline()

    # Or with options:
    results = run_pipeline(dry_run=True, date="2025-04-15")
"""

import json
import datetime
from pathlib import Path

from src.config import CONFIG, validate_config
from src.storage import load_hitters, save_hitters
from src.features import engineer_features
from src.scorer import score_all_hitters
from src.data_sources.schedule import enrich_all_hitters
from src.data_sources.mlb_stats import enrich_hitter_stats
from src.data_sources.statcast import enrich_hitter_statcast
from src.data_sources.weather import enrich_hitter_weather


# ─────────────────────────── LOGGING ───────────────────────────

def _log(level: str, msg: str):
    """Simple timestamped logger."""
    now = datetime.datetime.now().strftime("%H:%M:%S")
    icons = {"info": "ℹ", "ok": "✓", "warn": "⚠", "error": "✗", "step": "▶"}
    icon = icons.get(level, "·")
    print(f"[{now}] {icon} {msg}")


def _divider(title: str = ""):
    width = 60
    if title:
        padding = (width - len(title) - 2) // 2
        print(f"\n{'─' * padding} {title} {'─' * padding}\n")
    else:
        print(f"\n{'─' * width}\n")


# ─────────────────────────── HISTORY ───────────────────────────

def _save_run_to_history(scored_hitters: list, date: str):
    """
    Append today's scored picks to the scores history file.
    Keeps last 90 days of history.
    """
    history_file: Path = CONFIG["scores_file"]
    history = []

    if history_file.exists():
        try:
            with open(history_file) as f:
                history = json.load(f)
        except (json.JSONDecodeError, IOError):
            history = []

    import os
    run_record = {
        "date":      date,
        "run_at":    datetime.datetime.now().isoformat(),
        "run_label": os.getenv("RUN_LABEL", "manual"),
        "picks": [
            {
                "name":       h.name,
                "team":       h.team,
                "opp":        h.opp,
                "pitcher":    h.pitcher,
                "park":       h.park,
                "score":      h.score,
                "confidence": h.confidence,
                "key_factor": h.key_factor,
                "reasoning":  h.reasoning,
            }
            for h in scored_hitters
        ]
    }

    history.append(run_record)
    history = history[-90:]  # Keep last 90 days

    history_file.parent.mkdir(parents=True, exist_ok=True)
    with open(history_file, "w") as f:
        json.dump(history, f, indent=2)

    _log("ok", f"Run saved to history ({len(history)} total runs)")


def load_history(days: int = 30) -> list:
    """
    Load recent scoring history.

    Args:
        days: how many days back to load

    Returns list of run records.
    """
    history_file: Path = CONFIG["scores_file"]
    if not history_file.exists():
        return []

    with open(history_file) as f:
        history = json.load(f)

    cutoff = (
        datetime.date.today() - datetime.timedelta(days=days)
    ).isoformat()

    return [r for r in history if r.get("date", "") >= cutoff]


# ─────────────────────────── PIPELINE STEPS ───────────────────────────

def step_load_hitters() -> list:
    """Step 1 — Load hitter roster from disk."""
    _divider("STEP 1: Load Roster")
    hitters = load_hitters()
    if not hitters:
        _log("warn", "No hitters in roster — add hitters to data/hitters.json")
        return []
    _log("ok", f"Loaded {len(hitters)} hitters from roster")
    for h in hitters:
        _log("info", f"  {h.name} ({h.team})")
    return hitters


def step_enrich_matchups(hitters: list, date: str) -> list:
    """Step 2 — Auto-populate matchup data from today's schedule."""
    _divider("STEP 2: Enrich Matchups")
    _log("step", "Pulling today's MLB schedule and starting pitchers...")
    enriched = enrich_all_hitters(hitters, date)
    if not enriched:
        _log("warn", "No hitters have games today")
        return []

    # Filter out hitters whose lineup hasn't been confirmed yet
    confirmed = [
        h for h in enriched
        if "LINEUP_UNCONFIRMED" not in (h.notes or "")
    ]
    unconfirmed = [
        h for h in enriched
        if "LINEUP_UNCONFIRMED" in (h.notes or "")
    ]

    if unconfirmed:
        _log(
            "warn",
            f"{len(unconfirmed)} hitters excluded — lineup not yet posted:"
        )
        for h in unconfirmed:
            _log("info", f"  {h.name} ({h.team})")

    _log("ok", f"{len(confirmed)} hitters have confirmed lineups")
    return confirmed


def step_fetch_stats(hitters: list) -> list:
    """Step 3 — Fetch season stats from MLB Stats API."""
    _divider("STEP 3: Fetch Season Stats")
    enriched = []
    for h in hitters:
        try:
            _log("step", f"Fetching stats for {h.name}...")
            h = enrich_hitter_stats(h)
        except Exception as e:
            _log("warn", f"Stats fetch failed for {h.name}: {e}")
        enriched.append(h)
    _log("ok", "Season stats fetch complete")
    return enriched


def step_fetch_statcast(hitters: list) -> list:
    """Step 4 — Fetch Statcast advanced metrics."""
    _divider("STEP 4: Fetch Statcast Metrics")
    enriched = []
    for h in hitters:
        try:
            _log("step", f"Fetching Statcast for {h.name}...")
            h = enrich_hitter_statcast(h)
        except Exception as e:
            _log("warn", f"Statcast fetch failed for {h.name}: {e}")
        enriched.append(h)
    _log("ok", "Statcast fetch complete")
    return enriched


def step_fetch_weather(hitters: list) -> list:
    """Step 5 — Fetch game-time weather per ballpark."""
    _divider("STEP 5: Fetch Weather")
    if not CONFIG.get("openweather_api_key"):
        _log("warn", "No OpenWeather API key — skipping weather step")
        return hitters

    seen_parks = set()
    enriched = []
    for h in hitters:
        if h.park and h.park not in seen_parks:
            try:
                _log("step", f"Fetching weather for {h.park}...")
                h = enrich_hitter_weather(h)
                seen_parks.add(h.park)
            except Exception as e:
                _log("warn", f"Weather fetch failed for {h.park}: {e}")
        elif h.park in seen_parks:
            h = enrich_hitter_weather(h)
        enriched.append(h)

    _log("ok", f"Weather fetched for {len(seen_parks)} parks")
    return enriched

def step_auto_roster(date: str, skip_auto_roster: bool = False) -> list:
    """
    Step 2b — Pull all hitters batting 1-4 today.
    These are scored alongside the manual roster but not
    saved permanently to hitters.json.
    """
    from src.data_sources.schedule import get_top_of_order_hitters

    if skip_auto_roster:
        return []

    _divider("STEP 2b: Auto-Roster (slots 1-4)")
    _log("step", "Scanning all lineups for hitters batting 1st through 4th...")

    auto_hitters = get_top_of_order_hitters(date=date)

    if not auto_hitters:
        _log("warn", "No lineup data yet — lineups post 3-4 hours before games")
        return []

    _log("ok", f"Auto-rostered {len(auto_hitters)} hitters batting 1-4")
    return auto_hitters

def step_engineer_features(hitters: list) -> tuple[list, list]:
    """Step 6 — Engineer all features for each hitter."""
    _divider("STEP 6: Engineer Features")
    features_list = []
    for h in hitters:
        try:
            features = engineer_features(h)
            features_list.append(features)
            pre_score = features.get("pre_ai_score")
            _log("info", f"  {h.name}: pre-AI score = {pre_score}")
        except Exception as e:
            _log("warn", f"Feature engineering failed for {h.name}: {e}")
            features_list.append({})

    _log("ok", f"Features engineered for {len(features_list)} hitters")
    return hitters, features_list


def step_score(hitters: list, features_list: list) -> list:
    """Step 7 — Score all hitters with Claude AI."""
    _divider("STEP 7: AI Scoring")
    if not CONFIG.get("anthropic_api_key"):
        _log("warn", "No Anthropic API key — using mock scoring")

    # Load today's cached scores to avoid re-scoring hitters
    # already scored in an earlier run today
    today = datetime.date.today().isoformat()
    daily_cache = CONFIG["cache_dir"] / f"scored_{today}.json"
    cached_scores = {}

    if daily_cache.exists():
        try:
            with open(daily_cache) as f:
                cached = json.load(f)
            cached_scores = {
                p["name"].lower(): p
                for p in cached
                if p.get("score") is not None
            }
            _log("info", f"Loaded {len(cached_scores)} cached scores from earlier today")
        except Exception as e:
            _log("warn", f"Could not load daily cache: {e}")

    # Apply cached scores before sending to Claude
    if cached_scores:
        for h in hitters:
            if h.name.lower() in cached_scores:
                c = cached_scores[h.name.lower()]
                h.score      = c.get("score")
                h.confidence = c.get("confidence")
                h.reasoning  = c.get("reasoning")
                h.key_factor = c.get("key_factor")
                h.scored_at  = c.get("scored_at")

    scored = score_all_hitters(hitters, features_list)
    return scored or []


def step_filter_and_rank(scored: list) -> tuple[list, list]:
    """
    Step 8 — Filter by score threshold and rank.
    Returns (top_picks, all_scored).
    """
    _divider("STEP 8: Rank and Filter")
    threshold = CONFIG.get("score_threshold", 65)

    scored = sorted(scored, key=lambda h: h.score or 0, reverse=True)
    top_picks = [h for h in scored if (h.score or 0) >= threshold]

    _log("ok", f"{len(top_picks)} hitters above threshold ({threshold})")
    _log("info", "\nFull rankings:")
    for i, h in enumerate(scored, 1):
        marker = "★" if (h.score or 0) >= threshold else " "
        _log(
            "info",
            f"  {marker} {i:2}. {h.name:<25} "
            f"{h.score:3}/100  [{(h.confidence or 'med').upper():<6}]"
        )

    return top_picks, scored


def step_save(scored: list, date: str):
    """Step 9 — Save results to roster and history."""
    _divider("STEP 9: Save Results")

    # Save manual roster hitters back to hitters.json
    from src.storage import load_hitters as _load
    manual_names = {h.name.lower() for h in _load()}
    manual_scored = [h for h in scored if h.name.lower() in manual_names]
    if manual_scored:
        save_hitters(manual_scored)
        _log("ok", "Updated hitters.json with latest scores")

    # Save ALL scored hitters to daily cache so afternoon runs
    # can skip re-scoring players already done this morning
    daily_cache = CONFIG["cache_dir"] / f"scored_{date}.json"
    with open(daily_cache, "w") as f:
        json.dump(
            [h.to_dict() for h in scored],
            f, indent=2, default=str
        )
    _log("ok", f"Daily scores cached ({len(scored)} hitters) → {daily_cache.name}")

    _save_run_to_history(scored, date)


# ─────────────────────────── MAIN PIPELINE ───────────────────────────

def run_pipeline(
    dry_run: bool = False,
    date: str = None,
    skip_stats: bool = False,
    skip_statcast: bool = False,
    skip_weather: bool = False,
    skip_auto_roster: bool = False,
) -> list:
    """
    Run the full daily picks pipeline.

    Args:
        dry_run:        If True, skip saving results and sending email
        date:           "YYYY-MM-DD" to run for a specific date,
                        defaults to today
        skip_stats:     Skip MLB Stats API fetch (use cached/manual stats)
        skip_statcast:  Skip Statcast fetch (use cached/manual metrics)
        skip_weather:   Skip weather fetch

    Returns:
        List of scored Hitter objects above the score threshold,
        sorted by score descending.
    """
    if date is None:
        date = datetime.date.today().isoformat()

    import os
    run_label = os.getenv("RUN_LABEL", "manual")

    _divider()
    _log("step", f"STREAK·AI Pipeline — {date} [{run_label}]")
    _log("info", f"Streak mode: {CONFIG.get('streak_mode', 'conservative')}")
    _log("info", f"Score threshold: {CONFIG.get('score_threshold', 65)}")
    _log("info", f"Run: {run_label}")
    if dry_run:
        _log("warn", "DRY RUN — results will not be saved or emailed")
    _divider()

    # Check for missing config
    missing = validate_config()
    if missing:
        _log("warn", f"Missing API keys: {missing}")
        _log("warn", "Pipeline will continue with reduced functionality")

    start_time = datetime.datetime.now()

    # ── Step 1: Load ──────────────────────────────────────────────
    hitters = step_load_hitters()
    if not hitters:
        _log("error", "No hitters to process — exiting")
        return []
    
    # # Pre-filter — only keep hitters with reasonable matchups
    # # This cuts the list before expensive API calls
    # hitters = [
    #     h for h in hitters
    #     if h.era is None or h.era >= 2.0
    # ]

    # ── Step 2: Matchups ──────────────────────────────────────
    hitters = step_enrich_matchups(hitters, date)
    if not hitters:
        _log("error", "No hitters have games today — exiting")
        return []

    # ── Step 2b: Auto-roster top of order hitters ─────────────
    if not skip_auto_roster:
        auto_hitters = step_auto_roster(date)
        if auto_hitters:
            existing_names = {h.name.lower() for h in hitters}
            new_hitters = [
                h for h in auto_hitters
                if h.name.lower() not in existing_names
            ]
            _log("ok", f"Adding {len(new_hitters)} new auto-rostered hitters")
            hitters = hitters + new_hitters

    # ── Step 3: Season stats ──────────────────────────────────
    if not skip_stats:
        hitters = step_fetch_stats(hitters)

    # ── Step 4: Statcast ──────────────────────────────────────────
    if not skip_statcast:
        hitters = step_fetch_statcast(hitters)

    # ── Step 5: Weather ───────────────────────────────────────────
    if not skip_weather:
        hitters = step_fetch_weather(hitters)

    # ── Step 6: Feature engineering ───────────────────────────────
    hitters, features_list = step_engineer_features(hitters)

    # ── Step 7: AI scoring ────────────────────────────────────────
    scored = step_score(hitters, features_list)

    # ── Step 8: Rank and filter ───────────────────────────────────
    top_picks, all_scored = step_filter_and_rank(scored)

    # ── Step 9: Save ──────────────────────────────────────────────
    if not dry_run:
        step_save(all_scored, date)
        step_send_email(all_scored, top_picks)
    else:
        _log("warn", "Dry run — skipping save and email")

    # ── Summary ───────────────────────────────────────────────────
    elapsed = (datetime.datetime.now() - start_time).seconds
    _divider("PIPELINE COMPLETE")
    _log("ok", f"Finished in {elapsed}s")
    _log("ok", f"{len(top_picks)} picks above threshold")
    if top_picks:
        _log("info", "\nTop picks for today:")
        for i, h in enumerate(top_picks, 1):
            _log(
                "info",
                f"  {i}. {h.name} ({h.team}) — "
                f"{h.score}/100 [{h.confidence}] — {h.key_factor}"
            )
    _divider()

    return top_picks


# ─────────────────────────── UTILITIES ───────────────────────────

def get_todays_top_picks(n: int = 5) -> list:
    """
    Return the top N picks from the most recent pipeline run.
    Reads from scores history — does not re-run the pipeline.
    """
    history = load_history(days=1)
    if not history:
        return []
    latest = history[-1]
    picks = latest.get("picks", [])
    return sorted(picks, key=lambda p: p.get("score", 0), reverse=True)[:n]


def print_last_run_summary():
    """Print a summary of the most recent pipeline run."""
    history = load_history(days=1)
    if not history:
        print("No recent pipeline runs found.")
        return

    latest = history[-1]
    print(f"\nLast run: {latest['run_at']}")
    print(f"Date: {latest['date']}")
    print(f"Picks: {len(latest.get('picks', []))}\n")

    for i, pick in enumerate(latest.get("picks", []), 1):
        print(
            f"  {i:2}. {pick['name']:<25} "
            f"{pick['score']:3}/100  "
            f"[{(pick['confidence'] or 'med').upper():<6}]  "
            f"{pick.get('key_factor', '')}"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="STREAK·AI Pipeline")
    parser.add_argument("--dry-run",        action="store_true")
    parser.add_argument("--date",           type=str, default=None)
    parser.add_argument("--skip-stats",     action="store_true")
    parser.add_argument("--skip-statcast",  action="store_true")
    parser.add_argument("--skip-weather",   action="store_true")
    parser.add_argument("--last-run",       action="store_true")
    args = parser.parse_args()

    if args.last_run:
        print_last_run_summary()
    else:
        run_pipeline(
            dry_run=args.dry_run,
            date=args.date,
            skip_stats=args.skip_stats,
            skip_statcast=args.skip_statcast,
            skip_weather=args.skip_weather,
        )


def step_send_email(scored: list, top_picks: list):
    """Optional Step 10 — Send email report via SendGrid."""
    from src.email_reporter import send_picks_email
    _divider("STEP 10: Send Email")

    if not CONFIG.get("sendgrid_api_key"):
        _log("warn", "No SendGrid API key — skipping email")
        return

    if not CONFIG.get("email_recipients"):
        _log("warn", "No email recipients configured — skipping email")
        return

    _log("step", f"Sending picks email to {CONFIG['email_recipients']}...")
    success = send_picks_email(scored)
    if success:
        _log("ok", "Email sent successfully")
    else:
        _log("warn", "Email delivery failed — check SendGrid config")
