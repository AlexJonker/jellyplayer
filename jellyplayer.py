import os
import requests
import time
import subprocess
import threading
import tempfile
import socket
import json
import curses
import signal
from base64 import b64encode, b64decode
from pathlib import Path

# Initialize curses
stdscr = curses.initscr()
curses.noecho()
curses.cbreak()
stdscr.keypad(True)
curses.curs_set(0)  # Hide cursor

# Initialize colors if supported
if curses.has_colors():
    curses.start_color()
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Watched items
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)  # Error messages
    curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)  # Menu headers
    curses.init_pair(
        4, curses.COLOR_YELLOW, curses.COLOR_BLACK
    )  # Partially watched items

CONFIG_FILE = str(Path.home() / ".config/jellyplayer/config.json")
CONFIG_DIR = Path(CONFIG_FILE).parent

# Create the config directory if it doesn't exist
if not CONFIG_DIR.exists():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def cleanup():
    """Clean up curses and exit"""
    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()
    curses.endwin()


def signal_handler(sig, frame):
    """Handle Ctrl+C interrupt"""
    cleanup()
    os._exit(0)


signal.signal(signal.SIGINT, signal_handler)


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


def get_input(prompt, hidden=False):
    """Get user input with curses"""
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    stdscr.addstr(h // 2 - 1, (w - len(prompt)) // 2, prompt)
    stdscr.refresh()

    if hidden:
        curses.noecho()
    else:
        curses.echo()

    input_str = ""
    while True:
        c = stdscr.getch()
        if c == curses.KEY_ENTER or c in [10, 13]:
            break
        elif c == curses.KEY_BACKSPACE or c == 127:
            if len(input_str) > 0:
                input_str = input_str[:-1]
                stdscr.delch(h // 2, (w - len(prompt)) // 2 + len(input_str))
        else:
            input_str += chr(c)
            if hidden:
                stdscr.addch(h // 2, (w - len(prompt)) // 2 + len(input_str) - 1, "*")
            else:
                stdscr.addch(h // 2, (w - len(prompt)) // 2 + len(input_str) - 1, c)

    curses.noecho()
    return input_str


def generate_key():
    """Generate a random encryption key."""
    return b64encode(os.urandom(16)).decode()


def load_config():
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


def save_config(config):
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


def get_credentials():
    """Get credentials from the saved config file or prompt user for new ones."""
    config = load_config()

    if config:
        return config

    # Get new credentials
    stdscr.clear()
    config = {
        "JELLYFIN_URL": get_input(
            "Enter Jellyfin server URL (e.g., http://localhost:8096): "
        ),
        "JELLYFIN_USERNAME": get_input("Enter Jellyfin username: "),
        "JELLYFIN_PASSWORD": get_input("Enter Jellyfin password: ", hidden=True),
    }

    if save_config(config):
        stdscr.addstr(0, 0, "Credentials saved successfully!", curses.color_pair(1))
        stdscr.refresh()
        time.sleep(1)

    return config


# Get credentials
try:
    config = get_credentials()
    JELLYFIN_URL = config["JELLYFIN_URL"]
    JELLYFIN_USERNAME = config["JELLYFIN_USERNAME"]
    JELLYFIN_PASSWORD = config["JELLYFIN_PASSWORD"]
except Exception as e:
    cleanup()
    raise ValueError(f"Failed to get credentials: {str(e)}")


# === LOGIN ===
try:
    device_id = os.uname().nodename
    device = os.uname().sysname
    auth_header = f'MediaBrowser Client="JELLYPLAYER", Device="{device}", DeviceId="{device_id}", Version="0.1"'
    headers = {"Authorization": auth_header}

    stdscr.addstr(0, 0, "Logging in to Jellyfin...", curses.A_BOLD)
    stdscr.refresh()

    auth_res = requests.post(
        f"{JELLYFIN_URL}/Users/AuthenticateByName",
        headers=headers,
        json={"Username": JELLYFIN_USERNAME, "Pw": JELLYFIN_PASSWORD},
    )

    if auth_res.status_code != 200:
        cleanup()
        raise Exception("Login failed")

    data = auth_res.json()
    token = data["AccessToken"]
    user_id = data["User"]["Id"]
    headers["X-Emby-Token"] = token
except Exception as e:
    cleanup()
    raise

# Add after headers are defined
show_watch_cache = {}
season_watch_cache = {}


def cache_show_watch_status(show_id):
    """Cache all watch status for a show and its seasons"""
    if show_id in show_watch_cache:
        return

    episodes = (
        requests.get(f"{JELLYFIN_URL}/Shows/{show_id}/Episodes", headers=headers)
        .json()
        .get("Items", [])
    )

    show_has_watched = False  # Start with False
    show_has_partial = False
    season_status = {}
    
    # Track show-level watched status
    has_any_watched = False
    has_any_unwatched = False

    for ep in episodes:
        season_id = ep.get("SeasonId")
        if season_id not in season_status:
            season_status[season_id] = {
                "watched": False,
                "partial": False,
                "has_watched": False,
                "has_unwatched": False,
            }

        user_data = ep.get("UserData", {})
        if user_data.get("Played", False):
            # Episode is fully watched
            has_any_watched = True
            season_status[season_id]["has_watched"] = True
        elif user_data.get("PlaybackPositionTicks", 0) > 0:
            # Episode is partially watched
            show_has_partial = True
            season_status[season_id]["partial"] = True
            season_status[season_id]["has_watched"] = True  # Partially watched counts as watched
            has_any_watched = True
        else:
            # Episode is not watched at all
            has_any_unwatched = True
            season_status[season_id]["has_unwatched"] = True

    # Determine show status
    if has_any_watched and has_any_unwatched:
        show_has_partial = True
    show_has_watched = has_any_watched and not has_any_unwatched

    # Determine season status
    for season_id in season_status:
        season = season_status[season_id]
        if season["has_watched"] and season["has_unwatched"]:
            season["partial"] = True
        season["watched"] = season["has_watched"] and not season["has_unwatched"]

    show_watch_cache[show_id] = {
        "watched": show_has_watched,
        "partial": show_has_partial,
        "seasons": season_status,
    }



def get_cached_show_status(show_id):
    """Get cached watch status for a show"""
    if show_id not in show_watch_cache:
        cache_show_watch_status(show_id)
    return show_watch_cache[show_id]


def get_cached_season_status(show_id, season_id):
    """Get cached watch status for a season"""
    if show_id not in show_watch_cache:
        cache_show_watch_status(show_id)
    return show_watch_cache[show_id]["seasons"].get(
        season_id, {"watched": False, "partial": False}
    )


def display_menu(items, title, selected_index=0, status_msg=""):
    stdscr.clear()
    h, w = stdscr.getmaxyx()

    # Calculate the visible range of items
    max_visible_items = h - 4  # Leave space for title and status message
    start_index = max(0, selected_index - max_visible_items + 1)
    end_index = min(len(items), start_index + max_visible_items)

    # Draw title
    if curses.has_colors():
        stdscr.addstr(
            0, (w - len(title)) // 2, title, curses.color_pair(3) | curses.A_BOLD
        )
    else:
        stdscr.addstr(0, (w - len(title)) // 2, title, curses.A_BOLD)

    # First pass: draw all items without status (fast)
    for idx, item in enumerate(items[start_index:end_index]):
        actual_idx = start_index + idx
        item_text = (
            f"> {item['Name']}" if actual_idx == selected_index else f"  {item['Name']}"
        )
        stdscr.addstr(
            idx + 2,
            2,
            item_text,
            curses.A_REVERSE if actual_idx == selected_index else 0,
        )

    stdscr.refresh()  # Show initial draw quickly

    # Second pass: add status indicators (slower but now visible)
    for idx, item in enumerate(items[start_index:end_index]):
        actual_idx = start_index + idx
        user_data = item.get("UserData", {})
        is_watched = user_data.get("Played", False)
        is_partial = not is_watched and user_data.get("PlaybackPositionTicks", 0) > 0

        # Get status from cache if needed
        if "Id" in item and not (is_watched or is_partial):
            if item.get("Type") == "Series":
                status = get_cached_show_status(item["Id"])
                has_watched = status["watched"]
                has_partial = status["partial"]
            elif item.get("Type") == "Season":
                status = get_cached_season_status(item.get("SeriesId", ""), item["Id"])
                has_watched = status["watched"]
                has_partial = status["partial"]
            else:
                has_watched = False
                has_partial = False
        else:
            has_watched = False
            has_partial = False

        # Determine final status
        if is_watched:
            color = 1
            indicator = "✔"
        elif is_partial:
            color = 4
            indicator = "~"
        elif has_watched:
            color = 1
            indicator = "✔"
        elif has_partial:
            color = 4
            indicator = "~"
        else:
            color = 0
            indicator = " "

        # Apply color if needed
        if color > 0 and curses.has_colors():
            item_text = (
                f"> {item['Name']}"
                if actual_idx == selected_index
                else f"  {item['Name']}"
            )
            attr = curses.A_REVERSE if actual_idx == selected_index else 0
            stdscr.addstr(idx + 2, 2, item_text, attr | curses.color_pair(color))

        # Add indicator if needed
        if indicator != " ":
            if curses.has_colors():
                stdscr.addstr(idx + 2, w - 2, indicator, curses.color_pair(color))
            else:
                stdscr.addstr(idx + 2, w - 2, indicator)

    # Status message
    if status_msg:
        if curses.has_colors() and "Error" in status_msg:
            stdscr.addstr(h - 1, 0, status_msg, curses.color_pair(2))
        else:
            stdscr.addstr(h - 1, 0, status_msg)

    stdscr.refresh()


def select_from_list(items, title):
    selected_index = 0
    status_msg = "↑/↓: Navigate | Enter: Select | ESC: Exit"
    display_menu(items, title, selected_index, status_msg)

    while True:
        try:
            key = stdscr.getch()
            if key == curses.KEY_UP and selected_index > 0:
                selected_index -= 1
                display_menu(items, title, selected_index, status_msg)
            elif key == curses.KEY_DOWN and selected_index < len(items) - 1:
                selected_index += 1
                display_menu(items, title, selected_index, status_msg)
            elif key == curses.KEY_ENTER or key in [10, 13]:  # Enter key
                return selected_index
            elif key == 27:  # ESC key
                cleanup()
                os._exit(0)
        except Exception as e:
            display_menu(items, title, selected_index, f"Error: {str(e)}")

    return selected_index


def select_media_type():
    options = [
        {"Name": "TV Shows", "Type": "Series"},
        {"Name": "Movies", "Type": "Movie"},
    ]
    selected = select_from_list(options, "Select Media Type")
    return options[selected]["Type"]


# === MAIN MENU ===
media_type = select_media_type()

if media_type == "Series":
    # === GET TV SHOWS ===
    try:
        stdscr.addstr(0, 0, "Loading TV shows...", curses.A_BOLD)
        stdscr.refresh()

        shows = requests.get(
            f"{JELLYFIN_URL}/Users/{user_id}/Items?IncludeItemTypes=Series&Recursive=true",
            headers=headers,
        ).json()["Items"]

        if not shows:
            cleanup()
            print("No shows found.")
            exit()

        selected_show = select_from_list(shows, "TV Shows")
        show_id = shows[selected_show]["Id"]

        # === GET SEASONS ===
        stdscr.addstr(0, 0, "Loading seasons...", curses.A_BOLD)
        stdscr.refresh()

        seasons = requests.get(
            f"{JELLYFIN_URL}/Shows/{show_id}/Seasons", headers=headers
        ).json()["Items"]

        if not seasons:
            cleanup()
            print("No seasons found.")
            exit()

        selected_season = select_from_list(seasons, "Seasons")
        season_id = seasons[selected_season]["Id"]

        # === GET EPISODES ===
        stdscr.addstr(0, 0, "Loading episodes...", curses.A_BOLD)
        stdscr.refresh()

        episodes = requests.get(
            f"{JELLYFIN_URL}/Shows/{show_id}/Episodes?seasonId={season_id}",
            headers=headers,
        ).json()["Items"]

        if not episodes:
            cleanup()
            print("No episodes found.")
            exit()

        selected_episode = select_from_list(episodes, "Episodes")
        item_id = episodes[selected_episode]["Id"]
        item_name = episodes[selected_episode]["Name"]

    except Exception as e:
        cleanup()
        raise

elif media_type == "Movie":
    # === GET MOVIES ===
    try:
        stdscr.addstr(0, 0, "Loading movies...", curses.A_BOLD)
        stdscr.refresh()

        movies = requests.get(
            f"{JELLYFIN_URL}/Users/{user_id}/Items?IncludeItemTypes=Movie&Recursive=true",
            headers=headers,
        ).json()["Items"]

        if not movies:
            cleanup()
            print("No movies found.")
            exit()

        selected_movie = select_from_list(movies, "Movies")
        item_id = movies[selected_movie]["Id"]
        item_name = movies[selected_movie]["Name"]

    except Exception as e:
        cleanup()
        raise

# Clean up curses before starting playback
cleanup()

# === PLAYBACK CODE ===
try:
    stream_url = f"{JELLYFIN_URL}/Items/{item_id}/Download?api_key={token}"

    # === START PLAYBACK SESSION ===
    requests.post(
        f"{JELLYFIN_URL}/Sessions/Playing",
        headers=headers,
        json={
            "ItemId": item_id,
            "CanSeek": True,
            "IsPaused": True,
            "IsMuted": False,
            "PlaybackStartTimeTicks": 0,
            "PlayMethod": "DirectStream",
        },
    )

    # === MPV IPC ===
    ipc_path = tempfile.NamedTemporaryFile(delete=False).name
    playback_info = requests.get(
        f"{JELLYFIN_URL}/Users/{user_id}/Items/{item_id}", headers=headers
    ).json()

    start_position_ticks = playback_info.get("UserData", {}).get(
        "PlaybackPositionTicks", 0
    )
    start_position_seconds = (
        start_position_ticks // 10_000_000
    )  # Convert ticks to seconds

    print(
        f"Starting playback of '{item_name}' from {start_position_seconds} seconds..."
    )

    mpv_proc = subprocess.Popen(
        [
            "mpv",
            stream_url,
            f"--input-ipc-server={ipc_path}",
            "--slang=en",
            "--alang=ja",
            f"--start={start_position_seconds}",
            "--fs",
        ]
    )

    import errno

    sock = socket.socket(socket.AF_UNIX)

    timeout = time.time() + 5  # wait max 5 seconds
    while True:
        try:
            if os.path.exists(ipc_path):
                sock.connect(ipc_path)
                break
        except socket.error as e:
            if e.errno != errno.ECONNREFUSED:
                raise
        if time.time() > timeout:
            raise TimeoutError(f"Could not connect to MPV IPC socket at {ipc_path}")
        time.sleep(0.1)

    def send_ipc_command(command):
        try:
            msg = json.dumps({"command": command})
            sock.sendall((msg + "\n").encode())
            response = b""
            while not response.endswith(b"\n"):
                response += sock.recv(4096)
            return json.loads(response.decode())
        except Exception as e:
            print(f"IPC command failed: {e}")
            return None

    def get_position():
        result = send_ipc_command(["get_property", "playback-time"])
        if result and "data" in result and isinstance(result["data"], (int, float)):
            return result["data"]
        return None

    def get_playback_status():
        result = send_ipc_command(["get_property", "pause"])
        if result and "data" in result and isinstance(result["data"], bool):
            return not result["data"]  # Return True if playing, False if paused
        return None

    # === SIMPLE PROGRESS REPORTING ===
    def report_progress():
        while mpv_proc.poll() is None:  # While MPV is running
            try:
                current_pos = get_position()
                if current_pos is not None:
                    try:
                        requests.post(
                            f"{JELLYFIN_URL}/Sessions/Playing/Progress",
                            headers=headers,
                            json={
                                "ItemId": item_id,
                                "PositionTicks": int(current_pos * 10_000_000),
                            },
                            timeout=2,  # Short timeout to prevent hanging
                        )
                        print(
                            f"↻ Current progress: {current_pos:.1f} seconds", end="\r"
                        )
                    except requests.exceptions.RequestException as e:
                        print(f"⚠ Progress report failed: {e}")
                time.sleep(2)  # Report progress every 2 seconds
            except Exception as e:
                print(f"⚠ Unexpected error in progress reporting: {e}")
                time.sleep(2)

    progress_thread = threading.Thread(target=report_progress, daemon=True)
    progress_thread.start()

    mpv_proc.wait()

    # === STOP SESSION ===
    try:
        final_pos = get_position()
        if final_pos is not None:
            requests.post(
                f"{JELLYFIN_URL}/Sessions/Playing/Stopped",
                headers=headers,
                json={
                    "ItemId": item_id,
                    "PositionTicks": int(final_pos * 10_000_000),
                    "MediaSourceId": item_id,
                },
            )
            print(f"\n⏹ Playback stopped at position: {final_pos:.1f} seconds")
    except Exception as e:
        print(f"\n⚠ Failed to send stop notification: {e}")

    sock.close()
    try:
        os.unlink(ipc_path)
    except:
        pass

except Exception as e:
    print(f"\n⚠ Error during playback: {e}")
    cleanup()
    raise
