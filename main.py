import os
import requests
import curses
import signal
from pathlib import Path

CONFIG_FILE = str(Path.home() / ".config/playfin/config.json")
CONFIG_DIR = Path(CONFIG_FILE).parent

# Create the config directory if it doesn't exist
if not CONFIG_DIR.exists():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

#import other files
from configs import *
from ui import *
from cache import *
from mpv import *


def signal_handler(sig, frame):
    """Handle Ctrl+C interrupt"""
    cleanup()
    os._exit(0)


signal.signal(signal.SIGINT, signal_handler)


# Get credentials
from encryption import *

try:
    config = get_credentials(CONFIG_FILE)
    JELLYFIN_URL = config["JELLYFIN_URL"]
    JELLYFIN_USERNAME = config["JELLYFIN_USERNAME"]
    JELLYFIN_PASSWORD = config["JELLYFIN_PASSWORD"]
except Exception as e:
    cleanup()
    raise ValueError(f"Failed to get credentials: {str(e)}")





#import other files
from configs import *
from ui import *
from cache import *
from mpv import *


# === LOGIN ===
try:
    device_id = os.uname().nodename
    device = os.uname().sysname
    auth_header = f'MediaBrowser Client="playfin", Device="{device}", DeviceId="{device_id}", Version="0.1"'
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



# === MAIN MENU ===



# === MAIN MENU LOOP ===
while True:
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

            selected_show = select_from_list(shows, "TV Shows", allow_escape_up=True)
            if selected_show == -1:
                continue  # Go back to media type selection
            show_id = shows[selected_show]["Id"]
            show_name = shows[selected_show]["Name"]

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

            selected_season = select_from_list(seasons, f"{show_name}", allow_escape_up=True)
            if selected_season == -1:
                continue  # Go back to shows list
            season_id = seasons[selected_season]["Id"]
            season_name = seasons[selected_season]["Name"]

            # === EPISODE LOOP (stays in current season after playback) ===
            while True:
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

                for episode in episodes:
                    episode_number = episode.get("IndexNumber", 0)
                    episode["Name"] = f"{episode_number}. {episode['Name']}"

                selected_episode = select_from_list(episodes, f"{season_name}", allow_escape_up=True)
                if selected_episode == -1:
                    break  # Exit episode loop, go back to season selection
                
                item_id = episodes[selected_episode]["Id"]
                item_name = episodes[selected_episode]["Name"]

                # Play the selected episode
                play_item(item_id, item_name, token, headers, user_id)

                # After playback, loop continues, showing the same season's episodes again
        except Exception as e:
            cleanup()
            print(f"Error loading TV shows: {e}")
            exit()

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

            while True:
                selected_movie = select_from_list(movies, "Movies", allow_escape_up=True)
                if selected_movie == -1:
                    break  # Go back to media type selection
                item_id = movies[selected_movie]["Id"]
                item_name = movies[selected_movie]["Name"]
                
                # Play the selected movie
                play_item(item_id, item_name, token, headers, user_id)
                
                # After playback, we'll return to the movies list
                # because we're in the movies while loop
        except Exception as e:
            cleanup()
            print(f"Error loading movies: {e}")
            exit()