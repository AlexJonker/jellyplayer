import os
import requests
import time
import subprocess
import threading
import tempfile
import socket
import json
from dotenv import load_dotenv

load_dotenv()

JELLYFIN_URL = os.getenv("JELLYFIN_URL")
JELLYFIN_USERNAME = os.getenv("JELLYFIN_USERNAME")
JELLYFIN_PASSWORD = os.getenv("JELLYFIN_PASSWORD")

if not all([JELLYFIN_URL, JELLYFIN_USERNAME, JELLYFIN_PASSWORD]):
    raise ValueError("Make sure JELLYFIN_URL, JELLYFIN_USERNAME and JELLYFIN_PASSWORD are set in your .env file.")

# === LOGIN ===
device_id = os.uname().nodename
device = os.uname().sysname
auth_header = f'MediaBrowser Client="JELLYPLAYER", Device="{device}", DeviceId="{device_id}", Version="0.1"'
headers = {"Authorization": auth_header}

auth_res = requests.post(
    f"{JELLYFIN_URL}/Users/AuthenticateByName",
    headers=headers,
    json={"Username": JELLYFIN_USERNAME, "Pw": JELLYFIN_PASSWORD}
)

if auth_res.status_code != 200:
    raise Exception("Login failed")

data = auth_res.json()
token = data["AccessToken"]
user_id = data["User"]["Id"]
headers["X-Emby-Token"] = token

# === GET TV SHOWS ===
shows = requests.get(
    f"{JELLYFIN_URL}/Users/{user_id}/Items?IncludeItemTypes=Series&Recursive=true",
    headers=headers
).json()["Items"]

if not shows:
    print("No shows found.")
    exit()

print("\nTV Shows:")
for idx, show in enumerate(shows, start=1):
    print(f"{idx}. {show['Name']}")

choice = int(input("\nPick a show: ")) - 1
show_id = shows[choice]["Id"]

# === GET SEASONS ===
seasons = requests.get(
    f"{JELLYFIN_URL}/Shows/{show_id}/Seasons?isSpecialSeason=false",
    headers=headers
).json()["Items"]

if not seasons:
    print("No seasons found.")
    exit()

print("\nSeasons:")
for idx, season in enumerate(seasons, start=1):
    print(f"{idx}. {season['Name']}")

season_choice = int(input("\nPick a season: ")) - 1
season_id = seasons[season_choice]["Id"]

# === GET EPISODES ===
episodes = requests.get(
    f"{JELLYFIN_URL}/Shows/{show_id}/Episodes?seasonId={season_id}",
    headers=headers
).json()["Items"]

if not episodes:
    print("No episodes found.")
    exit()

print("\nEpisodes:")
for idx, episode in enumerate(episodes, start=1):
    print(f"{idx}. {episode['Name']}")

episode_choice = int(input("\nPick an episode: ")) - 1
episode_id = episodes[episode_choice]["Id"]

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

# === HIGH-PRECISION PROGRESS REPORTING ===
def report_progress():
    last_reported_time = 0
    last_reported_percentage = -1
    last_status = None

    # Get the total duration of the video in seconds
    playback_info = requests.get(
        f"{JELLYFIN_URL}/Users/{user_id}/Items/{episode_id}",
        headers=headers
    ).json()
    total_duration_ticks = playback_info.get("RunTimeTicks", 0)
    total_duration_seconds = total_duration_ticks / 10_000_000  # Convert ticks to seconds

    if total_duration_seconds == 0:
        print("⚠ Unable to determine total duration of the video.")
        return

    while mpv_proc.poll() is None:  # While MPV is running
        try:
            current_time = time.time()
            current_pos = get_position()
            current_status = get_playback_status()

            if current_pos is None:
                time.sleep(0.1)
                continue

            # Calculate progress percentage
            progress_percentage = (current_pos / total_duration_seconds) * 100

            # Report progress only if percentage changes significantly or every second
            if (current_time - last_reported_time >= 1.0 and
                (abs(progress_percentage - last_reported_percentage) >= 1 or
                 current_status != last_status)):

                try:
                    requests.post(
                        f"{JELLYFIN_URL}/Sessions/Playing/Progress",
                        headers=headers,
                        json={
                            "ItemId": episode_id,
                            "MediaSourceId": episode_id,
                            "PositionTicks": int(current_pos * 10_000_000),
                            "IsPaused": not current_status if current_status is not None else False,
                            "IsMuted": False,
                            "VolumeLevel": 100,
                            "PlayMethod": "DirectStream",
                            "RepeatMode": "RepeatNone",
                        },
                        timeout=2  # Short timeout to prevent hanging
                    )
                    last_reported_time = current_time
                    last_reported_percentage = progress_percentage
                    last_status = current_status
                    print(f"↻ Progress: {progress_percentage:.1f}% ({'▶' if current_status else '⏸'})", end='\r')
                except requests.exceptions.RequestException as e:
                    print(f"⚠ Progress report failed: {e}")

            time.sleep(0.1)  # Small sleep to prevent CPU overload

        except Exception as e:
            print(f"⚠ Unexpected error in progress reporting: {e}")
            time.sleep(1)

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