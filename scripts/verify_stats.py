"""
scripts/verify_stats.py
========================
Verify that stats returned by the MLB Stats API match
known reference values from Baseball Reference.

Run this manually to audit stat accuracy:
    python3 scripts/verify_stats.py

Expected values sourced from Baseball Reference / FanGraphs
as of the current season. Update KNOWN_PLAYERS each year.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_sources.mlb_stats import (
    search_player,
    get_batter_season_stats,
    get_batter_recent_stats,
)

# ── Known players to verify ───────────────────────────────────
# Update these values at the start of each season once enough
# games have been played (20+ games for reliable numbers).
# Source: Baseball Reference or MLB.com stats page.
#
# Format: {
#   "name": player name,
#   "expected_id": MLB AM player ID (from Baseball Savant),
#   "checks": dict of stat -> (min, max) acceptable range
# }

KNOWN_PLAYERS = [
    {
        "name": "Freddie Freeman",
        "expected_id": 518692,
        "checks": {
            "avg":  (0.200, 0.400),
            "obp":  (0.280, 0.480),
            "slg":  (0.350, 0.700),
            "ops":  (0.650, 1.100),
            "hits": (1, 250),
            "at_bats": (1, 650),
        }
    },
    {
        "name": "Mookie Betts",
        "expected_id": 605141,
        "checks": {
            "avg":  (0.180, 0.380),
            "obp":  (0.260, 0.460),
            "slg":  (0.350, 0.700),
            "ops":  (0.600, 1.100),
            "hits": (1, 250),
        }
    },
    {
        "name": "Paul Goldschmidt",
        "expected_id": 502671,
        "checks": {
            "avg":  (0.180, 0.380),
            "obp":  (0.260, 0.460),
            "slg":  (0.350, 0.700),
            "ops":  (0.600, 1.100),
        }
    },
    {
        "name": "Shohei Ohtani",
        "expected_id": 660271,
        "checks": {
            "avg":  (0.200, 0.400),
            "obp":  (0.280, 0.480),
            "slg":  (0.400, 0.800),
            "ops":  (0.700, 1.200),
        }
    },
    {
        "name": "Gunnar Henderson",
        "expected_id": 683002,
        "checks": {
            "avg":  (0.180, 0.380),
            "obp":  (0.260, 0.460),
            "slg":  (0.350, 0.750),
        }
    },
]


def check_range(value, min_val, max_val) -> tuple[bool, str]:
    """Check if a value falls within an acceptable range."""
    if value is None:
        return False, "MISSING"
    if value < min_val or value > max_val:
        return False, f"OUT OF RANGE (got {value}, expected {min_val}-{max_val})"
    return True, f"OK ({value})"


def verify_player(player_config: dict) -> dict:
    """Run all checks for a single player."""
    name = player_config["name"]
    expected_id = player_config["expected_id"]
    checks = player_config["checks"]

    print(f"\n{'─' * 50}")
    print(f"Verifying: {name}")
    print(f"{'─' * 50}")

    results = {
        "name": name,
        "passed": [],
        "failed": [],
        "warnings": [],
    }

    # Check player ID
    player = search_player(name)
    if not player:
        print(f"  [FAIL] Player not found in MLB API")
        results["failed"].append("player_search")
        return results

    actual_id = player.get("id")
    if actual_id != expected_id:
        msg = f"ID MISMATCH — got {actual_id}, expected {expected_id}"
        print(f"  [WARN] {msg}")
        results["warnings"].append(f"player_id: {msg}")
    else:
        print(f"  [OK] Player ID: {actual_id}")
        results["passed"].append("player_id")

    # Get season stats
    stats = get_batter_season_stats(name)
    if not stats:
        print(f"  [FAIL] No season stats returned")
        results["failed"].append("season_stats_missing")
        return results

    print(f"\n  Season stats returned:")
    for key, value in stats.items():
        if key not in ("name", "player_id", "season"):
            print(f"    {key:<20} {value}")

    # Run range checks
    print(f"\n  Range checks:")
    for stat, (min_val, max_val) in checks.items():
        value = stats.get(stat)
        passed, msg = check_range(value, min_val, max_val)
        icon = "[OK]  " if passed else "[FAIL]"
        print(f"    {icon} {stat:<15} {msg}")
        if passed:
            results["passed"].append(stat)
        else:
            results["failed"].append(f"{stat}: {msg}")

    # Check wOBA specifically — often missing
    woba = stats.get("woba")
    if woba is None:
        print(f"    [WARN] woba           MISSING (MLB API doesn't provide this natively)")
        results["warnings"].append("woba: not available from MLB Stats API")
    else:
        passed, msg = check_range(woba, 0.250, 0.500)
        print(f"    {'[OK]  ' if passed else '[FAIL]'} woba           {msg}")

    # Check BABIP
    babip = stats.get("babip")
    if babip is None:
        print(f"    [WARN] babip          MISSING")
        results["warnings"].append("babip: not returned by API")
    else:
        passed, msg = check_range(babip, 0.200, 0.450)
        print(f"    {'[OK]  ' if passed else '[FAIL]'} babip          {msg}")

    # Check recent stats
    print(f"\n  Recent stats (L7/L14/L30):")
    recent = get_batter_recent_stats(name)
    if not recent:
        print(f"    [WARN] No recent stats returned")
        results["warnings"].append("recent_stats: empty response")
    else:
        for key in ("l7", "l14", "l30"):
            val = recent.get(key)
            if val is None:
                print(f"    [WARN] {key:<6} MISSING")
                results["warnings"].append(f"{key}: missing")
            elif val < 0.050 or val > 0.600:
                print(f"    [FAIL] {key:<6} OUT OF RANGE ({val})")
                results["failed"].append(f"{key}: {val}")
            else:
                print(f"    [OK]   {key:<6} {val}")
                results["passed"].append(key)

        # Sanity check — recent avgs should be loosely correlated
        if recent.get("l7") and recent.get("l30"):
            delta = abs(recent["l7"] - recent["l30"])
            if delta > 0.200:
                msg = f"L7 ({recent['l7']}) vs L30 ({recent['l30']}) delta is very large ({delta:.3f}) — possible API error"
                print(f"    [WARN] {msg}")
                results["warnings"].append(msg)

    return results


def print_summary(all_results: list):
    """Print a summary table of all verification results."""
    print(f"\n\n{'=' * 60}")
    print("VERIFICATION SUMMARY")
    print(f"{'=' * 60}\n")

    total_passed = 0
    total_failed = 0
    total_warnings = 0

    for r in all_results:
        passed = len(r["passed"])
        failed = len(r["failed"])
        warnings = len(r["warnings"])
        total_passed += passed
        total_failed += failed
        total_warnings += warnings

        status = "PASS" if failed == 0 else "FAIL"
        icon = "✓" if failed == 0 else "✗"
        print(f"  {icon} {r['name']:<25} {status}  ({passed} passed, {failed} failed, {warnings} warnings)")

        if r["failed"]:
            for f in r["failed"]:
                print(f"      ✗ {f}")
        if r["warnings"]:
            for w in r["warnings"]:
                print(f"      ⚠ {w}")

    print(f"\n{'─' * 60}")
    print(f"  Total: {total_passed} passed, {total_failed} failed, {total_warnings} warnings")

    if total_failed == 0:
        print(f"\n  All checks passed!")
    else:
        print(f"\n  {total_failed} checks failed — review output above")


def main():
    print("STREAK·AI — Stats Verification Tool")
    print(f"Checking {len(KNOWN_PLAYERS)} players against MLB Stats API\n")

    # Clear cache so we get fresh data
    from pathlib import Path
    cache_dir = Path("data/cache")
    cleared = 0
    for f in cache_dir.glob("season_stats_*.json"):
        f.unlink()
        cleared += 1
    for f in cache_dir.glob("recent_stats_*.json"):
        f.unlink()
        cleared += 1
    for f in cache_dir.glob("player_search_*.json"):
        f.unlink()
        cleared += 1
    print(f"Cleared {cleared} cached stat files for fresh verification\n")

    all_results = []
    for player_config in KNOWN_PLAYERS:
        result = verify_player(player_config)
        all_results.append(result)

    print_summary(all_results)


if __name__ == "__main__":
    main()
