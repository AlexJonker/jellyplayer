# JellyPlayer

JellyPlayer is a lightweight media player built with Python. It uses `mpv` for media playback.

## Features

- **Progress Reporting**: JellyPlayer tracks your playback progress and displays it in real-time.
- **Resume Playback**: Start watching right where you left off, even after closing the application.

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/AlexJonker/jellyplayer
    cd jellyplayer
    ```

2. Install the required Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3. Ensure `mpv` is installed on your system:
    - **Linux**: Install via your package manager, e.g., `yay -S mpv`.
    - **macOS**: Install via Homebrew, e.g., `brew install mpv`.
    - **Windows**: Download from [mpv.io](https://mpv.io/installation/).

4. Build a standalone executable (optional):
    ```bash
    pyinstaller --onefile jellyplayer.py
    ```
    This will create an executable in `./dist/jellyplayer`.

## Usage

Run the application:
```bash
python jellyplayer.py
```