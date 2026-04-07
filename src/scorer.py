"""
src/scorer.py
==============
Claude AI scoring engine.

Takes a fully engineered feature vector and sends it to Claude
for analysis. Returns a structured score with reasoning.

Main functions:
    score_hitter(hitter, features)   -> ScoringResult dict
    score_all_hitters(hitters)       -> list of scored Hitter objects
    build_prompt(hitter, features)   -> the prompt sent to Claude
"""

import json
import time
import datetime
from src.config import CONFIG
from src.models import Hitter
from src.features import summarize_features

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("  [warn] anthropic package not installed")


# ─────────────────────────── PROMPT ───────────────────────────

SYSTEM_PROMPT = """You are an elite baseball analytics expert specializing
in ESPN Beat the Streak. Your job is to evaluate MLB hitters and score
their probability of getting at least ONE hit in today's game.

You have deep knowledge of:
- Batting statistics and what they predict
- Pitcher matchup analysis
- Park factors and their impact on batting
- Statcast metrics and quality of contact
- Hot/cold streaks and BABIP regression
- Platoon advantages and splits
- How to weight recent form vs season norms

You always respond with valid JSON only. No markdown, no explanation
outside the JSON structure."""

ANALYSIS_PROMPT = """Score this hitter 0-100 on probability of getting
at least ONE hit today.

SCORING GUIDE:
  85-100: Elite spot — multiple strong advantages, high floor
  70-84:  Strong pick — clear edge in matchup or form
  55-69:  Solid pick — some advantages, manageable risk
  40-54:  Borderline — mixed signals, proceed carefully
  25-39:  Lean avoid — notable disadvantages
  0-24:   Avoid — multiple red flags

HITTER: {name} ({team}) — Bats {hand}
TODAY'S MATCHUP: vs {opp} | Pitcher: {pitcher} ({phand}HP) | ERA: {era}
PARK: {park} | Home/Away: {home_away}

SEASON STATS:
  AVG/OBP/SLG: {avg}/{obp}/{slg}
  wOBA: {woba} | BABIP: {babip}

RECENT FORM:
  Last 7 days: {l7}
  Last 30 days: {l30}
  Trend: {trend}

STATCAST:
  Exit velocity: {exit_velo} mph
  Hard hit%: {hard_pct}%

ENGINEERED FEATURES:
{feature_summary}

STREAK MODE: {streak_mode}
- conservative: prioritize floor, penalize high-K pitchers heavily
- balanced: optimize expected hit probability
- aggressive: ceiling picks OK, higher variance acceptable

Respond ONLY with this exact JSON structure:
{{
  "score": <integer 0-100>,
  "confidence": "<high|medium|low>",
  "reasoning": "<3-4 sentence analysis explaining the score>",
  "key_factor": "<single most important factor driving the score today>",
  "risk_factor": "<main concern or reason this pick could fail>",
  "features_used": ["<top 3 features that most influenced the score>"],
  "recommendation": "<strong_pick|lean_pick|neutral|lean_avoid|avoid>"
}}"""


# ─────────────────────────── PROMPT BUILDER ───────────────────────────

