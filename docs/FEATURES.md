# STREAK·AI — Feature Documentation

Every feature the AI uses when scoring a hitter.

## Raw Stats

| Feature | Description | Source |
|---|---|---|
| season_avg | Season batting average | MLB Stats API |
| season_obp | On base percentage | MLB Stats API |
| season_slg | Slugging percentage | MLB Stats API |
| season_woba | Weighted on-base average | MLB Stats API |
| season_babip | Batting average on balls in play | MLB Stats API |
| l7_avg | Last 7 days batting average | MLB Stats API |
| l14_avg | Last 14 days batting average | MLB Stats API |
| l30_avg | Last 30 days batting average | MLB Stats API |

## Derived Batting Metrics

| Feature | Formula | What it means |
|---|---|---|
| ops | OBP + SLG | Overall offensive production |
| iso | SLG - AVG | Pure extra base hit power |
| contact_proxy | AVG / SLG | Contact rate relative to power |

## Momentum & Trend

| Feature | Description | Signal |
|---|---|---|
| l7_delta | L7 avg minus season avg | Positive = hot, negative = cold |
| l30_delta | L30 avg minus season avg | Medium term trend |
| hot_streak | L7 >= season avg + .030 | True = on a hot streak |
| cold_streak | L7 <= season avg - .030 | True = in a slump |
| short_vs_medium | L7 minus L30 | True = momentum accelerating |
| accelerating | L7 > L30 | Short term better than medium |

## BABIP Luck Adjustment

BABIP (Batting Average on Balls in Play) expected value is ~.300.
Significant deviation suggests luck that will regress.

| Feature | Description | Signal |
|---|---|---|
| babip_luck | BABIP minus .300 | Positive = lucky, negative = unlucky |
| babip_lucky | BABIP > .330 | Likely to regress downward |
| babip_unlucky | BABIP < .270 | Likely to regress upward (due for hits) |
| babip_regression_expected | Deviation > .040 | Strong regression signal |

## Platoon Advantage

Batters generally hit ~10% better against opposite-handed pitchers.

| Feature | Description |
|---|---|
| platoon_advantage | True if batter faces opposite-hand pitcher |
| platoon_multiplier | 1.10 for advantage, 1.00 for same hand |
| platoon_label | e.g. LHB_vs_RHP, switch_hitter |

## Pitcher Matchup

| Feature | Description | Signal |
|---|---|---|
| pitcher_era | Opposing pitcher ERA | Lower = harder matchup |
| pitcher_quality_score | 0-100 score (high = easy matchup) | >60 = favorable |
| favorable_matchup | ERA >= 4.50 | True = weak pitcher |
| elite_pitcher | ERA <= 2.75 | True = very difficult matchup |
| avg_pitcher | 3.50 <= ERA <= 4.50 | True = average matchup |

## Park Factors

| Feature | Description | Source |
|---|---|---|
| park_hits_factor | >1.0 = more hits expected | FanGraphs 3yr avg |
| park_hr_factor | Home run park factor | FanGraphs 3yr avg |
| park_impact_score | 0-100 composite park score | Computed |
| park_hitter_friendly | hits_factor >= 1.03 | True = hitter park |
| park_surface | grass or artificial | Built-in DB |
| park_roof | open, retractable, fixed | Built-in DB |
| park_elevation_ft | Elevation in feet | Built-in DB |
| is_home | True if hitter is at home park | Schedule API |

## Statcast Quality of Contact

| Feature | Description | Elite threshold |
|---|---|---|
| exit_velo_avg | Average exit velocity (mph) | >= 92 mph |
| hard_hit_pct | % of balls hit >= 95 mph | >= 45% |
| elite_contact | exit_velo >= 92 mph | Strong contact quality |
| weak_contact | exit_velo <= 86 mph | Poor contact quality |
| elite_hard_hit | hard_pct >= 45% | Elite hard contact |
| below_avg_hard | hard_pct <= 30% | Soft contact concern |

## Situational

| Feature | Description |
|---|---|
| batting_order | Lineup slot (1-9) |
| top_of_order | Slots 1-2 (most PAs) |
| middle_of_order | Slots 3-5 (RBI spots) |
| bottom_of_order | Slots 7-9 (fewer PAs) |
| early_season | March/April (small sample) |
| small_sample_warning | Same as early_season |

## Composite Scores

These combine multiple features into single scores for the AI:

| Feature | Weight | Components |
|---|---|---|
| contact_score | 40% of pre_ai | season_avg, l7_avg, hard_hit_pct |
| matchup_score | 35% of pre_ai | pitcher_quality_score, park_impact_score, platoon |
| momentum_score | 25% of pre_ai | l7_delta, hot/cold streak |
| pre_ai_score | Final composite | Weighted sum of above three |

## Streak Modes

The AI prompt changes behavior based on streak mode:

| Mode | Strategy |
|---|---|
| conservative | Prioritize floor, penalize high-K pitchers, avoid cold streaks |
| balanced | Optimize expected hit probability |
| aggressive | Ceiling picks OK, higher variance acceptable |
