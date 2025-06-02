import os
import json
import curses
import time
from ui import *

from pathlib import Path
CONFIG_FILE = str(Path.home() / ".config/playfin/config.json")

from encryption import *
# Get credentials
try:
    config = get_credentials(CONFIG_FILE)
    JELLYFIN_URL = config["JELLYFIN_URL"]
    JELLYFIN_USERNAME = config["JELLYFIN_USERNAME"]
    JELLYFIN_PASSWORD = config["JELLYFIN_PASSWORD"]
except Exception as e:
    cleanup()
    raise ValueError(f"Failed to get credentials: {str(e)}")

from encryption import *
from ui import *

stdscr = init_curses()


def load_config(CONFIG_FILE):
    """Load config from file or create a new one with a generated key."""
    if not os.path.exists(CONFIG_FILE):
        return None

    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)

        # Decrypt password
        key = config["ENCRYPTION_KEY"]
        config["JELLYFIN_PASSWORD"] = decrypt_password(config["JELLYFIN_PASSWORD"], key)
        return config
    except Exception as e:
        stdscr.addstr(0, 0, f"Error loading config: {str(e)}", curses.color_pair(2))
        stdscr.refresh()
        time.sleep(2)
        return None


def save_config(config, CONFIG_FILE):
    """Save config to file with encrypted password and generated key."""
    try:
        # Generate a key if it doesn't exist
        if "ENCRYPTION_KEY" not in config:
            config["ENCRYPTION_KEY"] = generate_key()

        # Encrypt password before saving
        config_copy = config.copy()
        config_copy["JELLYFIN_PASSWORD"] = encrypt_password(
            config["JELLYFIN_PASSWORD"], config["ENCRYPTION_KEY"]
        )

        with open(CONFIG_FILE, "w") as f:
            json.dump(config_copy, f, indent=2)
        return True
    except Exception as e:
        stdscr.addstr(0, 0, f"Error saving config: {str(e)}", curses.color_pair(2))
        stdscr.refresh()
        time.sleep(2)
        return False
    