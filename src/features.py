"""
src/features.py
================
Feature engineering pipeline.
Combines all data sources into a single scored feature vector
that gets passed to the Claude AI scorer.

Main function:
    engineer_features(hitter) -> dict of all features

All features are documented with their units and scoring direction
so the AI prompt can reference them clearly.
"""

import datetime
from src.models import Hitter
from src.data_sources.park_factors import get_park_factor, park_impact_score


def engineer_features(hitter: Hitter) -> dict:
    """
    Compute all engineered features for a hitter.

    Takes a fully enriched Hitter object (after running through
    schedule enrichment, MLB stats, Statcast, and weather modules)
    and returns a flat dict of named features ready for AI scoring.

    Args:
        hitter: a Hitter dataclass object with as many fields
                populated as possible

    Returns:
        dict of feature_name -> value pairs
    """
    features = {}

    # ── Raw stats passthrough ─────────────────────────────────────
    _add_raw_stats(features, hitter)

    # ── Derived batting metrics ───────────────────────────────────
    _add_derived_batting(features, hitter)

    # ── Trend and momentum features ───────────────────────────────
    _add_momentum(features, hitter)

    # ── BABIP luck adjustment ─────────────────────────────────────
    _add_babip_luck(features, hitter)

    # ── Platoon advantage ─────────────────────────────────────────
    _add_platoon(features, hitter)

    # ── Pitcher matchup ───────────────────────────────────────────
    _add_pitcher_matchup(features, hitter)

    # ── Park factors ──────────────────────────────────────────────
    _add_park_factors(features, hitter)

    # ── Statcast quality of contact ───────────────────────────────
    _add_statcast(features, hitter)

    # ── Situational context ───────────────────────────────────────
    _add_situational(features, hitter)

    # ── Composite scores ──────────────────────────────────────────
    _add_composite_scores(features)

    return features


# ─────────────────────────── FEATURE GROUPS ───────────────────────────

def _add_raw_stats(features: dict, hitter: Hitter):
    """Pass through raw stats directly from the Hitter object."""
    features["season_avg"]  = hitter.avg
    features["season_obp"]  = hitter.obp
    features["season_slg"]  = hitter.slg
    features["season_woba"] = hitter.woba
    features["season_babip"] = hitter.babip
    features["l7_avg"]      = hitter.l7
    features["l14_avg"]     = hitter.l14
    features["l30_avg"]     = hitter.l30
    features["exit_velo"]   = hitter.exit_velo
    features["hard_hit_pct"] = hitter.hard_pct


def _add_derived_batting(features: dict, hitter: Hitter):
    """Compute derived metrics from raw stats."""

    # OPS — on base plus slugging
    if hitter.obp and hitter.slg:
        features["ops"] = round(hitter.obp + hitter.slg, 3)
    else:
        features["ops"] = None

    # ISO — isolated power (extra base hit ability)
    if hitter.slg and hitter.avg:
        features["iso"] = round(hitter.slg - hitter.avg, 3)
    else:
        features["iso"] = None

    # Contact rate proxy — higher AVG relative to SLG = more contact
    if hitter.avg and hitter.slg and hitter.slg > 0:
        features["contact_proxy"] = round(hitter.avg / hitter.slg, 3)
    else:
        features["contact_proxy"] = None


def _add_momentum(features: dict, hitter: Hitter):
    """
    Compute trend and momentum features.
    Positive delta = hitter is hot, negative = cold.
    """
    # L7 vs season average delta
    if hitter.l7 and hitter.avg:
        features["l7_delta"] = round(hitter.l7 - hitter.avg, 3)
        features["hot_streak"] = hitter.l7 >= (hitter.avg + 0.030)
        features["cold_streak"] = hitter.l7 <= (hitter.avg - 0.030)
    else:
        features["l7_delta"]    = None
        features["hot_streak"]  = None
        features["cold_streak"] = None

    # L30 vs season average delta
    if hitter.l30 and hitter.avg:
        features["l30_delta"] = round(hitter.l30 - hitter.avg, 3)
    else:
        features["l30_delta"] = None

    # L7 vs L30 — short term vs medium term momentum
    if hitter.l7 and hitter.l30:
        features["short_vs_medium"] = round(hitter.l7 - hitter.l30, 3)
        features["accelerating"]    = hitter.l7 > hitter.l30
    else:
        features["short_vs_medium"] = None
        features["accelerating"]    = None


def _add_babip_luck(features: dict, hitter: Hitter):
    """
    BABIP luck adjustment.
    Expected BABIP for most hitters is around .300.
    High BABIP = likely to regress down (getting lucky).
    Low BABIP = likely to regress up (getting unlucky).
    """
    expected_babip = 0.300

    if hitter.babip:
        features["babip_luck"]      = round(hitter.babip - expected_babip, 3)
        features["babip_lucky"]     = hitter.babip > 0.330
        features["babip_unlucky"]   = hitter.babip < 0.270
        features["babip_regression_expected"] = abs(
            hitter.babip - expected_babip
        ) > 0.040
    else:
        features["babip_luck"]                = None
        features["babip_lucky"]               = None
        features["babip_unlucky"]             = None
        features["babip_regression_expected"] = None


