# main.py
from constants import CONFIG_FILE
import curses
from ui import init_curses, cleanup
from encryption import get_credentials

# Initialize curses first
stdscr = init_curses()

try:
    # Get credentials with the initialized stdscr
    config = get_credentials(CONFIG_FILE, stdscr)
    JELLYFIN_URL = config["JELLYFIN_URL"]
    JELLYFIN_USERNAME = config["JELLYFIN_USERNAME"]
    JELLYFIN_PASSWORD = config["JELLYFIN_PASSWORD"]
except Exception as e:
    cleanup()
    print(f"Failed to get credentials: {str(e)}")
    exit(1)

# Now import other modules that need these credentials
from ui import *
from cache import *
import requests
import os


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

            selected_show = select_from_list(
                shows, "TV Shows", 
                allow_escape_up=True,
                headers=headers
            )
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