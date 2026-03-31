import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent

CONFIG = {
    "anthropic_api_key":   os.getenv("ANTHROPIC_API_KEY", ""),
    "sendgrid_api_key":    os.getenv("SENDGRID_API_KEY", ""),
    "email_from":          os.getenv("EMAIL_FROM", ""),
    "email_recipients":    [
        r.strip()
        for r in os.getenv("EMAIL_RECIPIENTS", "").split(",")
        if r.strip()
    ],
    "openweather_api_key": os.getenv("OPENWEATHER_API_KEY", ""),
    "score_threshold":     int(os.getenv("SCORE_THRESHOLD", "65")),
    "streak_mode":         os.getenv("STREAK_MODE", "conservative"),
    "data_dir":            ROOT / "data",
    "cache_dir":           ROOT / "data" / "cache",
    "hitters_file":        ROOT / "data" / "hitters.json",
    "scores_file":         ROOT / "data" / "scores_history.json",
}

CONFIG["data_dir"].mkdir(exist_ok=True)
CONFIG["cache_dir"].mkdir(parents=True, exist_ok=True)

def validate_config():
    required = {
        "anthropic_api_key":  "ANTHROPIC_API_KEY",
        "sendgrid_api_key":   "SENDGRID_API_KEY",
        "email_from":         "EMAIL_FROM",
        "email_recipients":   "EMAIL_RECIPIENTS",
    }
    missing = []
    for config_key, env_name in required.items():
        value = CONFIG[config_key]
        if not value or value == []:
            missing.append(env_name)
    return missing

if __name__ == "__main__":
    print("CONFIG loaded:")
    for key, value in CONFIG.items():
        if "key" in key and value:
            print(f"  {key}: ***{str(value)[-4:]}")
        else:
            print(f"  {key}: {value}")

    missing = validate_config()
    if missing:
        print(f"\nMissing keys: {missing}")
    else:
        print("\nAll required keys present.")
