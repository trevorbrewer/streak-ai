"""
streak_ai.py
=============
Main CLI entry point for STREAK·AI.
"""

import argparse
import datetime
import schedule
import time

from src.pipeline import run_pipeline, print_last_run_summary
from src.storage import load_hitters, save_hitters, add_hitter
from src.models import Hitter


def cmd_run(args):
    run_pipeline(
        dry_run=getattr(args, 'dry_run', False),
        date=getattr(args, 'date', None),
        skip_stats=getattr(args, 'skip_stats', False),
        skip_statcast=getattr(args, 'skip_statcast', False),
        skip_weather=getattr(args, 'skip_weather', False),
        skip_auto_roster=getattr(args, 'skip_auto_roster', False),
    )


def cmd_last_run(args):
    print_last_run_summary()


def cmd_list(args):
    hitters = load_hitters()
    if not hitters:
        print("No hitters in roster.")
        return
    print(f"\nRoster ({len(hitters)} hitters):\n")
    for h in hitters:
        score_str = f"{h.score}/100" if h.score is not None else "not scored"
        conf_str  = f"[{h.confidence.upper()}]" if h.confidence else ""
        print(f"  {h.name:<25} {h.team:<5} AVG={h.avg:.3f}  {score_str} {conf_str}")
    print()


def cmd_add_hitter(args):
    print("\n─── Add Hitter ───\n")
    name  = input("Player name: ").strip()
    team  = input("Team (e.g. LAD): ").strip().upper()
    hand  = input("Bats L/R/S [R]: ").strip().upper() or "R"
    avg   = float(input("Season AVG (e.g. .298) [0]: ") or "0")
    obp   = float(input("OBP [0]: ") or "0")
    slg   = float(input("SLG [0]: ") or "0")
    woba  = float(input("wOBA (optional) [skip]: ") or "0") or None
    babip = float(input("BABIP (optional) [skip]: ") or "0") or None
    notes = input("Notes (optional): ").strip() or None

    hitter = Hitter(
        name=name, team=team, hand=hand,
        avg=avg, obp=obp, slg=slg,
        woba=woba, babip=babip, notes=notes,
    )

    try:
        roster = add_hitter(hitter)
        print(f"\n✓ {name} added to roster ({len(roster)} total hitters)")
    except ValueError as e:
        print(f"\n✗ {e}")


def cmd_schedule(args):
    print("[scheduler] Pipeline will run daily at 10:00 AM ET")
    print("  Press Ctrl+C to stop\n")

    def run():
        print(f"\n[scheduler] Triggered at {datetime.datetime.now()}")
        run_pipeline()

    schedule.every().day.at("10:00").do(run)
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="STREAK·AI — Beat the Streak prediction system"
    )
    parser.add_argument("--run-now",       action="store_true")
    parser.add_argument("--dry-run",       action="store_true")
    parser.add_argument("--date",          type=str, default=None)
    parser.add_argument("--last-run",      action="store_true")
    parser.add_argument("--list",          action="store_true")
    parser.add_argument("--add-hitter",    action="store_true")
    parser.add_argument("--schedule",      action="store_true")
    parser.add_argument("--skip-stats",    action="store_true")
    parser.add_argument("--skip-statcast", action="store_true")
    parser.add_argument("--skip-weather",  action="store_true")
    parser.add_argument("--skip-auto-roster", action="store_true")

    args = parser.parse_args()

    if args.run_now:
        cmd_run(args)
    elif args.last_run:
        cmd_last_run(args)
    elif args.list:
        cmd_list(args)
    elif args.add_hitter:
        cmd_add_hitter(args)
    elif args.schedule:
        cmd_schedule(args)
    else:
        parser.print_help()
        print("\nQuick start:")
        print("  python3 streak_ai.py --add-hitter")
        print("  python3 streak_ai.py --run-now")
        print("  python3 streak_ai.py --dry-run --skip-statcast")
        print("  python3 streak_ai.py --list")
        print("  python3 streak_ai.py --last-run")
