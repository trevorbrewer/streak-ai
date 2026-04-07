"""
tests/test_features.py
Tests for the feature engineering pipeline.
Pure unit tests — no API calls needed.
"""

import pytest
from src.models import Hitter
from src.features import (
    engineer_features,
    summarize_features,
    _add_momentum,
    _add_babip_luck,
    _add_platoon,
    _add_pitcher_matchup,
    _add_composite_scores,
)


def make_hitter(**kwargs) -> Hitter:
    """Create a fully populated test hitter with sensible defaults."""
    defaults = dict(
        name="Test Player",
        team="LAD",
        hand="R",
        avg=0.280,
        obp=0.350,
        slg=0.460,
        l7=0.300,
        l14=0.290,
        l30=0.285,
        woba=0.345,
        babip=0.305,
        exit_velo=90.5,
        hard_pct=38.0,
        opp="SD",
        pitcher="Test Pitcher",
        phand="L",
        era=4.20,
        park="Dodger Stadium",
        home_away="home",
        batting_order=3,
    )
    defaults.update(kwargs)
    return Hitter(**defaults)


def test_engineer_features_returns_dict():
    hitter = make_hitter()
    features = engineer_features(hitter)
    assert isinstance(features, dict)
    assert len(features) > 20


def test_raw_stats_passthrough():
    hitter = make_hitter(avg=0.302, obp=0.390, slg=0.510)
    features = engineer_features(hitter)
    assert features["season_avg"] == 0.302
    assert features["season_obp"] == 0.390
    assert features["season_slg"] == 0.510


def test_ops_calculation():
    hitter = make_hitter(obp=0.350, slg=0.450)
    features = engineer_features(hitter)
    assert features["ops"] == round(0.350 + 0.450, 3)


def test_iso_calculation():
    hitter = make_hitter(avg=0.280, slg=0.460)
    features = engineer_features(hitter)
    assert features["iso"] == round(0.460 - 0.280, 3)


def test_hot_streak_detected():
    """L7 avg 30+ points above season avg = hot streak."""
    hitter = make_hitter(avg=0.250, l7=0.350)
    features = engineer_features(hitter)
    assert features["hot_streak"] is True
    assert features["cold_streak"] is False
    assert features["l7_delta"] == round(0.350 - 0.250, 3)


def test_cold_streak_detected():
    """L7 avg 30+ points below season avg = cold streak."""
    hitter = make_hitter(avg=0.300, l7=0.200)
    features = engineer_features(hitter)
    assert features["cold_streak"] is True
    assert features["hot_streak"] is False


def test_no_streak_when_close():
    """L7 within 30 points of season avg = no streak."""
    hitter = make_hitter(avg=0.280, l7=0.290)
    features = engineer_features(hitter)
    assert features["hot_streak"] is False
    assert features["cold_streak"] is False


def test_momentum_none_when_missing_l7():
    hitter = make_hitter()
    hitter.l7 = None
    features = engineer_features(hitter)
    assert features["l7_delta"] is None
    assert features["hot_streak"] is None


def test_babip_lucky():
    """BABIP above .330 = getting lucky."""
    hitter = make_hitter(babip=0.380)
    features = engineer_features(hitter)
    assert features["babip_lucky"] is True
    assert features["babip_unlucky"] is False
    assert features["babip_luck"] == round(0.380 - 0.300, 3)


def test_babip_unlucky():
    """BABIP below .270 = getting unlucky."""
    hitter = make_hitter(babip=0.230)
    features = engineer_features(hitter)
    assert features["babip_unlucky"] is True
    assert features["babip_lucky"] is False


def test_babip_none_when_missing():
    hitter = make_hitter()
    hitter.babip = None
    features = engineer_features(hitter)
    assert features["babip_luck"] is None


def test_platoon_advantage_lhb_vs_rhp():
    """Left handed batter vs right handed pitcher = advantage."""
    hitter = make_hitter(hand="L", phand="R")
    features = engineer_features(hitter)
    assert features["platoon_advantage"] is True
    assert features["platoon_multiplier"] == 1.10


