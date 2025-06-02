from base64 import b64encode, b64decode
import os
import curses
from constants import CONFIG_FILE

def xor_cipher(text, key):
    """Simple XOR cipher for basic obfuscation"""
    return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(text))

def encrypt_password(password, key):
    """Encrypt password with XOR and base64 encode"""
    encrypted = xor_cipher(password, key)
    return b64encode(encrypted.encode()).decode()

def decrypt_password(encrypted_password, key):
    """Decrypt password from base64 and XOR"""
    decoded = b64decode(encrypted_password.encode()).decode()
    return xor_cipher(decoded, key)

def generate_key():
    """Generate a random encryption key."""
    return b64encode(os.urandom(16)).decode()

def get_credentials(CONFIG_FILE, stdscr):
    """Get credentials from the saved config file or prompt user for new ones."""
    from configs import load_config, save_config
    
    config = load_config(CONFIG_FILE)
    if config:
        return config

    # Get new credentials
    stdscr.clear()
    config = {
        "JELLYFIN_URL": get_input(stdscr, "Enter Jellyfin server URL (e.g., http://localhost:8096): "),
        "JELLYFIN_USERNAME": get_input(stdscr, "Enter Jellyfin username: "),
        "JELLYFIN_PASSWORD": get_input(stdscr, "Enter Jellyfin password: ", hidden=True),
    }

    if save_config(config, CONFIG_FILE):
        stdscr.addstr(0, 0, "Credentials saved successfully!", curses.color_pair(1))
        stdscr.refresh()
        time.sleep(1)

    return config