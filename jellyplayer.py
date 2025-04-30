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
from dotenv import load_dotenv

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
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)    # Error messages

load_dotenv()

JELLYFIN_URL = os.getenv("JELLYFIN_URL")
JELLYFIN_USERNAME = os.getenv("JELLYFIN_USERNAME")
JELLYFIN_PASSWORD = os.getenv("JELLYFIN_PASSWORD")

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

if not all([JELLYFIN_URL, JELLYFIN_USERNAME, JELLYFIN_PASSWORD]):
    cleanup()
    raise ValueError("Make sure JELLYFIN_URL, JELLYFIN_USERNAME and JELLYFIN_PASSWORD are set in your .env file.")

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
        json={"Username": JELLYFIN_USERNAME, "Pw": JELLYFIN_PASSWORD}
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

def display_menu(items, title, selected_index=0, status_msg=""):
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    
    # Draw title
    stdscr.addstr(0, (w - len(title)) // 2, title, curses.A_BOLD)
    
    # Draw items
    for idx, item in enumerate(items):
        is_watched = item.get("UserData", {}).get("Played", False)
        item_text = f"> {item['Name']}" if idx == selected_index else f"  {item['Name']}"
        
        # Apply color and highlighting
        if idx == selected_index:
            if is_watched and curses.has_colors():
                stdscr.addstr(idx + 2, 2, item_text, curses.A_REVERSE | curses.color_pair(1))
            else:
                stdscr.addstr(idx + 2, 2, item_text, curses.A_REVERSE)
        else:
            if is_watched and curses.has_colors():
                stdscr.addstr(idx + 2, 2, item_text, curses.color_pair(1))
            else:
                stdscr.addstr(idx + 2, 2, item_text)
            
        # Add watched checkmark
        if is_watched:
            if curses.has_colors():
                stdscr.addstr(idx + 2, w - 2, "✔", curses.color_pair(1))
            else:
                stdscr.addstr(idx + 2, w - 2, "✔")
    
    # Status message at bottom
    if status_msg:
        if curses.has_colors() and "Error" in status_msg:
            stdscr.addstr(h-1, 0, status_msg, curses.color_pair(2))
        else:
            stdscr.addstr(h-1, 0, status_msg)
    
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

# === GET TV SHOWS ===
try:
    stdscr.addstr(0, 0, "Loading TV shows...", curses.A_BOLD)
    stdscr.refresh()

    shows = requests.get(
        f"{JELLYFIN_URL}/Users/{user_id}/Items?IncludeItemTypes=Series&Recursive=true",
        headers=headers
    ).json()["Items"]

    if not shows:
        cleanup()
        print("No shows found.")
        exit()

    selected_show = select_from_list(shows, "TV Shows")
    show_id = shows[selected_show]["Id"]
except Exception as e:
    cleanup()
    raise

# === GET SEASONS ===
try:
    stdscr.addstr(0, 0, "Loading seasons...", curses.A_BOLD)
    stdscr.refresh()

    seasons = requests.get(
        f"{JELLYFIN_URL}/Shows/{show_id}/Seasons?isSpecialSeason=false",
        headers=headers
    ).json()["Items"]

    if not seasons:
        cleanup()
        print("No seasons found.")
        exit()

    selected_season = select_from_list(seasons, "Seasons")
    season_id = seasons[selected_season]["Id"]
except Exception as e:
    cleanup()
    raise

# === GET EPISODES ===
try:
    stdscr.addstr(0, 0, "Loading episodes...", curses.A_BOLD)
    stdscr.refresh()

    episodes = requests.get(
        f"{JELLYFIN_URL}/Shows/{show_id}/Episodes?seasonId={season_id}",
        headers=headers
    ).json()["Items"]

    if not episodes:
        cleanup()
        print("No episodes found.")
        exit()

    selected_episode = select_from_list(episodes, "Episodes")
    episode_id = episodes[selected_episode]["Id"]
except Exception as e:
    cleanup()
    raise

# Clean up curses before starting playback
cleanup()

# === PLAYBACK CODE ===
try:
    stream_url = f"{JELLYFIN_URL}/Items/{episode_id}/Download?api_key={token}"

    # === START PLAYBACK SESSION ===
    requests.post(
        f"{JELLYFIN_URL}/Sessions/Playing",
        headers=headers,
        json={
            "ItemId": episode_id,
            "CanSeek": True,
            "IsPaused": True,
            "IsMuted": False,
            "PlaybackStartTimeTicks": 0,
            "PlayMethod": "DirectStream"
        }
    )

    # === MPV IPC ===
    ipc_path = tempfile.NamedTemporaryFile(delete=False).name
    playback_info = requests.get(
        f"{JELLYFIN_URL}/Users/{user_id}/Items/{episode_id}",
        headers=headers
    ).json()

    start_position_ticks = playback_info.get("UserData", {}).get("PlaybackPositionTicks", 0)
    start_position_seconds = start_position_ticks // 10_000_000  # Convert ticks to seconds

    print(f"Starting playback from {start_position_seconds} seconds...")

    mpv_proc = subprocess.Popen([
        "mpv",
        stream_url,
        f"--input-ipc-server={ipc_path}",
        "--slang=en",
        "--alang=ja",
        f"--start={start_position_seconds}",
        "--fs"
    ])

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
                                "ItemId": episode_id,
                                "PositionTicks": int(current_pos * 10_000_000),
                            },
                            timeout=2  # Short timeout to prevent hanging
                        )
                        print(f"↻ Current progress: {current_pos:.1f} seconds", end='\r')
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
                    "ItemId": episode_id,
                    "PositionTicks": int(final_pos * 10_000_000),
                    "MediaSourceId": episode_id
                }
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