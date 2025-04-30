# JellyPlayer

JellyPlayer is a tui and user-friendly media player built with Python. It uses `mpv` for media playback.

## Features

- **Real-Time Progress Tracking**: Keep track of your playback progress with real-time updates.
- **Resume Playback**: Automatically pick up where you left off, even after closing the application.

## Installation

### Option 1: Arch-Based Linux Distributions

For Arch-based Linux distributions, you can install JellyPlayer directly from the AUR:
```bash
yay -S jellyplayer-git
```

Once installed, you can run JellyPlayer using the following command:
```bash
jellyplayer
```

### Option 2: Manual Installation

Ensure `mpv` is installed on your system:

- **Linux**: Install via your package manager, e.g., `yay -S mpv`.
- **macOS**: Install via Homebrew, e.g., `brew install mpv`.
- **Windows**: Download the installer from [mpv.io](https://mpv.io/installation/).

1. Clone the repository:
    ```bash
    git clone https://github.com/AlexJonker/jellyplayer
    cd jellyplayer
    ```

2. Install the required Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3. Run JellyPlayer:
    ```bash
    python jellyplayer.py
    ```

    ### Configuration

    The config is stored at `~/.config/jellyplayer/config.json`
