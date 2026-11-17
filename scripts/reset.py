"""Reset script for Ohmworks test site.
Restores SQLite seed database, resets config levels to default 'low', and clears sessions.
"""

import os
import sys
import json

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from data.seed import reset_database
from server.tools import clear_pending_confirmations


def reset_all():
    print("Resetting Ohmworks SQLite database...")
    reset_database()
    clear_pending_confirmations()

    # Reset config.json to default 'low'
    config_path = os.path.join(PROJECT_ROOT, "config.json")
    default_config = {
        "LLM01": "low",
        "LLM03": "low",
        "LLM08": "low",
        "LLM10": "low"
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(default_config, f, indent=2)
    print("Reset config.json to defaults (all 'low').")

    print("Reset complete! All chat sessions and state restored.")


if __name__ == "__main__":
    reset_all()
