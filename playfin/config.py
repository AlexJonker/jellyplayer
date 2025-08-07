import os
import json
import curses
import time
from .constants import CONFIG_FILE
from .encryption import encrypt_password, decrypt_password, generate_key
from .ui import init_curses, get_input

def load_config():
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
        return None

def save_config(config):
    try:
        # Generate a key if it doesn't exist
        if "ENCRYPTION_KEY" not in config:
            config["ENCRYPTION_KEY"] = generate_key()

        # Encrypt password before saving
        config_copy = config.copy()
        config_copy["JELLYFIN_PASSWORD"] = encrypt_password(
            config["JELLYFIN_PASSWORD"], config["ENCRYPTION_KEY"]
        )

        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_copy, f, indent=2)
        return True
    except Exception as e:
        return False
    

def get_credentials():
    stdscr = init_curses()
    config = load_config()

    if config:
        return config

    # Get new credentials
    stdscr.clear()
    config = {
        "JELLYFIN_URL": get_input(
            stdscr,
            "Enter Jellyfin server URL (e.g., http://localhost:8096): "
        ),
        "JELLYFIN_USERNAME": get_input(stdscr, "Enter Jellyfin username: "),
        "JELLYFIN_PASSWORD": get_input(stdscr, "Enter Jellyfin password: ", hidden=True),
    }

    if save_config(config):
        stdscr.addstr(0, 0, "Credentials saved successfully!", curses.color_pair(1))
        stdscr.refresh()
        time.sleep(1)

    return config