def build_prompt(hitter: Hitter, features: dict) -> str:
    """
    Build the analysis prompt for a single hitter.
    Fills in all available data — uses 'N/A' for missing fields.
    """
    def fmt(val, decimals=3):
        if val is None:
            return "N/A"
        if isinstance(val, float):
            return f"{val:.{decimals}f}"
        return str(val)

    # Build trend description
    trend = "N/A"
    if features.get("hot_streak"):
        delta = features.get("l7_delta", 0) or 0
        trend = f"HOT — L7 is +{delta:.3f} above season avg"
    elif features.get("cold_streak"):
        delta = features.get("l7_delta", 0) or 0
        trend = f"COLD — L7 is {delta:.3f} below season avg"
    elif features.get("l7_delta") is not None:
        trend = f"Neutral — L7 delta {features['l7_delta']:+.3f}"

    # Build feature summary for the prompt
    feature_lines = []
    important_features = [
        ("platoon_label",         "Platoon"),
        ("platoon_advantage",     "Platoon advantage"),
        ("park_hits_factor",      "Park hits factor"),
        ("park_impact_score",     "Park impact score"),
        ("pitcher_quality_score", "Pitcher quality score"),
        ("favorable_matchup",     "Favorable matchup"),
        ("elite_pitcher",         "Elite pitcher"),
        ("babip_luck",            "BABIP luck"),
        ("babip_unlucky",         "BABIP unlucky (due for hits)"),
        ("babip_lucky",           "BABIP lucky (due for regression)"),
        ("contact_score",         "Contact score"),
        ("matchup_score",         "Matchup score"),
        ("momentum_score",        "Momentum score"),
        ("pre_ai_score",          "Pre-AI composite score"),
        ("top_of_order",          "Top of batting order"),
        ("early_season",          "Early season (small sample)"),
        ("elite_contact",         "Elite contact quality"),
        ("accelerating",          "Momentum accelerating"),
    ]
    for key, label in important_features:
        val = features.get(key)
        if val is not None:
            feature_lines.append(f"  {label}: {val}")

    feature_summary = "\n".join(feature_lines) if feature_lines else "  No computed features"

    return ANALYSIS_PROMPT.format(
        name=hitter.name,
        team=hitter.team or "?",
        hand=hitter.hand or "?",
        opp=hitter.opp or "TBD",
        pitcher=hitter.pitcher or "TBD",
        phand=hitter.phand or "?",
        era=fmt(hitter.era, 2),
        park=hitter.park or "TBD",
        home_away=hitter.home_away or "?",
        avg=fmt(hitter.avg),
        obp=fmt(hitter.obp),
        slg=fmt(hitter.slg),
        woba=fmt(hitter.woba),
        babip=fmt(hitter.babip),
        l7=fmt(hitter.l7),
        l30=fmt(hitter.l30),
        trend=trend,
        exit_velo=fmt(hitter.exit_velo, 1),
        hard_pct=fmt(hitter.hard_pct, 1),
        feature_summary=feature_summary,
        streak_mode=CONFIG.get("streak_mode", "conservative"),
    )


# ─────────────────────────── SCORING ───────────────────────────

def score_hitter(hitter: Hitter, features: dict) -> dict:
    """
    Score a single hitter using Claude AI.

    Args:
        hitter:   Hitter dataclass object
        features: engineered feature dict from src.features

    Returns dict with:
        score, confidence, reasoning, key_factor,
        risk_factor, features_used, recommendation
    """
    api_key = CONFIG.get("anthropic_api_key", "")

    if not api_key or not ANTHROPIC_AVAILABLE:
        return _mock_score(hitter, features)

    prompt = build_prompt(hitter, features)

    print(f"  Scoring {hitter.name} with Claude AI...")

    for attempt in range(3):
        try:
            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=600,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            raw = message.content[0].text.strip()

            # Strip any accidental markdown fences
            raw = raw.replace("```json", "").replace("```", "").strip()

            result = json.loads(raw)

            # Validate required fields
            required = ["score", "confidence", "reasoning",
                        "key_factor", "risk_factor"]
            for field in required:
                if field not in result:
                    raise ValueError(f"Missing field in AI response: {field}")

            # Clamp score to valid range
            result["score"] = max(0, min(100, int(result["score"])))

            print(
                f"  [ok] {hitter.name}: {result['score']}/100 "
                f"[{result['confidence'].upper()}] — {result['key_factor']}"
            )
            return result

        except json.JSONDecodeError as e:
            print(f"  [warn] JSON parse failed (attempt {attempt + 1}): {e}")
            if attempt < 2:
                time.sleep(2)

        except anthropic.RateLimitError:
            print(f"  [warn] Rate limit hit — waiting 30 seconds...")
            time.sleep(30)

        except anthropic.APIError as e:
            print(f"  [error] Anthropic API error: {e}")
            break

        except Exception as e:
            print(f"  [error] Scoring failed for {hitter.name}: {e}")
            break

    # All attempts failed — return fallback
    print(f"  [warn] All attempts failed for {hitter.name} — using fallback")
    return _fallback_score(hitter, features)