def _add_platoon(features: dict, hitter: Hitter):
    """
    Platoon advantage.
    Batters generally hit better against opposite-handed pitchers.
    Switch hitters always have the advantage.
    """
    batter_hand = (hitter.hand or "R").upper()
    pitcher_hand = (hitter.phand or "R").upper()

    if batter_hand == "S":
        # Switch hitter always has platoon advantage
        features["platoon_advantage"]  = True
        features["platoon_multiplier"] = 1.08
        features["platoon_label"]      = "switch_hitter"
    elif batter_hand != pitcher_hand:
        features["platoon_advantage"]  = True
        features["platoon_multiplier"] = 1.10
        features["platoon_label"]      = f"{batter_hand}HB_vs_{pitcher_hand}HP"
    else:
        features["platoon_advantage"]  = False
        features["platoon_multiplier"] = 1.00
        features["platoon_label"]      = f"same_hand_{batter_hand}"


def _add_pitcher_matchup(features: dict, hitter: Hitter):
    """
    Pitcher quality features.
    Lower ERA/WHIP = harder matchup for hitter.
    """
    era = hitter.era

    if era is not None:
        # Favorable matchup = weak pitcher (ERA >= 4.50)
        features["pitcher_era"]         = era
        features["favorable_matchup"]   = era >= 4.50
        features["elite_pitcher"]       = era <= 2.75
        features["avg_pitcher"]         = 3.50 <= era <= 4.50

        # Pitcher quality score 0-100
        # ERA 1.0 = score ~8 (very hard), ERA 6.0 = score ~72 (very easy)
        features["pitcher_quality_score"] = round(
            min(100, max(0, (era - 1.0) / 5.0 * 100)), 1
        )
    else:
        features["pitcher_era"]           = None
        features["favorable_matchup"]     = None
        features["elite_pitcher"]         = None
        features["avg_pitcher"]           = None
        features["pitcher_quality_score"] = 50.0  # neutral when unknown


def _add_park_factors(features: dict, hitter: Hitter):
    """
    Park factor features.
    hits_factor > 1.0 = more hits expected at this park.
    """
    park_name = hitter.park or ""
    park_data = get_park_factor(park_name)

    features["park_name"]         = park_data.get("park_name", park_name)
    features["park_hits_factor"]  = park_data.get("hits_factor", 1.00)
    features["park_hr_factor"]    = park_data.get("hr_factor", 1.00)
    features["park_surface"]      = park_data.get("surface", "grass")
    features["park_roof"]         = park_data.get("roof", "open")
    features["park_elevation_ft"] = park_data.get("elevation_ft", 0)
    features["park_hitter_friendly"] = park_data.get("hits_factor", 1.0) >= 1.03
    features["park_impact_score"] = park_impact_score(park_name)

    # Home/away split
    features["is_home"] = hitter.home_away == "home"


def _add_statcast(features: dict, hitter: Hitter):
    """
    Statcast quality of contact metrics.
    Higher exit velo and hard hit% = better hitter.
    """
    features["exit_velo_avg"] = hitter.exit_velo
    features["hard_hit_pct"]  = hitter.hard_pct

    # Quality tiers
    if hitter.exit_velo:
        features["elite_contact"]  = hitter.exit_velo >= 92.0
        features["weak_contact"]   = hitter.exit_velo <= 86.0
    else:
        features["elite_contact"] = None
        features["weak_contact"]  = None

    if hitter.hard_pct:
        features["elite_hard_hit"] = hitter.hard_pct >= 45.0
        features["below_avg_hard"] = hitter.hard_pct <= 30.0
    else:
        features["elite_hard_hit"] = None
        features["below_avg_hard"] = None


def _add_situational(features: dict, hitter: Hitter):
    """
    Situational and contextual features.
    """
    # Batting order — top of order sees more PAs
    batting_order = hitter.batting_order
    features["batting_order"]     = batting_order
    features["top_of_order"]      = batting_order in (1, 2) if batting_order else None
    features["middle_of_order"]   = batting_order in (3, 4, 5) if batting_order else None
    features["bottom_of_order"]   = batting_order in (7, 8, 9) if batting_order else None

    # Time of year / season context
    today = datetime.date.today()
    month = today.month
    features["month"]             = month
    features["early_season"]      = month in (3, 4)
    features["mid_season"]        = month in (5, 6, 7)
    features["late_season"]       = month in (8, 9, 10)

    # Small sample size warning — early season stats less reliable
    features["small_sample_warning"] = month in (3, 4)