def test_platoon_disadvantage_same_hand():
    """Same hand batter and pitcher = no advantage."""
    hitter = make_hitter(hand="R", phand="R")
    features = engineer_features(hitter)
    assert features["platoon_advantage"] is False
    assert features["platoon_multiplier"] == 1.00


def test_platoon_switch_hitter():
    """Switch hitter always has platoon advantage."""
    hitter = make_hitter(hand="S", phand="R")
    features = engineer_features(hitter)
    assert features["platoon_advantage"] is True
    assert features["platoon_label"] == "switch_hitter"


def test_pitcher_quality_score_easy():
    """High ERA pitcher = easier matchup = higher score."""
    hitter = make_hitter(era=6.00)
    features = engineer_features(hitter)
    assert features["pitcher_quality_score"] > 70
    assert features["favorable_matchup"] is True


def test_pitcher_quality_score_hard():
    """Low ERA pitcher = harder matchup = lower score."""
    hitter = make_hitter(era=2.00)
    features = engineer_features(hitter)
    assert features["pitcher_quality_score"] < 30
    assert features["elite_pitcher"] is True


def test_pitcher_none_defaults_to_neutral():
    hitter = make_hitter()
    hitter.era = None
    features = engineer_features(hitter)
    assert features["pitcher_quality_score"] == 50.0
    assert features["favorable_matchup"] is None


def test_park_factors_populated():
    hitter = make_hitter(park="Coors Field")
    features = engineer_features(hitter)
    assert features["park_hits_factor"] == 1.22
    assert features["park_hitter_friendly"] is True
    assert features["park_impact_score"] > 50


def test_park_pitcher_friendly():
    hitter = make_hitter(park="Oracle Park")
    features = engineer_features(hitter)
    assert features["park_hits_factor"] < 1.0
    assert features["park_hitter_friendly"] is False


def test_batting_order_top():
    hitter = make_hitter(batting_order=1)
    features = engineer_features(hitter)
    assert features["top_of_order"] is True
    assert features["middle_of_order"] is False


def test_batting_order_middle():
    hitter = make_hitter(batting_order=4)
    features = engineer_features(hitter)
    assert features["middle_of_order"] is True
    assert features["top_of_order"] is False


def test_exit_velo_elite():
    hitter = make_hitter(exit_velo=93.5)
    features = engineer_features(hitter)
    assert features["elite_contact"] is True
    assert features["weak_contact"] is False


def test_exit_velo_weak():
    hitter = make_hitter(exit_velo=84.0)
    features = engineer_features(hitter)
    assert features["weak_contact"] is True
    assert features["elite_contact"] is False


def test_composite_scores_present():
    hitter = make_hitter()
    features = engineer_features(hitter)
    assert "contact_score" in features
    assert "matchup_score" in features
    assert "momentum_score" in features
    assert "pre_ai_score" in features


def test_pre_ai_score_range():
    """Pre-AI score should always be between 0 and 100."""
    hitter = make_hitter()
    features = engineer_features(hitter)
    if features["pre_ai_score"] is not None:
        assert 0 <= features["pre_ai_score"] <= 100


def test_summarize_features_returns_string():
    hitter = make_hitter()
    features = engineer_features(hitter)
    summary = summarize_features(features)
    assert isinstance(summary, str)
    assert len(summary) > 0
    assert "AVG" in summary


def test_summarize_features_hot_streak():
    hitter = make_hitter(avg=0.250, l7=0.400)
    features = engineer_features(hitter)
    summary = summarize_features(features)
    assert "HOT STREAK" in summary


def test_full_pipeline_no_errors():
    """
    Full pipeline should run without exceptions
    even when many fields are None.
    """
    minimal_hitter = Hitter(name="Minimal Player", team="LAD")
    features = engineer_features(minimal_hitter)
    assert isinstance(features, dict)
    assert "season_avg" in features
    assert "platoon_advantage" in features
