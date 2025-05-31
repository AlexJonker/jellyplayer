# playfin

playfin is a tui and user-friendly media player built with Python. It uses `mpv` for media playback.

## Features

- **Real-Time Progress Tracking**: Keep track of your playback progress with real-time updates.
- **Resume Playback**: Automatically pick up where you left off, even after closing the application.

## Installation

### Option 1: Arch-Based Linux Distributions

For Arch-based Linux distributions, you can install playfin directly from the AUR:
```bash
yay -S playfin
```

Once installed, you can run playfin using the following command:
```bash
playfin
```

### Option 2: Manual Installation

Ensure `mpv` is installed on your system:

- **Linux**: Install via your package manager, e.g., `yay -S mpv`.
- **macOS**: Install via Homebrew, e.g., `brew install mpv`.
- **Windows**: Download the installer from [mpv.io](https://mpv.io/installation/).

1. Clone the repository:
    ```bash
    git clone https://github.com/AlexJonker/playfin
    cd playfin
    ```

2. Install the required Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3. Run playfin:
    ```bash
    python playfin.py
    ```

    ### Configuration

    The config is stored at `~/.config/playfin/config.json`