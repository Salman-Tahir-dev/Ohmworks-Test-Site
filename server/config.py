"""Configuration and Vulnerability Level Manager for Ohmworks."""

import json
import os
from typing import Dict

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

VALID_LEVELS = ["off", "low", "medium", "high"]
DEFAULT_CONFIG = {
    "LLM01": "low",
    "LLM03": "low",
    "LLM08": "low",
    "LLM10": "low"
}


def load_config() -> Dict[str, str]:
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for cat in ["LLM01", "LLM03", "LLM08", "LLM10"]:
                    if cat in saved and saved[cat] in VALID_LEVELS:
                        config[cat] = saved[cat]
        except Exception:
            pass

    # Environment variable overrides
    env_map = {
        "LLM01": os.environ.get("OHMWORKS_LLM01_LEVEL"),
        "LLM03": os.environ.get("OHMWORKS_LLM03_LEVEL"),
        "LLM08": os.environ.get("OHMWORKS_LLM08_LEVEL"),
        "LLM10": os.environ.get("OHMWORKS_LLM10_LEVEL"),
    }
    for cat, val in env_map.items():
        if val and val.lower() in VALID_LEVELS:
            config[cat] = val.lower()

    return config


def save_config(new_levels: Dict[str, str]) -> Dict[str, str]:
    config = load_config()
    for cat in ["LLM01", "LLM03", "LLM08", "LLM10"]:
        if cat in new_levels and new_levels[cat] in VALID_LEVELS:
            config[cat] = new_levels[cat]

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return config


def get_level(category: str) -> str:
    config = load_config()
    return config.get(category, "low")
