import requests
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

show_watch_cache = {}
season_watch_cache = {}


def cache_show_watch_status(show_id, headers):
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


def get_cached_show_status(show_id, headers):
    """Get cached watch status for a show"""
    if show_id not in show_watch_cache:
        cache_show_watch_status(show_id, headers)
    return show_watch_cache[show_id]


def get_cached_season_status(show_id, season_id, headers):
    """Get cached watch status for a season"""
    if show_id not in show_watch_cache:
        cache_show_watch_status(show_id, headers)
    return show_watch_cache[show_id]["seasons"].get(
        season_id, {"watched": False, "partial": False}
    )