def _add_composite_scores(features: dict):
    """
    Combine individual features into composite scores.
    These give the AI a high-level summary alongside the raw features.
    """

    # Contact score — how likely is this hitter to make contact?
    contact_inputs = []
    if features.get("season_avg"):
        contact_inputs.append(features["season_avg"] * 200)
    if features.get("l7_avg"):
        contact_inputs.append(features["l7_avg"] * 200)
    if features.get("hard_hit_pct"):
        contact_inputs.append(features["hard_hit_pct"])
    features["contact_score"] = round(
        sum(contact_inputs) / len(contact_inputs), 1
    ) if contact_inputs else None

    # Matchup score — how favorable is today's matchup?
    matchup_inputs = []
    if features.get("pitcher_quality_score") is not None:
        matchup_inputs.append(features["pitcher_quality_score"])
    if features.get("park_impact_score") is not None:
        matchup_inputs.append(features["park_impact_score"])
    if features.get("platoon_advantage"):
        matchup_inputs.append(60.0)
    elif features.get("platoon_advantage") is False:
        matchup_inputs.append(40.0)
    features["matchup_score"] = round(
        sum(matchup_inputs) / len(matchup_inputs), 1
    ) if matchup_inputs else None

    # Momentum score — is this hitter hot or cold?
    momentum_inputs = []
    if features.get("l7_delta") is not None:
        # Convert delta to 0-100 scale: +.100 = 100, -.100 = 0
        momentum_inputs.append(
            min(100, max(0, 50 + features["l7_delta"] * 500))
        )
    if features.get("hot_streak"):
        momentum_inputs.append(70.0)
    elif features.get("cold_streak"):
        momentum_inputs.append(30.0)
    features["momentum_score"] = round(
        sum(momentum_inputs) / len(momentum_inputs), 1
    ) if momentum_inputs else None

    # Overall pre-AI score — weighted composite of all three
    overall_inputs = []
    weights = []
    if features.get("contact_score") is not None:
        overall_inputs.append(features["contact_score"] * 0.40)
        weights.append(0.40)
    if features.get("matchup_score") is not None:
        overall_inputs.append(features["matchup_score"] * 0.35)
        weights.append(0.35)
    if features.get("momentum_score") is not None:
        overall_inputs.append(features["momentum_score"] * 0.25)
        weights.append(0.25)

    if overall_inputs and sum(weights) > 0:
        features["pre_ai_score"] = round(
            sum(overall_inputs) / sum(weights), 1
        )
    else:
        features["pre_ai_score"] = None


def summarize_features(features: dict) -> str:
    """
    Return a human readable summary of the most important features.
    Used in AI prompts and email reports.
    """
    lines = []

    if features.get("season_avg"):
        lines.append(f"AVG: {features['season_avg']:.3f}")
    if features.get("ops"):
        lines.append(f"OPS: {features['ops']:.3f}")
    if features.get("l7_avg"):
        lines.append(f"L7: {features['l7_avg']:.3f}")
    if features.get("l7_delta") is not None:
        delta = features["l7_delta"]
        sign = "+" if delta >= 0 else ""
        lines.append(f"L7 delta: {sign}{delta:.3f}")
    if features.get("hot_streak"):
        lines.append("Status: HOT STREAK")
    elif features.get("cold_streak"):
        lines.append("Status: COLD STREAK")
    if features.get("platoon_label"):
        lines.append(f"Platoon: {features['platoon_label']}")
    if features.get("pitcher_era") is not None:
        lines.append(f"Pitcher ERA: {features['pitcher_era']}")
    if features.get("park_hits_factor"):
        lines.append(f"Park hits factor: {features['park_hits_factor']}")
    if features.get("exit_velo_avg"):
        lines.append(f"Exit velo: {features['exit_velo_avg']} mph")
    if features.get("hard_hit_pct"):
        lines.append(f"Hard hit%: {features['hard_hit_pct']}%")
    if features.get("pre_ai_score") is not None:
        lines.append(f"Pre-AI score: {features['pre_ai_score']}/100")

    return " | ".join(lines)


if __name__ == "__main__":
    from src.models import Hitter

    # Build a fully populated test hitter
    hitter = Hitter(
        name="Freddie Freeman",
        team="LAD",
        hand="L",
        avg=0.302,
        obp=0.390,
        slg=0.510,
        l7=0.340,
        l14=0.315,
        l30=0.308,
        woba=0.375,
        babip=0.315,
        exit_velo=91.2,
        hard_pct=42.1,
        opp="SD",
        pitcher="Yu Darvish",
        phand="R",
        era=3.85,
        park="Petco Park",
        home_away="away",
        batting_order=3,
    )

    print(f"Engineering features for {hitter.name}...\n")
    features = engineer_features(hitter)

    print("All features:")
    for key, value in features.items():
        print(f"  {key:<35} {value}")

    print(f"\nSummary:")
    print(f"  {summarize_features(features)}")