def _mock_score(hitter: Hitter, features: dict) -> dict:
    """
    Generate a mock score when no API key is configured.
    Uses the pre_ai_score from feature engineering as the estimate.
    Useful for testing the pipeline end to end without API costs.
    """
    import random
    base = features.get("pre_ai_score") or 55.0
    noise = random.uniform(-8, 8)
    score = max(10, min(95, int(base + noise)))

    confidence = "high" if score >= 72 else "medium" if score >= 55 else "low"

    return {
        "score":          score,
        "confidence":     confidence,
        "reasoning":      (
            f"Mock score for {hitter.name} — add ANTHROPIC_API_KEY to .env "
            f"for real AI analysis. Pre-AI composite score was {base}."
        ),
        "key_factor":     "Mock mode — feature engineering composite",
        "risk_factor":    "No real AI analysis performed",
        "features_used":  ["pre_ai_score", "platoon_advantage", "park_hits_factor"],
        "recommendation": (
            "strong_pick" if score >= 72
            else "lean_pick" if score >= 60
            else "neutral" if score >= 50
            else "lean_avoid"
        ),
    }


def _fallback_score(hitter: Hitter, features: dict) -> dict:
    """
    Fallback score when API calls fail after retries.
    Uses feature engineering scores as best estimate.
    """
    base = features.get("pre_ai_score") or 50.0
    score = max(10, min(90, int(base)))

    return {
        "score":          score,
        "confidence":     "low",
        "reasoning":      f"API scoring failed — using feature engineering estimate of {base}.",
        "key_factor":     "API unavailable",
        "risk_factor":    "Score reliability low — API error",
        "features_used":  ["pre_ai_score"],
        "recommendation": "neutral",
    }


def score_all_hitters(hitters: list[Hitter], features_list: list[dict]) -> list[Hitter]:
    """
    Score an entire roster of hitters.

    Args:
        hitters:       list of Hitter objects
        features_list: list of feature dicts in the same order

    Returns:
        List of Hitter objects with score, confidence, reasoning,
        key_factor fields populated. Sorted by score descending.
    """
    if not hitters:
        return []

    print(f"\n[scorer] Scoring {len(hitters)} hitters with Claude AI...\n")
    scored = []

    for hitter, features in zip(hitters, features_list):
        result = score_hitter(hitter, features)

        hitter.score      = result["score"]
        hitter.confidence = result.get("confidence", "medium")
        hitter.reasoning  = result.get("reasoning", "")
        hitter.key_factor = result.get("key_factor", "")
        hitter.scored_at  = datetime.datetime.now().isoformat()

        scored.append(hitter)

        # Small delay between API calls to avoid rate limiting
        if CONFIG.get("anthropic_api_key"):
            time.sleep(0.5)

    # Sort by score descending
    scored.sort(key=lambda h: h.score or 0, reverse=True)

    print(f"\n[scorer] Scoring complete. Rankings:")
    for i, h in enumerate(scored, 1):
        print(
            f"  {i:2}. {h.name:<25} "
            f"{h.score:3}/100  [{(h.confidence or 'med').upper():<6}]  "
            f"{h.key_factor or ''}"
        )

    return scored


# ─────────────────────────── CLI TEST ───────────────────────────

if __name__ == "__main__":
    from src.features import engineer_features

    print("Testing Claude AI scorer...\n")

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

    features = engineer_features(hitter)
    result = score_hitter(hitter, features)

    print(f"\nScoring result for {hitter.name}:")
    print(f"  Score:          {result['score']}/100")
    print(f"  Confidence:     {result['confidence']}")
    print(f"  Recommendation: {result.get('recommendation', 'N/A')}")
    print(f"  Key factor:     {result['key_factor']}")
    print(f"  Risk factor:    {result['risk_factor']}")
    print(f"\nReasoning:")
    print(f"  {result['reasoning']}")

    print(f"\nPrompt sent to Claude:")
    print("-" * 60)
    print(build_prompt(hitter, features))
